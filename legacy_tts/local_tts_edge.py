#!/usr/bin/env python3
"""
Local TTS Audio Generation using Edge-TTS (Microsoft)

Generates high-quality audiobooks locally using Microsoft Edge's TTS engine.
No API costs, fully local processing with automatic chapter detection.

Features:
- FREE - No API costs, unlimited generation
- High Quality - Much better than XTTS-v2
- Fast - Near realtime generation
- 400+ Voices - Multiple languages and styles

Requirements:
    pip install edge-tts
    brew install ffmpeg  # macOS
"""

import os
import sys
import re
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    import edge_tts
except ImportError:
    print("❌ ERROR: edge-tts library not installed")
    print("\nPlease install Edge-TTS:")
    print("  pip install edge-tts")
    sys.exit(1)


class EdgeTTSAudioGenerator:
    """Local TTS audio generation using Edge-TTS (Microsoft)"""

    # Top recommended voices
    VOICE_JENNY = "en-US-JennyNeural"           # Friendly female (DEFAULT)
    VOICE_SONIA = "en-GB-SoniaNeural"           # British female (classics)
    VOICE_ARIA = "en-US-AriaNeural"             # Warm female
    VOICE_GUY = "en-US-GuyNeural"               # Professional male
    VOICE_ERIC = "en-US-EricNeural"             # Deep male
    VOICE_RYAN = "en-GB-RyanNeural"             # British male

    def __init__(self, voice: str = VOICE_JENNY):
        """
        Initialize Edge-TTS audio generator.

        Args:
            voice: Voice to use (default: en-US-JennyNeural)
        """
        self.voice = voice
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

    def clean_text_for_speech(self, text: str, preserve_chapter_markers: bool = False) -> str:
        """
        Clean markdown text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown
            preserve_chapter_markers: If True, keep Roman numeral chapter markers

        Returns:
            Cleaned text suitable for TTS
        """
        # Preserve standalone Roman numeral chapter markers FIRST
        if preserve_chapter_markers:
            text = re.sub(
                r'^(X{0,3})(IX|IV|V?I{0,3})\.$',
                lambda m: f"CHAPTER_MARKER_{m.group(0)}",
                text,
                flags=re.MULTILINE
            )

        # Remove markdown headers but keep text
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

        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def chunk_text(self, text: str, max_chars: int = 3000) -> List[str]:
        """
        Split text into chunks for TTS, ensuring complete sentences.
        Edge-TTS can handle larger chunks than XTTS (~3000 chars).

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk

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

    async def generate_audio_chunk(self, text: str, output_path: Path) -> Path:
        """
        Generate audio for a single text chunk using Edge-TTS.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file

        Returns:
            Path to generated audio file
        """
        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(output_path))

        print(f"✓ Saved: {output_path.name}")
        return output_path

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

            header_match = re.match(r'^#+\s+(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+)', line_stripped)
            if header_match:
                char_pos = len('\n'.join(lines[:i]))
                chapter_num = len(chapters) + 1
                chapters.append((chapter_num, char_pos, line_stripped))
                continue

            # Detect numbered list chapters (e.g., "1. The Horror in Clay.")
            # But exclude TOC markdown links (e.g., "1. [I](#chapter-1)")
            numbered_match = re.match(r'^(\d+)\.\s+(.+)$', line_stripped)
            if numbered_match and not re.search(r'\[.*?\]\(#', numbered_match.group(2)):
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
        chunk_size: int = 3000
    ) -> dict:
        """
        Generate complete audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per chunk (3000 recommended for Edge-TTS)

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

        has_chapters = len(chapters_raw) > 0
        if has_chapters:
            print(f"✓ Found {len(chapters_raw)} chapters")
        else:
            print("ℹ  No chapters detected (will create single file)")

        print("Cleaning text for speech...")
        clean_text = self.clean_text_for_speech(raw_text, preserve_chapter_markers=False)

        # Detect chapters from fully cleaned text (no markers)
        chapters = self.detect_chapters(clean_text, is_cleaned=False) if has_chapters else []

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"Text ready: {char_count:,} characters, {word_count:,} words")

        print(f"Chunking text (max {chunk_size} chars per chunk)...")
        chunks = self.chunk_text(clean_text, chunk_size)

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
            output_dir = input_path.parent / "audio_edge"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("LOCAL TTS AUDIO GENERATION (Edge-TTS)")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Voice: {self.voice}")
        print(f"Chunks: {len(chunks)}")
        print("="*70)
        print()

        # Generate audio for each chunk
        audio_files = []

        import time as time_module
        generation_start = time_module.time()

        # Run async generation
        asyncio.run(self._generate_all_chunks(chunks, base_name, output_dir, audio_files, generation_start))

        # Generate playlist for individual chunks
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
                    chapter_filename = f"{base_name}_chapter_{chapter_num:02d}.mp3"
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
            combined_path = output_dir / f"{base_name}_complete.mp3"

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
        print(f"Format: MP3")
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
            'format': 'mp3'
        }

    async def _generate_all_chunks(self, chunks, base_name, output_dir, audio_files, generation_start):
        """Generate all audio chunks asynchronously"""
        import time as time_module

        for i, chunk_text in enumerate(chunks, 1):
            if i == 1 or i == len(chunks) or i % 10 == 0:
                elapsed = time_module.time() - generation_start
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

            filename = f"{base_name}_chunk{i:03d}.mp3"
            output_path = output_dir / filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            try:
                await self.generate_audio_chunk(chunk_text, output_path)
                audio_files.append(output_path)
            except Exception as e:
                print(f"✗ ERROR: {e}")
                raise


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Local TTS Audio Generation using Edge-TTS (Microsoft)")
        print("="*70)
        print("\nUsage:")
        print("  python local_tts_edge.py <input_file> [--voice VOICE]")
        print("\nExamples:")
        print("  # Basic usage (default voice: Jenny - friendly)")
        print("  python local_tts_edge.py translated.md")
        print()
        print("  # Use British voice (great for classics)")
        print("  python local_tts_edge.py translated.md --voice en-GB-SoniaNeural")
        print()
        print("\nTop Recommended Voices:")
        print("  en-US-JennyNeural  - Friendly female (DEFAULT)")
        print("  en-GB-SoniaNeural  - British female (classics)")
        print("  en-US-AriaNeural   - Warm female")
        print("  en-US-GuyNeural    - Professional male")
        print("  en-US-EricNeural   - Deep male")
        print("  en-GB-RyanNeural   - British male")
        print("\nFeatures:")
        print("  • FREE - No API costs")
        print("  • High Quality - Much better than XTTS-v2")
        print("  • Fast - Near realtime generation")
        print("  • 400+ Voices available")
        print("  • Automatic chapter detection")
        print("\nRequirements:")
        print("  pip install edge-tts")
        print("  brew install ffmpeg  # macOS")
        sys.exit(1)

    input_file = sys.argv[1]
    voice = EdgeTTSAudioGenerator.VOICE_JENNY  # Default to Jenny

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
        else:
            print(f"⚠️  Warning: Unknown argument: {arg}")
            i += 1

    try:
        generator = EdgeTTSAudioGenerator(voice=voice)

        result = generator.generate_audiobook(
            input_file,
            chunk_size=3000  # Edge-TTS can handle larger chunks
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
