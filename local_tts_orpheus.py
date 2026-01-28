#!/usr/bin/env python3
"""
Local TTS Audio Generation using Orpheus-TTS (Llama-based)

Generates high-quality audiobooks locally using Orpheus-TTS with natural intonation,
emotion control, and low-latency streaming. Superior quality to commercial models.

Requirements:
    pip install orpheus-speech  # uses vllm under the hood
    brew install ffmpeg  # macOS
"""

import os
import sys
import re
import subprocess
import wave
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    from orpheus_tts import OrpheusModel
except ImportError:
    print("❌ ERROR: orpheus-speech library not installed")
    print("\nPlease install Orpheus-TTS:")
    print("  pip install orpheus-speech")
    print("\nNote: Some bugs may require reverting to vllm 0.7.3:")
    print("  pip install vllm==0.7.3")
    sys.exit(1)


class OrpheusAudioGenerator:
    """Local TTS audio generation using Orpheus-TTS (Llama-based)"""

    # Orpheus-TTS models
    FINETUNE_MODEL = "canopylabs/orpheus-tts-0.1-finetune-prod"
    PRETRAIN_MODEL = "canopylabs/orpheus-tts-0.1"

    # Available voices (in order of conversational realism per docs)
    VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]

    # Emotion tags supported by Orpheus
    EMOTION_TAGS = ["<laugh>", "<chuckle>", "<sigh>", "<cough>", "<sniffle>",
                    "<groan>", "<yawn>", "<gasp>"]

    def __init__(self, voice: str = "tara", use_pretrain: bool = False, max_model_len: int = 2048):
        """
        Initialize Orpheus-TTS audio generator.

        Args:
            voice: Voice to use (tara, leah, jess, leo, dan, mia, zac, zoe)
            use_pretrain: Use pretrained model instead of finetuned (for custom voice cloning)
            max_model_len: Maximum model context length
        """
        self.voice = voice
        self.model_name = self.PRETRAIN_MODEL if use_pretrain else self.FINETUNE_MODEL

        if voice not in self.VOICES:
            print(f"⚠️  Warning: '{voice}' not in recommended voices. Using 'tara' instead.")
            print(f"   Recommended: {', '.join(self.VOICES)}")
            self.voice = "tara"

        print(f"Loading Orpheus-TTS model ({self.model_name})...")
        print("(This may take a moment on first run)")

        self.model = OrpheusModel(
            model_name=self.model_name,
            max_model_len=max_model_len
        )

        print("✓ Model loaded successfully")
        print(f"✓ Using voice: {self.voice}")

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

    def clean_text_for_speech(self, text: str, preserve_chapter_markers: bool = False, preserve_emotions: bool = True) -> str:
        """
        Clean markdown text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown
            preserve_chapter_markers: If True, keep Roman numeral chapter markers
            preserve_emotions: If True, keep emotion tags like <laugh>, <sigh>, etc.

        Returns:
            Cleaned text suitable for TTS
        """
        # Preserve standalone Roman numeral chapter markers FIRST (before other cleaning)
        if preserve_chapter_markers:
            text = re.sub(
                r'^(X{0,3})(IX|IV|V?I{0,3})\.$',
                lambda m: f"CHAPTER_MARKER_{m.group(0)}",
                text,
                flags=re.MULTILINE
            )

        # Remove markdown headers but keep text (unless it's a chapter marker)
        if preserve_chapter_markers:
            def replace_header(match):
                header_text = match.group(2)
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

        # Remove URLs (but preserve emotion tags)
        if preserve_emotions:
            # Only remove http URLs, not emotion tags
            text = re.sub(r'http[s]?://\S+', '', text)
        else:
            # Remove both URLs and emotion tags
            text = re.sub(r'http[s]?://\S+', '', text)
            for tag in self.EMOTION_TAGS:
                text = text.replace(tag, '')

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def chunk_text(self, text: str, max_chars: int = 500) -> List[str]:
        """
        Split text into chunks for better TTS quality.
        Orpheus can handle longer contexts than XTTS (~500 chars recommended).

        PRIORITY: Always split at sentence boundaries for natural audio flow.

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (500 recommended)

        Returns:
            List of text chunks
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If single sentence is too long, split it
            if len(sentence) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # Split at clause boundaries
                clauses = re.split(r'([,;:—\-]\s+)', sentence)
                temp_chunk = ""

                for clause in clauses:
                    if not clause.strip():
                        continue

                    if len(temp_chunk) + len(clause) > max_chars:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                        temp_chunk = clause
                    else:
                        temp_chunk += clause

                if temp_chunk:
                    current_chunk = temp_chunk.strip()

            # Normal case: sentence fits
            elif len(current_chunk) + len(sentence) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def format_prompt(self, text: str) -> str:
        """
        Format text as Orpheus prompt.
        Format: "{voice}: {text}"

        Args:
            text: Text to speak

        Returns:
            Formatted prompt
        """
        return f"{self.voice}: {text}"

    def generate_audio_chunk(self, text: str, output_path: Path) -> Path:
        """
        Generate audio for a single text chunk using Orpheus-TTS.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file

        Returns:
            Path to generated audio file
        """
        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Format prompt for Orpheus
        prompt = self.format_prompt(text)

        # Generate speech with streaming
        start_time = time.monotonic()
        syn_tokens = self.model.generate_speech(
            prompt=prompt,
            voice=self.voice,
        )

        # Write to WAV file
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)

            total_frames = 0
            for audio_chunk in syn_tokens:
                frame_count = len(audio_chunk) // (wf.getsampwidth() * wf.getnchannels())
                total_frames += frame_count
                wf.writeframes(audio_chunk)

            duration = total_frames / wf.getframerate()

        end_time = time.monotonic()
        generation_time = end_time - start_time

        print(f"✓ {duration:.1f}s audio in {generation_time:.1f}s (RTF: {generation_time/duration:.2f}x)")
        return output_path

    def post_process_audio(
        self,
        input_file: Path,
        output_file: Path,
        speed: float = 1.0,
        normalize: bool = True,
        convert_to_mp3: bool = False
    ) -> Path:
        """
        Post-process audio with FFmpeg for better quality.

        Args:
            input_file: Input WAV file
            output_file: Output file path
            speed: Speed multiplier (1.0 = normal, Orpheus already sounds natural)
            normalize: Apply loudness normalization
            convert_to_mp3: Convert final output to MP3

        Returns:
            Path to processed audio file
        """
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, skipping post-processing")
            return input_file

        print(f"  Post-processing (speed={speed}x, normalize={normalize})...", end=" ", flush=True)

        filters = []

        if speed != 1.0:
            if speed > 2.0:
                filters.append("atempo=2.0")
                remaining = speed / 2.0
                while remaining > 1.0:
                    next_tempo = min(remaining, 2.0)
                    filters.append(f"atempo={next_tempo}")
                    remaining /= next_tempo
            else:
                filters.append(f"atempo={speed}")

        if normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

        filter_string = ",".join(filters) if filters else None

        cmd = ['ffmpeg', '-y', '-i', str(input_file)]

        if filter_string:
            cmd.extend(['-filter:a', filter_string])

        if convert_to_mp3:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '128k'])

        cmd.append(str(output_file))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ FFmpeg error: {result.stderr}")
            return input_file

        print(f"✓ Processed: {output_file.name}")
        return output_file

    def detect_chapters(self, text: str, is_cleaned: bool = False) -> list:
        """
        Detect chapter boundaries in text.

        Args:
            text: Text to search for chapters
            is_cleaned: Whether text has been cleaned

        Returns:
            List of tuples: (chapter_number, start_position, title)
        """
        chapters = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            if is_cleaned and line_stripped.startswith('CHAPTER_MARKER_'):
                marker = line_stripped.replace('CHAPTER_MARKER_', '')
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, marker))
                continue

            roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', line_stripped)
            if roman_match:
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, line_stripped))
                continue

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

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: str = None,
        chunk_size: int = 500,
        speed: float = 1.0,
        normalize: bool = True,
        to_mp3: bool = True
    ) -> dict:
        """
        Generate complete audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per chunk (500 recommended for Orpheus)
            speed: Speed multiplier (1.0 recommended, Orpheus already natural)
            normalize: Apply loudness normalization
            to_mp3: Convert to MP3 (smaller files)

        Returns:
            Dictionary with generation results
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        print(f"Reading: {input_file}")
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        print("Detecting chapters...")
        chapters_raw = self.detect_chapters(raw_text, is_cleaned=False)

        preserve_markers = len(chapters_raw) > 0
        if preserve_markers:
            print(f"✓ Found {len(chapters_raw)} chapters - preserving markers during cleaning")
        else:
            print("ℹ  No chapters detected (will create single file)")

        print("Cleaning text for speech...")
        clean_text = self.clean_text_for_speech(
            raw_text,
            preserve_chapter_markers=preserve_markers,
            preserve_emotions=True
        )

        chapters = self.detect_chapters(clean_text, is_cleaned=True) if preserve_markers else []

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"Text ready: {char_count:,} characters, {word_count:,} words")

        print(f"Chunking text (max {chunk_size} chars per chunk)...")
        chunks = self.chunk_text(clean_text, chunk_size)

        # Remove CHAPTER_MARKER_ tags from chunks
        if preserve_markers:
            chunks = [re.sub(r'CHAPTER_MARKER_[^\s]*', '', chunk).strip() for chunk in chunks]

        print(f"Created {len(chunks)} audio chunks")

        # Map chunks to chapters
        chunk_to_chapter = []
        if chapters:
            current_char_pos = 0
            current_chapter = 1
            chapter_idx = 0

            for i, chunk in enumerate(chunks):
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

        if output_dir is None:
            output_dir = input_path.parent / "audio_orpheus"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("LOCAL TTS AUDIO GENERATION (Orpheus-TTS)")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Voice: {self.voice}")
        print(f"Model: {self.model_name}")
        print(f"Chunks: {len(chunks)}")
        print(f"Post-processing: speed={speed}x, normalize={normalize}, mp3={to_mp3}")
        print("="*70)
        print()

        # Generate audio for each chunk
        audio_files = []
        raw_dir = output_dir / "raw" if (speed != 1.0 or normalize or to_mp3) else output_dir
        raw_dir.mkdir(exist_ok=True)

        generation_start = time.time()

        for i, chunk_text in enumerate(chunks, 1):
            if i == 1 or i == len(chunks) or i % 10 == 0:
                elapsed = time.time() - generation_start
                percentage = (i / len(chunks)) * 100

                if i > 1:
                    rate = i / elapsed
                    remaining = len(chunks) - i
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta_str = self._format_eta(eta_seconds)
                else:
                    eta_str = "calculating..."

                bar_width = 40
                filled = int(bar_width * i / len(chunks))
                bar = "█" * filled + "░" * (bar_width - filled)

                print(f"\n  Progress: [{bar}] {i}/{len(chunks)} ({percentage:.1f}%) | ETA: {eta_str}")

            raw_filename = f"{base_name}_chunk{i:03d}_raw.wav"
            raw_path = raw_dir / raw_filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            try:
                self.generate_audio_chunk(chunk_text, raw_path)

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
            print(f"\n📚 Combining all {len(audio_files)} chunks into single file...")
            combined_path = output_dir / f"{base_name}_complete.{ext}"

            result = self.combine_audio_files(audio_files, combined_path)
            if result:
                chapter_files.append(result)
                print(f"✓ Complete audiobook: {combined_path.name}")

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


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Local TTS Audio Generation using Orpheus-TTS")
        print("="*70)
        print("\nUsage:")
        print("  python local_tts_orpheus.py <input_file> [--voice VOICE] [--pretrain]")
        print("\nExamples:")
        print("  # Basic usage (default voice: tara)")
        print("  python local_tts_orpheus.py translated.md")
        print()
        print("  # Use different voice")
        print("  python local_tts_orpheus.py translated.md --voice leah")
        print()
        print("  # Use pretrained model (for custom voice cloning)")
        print("  python local_tts_orpheus.py translated.md --pretrain")
        print()
        print("\nAvailable voices (in order of conversational realism):")
        print(f"  {', '.join(OrpheusAudioGenerator.VOICES)}")
        print("\nEmotion Tags (add to text for expressive speech):")
        print(f"  {', '.join(OrpheusAudioGenerator.EMOTION_TAGS)}")
        print("\nFeatures:")
        print("  • Human-like intonation and emotion")
        print("  • ~200ms streaming latency")
        print("  • Superior to commercial TTS models")
        print("  • Automatic chapter detection and combining")
        print("  • FFmpeg post-processing (normalization, MP3)")
        print("\nRequirements:")
        print("  pip install orpheus-speech")
        print("  pip install vllm==0.7.3  # if you encounter bugs")
        print("  brew install ffmpeg  # macOS")
        sys.exit(1)

    input_file = sys.argv[1]
    voice = "tara"
    use_pretrain = False

    # Parse arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--voice":
            if i + 1 < len(sys.argv):
                voice = sys.argv[i + 1]
                i += 2
            else:
                print("❌ ERROR: --voice requires a voice name")
                sys.exit(1)
        elif arg == "--pretrain":
            use_pretrain = True
            i += 1
        else:
            print(f"⚠️  Warning: Unknown argument: {arg}")
            i += 1

    try:
        generator = OrpheusAudioGenerator(
            voice=voice,
            use_pretrain=use_pretrain
        )

        result = generator.generate_audiobook(
            input_file,
            chunk_size=500,       # Orpheus can handle longer contexts
            speed=1.0,            # No speed adjustment needed (already natural)
            normalize=True,       # Audiobook-standard loudness
            to_mp3=True          # Smaller files
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
