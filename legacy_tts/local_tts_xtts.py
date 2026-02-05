#!/usr/bin/env python3
"""
Local TTS Audio Generation using XTTS-v2 (Coqui TTS)

Generates high-quality audiobooks locally using voice cloning with XTTS-v2.
No API costs, fully local processing with optional FFmpeg post-processing.

Requirements:
    pip install TTS==0.27.3
    brew install ffmpeg  # macOS
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    from TTS.api import TTS
except ImportError:
    print("❌ ERROR: TTS library not installed")
    print("\nPlease install Coqui TTS:")
    print("  pip install TTS==0.27.3")
    sys.exit(1)


class XTTSAudioGenerator:
    """Local TTS audio generation using XTTS-v2 with voice cloning"""

    # XTTS-v2 model
    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Supported languages (XTTS-v2 is multilingual)
    LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "ko", "hu"]

    def __init__(self, reference_voice=None, language: str = "en"):
        """
        Initialize XTTS-v2 audio generator.

        Args:
            reference_voice: Path(s) to reference voice WAV file(s) (10-30s each, clean, mono, 24kHz recommended)
                            Can be a string (single file) or list of strings (multiple files)
            language: Target language code (default: "en")
        """
        # Normalize to list format
        if reference_voice is None:
            self.reference_voice = None
        elif isinstance(reference_voice, str):
            self.reference_voice = [reference_voice]
        elif isinstance(reference_voice, list):
            self.reference_voice = reference_voice
        else:
            raise TypeError(f"reference_voice must be str, list, or None, got {type(reference_voice)}")

        self.language = language

        if language not in self.LANGUAGES:
            print(f"⚠️  Warning: '{language}' may not be fully supported. Recommended: {', '.join(self.LANGUAGES)}")

        print("Loading XTTS-v2 model (this may take a moment)...")
        self.tts = TTS(model_name=self.MODEL_NAME, progress_bar=False, gpu=False)
        print("✓ Model loaded successfully")

        # Verify reference voice(s) if provided
        if self.reference_voice:
            for ref_voice in self.reference_voice:
                ref_path = Path(ref_voice)
                if not ref_path.exists():
                    raise FileNotFoundError(f"Reference voice not found: {ref_voice}")

            if len(self.reference_voice) == 1:
                print(f"✓ Using reference voice: {Path(self.reference_voice[0]).name}")
            else:
                print(f"✓ Using {len(self.reference_voice)} reference voices:")
                for i, ref in enumerate(self.reference_voice, 1):
                    print(f"  {i}. {Path(ref).name}")

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

    def clean_text_for_speech(self, text: str, preserve_chapter_markers: bool = False) -> str:
        """
        Clean markdown text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown
            preserve_chapter_markers: If True, keep Roman numeral chapter markers

        Returns:
            Cleaned text suitable for TTS
        """
        # Preserve standalone Roman numeral chapter markers FIRST (before other cleaning)
        if preserve_chapter_markers:
            # Replace standalone Roman numerals on their own line with markers
            text = re.sub(
                r'^(X{0,3})(IX|IV|V?I{0,3})\.$',
                lambda m: f"CHAPTER_MARKER_{m.group(0)}",
                text,
                flags=re.MULTILINE
            )

        # Remove markdown headers but keep text (unless it's a chapter marker)
        if preserve_chapter_markers:
            # Keep Roman numerals in headers as chapter markers
            def replace_header(match):
                header_text = match.group(2)
                # Check if it's a Roman numeral chapter marker
                if re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', header_text.strip()):
                    return f"CHAPTER_MARKER_{header_text.strip()}"
                return header_text
            text = re.sub(r'^(#{1,6})\s+(.+)$', replace_header, text, flags=re.MULTILINE)
        else:
            text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)

        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

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

    def chunk_text(self, text: str, max_chars: int = 250) -> List[str]:
        """
        Split text into chunks for better TTS quality, ensuring complete sentences.
        XTTS-v2 has a 400 token limit (~250 chars max).

        PRIORITY: Always split at sentence boundaries for natural audio flow.
        Better to have shorter chunks than to split sentences mid-way.

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (250 max for XTTS-v2)

        Returns:
            List of text chunks (each chunk contains only complete sentences when possible)
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

        # Final safety validation - ensure NO chunk exceeds max_chars
        # If any do, split them at natural pause points
        validated_chunks = []
        for chunk in chunks:
            if len(chunk) > max_chars:
                print(f"⚠️  Warning: Chunk still too long ({len(chunk)} chars), splitting at clause boundaries...")

                # Emergency split at clauses/commas
                parts = re.split(r'([,;:\-—]\s+)', chunk)
                temp = ""
                for part in parts:
                    if len(temp) + len(part) > max_chars:
                        if temp:
                            validated_chunks.append(temp.strip())
                        temp = part
                    else:
                        temp += part
                if temp:
                    validated_chunks.append(temp.strip())
            else:
                validated_chunks.append(chunk)

        return validated_chunks

    def generate_audio_chunk(self, text: str, output_path: Path) -> Path:
        """
        Generate audio for a single text chunk using XTTS-v2.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file

        Returns:
            Path to generated audio file
        """
        # Safety check - XTTS has 250 char limit
        if len(text) > 250:
            print(f"⚠️  WARNING: Text too long ({len(text)} chars), truncating to 250...", end=" ", flush=True)
            text = text[:250]

        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.tts.tts_to_file(
            text=text,
            speaker_wav=self.reference_voice,
            language=self.language,
            file_path=str(output_path)
        )

        print(f"✓ Saved: {output_path.name}")
        return output_path

    def post_process_audio(
        self,
        input_file: Path,
        output_file: Path,
        speed: float = 1.15,
        normalize: bool = True,
        convert_to_mp3: bool = False
    ) -> Path:
        """
        Post-process audio with FFmpeg for better quality.

        Args:
            input_file: Input WAV file
            output_file: Output file path
            speed: Speed multiplier (1.15 = 15% faster, reduces "draggy" feel)
            normalize: Apply loudness normalization
            convert_to_mp3: Convert final output to MP3

        Returns:
            Path to processed audio file
        """
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, skipping post-processing")
            return input_file

        print(f"  Post-processing (speed={speed}x, normalize={normalize})...", end=" ", flush=True)

        # Build ffmpeg filter chain
        filters = []

        # Speed adjustment
        if speed != 1.0:
            # Handle speeds > 2.0 by chaining filters
            if speed > 2.0:
                filters.append("atempo=2.0")
                remaining = speed / 2.0
                while remaining > 1.0:
                    next_tempo = min(remaining, 2.0)
                    filters.append(f"atempo={next_tempo}")
                    remaining /= next_tempo
            else:
                filters.append(f"atempo={speed}")

        # Loudness normalization (audiobook-friendly)
        if normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

        filter_string = ",".join(filters) if filters else None

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', str(input_file)]

        if filter_string:
            cmd.extend(['-filter:a', filter_string])

        # Output format
        if convert_to_mp3:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '128k'])

        cmd.append(str(output_file))

        # Run ffmpeg
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ FFmpeg error: {result.stderr}")
            return input_file

        print(f"✓ Processed: {output_file.name}")
        return output_file

    def detect_chapters(self, text: str, is_cleaned: bool = False) -> list:
        """
        Detect chapter boundaries in text.
        Looks for Roman numerals (I., II., III.), CHAPTER_MARKER_ tags, or Markdown headers.

        Args:
            text: Text to search for chapters
            is_cleaned: Whether text has been cleaned (looks for CHAPTER_MARKER_ tags)

        Returns:
            List of tuples: (chapter_number, start_position, title)
        """
        chapters = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Check for preserved chapter markers (in cleaned text)
            if is_cleaned and line_stripped.startswith('CHAPTER_MARKER_'):
                marker = line_stripped.replace('CHAPTER_MARKER_', '')
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, marker))
                continue

            # Roman numeral pattern (I., II., III., etc.)
            roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', line_stripped)
            if roman_match:
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, line_stripped))
                continue

            # Detect standalone Roman numerals in markdown headers (e.g., "## I", "## II")
            # Common in classic literature like The Great Gatsby
            roman_header_match = re.match(r'^#+\s+([IVXLCDM]+)$', line_stripped)
            if roman_header_match:
                roman_text = roman_header_match.group(1)
                # Validate it's a valid Roman numeral (basic check)
                if re.fullmatch(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', roman_text):
                    char_pos = len('\n'.join(lines[:i]))
                    chapter_num = len(chapters) + 1
                    chapters.append((chapter_num, char_pos, line_stripped))
                    continue

            # Markdown header patterns
            header_match = re.match(r'^#+\s+(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+)', line_stripped)
            if header_match:
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, line_stripped))

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

        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, cannot combine files")
            return None

        # Create concat file for ffmpeg
        concat_file = output_file.parent / f"concat_{output_file.stem}.txt"
        with open(concat_file, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                # Use absolute paths for ffmpeg concat
                abs_path = Path(audio_file).resolve()
                f.write(f"file '{abs_path}'\n")

        # Combine files
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
            concat_file.unlink()  # Clean up concat file
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Warning: Failed to combine files: {e}")
            return None

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: str = None,
        chunk_size: int = 250,
        speed: float = 1.20,
        normalize: bool = True,
        to_mp3: bool = True
    ) -> dict:
        """
        Generate complete audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per chunk (250 max due to XTTS 400 token limit)
            speed: Speed multiplier (1.20 recommended, reduces "robotic" feel)
            normalize: Apply loudness normalization
            to_mp3: Convert to MP3 (smaller files)

        Returns:
            Dictionary with generation results
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Read text
        print(f"Reading: {input_file}")
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        # Detect chapters BEFORE cleaning
        print("Detecting chapters...")
        chapters_raw = self.detect_chapters(raw_text, is_cleaned=False)

        # Clean text for speech, preserving chapter markers if chapters found
        preserve_markers = len(chapters_raw) > 0
        if preserve_markers:
            print(f"✓ Found {len(chapters_raw)} chapters - preserving markers during cleaning")
        else:
            print("ℹ  No chapters detected (will create single file)")

        print("Cleaning text for speech...")
        clean_text = self.clean_text_for_speech(raw_text, preserve_chapter_markers=preserve_markers)

        # Re-detect chapters in cleaned text
        chapters = self.detect_chapters(clean_text, is_cleaned=True) if preserve_markers else []

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"Text ready: {char_count:,} characters, {word_count:,} words")

        # Chunk text
        print(f"Chunking text (max {chunk_size} chars per chunk)...")
        chunks = self.chunk_text(clean_text, chunk_size)

        # Remove CHAPTER_MARKER_ tags from chunks (so they don't get spoken)
        if preserve_markers:
            chunks = [chunk.replace('CHAPTER_MARKER_', '').replace('CHAPTER_MARKER_I.', '').replace('CHAPTER_MARKER_II.', '').replace('CHAPTER_MARKER_III.', '').replace('CHAPTER_MARKER_IV.', '').replace('CHAPTER_MARKER_V.', '').replace('CHAPTER_MARKER_VI.', '').replace('CHAPTER_MARKER_VII.', '').replace('CHAPTER_MARKER_VIII.', '').replace('CHAPTER_MARKER_IX.', '').replace('CHAPTER_MARKER_X.', '').replace('CHAPTER_MARKER_XI.', '').replace('CHAPTER_MARKER_XII.', '').replace('CHAPTER_MARKER_XIII.', '').replace('CHAPTER_MARKER_XIV.', '').replace('CHAPTER_MARKER_XV.', '').replace('CHAPTER_MARKER_XVI.', '').replace('CHAPTER_MARKER_XVII.', '').replace('CHAPTER_MARKER_XVIII.', '').replace('CHAPTER_MARKER_XIX.', '').replace('CHAPTER_MARKER_XX.', '') for chunk in chunks]
            # Clean up - use regex to remove any remaining markers
            chunks = [re.sub(r'CHAPTER_MARKER_[^\s]*', '', chunk).strip() for chunk in chunks]

        print(f"Created {len(chunks)} audio chunks")

        # Map chunks to chapters (if chapters detected)
        chunk_to_chapter = []
        if chapters:
            # Chapters now have accurate positions in cleaned text
            # Assign each chunk to a chapter based on text position

            current_char_pos = 0
            current_chapter = 1
            chapter_idx = 0

            for i, chunk in enumerate(chunks):
                # Check if we've crossed into a new chapter
                while chapter_idx < len(chapters) - 1:
                    next_chapter_pos = chapters[chapter_idx + 1][1]
                    if current_char_pos >= next_chapter_pos:
                        current_chapter += 1
                        chapter_idx += 1
                    else:
                        break

                chunk_to_chapter.append(current_chapter)
                current_char_pos += len(chunk)

            print(f"✓ Mapped {len(chunks)} chunks to {max(chunk_to_chapter)} chapters\n")
        else:
            chunk_to_chapter = [1] * len(chunks)
            print()

        # Create output directory
        if output_dir is None:
            output_dir = input_path.parent / "audio_xtts"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate base filename
        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("LOCAL TTS AUDIO GENERATION (XTTS-v2)")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Language: {self.language}")
        if self.reference_voice:
            if len(self.reference_voice) == 1:
                print(f"Reference voice: {Path(self.reference_voice[0]).name}")
            else:
                print(f"Reference voices ({len(self.reference_voice)}):")
                for i, ref in enumerate(self.reference_voice, 1):
                    print(f"  {i}. {Path(ref).name}")
        else:
            print(f"Reference voice: None")
        print(f"Chunks: {len(chunks)}")
        print(f"Post-processing: speed={speed}x, normalize={normalize}, mp3={to_mp3}")
        print("="*70)
        print()

        # Generate audio for each chunk
        audio_files = []
        raw_dir = output_dir / "raw" if (speed != 1.0 or normalize or to_mp3) else output_dir
        raw_dir.mkdir(exist_ok=True)

        import time as time_module
        generation_start = time_module.time()

        for i, chunk_text in enumerate(chunks, 1):
            # Show progress bar every 10 chunks or on first/last
            if i == 1 or i == len(chunks) or i % 10 == 0:
                elapsed = time_module.time() - generation_start
                percentage = (i / len(chunks)) * 100

                # Calculate ETA
                if i > 1:
                    rate = i / elapsed
                    remaining = len(chunks) - i
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta_str = self._format_eta(eta_seconds)
                else:
                    eta_str = "calculating..."

                # Progress bar
                bar_width = 40
                filled = int(bar_width * i / len(chunks))
                bar = "█" * filled + "░" * (bar_width - filled)

                print(f"\n  Progress: [{bar}] {i}/{len(chunks)} ({percentage:.1f}%) | ETA: {eta_str}")

            # Generate raw audio
            raw_filename = f"{base_name}_chunk{i:03d}_raw.wav"
            raw_path = raw_dir / raw_filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            try:
                self.generate_audio_chunk(chunk_text, raw_path)

                # Post-process if requested
                if speed != 1.0 or normalize or to_mp3:
                    ext = "mp3" if to_mp3 else "wav"
                    processed_filename = f"{base_name}_chunk{i:03d}.{ext}"
                    processed_path = output_dir / processed_filename

                    final_path = self.post_process_audio(
                        raw_path,
                        processed_path,
                        speed=speed,
                        normalize=normalize,
                        convert_to_mp3=to_mp3
                    )
                    audio_files.append(final_path)
                else:
                    audio_files.append(raw_path)

            except Exception as e:
                print(f"✗ ERROR: {e}")
                raise

        # Generate playlist for individual chunks
        ext = "mp3" if to_mp3 else "wav"
        chunks_playlist_path = output_dir / f"{base_name}_chunks_{timestamp}.m3u"
        with open(chunks_playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for audio_file in audio_files:
                f.write(f"#EXTINF:-1,{audio_file.stem}\n")
                f.write(f"{audio_file.name}\n")

        print(f"\n✓ Chunks playlist created: {chunks_playlist_path.name}")

        # Combine chunks into chapter files
        chapter_files = []
        if chapters and len(chapters) > 1:
            print(f"\n📚 Combining {len(chunks)} chunks into {len(chapters)} chapters...")

            for chapter_num in range(1, max(chunk_to_chapter) + 1):
                # Find all audio files for this chapter
                chapter_audio_files = [
                    audio_files[i] for i in range(len(audio_files))
                    if chunk_to_chapter[i] == chapter_num
                ]

                if chapter_audio_files:
                    chapter_filename = f"{base_name}_chapter_{chapter_num:02d}.{ext}"
                    chapter_path = output_dir / chapter_filename

                    print(f"  Chapter {chapter_num:2d}: Combining {len(chapter_audio_files)} chunks...", end=" ", flush=True)

                    result = self.combine_audio_files(chapter_audio_files, chapter_path)
                    if result:
                        chapter_files.append(result)
                        print(f"✓ {chapter_path.name}")
                    else:
                        print("✗ Failed")

            # Generate master audiobook playlist
            if chapter_files:
                playlist_path = output_dir / f"{base_name}_audiobook_{timestamp}.m3u"
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for i, chapter_file in enumerate(chapter_files, 1):
                        f.write(f"#EXTINF:-1,Chapter {i}\n")
                        f.write(f"{chapter_file.name}\n")

                print(f"\n✓ Master audiobook playlist created: {playlist_path.name}")
                print(f"  ({len(chapter_files)} chapters)")
        else:
            # No chapters detected - create single combined file
            print(f"\n📚 Combining all {len(audio_files)} chunks into single file...")
            combined_path = output_dir / f"{base_name}_complete.{ext}"

            result = self.combine_audio_files(audio_files, combined_path)
            if result:
                chapter_files.append(result)
                print(f"✓ Complete audiobook: {combined_path.name}")

                # Create simple playlist
                playlist_path = output_dir / f"{base_name}_audiobook_{timestamp}.m3u"
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1,Complete Audiobook\n")
                    f.write(f"{combined_path.name}\n")
                print(f"✓ Audiobook playlist created: {playlist_path.name}")
            else:
                playlist_path = chunks_playlist_path

        print("\n" + "="*70)
        print("AUDIO GENERATION COMPLETE")
        print("="*70)
        print(f"Total chunks: {len(audio_files)}")
        if chapters and len(chapters) > 1:
            print(f"Chapters: {len(chapter_files)}")
        print(f"Format: {ext.upper()}")
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
            'format': ext
        }


def prepare_reference_voice(input_file: str, output_file: str = "voice_ref_clean.wav"):
    """
    Prepare a clean reference voice sample for XTTS-v2.
    Converts to mono, 24kHz, PCM WAV format.

    Args:
        input_file: Input audio file (any format)
        output_file: Output WAV file

    Returns:
        Path to prepared reference voice
    """
    print(f"Preparing reference voice from: {input_file}")

    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ERROR: ffmpeg not found")
        print("\nPlease install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        return None

    output_path = Path(output_file)

    # Convert to clean reference format
    cmd = [
        'ffmpeg', '-y',
        '-i', input_file,
        '-ac', '1',              # Mono
        '-ar', '24000',          # 24kHz sample rate
        '-c:a', 'pcm_s16le',     # 16-bit PCM
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ ERROR: {result.stderr}")
        return None

    print(f"✓ Reference voice ready: {output_path}")
    print(f"  Format: 24kHz, Mono, 16-bit PCM WAV")

    return str(output_path)


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Local TTS Audio Generation using XTTS-v2")
        print("="*70)
        print("\nUsage:")
        print("  python local_tts_xtts.py <input_file> [reference_voice...] [--lang LANGUAGE] [--generate-cover]")
        print("\nExamples:")
        print("  # Basic usage (default voice)")
        print("  python local_tts_xtts.py translated.md")
        print()
        print("  # With single voice cloning")
        print("  python local_tts_xtts.py translated.md voice_ref.wav --lang en")
        print()
        print("  # With MULTIPLE reference voices (recommended for better quality)")
        print("  python local_tts_xtts.py translated.md voice1.wav voice2.wav --lang en")
        print("  python local_tts_xtts.py book.md clean_audio.m4a voice_ref_clean.wav --lang en")
        print()
        print("  # Generate cover art automatically")
        print("  python local_tts_xtts.py translated.md voice_ref.wav --lang en --generate-cover")
        print()
        print("  # Prepare reference voice first")
        print("  python local_tts_xtts.py --prepare-voice input.m4a voice_ref.wav")
        print()
        print("  # Spanish audiobook with multiple voices")
        print("  python local_tts_xtts.py libro.md voz1.wav voz2.wav --lang es")
        print("\nSupported languages:")
        print(f"  {', '.join(XTTSAudioGenerator.LANGUAGES)}")
        print("\nReference Voice Tips:")
        print("  • 10-30 seconds of clear speech PER FILE")
        print("  • Use MULTIPLE clips (2-3) for better quality and less robotic sound")
        print("  • Vary content across clips (different sentences, pitches)")
        print("  • Keep same speaker, mic, and environment across all clips")
        print("  • No music, no reverb, consistent mic distance")
        print("  • Mono audio at 22-24kHz recommended")
        print("  • Clean, dry voice works best")
        print("\nPost-Processing (automatic via FFmpeg):")
        print("  • Speed: 1.20x (reduces 'robotic' feel)")
        print("  • Normalization: -16 LUFS (audiobook standard)")
        print("  • Format: MP3 @ 128kbps")
        print("\nCover Art Generation (optional):")
        print("  • Use --generate-cover to create AI cover art")
        print("  • Requires: pip install diffusers transformers accelerate")
        print("  • Uses Stable Diffusion v1.5 (local, free)")
        print("\nRequirements:")
        print("  pip install TTS==0.27.3")
        print("  brew install ffmpeg  # macOS")
        sys.exit(1)

    # Handle --prepare-voice mode
    if sys.argv[1] == "--prepare-voice":
        if len(sys.argv) < 3:
            print("Usage: python local_tts_xtts.py --prepare-voice <input_audio> [output.wav]")
            sys.exit(1)

        input_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else "voice_ref_clean.wav"

        prepare_reference_voice(input_file, output_file)
        sys.exit(0)

    # Parse arguments
    input_file = sys.argv[1]

    # Collect reference voices, language, and flags
    reference_voices = []
    language = "en"
    generate_cover = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--lang":
            if i + 1 < len(sys.argv):
                language = sys.argv[i + 1]
                i += 2
            else:
                print("❌ ERROR: --lang requires a language code")
                sys.exit(1)
        elif arg == "--generate-cover":
            generate_cover = True
            i += 1
        else:
            # Treat as reference voice file
            if Path(arg).exists():
                reference_voices.append(arg)
                i += 1
            else:
                print(f"⚠️  Warning: Skipping non-existent file: {arg}")
                i += 1

    # Use None if no voices provided, otherwise use the list
    reference_voice = reference_voices if reference_voices else None

    try:
        # Generate cover art if requested
        if generate_cover:
            print("\n" + "="*70)
            print("COVER ART GENERATION")
            print("="*70)
            try:
                from generate import CoverArtGenerator
                from book_prompts import get_book_prompt

                # Generate prompt from book title/filename
                input_path = Path(input_file)
                prompt = get_book_prompt(input_path.stem)
                print(f"Prompt: {prompt}")

                cover_generator = CoverArtGenerator()
                cover_output = input_path.parent / "audio_xtts" / f"{input_path.stem}_cover.png"

                cover_path = cover_generator.generate_cover(
                    prompt,
                    str(cover_output)
                )

                print(f"✓ Cover art saved: {cover_path}")
                print("="*70 + "\n")

            except ImportError:
                print("⚠️  Warning: Cover art generation requires additional libraries")
                print("  Install with: pip install diffusers transformers accelerate")
                print("  Skipping cover generation...\n")
            except Exception as e:
                print(f"⚠️  Warning: Cover generation failed: {e}")
                print("  Continuing with audio generation...\n")

        # Generate audio
        generator = XTTSAudioGenerator(
            reference_voice=reference_voice,
            language=language
        )

        result = generator.generate_audiobook(
            input_file,
            chunk_size=250,       # XTTS-v2 limit (400 tokens ~= 250 chars)
            speed=1.20,           # 20% faster (reduces robotic feel)
            normalize=True,       # Audiobook-standard loudness
            to_mp3=True          # Smaller files
        )

        print("\n✅ Success! Audio files ready to play.")
        print(f"\n💡 Tip: Play with: afplay {result['playlist']}")

        if generate_cover:
            cover_path = Path(result['output_directory']) / f"{Path(input_file).stem}_cover.png"
            if cover_path.exists():
                print(f"🎨 Cover art: {cover_path}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
