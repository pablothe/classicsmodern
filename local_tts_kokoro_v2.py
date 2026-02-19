#!/usr/bin/env python3
"""
Local TTS with Kokoro v2 - Uses manifest system for perfect chapter alignment.

This version uses the unified manifest system from book_processor.py to ensure
consistent chapter boundaries across the entire pipeline.

Key improvements:
- Uses BookManifest for chapter boundaries (no detection needed)
- Generates audio chapter-by-chapter with checkpoints
- Can resume from any chapter
- Backwards compatible with .md files (auto-generates manifest)

Usage:
    # From book file (auto-generates manifest)
    python3 local_tts_kokoro_v2.py books/mybook/book.md --voice bf_emma

    # From manifest (with chapter boundaries)
    python3 local_tts_kokoro_v2.py books/mybook/book_manifest.json --voice bf_emma

    # Resume interrupted generation
    python3 local_tts_kokoro_v2.py books/mybook/book_manifest.json --resume
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import argparse

# Import manifest utilities
from manifest_utils import ManifestManager
from book_processor import BookManifest

# Import existing Kokoro TTS functions
from local_tts_kokoro import KokoroAudioGenerator


class ManifestAudioGenerator(KokoroAudioGenerator):
    """Audio generator that works with book manifests."""

    def __init__(self,
                 manifest: BookManifest,
                 manifest_path: Path,
                 voice: str = 'af_sky',
                 language: str = 'en',
                 verbose: bool = True):
        """
        Initialize audio generator with manifest.

        Args:
            manifest: The book manifest
            manifest_path: Path to save manifest updates
            voice: Kokoro voice to use
            language: Language code
            verbose: Print progress messages
        """
        super().__init__(voice=voice, language=language)
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.verbose = verbose

    def generate_audiobook_from_manifest(self,
                                        output_dir: Optional[Path] = None,
                                        chunk_size: int = 800,
                                        speed: float = 1.0,
                                        normalize: bool = True,
                                        to_mp3: bool = True,
                                        resume: bool = True) -> dict:
        """
        Generate audiobook using manifest for chapter boundaries.

        Args:
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per TTS chunk
            speed: Playback speed
            normalize: Whether to normalize audio
            to_mp3: Convert to MP3
            resume: Resume from checkpoint if available

        Returns:
            Dictionary with generation results
        """
        print(f"\n🎵 AUDIO GENERATION USING MANIFEST")
        print("=" * 60)
        print(f"📖 Book: {self.manifest.metadata.get('title', 'Unknown')}")
        print(f"📚 Chapters: {len(self.manifest.chapters)}")
        print(f"🎤 Voice: {self.voice}")
        print(f"⚡ Speed: {speed}x")
        print(f"🔊 Normalize: {normalize}")
        print(f"📀 Format: {'MP3' if to_mp3 else 'WAV'}")
        print("=" * 60)
        print()

        # Set up output directory
        if output_dir is None:
            base_dir = Path(self.manifest.original_file).parent
            output_dir = base_dir / f"audio_kokoro_manifest"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectory for raw audio
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(exist_ok=True)

        # Check for existing progress
        if resume:
            incomplete = ManifestManager.get_incomplete_chapters(self.manifest, 'audio')
            if len(incomplete) < len(self.manifest.chapters):
                completed = len(self.manifest.chapters) - len(incomplete)
                print(f"📂 Found existing progress: {completed}/{len(self.manifest.chapters)} chapters completed")

                # Check if voice matches
                for ch in self.manifest.chapters:
                    checkpoint = ch.checkpoints.get('audio', {})
                    if checkpoint.get('complete') and checkpoint.get('voice') != self.voice:
                        print(f"⚠️  WARNING: Previous audio used voice {checkpoint.get('voice')}")
                        print(f"   Starting fresh with voice {self.voice}")
                        resume = False
                        break

        # Process each chapter
        chapter_files = []
        failed_chapters = []
        total_chunks = 0
        MAX_CHAPTER_RETRIES = 2

        for chapter_num in range(1, len(self.manifest.chapters) + 1):
            chapter = self.manifest.chapters[chapter_num - 1]

            # Check if already complete
            if resume:
                checkpoint = chapter.checkpoints.get('audio', {})
                if checkpoint.get('complete') and checkpoint.get('voice') == self.voice:
                    if checkpoint.get('chapter_file'):
                        chapter_file = Path(checkpoint['chapter_file'])
                        if chapter_file.exists():
                            chapter_files.append(chapter_file)
                            if self.verbose:
                                print(f"✓ Chapter {chapter_num} ({chapter.marker}): Using existing audio")
                            continue

            print(f"\n📖 Chapter {chapter_num}/{len(self.manifest.chapters)}: {chapter.marker}")
            print(f"   Words: {chapter.word_count}")

            # Generate audio for this chapter with retry
            chapter_audio_path = None
            for attempt in range(MAX_CHAPTER_RETRIES):
                chapter_audio_path = self._generate_chapter_audio(
                    chapter_num=chapter_num,
                    chapter=chapter,
                    output_dir=output_dir,
                    raw_dir=raw_dir,
                    chunk_size=chunk_size,
                    speed=speed,
                    normalize=normalize,
                    to_mp3=to_mp3
                )
                if chapter_audio_path:
                    break
                if attempt < MAX_CHAPTER_RETRIES - 1:
                    print(f"   ⚠ Retrying chapter {chapter_num} (attempt {attempt + 2}/{MAX_CHAPTER_RETRIES})")

            if chapter_audio_path:
                chapter_files.append(chapter_audio_path)

                # Update checkpoint
                ManifestManager.update_audio_checkpoint(
                    self.manifest,
                    self.manifest_path,
                    chapter_num,
                    complete=True,
                    voice=self.voice,
                    speed=speed,
                    chapter_file=str(chapter_audio_path)
                )
            else:
                failed_chapters.append((chapter_num, chapter.marker))
                print(f"   ✗ FAILED chapter {chapter_num} after {MAX_CHAPTER_RETRIES} attempts")

        # Report failed chapters
        if failed_chapters:
            print(f"\n⚠ WARNING: {len(failed_chapters)} chapter(s) failed to generate:")
            for ch_num, ch_marker in failed_chapters:
                print(f"   Chapter {ch_num}: {ch_marker}")
            print(f"   Run the same command to retry these chapters (progress is saved)")

        # Create master playlist
        ext = '.mp3' if to_mp3 else '.wav'
        playlist_path = output_dir / "audiobook.m3u"
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for i, chapter_file in enumerate(chapter_files, 1):
                f.write(f"#EXTINF:-1,Chapter {i}\n")
                f.write(f"{chapter_file.name}\n")

        total_chapters = len(self.manifest.chapters)
        status = "COMPLETE" if not failed_chapters else f"PARTIAL ({len(chapter_files)}/{total_chapters})"
        print(f"\n✅ AUDIO GENERATION {status}")
        print(f"📂 Output directory: {output_dir}")
        print(f"🎵 Chapters generated: {len(chapter_files)}/{total_chapters}")
        print(f"📜 Playlist: {playlist_path.name}")

        # Update manifest with audio info
        self.manifest.metadata['audio_generated'] = datetime.now().isoformat()
        self.manifest.metadata['audio_voice'] = self.voice
        self.manifest.metadata['audio_directory'] = str(output_dir)
        self.manifest.save(self.manifest_path)

        return {
            'output_directory': str(output_dir),
            'chapters': len(chapter_files),
            'playlist': str(playlist_path),
            'format': 'mp3' if to_mp3 else 'wav',
            'voice': self.voice
        }

    def _generate_chapter_audio(self,
                               chapter_num: int,
                               chapter,
                               output_dir: Path,
                               raw_dir: Path,
                               chunk_size: int,
                               speed: float,
                               normalize: bool,
                               to_mp3: bool) -> Optional[Path]:
        """Generate audio for a single chapter."""
        try:
            # Clean text for TTS (skip Gutenberg — manifest content is already clean)
            cleaned_text = self.clean_text_for_speech(chapter.content, skip_gutenberg=True)

            # Split into chunks
            chunks = self.chunk_text(cleaned_text, chunk_size)
            print(f"   Chunks: {len(chunks)} ({chunk_size} chars each)")

            # Generate audio for each chunk
            chunk_audio_files = []

            for i, chunk_text in enumerate(chunks, 1):
                if i % 10 == 0 or i == 1 or i == len(chunks):
                    percentage = 100 * i / len(chunks)
                    print(f"   Progress: {i}/{len(chunks)} ({percentage:.0f}%)")

                # Generate raw WAV
                raw_filename = f"chapter_{chapter_num:02d}_chunk_{i:03d}_raw.wav"
                raw_path = raw_dir / raw_filename

                self.generate_audio_chunk(chunk_text, raw_path)
                chunk_audio_files.append(raw_path)

                # Update checkpoint with progress
                if i % 10 == 0:  # Save progress every 10 chunks
                    ManifestManager.update_audio_checkpoint(
                        self.manifest,
                        self.manifest_path,
                        chapter_num,
                        complete=False,
                        voice=self.voice,
                        speed=speed,
                        chunks_complete=i,
                        total_chunks=len(chunks)
                    )

            # Post-process and combine chunks
            ext = '.mp3' if to_mp3 else '.wav'
            chapter_filename = f"chapter_{chapter_num:02d}{ext}"
            chapter_path = output_dir / chapter_filename

            # Process each chunk
            processed_chunks = []
            for chunk_file in chunk_audio_files:
                processed = self.post_process_audio(
                    chunk_file,
                    chunk_file.with_suffix(ext),
                    speed=speed,
                    normalize=normalize,
                    convert_to_mp3=to_mp3
                )
                processed_chunks.append(processed)

            # Combine all chunks into chapter file
            print(f"   Combining {len(processed_chunks)} chunks into chapter file...")
            result = self.combine_audio_files(processed_chunks, chapter_path)

            if result:
                print(f"   ✅ Chapter audio: {chapter_path.name}")
                return chapter_path
            else:
                print(f"   ❌ Failed to combine chunks")
                return None

        except Exception as e:
            print(f"   ❌ Error generating chapter {chapter_num}: {e}")
            return None


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Kokoro TTS v2 - Audio generation using manifest system"
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to book file (.md) or manifest (.json)'
    )

    parser.add_argument(
        '--voice',
        default='af_sky',
        help='Kokoro voice (default: af_sky). Options: af_*, am_*, bf_*, bm_*'
    )

    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Playback speed (default: 1.0)'
    )

    parser.add_argument(
        '--chunk-size',
        type=int,
        default=800,
        help='Characters per TTS chunk (default: 800)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory (default: auto-generated)'
    )

    parser.add_argument(
        '--no-normalize',
        action='store_true',
        help='Skip audio normalization'
    )

    parser.add_argument(
        '--no-mp3',
        action='store_true',
        help='Keep as WAV instead of converting to MP3'
    )

    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start fresh, ignore existing progress'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )

    args = parser.parse_args()

    try:
        print(f"\n🎵 KOKORO TTS v2")
        print("=" * 60)

        # Get or create manifest
        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            args.input_file,
            auto_fix=True,
            verbose=not args.quiet
        )

        # Create audio generator
        generator = ManifestAudioGenerator(
            manifest=manifest,
            manifest_path=manifest_path,
            voice=args.voice,
            verbose=not args.quiet
        )

        # Generate audiobook
        result = generator.generate_audiobook_from_manifest(
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            speed=args.speed,
            normalize=not args.no_normalize,
            to_mp3=not args.no_mp3,
            resume=not args.no_resume
        )

        # Show final progress
        if not args.quiet:
            ManifestManager.print_progress_report(manifest)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Audio generation interrupted by user")
        print("   Progress has been saved in the manifest")
        print("   Run the same command to resume")
        return 130

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())