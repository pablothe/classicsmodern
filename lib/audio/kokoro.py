#!/usr/bin/env python3
"""
Local TTS Audio Generation using Kokoro (ONNX Runtime)

Generates high-quality audiobooks locally using Kokoro TTS with ONNX Runtime.
100% local, commercial-friendly (Apache 2.0), and 31× faster than Bark.

Features:
- FREE & LOCAL - No API costs, fully local inference
- FAST - 31× faster than Bark (~6.5s for 39-word passage)
- HIGH QUALITY - Rivals commercial APIs
- 52 VOICES - American, British, male/female options
- COMMERCIAL - Apache 2.0 license (commercial-friendly)
- OPTIMIZED - Apple Silicon GPU acceleration (MPS)

Requirements:
    pip install kokoro-tts kokoro-onnx soundfile
    brew install ffmpeg  # macOS
"""

import os
import sys
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    from kokoro_onnx import Kokoro
except ImportError:
    print("❌ ERROR: kokoro-onnx library not installed")
    print("\nPlease install Kokoro TTS:")
    print("  pip install kokoro-tts kokoro-onnx soundfile")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    print("❌ ERROR: soundfile library not installed")
    print("\nPlease install soundfile:")
    print("  pip install soundfile")
    sys.exit(1)

from lib.book.validator import validate_book

try:
    from lib.audio.preprocessor import AudioTextPreprocessor
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False


class KokoroAudioGenerator:
    """Local TTS audio generation using Kokoro (ONNX Runtime)"""

    # Safety limits
    MAX_SAFE_CHUNK_SIZE = 800              # Characters per chunk (reduced for phoneme safety)
    KOKORO_PHONEME_LIMIT = 510             # Hard limit in kokoro-onnx library

    # Top recommended voices for audiobooks
    VOICE_AF_SKY = "af_sky"                # American Female - Sky (DEFAULT)
    VOICE_BF_EMMA = "bf_emma"              # British Female - Emma (classics)
    VOICE_BF_ISABELLA = "bf_isabella"      # British Female - Isabella
    VOICE_BM_GEORGE = "bm_george"          # British Male - George (classics)
    VOICE_AM_ADAM = "am_adam"              # American Male - Adam
    VOICE_AM_ONYX = "am_onyx"              # American Male - Onyx (deep)

    def __init__(self, voice: str = VOICE_AF_SKY, language: str = "en-us"):
        """
        Initialize Kokoro TTS audio generator.

        Args:
            voice: Voice ID to use (default: af_sky)
            language: Language code (default: en-us)
        """
        self.voice = voice
        self.language = language
        self.model = None

        # Ensure models are downloaded
        self.model_path, self.voices_path = self._ensure_models_downloaded()

        print(f"✓ Using voice: {self.voice}")

    def _ensure_models_downloaded(self) -> tuple:
        """
        Ensure Kokoro models are downloaded to cache.

        Returns:
            Tuple of (model_path, voices_path)
        """
        cache_dir = Path.home() / ".cache" / "kokoro"
        cache_dir.mkdir(parents=True, exist_ok=True)

        model_path = cache_dir / "kokoro-v1.0.onnx"
        voices_path = cache_dir / "voices-v1.0.bin"

        # Check if models exist
        if model_path.exists() and voices_path.exists():
            return str(model_path), str(voices_path)

        # Models not found - provide download instructions
        print("\n⚠️  Kokoro models not found in cache")
        print(f"   Expected location: {cache_dir}")
        print("\n📥 Please download the models (first time only):")
        print("\n   cd ~/.cache/kokoro")
        print("   curl -L -O https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx")
        print("   curl -L -O https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin")
        print("\n   Total size: ~335MB (downloaded once)")
        print("\n❌ Please download models and try again.\n")
        sys.exit(1)

    def _load_model(self):
        """Load Kokoro model lazily (only when needed)"""
        if self.model is None:
            print("Loading Kokoro model...")
            self.model = Kokoro(
                model_path=self.model_path,
                voices_path=self.voices_path
            )
            print("✓ Model loaded")

    def _format_eta(self, seconds: float) -> str:
        """Format seconds to human-readable ETA"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def strip_gutenberg_boilerplate(self, text: str) -> tuple:
        """
        Strip Project Gutenberg boilerplate and extract metadata.

        Args:
            text: Raw text that may contain Gutenberg boilerplate

        Returns:
            Tuple of (cleaned_text, title, author)
        """
        lines = text.split('\n')

        # Find START and END markers
        start_idx = -1
        end_idx = -1

        for i, line in enumerate(lines):
            if '*** START OF THE PROJECT GUTENBERG EBOOK' in line.upper():
                start_idx = i
            if '*** END OF THE PROJECT GUTENBERG EBOOK' in line.upper():
                end_idx = i
                break

        # Extract title and author from the content
        title = None
        author = None

        if start_idx >= 0:
            # Extract title from START line (e.g., "*** START ... EBOOK THE CALL OF CTHULHU ***")
            start_line = lines[start_idx]
            title_match = re.search(r'EBOOK\s+(.+?)\s*\*\*\*', start_line, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

            # Look for title in next few lines (markdown headers)
            for j in range(start_idx, min(start_idx + 5, len(lines))):
                line = lines[j].strip()
                # Remove markdown markers
                title_line = re.sub(r'^#+\s+', '', line)
                if title_line and not title_line.startswith('***'):
                    if not title:
                        title = title_line
                    # Look for author
                    author_match = re.match(r'By\s+(.+)', title_line, re.IGNORECASE)
                    if author_match:
                        author = author_match.group(1).strip()
                        break

        # If we found markers, strip the boilerplate
        if start_idx >= 0:
            # Keep content after START marker
            if end_idx > start_idx:
                # Remove everything from START to END
                content = '\n'.join(lines[start_idx + 1:end_idx])
            else:
                # No END marker, just remove header
                content = '\n'.join(lines[start_idx + 1:])
        else:
            # No markers found, return as-is
            content = text

        # Remove any "By {author}" lines from content (already in intro)
        if author:
            content = re.sub(
                rf'^##?\s*By\s+{re.escape(author)}\s*$',
                '',
                content,
                flags=re.MULTILINE | re.IGNORECASE
            )

        # Generate intro if we have metadata
        if title and author:
            intro = f"Classics Modern presents: {title}. Written by {author}.\n\n"
            content = intro + content
        elif title:
            intro = f"Classics Modern presents: {title}.\n\n"
            content = intro + content

        return content, title, author

    def clean_text_for_speech(self, text: str, preserve_chapter_markers: bool = False,
                              skip_gutenberg: bool = False) -> str:
        """
        Clean markdown text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown
            preserve_chapter_markers: If True, keep Roman numeral chapter markers
            skip_gutenberg: If True, skip Gutenberg stripping (for pre-cleaned content)

        Returns:
            Cleaned text suitable for TTS
        """
        # Strip Gutenberg boilerplate first (skip if content already cleaned)
        if not skip_gutenberg:
            text, _, _ = self.strip_gutenberg_boilerplate(text)
        # Preserve chapter markers FIRST (before cleaning)
        if preserve_chapter_markers:
            # Preserve standalone Roman numerals (e.g., "I.", "II.", "III.")
            text = re.sub(
                r'^(X{0,3})(IX|IV|V?I{0,3})\.$',
                lambda m: f"<<<CHAPTER:MARKER:{m.group(0)}>>>",
                text,
                flags=re.MULTILINE
            )

            # Preserve numbered chapters (e.g., "1. The Horror in Clay.")
            text = re.sub(
                r'^(\d+)\.\s+(.+)$',
                lambda m: f"<<<CHAPTER:MARKER:{m.group(1)}>>>",
                text,
                flags=re.MULTILINE
            )

        # Remove markdown links FIRST (before headers), so [## Chapter 1](#...)
        # becomes ## Chapter 1, which the header regex can then clean
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # Remove markdown headers but keep text
        if preserve_chapter_markers:
            def replace_header(match):
                header_text = match.group(2)
                # Check if it's a Roman numeral marker
                if re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', header_text.strip()):
                    return f"<<<CHAPTER:MARKER:{header_text.strip()}>>>"
                # Check if it's a numbered chapter
                if re.match(r'^\d+\.\s+.+$', header_text.strip()):
                    numbered_match = re.match(r'^(\d+)\.', header_text.strip())
                    if numbered_match:
                        return f"<<<CHAPTER:MARKER:{numbered_match.group(1)}>>>"
                return header_text
            text = re.sub(r'^(#{1,6})\s+(.+)$', replace_header, text, flags=re.MULTILINE)
        else:
            text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)
        # Also strip any ## markers mid-line (from TOC link cleanup above)
        text = re.sub(r'#{1,6}\s+', '', text)

        # Remove emphasis symbols
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        # Remove image references
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def chunk_text(self, text: str, max_chars: int = 800) -> List[str]:
        """
        Split text into chunks for TTS, ensuring complete sentences.
        Kokoro can handle moderate chunks (~800 chars recommended for safety).

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (default: 800 for phoneme safety)

        Returns:
            List of text chunks (each chunk contains only complete sentences)
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        # Split on sentence boundaries (period, exclamation, question mark followed by space)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If single sentence is too long, we must split it intelligently
            if len(sentence) > max_chars:
                # First, save any accumulated chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # Split long sentence at clause boundaries (commas, semicolons, etc.)
                # but try to keep complete clauses together
                clauses = re.split(r'([,;:—\-]\s+)', sentence)
                temp_chunk = ""

                for i, clause in enumerate(clauses):
                    if not clause.strip():
                        continue

                    # Check if adding this clause would exceed limit
                    if len(temp_chunk) + len(clause) > max_chars:
                        if temp_chunk:
                            # Only add if we have accumulated something
                            chunks.append(temp_chunk.strip())
                        temp_chunk = clause
                    else:
                        temp_chunk += clause

                # After processing all clauses, add to current_chunk
                # This ensures the sentence parts stay together when possible
                if temp_chunk:
                    current_chunk = temp_chunk.strip()

            # Normal case: sentence fits in remaining space of current chunk
            elif len(current_chunk) + len(sentence) + 1 > max_chars:
                # Current chunk is full, save it and start new chunk with this sentence
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    # Maximum time (seconds) for a single TTS chunk generation
    TTS_CHUNK_TIMEOUT = 120

    def generate_audio_chunk(self, text: str, output_path: Path, retry_count: int = 0) -> Path:
        """
        Generate audio for a single text chunk using Kokoro.
        Implements retry logic with recursive splitting if phoneme limit is exceeded.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            retry_count: Internal counter for recursion depth (max 3)

        Returns:
            Path to generated audio file
        """
        self._load_model()

        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Generate audio using Kokoro with timeout protection
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

            def _tts_generate():
                return self.model.create(
                    text=text,
                    voice=self.voice,
                    speed=1.0,
                    lang=self.language,
                    trim=True
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_tts_generate)
                try:
                    audio_array, sample_rate = future.result(timeout=self.TTS_CHUNK_TIMEOUT)
                except FuturesTimeoutError:
                    raise RuntimeError(
                        f"TTS generation timed out after {self.TTS_CHUNK_TIMEOUT}s "
                        f"for chunk ({len(text)} chars)"
                    )

            # Save as WAV
            sf.write(str(output_path), audio_array, sample_rate)

            print(f"✓ Saved: {output_path.name}")
            return output_path

        except IndexError as e:
            # Phoneme limit exceeded - split and retry
            if "out of bounds" in str(e) and retry_count < 3:
                print(f"⚠️  Phoneme limit hit, splitting chunk...")

                # Split text in half at sentence boundary
                mid_point = len(text) // 2
                sentences = re.split(r'(?<=[.!?])\s+', text)

                # Find best split point near middle
                current_len = 0
                split_idx = 0
                for i, sent in enumerate(sentences):
                    if current_len + len(sent) >= mid_point:
                        split_idx = i
                        break
                    current_len += len(sent) + 1

                # Split into two parts
                part1 = ' '.join(sentences[:split_idx]).strip()
                part2 = ' '.join(sentences[split_idx:]).strip()

                if not part1 or not part2:
                    # Fallback: hard split at mid_point
                    part1 = text[:mid_point].strip()
                    part2 = text[mid_point:].strip()

                print(f"  → Split into {len(part1)} + {len(part2)} chars")

                # Generate two separate files
                base_name = output_path.stem
                part1_path = output_path.parent / f"{base_name}_a.wav"
                part2_path = output_path.parent / f"{base_name}_b.wav"

                # Recursive retry on each part
                self.generate_audio_chunk(part1, part1_path, retry_count + 1)
                self.generate_audio_chunk(part2, part2_path, retry_count + 1)

                # Combine the two parts using ffmpeg
                print(f"  Combining parts...", end=" ", flush=True)
                combine_cmd = [
                    'ffmpeg', '-y', '-i', str(part1_path), '-i', str(part2_path),
                    '-filter_complex', '[0:0][1:0]concat=n=2:v=0:a=1[out]',
                    '-map', '[out]', str(output_path)
                ]

                try:
                    subprocess.run(combine_cmd, capture_output=True, check=True)
                    # Clean up temporary files
                    part1_path.unlink()
                    part2_path.unlink()
                    print(f"✓ Combined: {output_path.name}")
                    return output_path
                except subprocess.CalledProcessError:
                    # Retry with concat demuxer approach (more robust)
                    print(f"⚠️  filter_complex failed, retrying with concat demuxer...")
                    concat_file = output_path.parent / f"_concat_{output_path.stem}.txt"
                    try:
                        with open(concat_file, 'w') as f:
                            f.write(f"file '{part1_path.resolve()}'\n")
                            f.write(f"file '{part2_path.resolve()}'\n")
                        retry_cmd = [
                            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                            '-i', str(concat_file), '-c', 'copy', str(output_path)
                        ]
                        subprocess.run(retry_cmd, capture_output=True, check=True)
                        part1_path.unlink()
                        part2_path.unlink()
                        concat_file.unlink(missing_ok=True)
                        print(f"✓ Combined (concat retry): {output_path.name}")
                        return output_path
                    except subprocess.CalledProcessError:
                        concat_file.unlink(missing_ok=True)
                        print(f"⚠️  Both combine methods failed — second half lost")
                        print(f"  Part 1: {part1_path}")
                        print(f"  Part 2: {part2_path}")
                        return part1_path
            else:
                # Max retries reached or other error
                raise

    def _clean_chapter_text(self, text: str) -> str:
        """Clean chapter text for speech without Gutenberg stripping (already clean)."""
        # Remove markdown links FIRST (before headers), so [## Chapter 1](#...)
        # becomes ## Chapter 1, which the header regex can then clean
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # Remove markdown headers but keep text
        text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)
        # Also strip any ## markers mid-line (from TOC link cleanup above)
        text = re.sub(r'#{1,6}\s+', '', text)

        # Remove emphasis symbols
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        # Remove image references
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def _generate_silence_placeholder(self, output_path: Path, duration: float = 0.5):
        """Generate a short silence WAV as placeholder for a failed chunk."""
        import numpy as np
        sample_rate = 24000
        silence = np.zeros(int(sample_rate * duration), dtype=np.float32)
        sf.write(str(output_path), silence, sample_rate)

    def detect_chapters(self, text: str, is_cleaned: bool = False) -> list:
        """
        Detect chapter boundaries in text.

        Delegates to BookProcessor for raw text detection (canonical 14-pattern system).
        For cleaned text (with <<<CHAPTER:MARKER:...>>> tags), uses marker-based detection.

        Args:
            text: Text to search for chapters (should have Gutenberg boilerplate stripped)
            is_cleaned: Whether text has been cleaned for speech

        Returns:
            List of tuples: (chapter_number, start_position, title)
        """
        if is_cleaned:
            return self._detect_markers_in_cleaned_text(text)

        # Delegate to BookProcessor for raw text — single source of truth for chapter detection
        from lib.book.processor import BookProcessor
        processor = BookProcessor(verbose=False)
        cleaned_text, _ = processor.strip_gutenberg(text)
        bp_chapters = processor.detect_chapters(cleaned_text)

        # Convert BookProcessor Chapter objects to v1 tuple format
        return [(ch.number, ch.start_char, ch.marker) for ch in bp_chapters]

    def _detect_markers_in_cleaned_text(self, text: str) -> list:
        """Detect chapter markers in text that has been cleaned for speech."""
        chapters = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('<<<CHAPTER:MARKER:'):
                marker = line_stripped.replace('<<<CHAPTER:MARKER:', '').replace('>>>', '')
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, marker))

        return chapters

    def combine_audio_files(self, audio_files: list, output_file: Path) -> Path:
        """
        Combine multiple audio files into one using FFmpeg.

        Args:
            audio_files: List of audio file paths to combine
            output_file: Output file path

        Returns:
            Path to combined audio file
        """
        if not audio_files:
            return None

        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, cannot combine files")
            return None

        concat_file = output_file.parent / f"concat_{output_file.stem}.txt"
        with open(concat_file, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                abs_path = Path(audio_file).resolve()
                f.write(f"file '{abs_path}'\n")

        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(output_file)
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Warning: Failed to combine files: {e}")
            return None

    def post_process_audio(
        self,
        input_file: Path,
        output_file: Path,
        speed: float = 1.0,
        normalize: bool = True,
        convert_to_mp3: bool = True
    ) -> Path:
        """
        Post-process audio file (speed, normalize, convert to MP3).

        Args:
            input_file: Input audio file
            output_file: Output audio file
            speed: Speed multiplier (1.0 = normal)
            normalize: Whether to normalize loudness
            convert_to_mp3: Whether to convert to MP3

        Returns:
            Path to processed audio file
        """
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, skipping post-processing")
            return input_file

        filters = []

        # Speed adjustment
        if speed != 1.0:
            if speed <= 2.0:
                filters.append(f"atempo={speed}")
            else:
                # Chain multiple atempo filters for >2.0x
                remaining = speed
                while remaining > 1.0:
                    factor = min(remaining, 2.0)
                    filters.append(f"atempo={factor}")
                    remaining /= factor

        # Loudness normalization
        if normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

        cmd = ['ffmpeg', '-y', '-i', str(input_file)]

        if filters:
            cmd.extend(['-af', ','.join(filters)])

        if convert_to_mp3:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '128k'])
        else:
            cmd.extend(['-c:a', 'copy'])

        cmd.append(str(output_file))

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Warning: Post-processing failed: {e}")
            return input_file

    def _generate_chunk_manifest(
        self,
        chunks: List[str],
        audio_files: List[Path],
        chunk_to_chapter: List[int],
        clean_text: str,
        base_name: str,
        output_dir: Path
    ) -> dict:
        """
        Generate chunk manifest for text synchronization.

        Args:
            chunks: List of text chunks
            audio_files: List of generated audio file paths
            chunk_to_chapter: List mapping chunk index to chapter number
            clean_text: Full cleaned text (spoken version)
            base_name: Base filename for output
            output_dir: Output directory

        Returns:
            Chunk manifest dictionary
        """
        import json

        manifest = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_chunks": len(chunks),
            "total_text_length": len(clean_text),
            "chunks": []
        }

        cumulative_duration = 0.0
        current_text_pos = 0

        for i, (chunk_text, audio_file, chapter_num) in enumerate(zip(chunks, audio_files, chunk_to_chapter), 1):
            # Get audio duration using ffprobe
            try:
                result = subprocess.run(
                    [
                        'ffprobe', '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        str(audio_file)
                    ],
                    capture_output=True,
                    text=True,
                    check=True
                )
                duration = float(result.stdout.strip())
            except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
                print(f"⚠️  Warning: Could not get duration for chunk {i}: {e}")
                duration = 0.0

            text_start = current_text_pos
            text_end = current_text_pos + len(chunk_text)

            chunk_info = {
                "number": i,
                "file": audio_file.name,
                "duration": round(duration, 3),
                "text_start": text_start,
                "text_end": text_end,
                "text_length": len(chunk_text),
                "text_preview": chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text,
                "chapter": chapter_num,
                "cumulative_duration": round(cumulative_duration, 3)
            }

            manifest["chunks"].append(chunk_info)

            cumulative_duration += duration
            current_text_pos = text_end

        manifest["total_duration"] = round(cumulative_duration, 3)

        # Save manifest
        manifest_path = output_dir / f"{base_name}_chunk_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Save the clean text for word timing generation (karaoke)
        clean_text_path = output_dir / f"{base_name}_clean_text.txt"
        with open(clean_text_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)

        return manifest

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: str = None,
        chunk_size: int = 800,
        speed: float = 1.0,
        normalize: bool = True,
        to_mp3: bool = True,
        generate_cover: bool = False
    ) -> dict:
        """
        Generate complete audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per chunk (800 recommended for phoneme safety)
            speed: Playback speed multiplier (1.0 = normal)
            normalize: Whether to normalize loudness
            to_mp3: Whether to convert to MP3 format
            generate_cover: Whether to generate cover art (requires generate.py)

        Returns:
            Dictionary with generation results
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Extract base name for output files
        base_name = input_path.stem

        print(f"Reading: {input_file}")
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        # IMPORTANT: Detect chapters from ORIGINAL markdown using BookProcessor
        # This ensures chapter structure comes from source text with full 14-pattern detection
        print("Detecting chapters from source markdown...")
        from lib.book.processor import BookProcessor
        processor = BookProcessor(verbose=False)
        stripped_text, _ = processor.strip_gutenberg(raw_text)
        chapter_objects = processor.detect_chapters(stripped_text)

        # Also build tuples for backward-compat
        chapters = [(ch.number, ch.start_char, ch.marker) for ch in chapter_objects]

        has_chapters = len(chapters) > 0
        if has_chapters:
            print(f"✓ Found {len(chapters)} chapters")
            for ch_num, ch_pos, ch_title in chapters:
                print(f"   Chapter {ch_num}: {ch_title}")
        else:
            print("ℹ  No chapters detected (will create single file)")

        # Optional: Preprocess text for natural speech (markdown → spoken form)
        text_mapping_file = None

        # Process per-chapter: clean and chunk each chapter independently
        # This eliminates the fragile proportional position mapping
        chunks = []
        chunk_to_chapter = []
        clean_text = ""

        if has_chapters:
            print(f"\nProcessing {len(chapter_objects)} chapters independently...")
            for ch_obj in chapter_objects:
                chapter_content = ch_obj.content

                # Preprocess chapter if available
                if PREPROCESSOR_AVAILABLE:
                    preprocessor = AudioTextPreprocessor()
                    preprocess_result = preprocessor.preprocess_for_speech(chapter_content)
                    chapter_content = preprocess_result.spoken_text

                # Clean chapter text for speech (skip Gutenberg — already stripped)
                chapter_clean = self._clean_chapter_text(chapter_content)

                if not chapter_clean.strip():
                    print(f"  Chapter {ch_obj.number}: (empty after cleaning, skipping)")
                    continue

                # Chunk this chapter
                chapter_chunks = self.chunk_text(chapter_clean, chunk_size)
                chunk_count = len(chapter_chunks)

                chunks.extend(chapter_chunks)
                chunk_to_chapter.extend([ch_obj.number] * chunk_count)
                clean_text += chapter_clean + "\n\n"

                print(f"  Chapter {ch_obj.number}: {chunk_count} chunks ({len(chapter_clean):,} chars)")

            # Save text mapping if preprocessing was used
            if PREPROCESSOR_AVAILABLE:
                temp_output_dir = output_dir if output_dir else input_path.parent / "audio_kokoro"
                temp_output_dir = Path(temp_output_dir)
                text_mapping_file = temp_output_dir / f"{base_name}_text_mapping.json"
                text_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            # No chapters: process entire text as one unit
            preprocessed_text = raw_text
            if PREPROCESSOR_AVAILABLE:
                preprocessor = AudioTextPreprocessor()
                preprocess_result = preprocessor.preprocess_for_speech(raw_text)
                preprocessed_text = preprocess_result.spoken_text

                if preprocess_result.transformations:
                    temp_output_dir = output_dir if output_dir else input_path.parent / "audio_kokoro"
                    temp_output_dir = Path(temp_output_dir)
                    text_mapping_file = temp_output_dir / f"{base_name}_text_mapping.json"
                    text_mapping_file.parent.mkdir(parents=True, exist_ok=True)
                    preprocessor.save_mapping(preprocess_result, text_mapping_file)

            clean_text = self.clean_text_for_speech(preprocessed_text, preserve_chapter_markers=False)
            chunks = self.chunk_text(clean_text, chunk_size)
            chunk_to_chapter = [1] * len(chunks)

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"\nText ready: {char_count:,} characters, {word_count:,} words")
        print(f"Created {len(chunks)} audio chunks across {len(set(chunk_to_chapter))} chapter(s)")
        print()

        if output_dir is None:
            output_dir = input_path.parent / "audio_kokoro"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Acquire file lock to prevent concurrent generation to same directory
        import fcntl
        lock_file_path = output_dir / ".generation.lock"
        lock_fd = open(lock_file_path, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_fd.close()
            raise RuntimeError(
                f"Another audio generation is already running for {output_dir}.\n"
                f"Wait for it to finish or remove {lock_file_path}"
            )

        # Create raw directory if post-processing
        if speed != 1.0 or normalize or to_mp3:
            raw_dir = output_dir / "raw"
            raw_dir.mkdir(exist_ok=True)
        else:
            raw_dir = output_dir

        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("LOCAL TTS AUDIO GENERATION (Kokoro)")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Voice: {self.voice}")
        print(f"Chunks: {len(chunks)}")
        print(f"Speed: {speed}x")
        print(f"Normalize: {normalize}")
        print(f"Format: {'MP3' if to_mp3 else 'WAV'}")
        print("="*70)
        print()

        # Generate audio for each chunk (with checkpointing for resume)
        import json as json_module
        raw_audio_files = []
        audio_files = []
        failed_chunks = []
        MAX_CHUNK_RETRIES = 3
        start_chunk = 0

        # Check for existing checkpoint to resume from
        checkpoint_file = output_dir / ".generation_checkpoint.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r') as cf:
                    checkpoint = json_module.load(cf)
                if (checkpoint.get('input_file') == str(input_path) and
                        checkpoint.get('voice') == self.voice and
                        checkpoint.get('total_chunks') == len(chunks)):
                    start_chunk = checkpoint.get('last_complete_chunk', 0)
                    raw_audio_files = [Path(f) for f in checkpoint.get('completed_files', []) if Path(f).exists()]
                    if start_chunk > 0:
                        print(f"📌 Resuming from chunk {start_chunk + 1}/{len(chunks)} ({start_chunk} already complete)")
            except (json_module.JSONDecodeError, KeyError):
                pass  # Corrupt checkpoint, start fresh

        import time as time_module
        generation_start = time_module.time()

        for i, chunk_text in enumerate(chunks, 1):
            if i <= start_chunk:
                continue  # Skip already-completed chunks

            if i == 1 or i == len(chunks) or i % 10 == 0 or i == start_chunk + 1:
                elapsed = time_module.time() - generation_start
                chunks_done = i - start_chunk
                percentage = (i / len(chunks)) * 100

                if chunks_done > 1:
                    rate = chunks_done / elapsed
                    remaining = len(chunks) - i
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta_str = self._format_eta(eta_seconds)
                else:
                    eta_str = "calculating..."

                bar_width = 40
                filled = int(bar_width * i / len(chunks))
                bar = "█" * filled + "░" * (bar_width - filled)

                print(f"\n  Progress: [{bar}] {i}/{len(chunks)} ({percentage:.1f}%) | ETA: {eta_str}")

            # Generate raw WAV with retry logic
            raw_filename = f"{base_name}_chunk{i:03d}_raw.wav"
            raw_output_path = raw_dir / raw_filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            success = False
            for attempt in range(MAX_CHUNK_RETRIES):
                try:
                    self.generate_audio_chunk(chunk_text, raw_output_path)
                    raw_audio_files.append(raw_output_path)
                    success = True
                    break
                except Exception as e:
                    if attempt < MAX_CHUNK_RETRIES - 1:
                        print(f"\n  ⚠ Retry {attempt + 1}/{MAX_CHUNK_RETRIES} for chunk {i}: {e}")
                        time_module.sleep(1)
                    else:
                        print(f"\n  ✗ SKIPPING chunk {i} after {MAX_CHUNK_RETRIES} attempts: {e}")
                        failed_chunks.append((i, str(e)))

            if not success:
                # Generate silence placeholder so chapter boundaries stay correct
                self._generate_silence_placeholder(raw_output_path, duration=0.5)
                raw_audio_files.append(raw_output_path)

            # Save checkpoint every 10 chunks
            if i % 10 == 0:
                checkpoint_data = {
                    'input_file': str(input_path),
                    'voice': self.voice,
                    'last_complete_chunk': i,
                    'completed_files': [str(f) for f in raw_audio_files],
                    'total_chunks': len(chunks)
                }
                with open(checkpoint_file, 'w') as cf:
                    json_module.dump(checkpoint_data, cf, indent=2)

        # Report any failed chunks
        if failed_chunks:
            print(f"\n⚠ WARNING: {len(failed_chunks)} chunk(s) failed and were replaced with silence:")
            for chunk_num, error in failed_chunks:
                print(f"   Chunk {chunk_num}: {error}")

        # Post-process audio files
        if speed != 1.0 or normalize or to_mp3:
            print(f"\n🔧 Post-processing audio...")
            print(f"   Speed: {speed}x, Normalize: {normalize}, MP3: {to_mp3}")

            for i, raw_file in enumerate(raw_audio_files, 1):
                ext = '.mp3' if to_mp3 else '.wav'
                processed_filename = f"{base_name}_chunk{i:03d}{ext}"
                processed_path = output_dir / processed_filename

                if i % 10 == 0 or i == 1 or i == len(raw_audio_files):
                    print(f"  [{i}/{len(raw_audio_files)}] Processing {raw_file.name}...", end=" ", flush=True)

                result = self.post_process_audio(
                    raw_file,
                    processed_path,
                    speed=speed,
                    normalize=normalize,
                    convert_to_mp3=to_mp3
                )

                if i % 10 == 0 or i == 1 or i == len(raw_audio_files):
                    print("✓")

                audio_files.append(result)
        else:
            audio_files = raw_audio_files

        # Generate chunk manifest for text synchronization
        print(f"\n📊 Generating chunk manifest for text sync...")
        chunk_manifest = self._generate_chunk_manifest(
            chunks=chunks,
            audio_files=audio_files,
            chunk_to_chapter=chunk_to_chapter,
            clean_text=clean_text,
            base_name=base_name,
            output_dir=output_dir
        )
        print(f"✓ Chunk manifest saved: {base_name}_chunk_manifest.json")

        # Generate playlist for individual chunks
        ext = '.mp3' if to_mp3 else '.wav'
        # Primary chunks playlist (consistent name)
        chunks_playlist_path = output_dir / f"{base_name}_chunks.m3u"
        with open(chunks_playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for audio_file in audio_files:
                f.write(f"#EXTINF:-1,{audio_file.stem}\n")
                f.write(f"{audio_file.name}\n")

        # Timestamped backup
        timestamped_chunks_path = output_dir / f"{base_name}_chunks_{timestamp}.m3u"
        with open(timestamped_chunks_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for audio_file in audio_files:
                f.write(f"#EXTINF:-1,{audio_file.stem}\n")
                f.write(f"{audio_file.name}\n")

        print(f"\n✓ Chunks playlist created: {chunks_playlist_path.name}")
        print(f"  Backup: {timestamped_chunks_path.name}")

        # Combine chunks into chapter files
        chapter_files = []
        if chapters and len(chapters) > 1:
            print(f"\n📚 Combining {len(chunks)} chunks into {len(chapters)} chapters...")

            # Get unique chapter numbers from mapping, sorted
            unique_chapters = sorted(set(chunk_to_chapter))

            # Iterate through detected chapters and create sequential files (chapter_01, chapter_02, etc.)
            for sequential_index, chapter_num in enumerate(unique_chapters, 1):
                chapter_audio_files = [
                    audio_files[i] for i in range(len(audio_files))
                    if chunk_to_chapter[i] == chapter_num
                ]

                if chapter_audio_files:
                    # Use sequential index for filename (not source chapter number)
                    chapter_filename = f"{base_name}_chapter_{sequential_index:02d}{ext}"
                    chapter_path = output_dir / chapter_filename

                    print(f"  Chapter {sequential_index:2d}: Combining {len(chapter_audio_files)} chunks...", end=" ", flush=True)

                    result = self.combine_audio_files(chapter_audio_files, chapter_path)
                    if result:
                        chapter_files.append(result)
                        print(f"✓ {chapter_path.name}")
                    else:
                        print("✗ Failed")

            if chapter_files:
                # Create primary playlist (consistent name for server, no timestamp)
                primary_playlist_path = output_dir / f"{base_name}_audiobook.m3u"
                with open(primary_playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for i, chapter_file in enumerate(chapter_files, 1):
                        f.write(f"#EXTINF:-1,Chapter {i}\n")
                        f.write(f"{chapter_file.name}\n")

                # Also create timestamped backup for history
                timestamped_playlist_path = output_dir / f"{base_name}_audiobook_{timestamp}.m3u"
                with open(timestamped_playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for i, chapter_file in enumerate(chapter_files, 1):
                        f.write(f"#EXTINF:-1,Chapter {i}\n")
                        f.write(f"{chapter_file.name}\n")

                playlist_path = primary_playlist_path  # Use primary for return value
                print(f"\n✓ Master audiobook playlist created: {primary_playlist_path.name}")
                print(f"  ({len(chapter_files)} chapters)")
                print(f"  Backup: {timestamped_playlist_path.name}")
        else:
            print(f"\n📚 Combining all {len(audio_files)} chunks into single file...")
            combined_filename = f"{base_name}_complete{ext}"
            combined_path = output_dir / combined_filename

            result = self.combine_audio_files(audio_files, combined_path)
            if result:
                chapter_files.append(result)
                print(f"✓ Complete audiobook: {combined_path.name}")

                # Create primary playlist (consistent name for server, no timestamp)
                primary_playlist_path = output_dir / f"{base_name}_audiobook.m3u"
                with open(primary_playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1,Complete Audiobook\n")
                    f.write(f"{combined_path.name}\n")

                # Also create timestamped backup for history
                timestamped_playlist_path = output_dir / f"{base_name}_audiobook_{timestamp}.m3u"
                with open(timestamped_playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1,Complete Audiobook\n")
                    f.write(f"{combined_path.name}\n")

                playlist_path = primary_playlist_path  # Use primary for return value
                print(f"✓ Audiobook playlist created: {primary_playlist_path.name}")
                print(f"  Backup: {timestamped_playlist_path.name}")
            else:
                playlist_path = chunks_playlist_path

        # Generate cover art if requested
        if generate_cover:
            print("\n🎨 Generating cover art...")
            try:
                # Extract title from filename
                title = base_name.replace('_', ' ').title()

                # Try to generate cover
                cover_script = Path(__file__).parent / "generate.py"
                if cover_script.exists():
                    cover_path = output_dir / f"{base_name}_cover.png"
                    prompt = f"Book cover art for '{title}', classic literature style, elegant"

                    cmd = [
                        sys.executable,
                        str(cover_script),
                        prompt,
                        '--output', str(cover_path)
                    ]

                    subprocess.run(cmd, capture_output=True, check=True)
                    print(f"✓ Cover art saved: {cover_path.name}")
                else:
                    print("⚠️  generate.py not found, skipping cover art")
            except Exception as e:
                print(f"⚠️  Cover generation failed: {e}")

        # Clean up checkpoint and lock on successful completion
        checkpoint_file = output_dir / ".generation_checkpoint.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            lock_file_path.unlink(missing_ok=True)
        except Exception:
            pass

        print("\n" + "="*70)
        print("AUDIO GENERATION COMPLETE")
        print("="*70)
        print(f"Total chunks: {len(audio_files)}")
        if chapters and len(chapters) > 1:
            print(f"Chapters: {len(chapter_files)}")
        print(f"Format: {'MP3' if to_mp3 else 'WAV'}")
        print(f"Playlist: {playlist_path}")
        print(f"Output directory: {output_dir}")
        print("="*70)

        return {
            'audio_files': [str(f) for f in audio_files],
            'chapter_files': [str(f) for f in chapter_files] if chapter_files else [],
            'playlist': str(playlist_path),
            'chunks': len(chunks),
            'chapters': len(chapters) if chapters else 0,
            'word_count': word_count,
            'output_directory': str(output_dir),
            'format': 'mp3' if to_mp3 else 'wav'
        }


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Local TTS Audio Generation using Kokoro (ONNX Runtime)")
        print("="*70)
        print("\nUsage:")
        print("  python local_tts_kokoro.py <input_file> [options]")
        print("\nOptions:")
        print("  --voice VOICE          Voice ID (default: af_sky)")
        print("  --lang LANG            Language code (default: en-us)")
        print("  --chunk-size SIZE      Characters per chunk (default: 800)")
        print("  --speed SPEED          Playback speed multiplier (default: 1.0)")
        print("  --no-normalize         Skip loudness normalization")
        print("  --no-mp3               Keep WAV format (don't convert to MP3)")
        print("  --generate-cover       Generate cover art for audiobook")
        print("  --output-dir DIR       Custom output directory")
        print("\nExamples:")
        print("  # Basic usage (default voice: af_sky - American Female)")
        print("  python local_tts_kokoro.py translated.md")
        print()
        print("  # British female voice (great for classics)")
        print("  python local_tts_kokoro.py translated.md --voice bf_emma")
        print()
        print("  # British male voice with cover art")
        print("  python local_tts_kokoro.py translated.md --voice bm_george --generate-cover")
        print()
        print("  # Custom speed")
        print("  python local_tts_kokoro.py translated.md --speed 1.15")
        print()
        print("\nTop Recommended Voices:")
        print("  af_sky         - American Female - Sky (DEFAULT)")
        print("  bf_emma        - British Female - Emma (classics)")
        print("  bf_isabella    - British Female - Isabella")
        print("  bm_george      - British Male - George (classics)")
        print("  am_adam        - American Male - Adam")
        print("  am_onyx        - American Male - Onyx (deep)")
        print()
        print("  Total: 52 voices available (af_*, am_*, bf_*, bm_*, etc.)")
        print()
        print("\nFeatures:")
        print("  • FREE & LOCAL - No API costs, 100% local")
        print("  • FAST - 31× faster than Bark")
        print("  • HIGH QUALITY - Rivals commercial APIs")
        print("  • COMMERCIAL - Apache 2.0 license")
        print("  • OPTIMIZED - Apple Silicon GPU acceleration")
        print("  • Automatic chapter detection")
        print("\nRequirements:")
        print("  pip install kokoro-tts kokoro-onnx soundfile")
        print("  brew install ffmpeg  # macOS")
        print()
        print("  Models (downloaded once to ~/.cache/kokoro/):")
        print("    kokoro-v1.0.onnx (310MB)")
        print("    voices-v1.0.bin (25MB)")
        sys.exit(1)

    input_file = sys.argv[1]
    voice = KokoroAudioGenerator.VOICE_AF_SKY
    language = "en-us"
    chunk_size = 800
    speed = 1.0
    normalize = True
    to_mp3 = True
    generate_cover = False
    output_dir = None

    # Parse arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--voice":
            if i + 1 < len(sys.argv):
                voice = sys.argv[i + 1]
                i += 2
            else:
                print("❌ ERROR: --voice requires a voice ID")
                sys.exit(1)
        elif arg == "--lang":
            if i + 1 < len(sys.argv):
                language = sys.argv[i + 1]
                i += 2
            else:
                print("❌ ERROR: --lang requires a language code")
                sys.exit(1)
        elif arg == "--chunk-size":
            if i + 1 < len(sys.argv):
                chunk_size = int(sys.argv[i + 1])
                i += 2
            else:
                print("❌ ERROR: --chunk-size requires a number")
                sys.exit(1)
        elif arg == "--speed":
            if i + 1 < len(sys.argv):
                speed = float(sys.argv[i + 1])
                i += 2
            else:
                print("❌ ERROR: --speed requires a number")
                sys.exit(1)
        elif arg == "--no-normalize":
            normalize = False
            i += 1
        elif arg == "--no-mp3":
            to_mp3 = False
            i += 1
        elif arg == "--generate-cover":
            generate_cover = True
            i += 1
        elif arg == "--output-dir":
            if i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            else:
                print("❌ ERROR: --output-dir requires a directory path")
                sys.exit(1)
        else:
            print(f"⚠️  Warning: Unknown argument: {arg}")
            i += 1

    try:
        # Validate input file before processing
        print("\n" + "="*70)
        print("PRE-FLIGHT VALIDATION")
        print("="*70)
        validation_report = validate_book(input_file, verbose=False)

        if not validation_report.valid:
            print("⚠️  Input validation found issues:")
            for error in validation_report.errors:
                print(f"   ❌ {error}")
            for warning in validation_report.warnings:
                print(f"   ⚠️  {warning}")

            if validation_report.fixes:
                print("\n💡 Suggested fixes:")
                for fix in validation_report.fixes:
                    print(f"   • {fix}")

            print("\n❓ Continue anyway? (y/N): ", end="")
            response = input().strip().lower()
            if response != 'y':
                print("Aborted by user.")
                sys.exit(1)
        else:
            print("✅ Input validation passed!")
            feature_count = sum(validation_report.feature_support.values())
            print(f"✅ Feature support: {feature_count}/3 features ready")

        print("="*70 + "\n")

        generator = KokoroAudioGenerator(voice=voice, language=language)

        result = generator.generate_audiobook(
            input_file,
            output_dir=output_dir,
            chunk_size=chunk_size,
            speed=speed,
            normalize=normalize,
            to_mp3=to_mp3,
            generate_cover=generate_cover
        )

        print("\n✅ Success! Audio files ready to play.")
        print(f"\n💡 Tip: Play with: afplay {result['playlist']}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
