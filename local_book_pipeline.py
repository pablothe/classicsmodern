#!/usr/bin/env python3
"""
Local Book Processing Pipeline

Complete pipeline for translating books and generating audiobooks locally.
Handles: auto-chunking, translation, deduplication, and TTS audio generation.

Features:
- Resume capability (survive interruptions)
- Detailed progress bars at each stage
- Fully local processing (Ollama + XTTS-v2)
- Automatic deduplication
- State persistence
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

# Import existing components
from local_reader_smart_splitter import analyze_and_split
from local_reader_batch_translator import BatchTranslator
from local_reader_deduplicate import deduplicate_chunks
from local_tts_xtts import XTTSAudioGenerator


@dataclass
class PipelineState:
    """Track pipeline progress for resume capability"""
    book_path: str
    source_lang: str
    target_lang: str
    voice_ref: str

    # Stage completion flags
    chunking_complete: bool = False
    translation_complete: bool = False
    deduplication_complete: bool = False
    audio_complete: bool = False

    # Paths to intermediate outputs
    chunks_dir: Optional[str] = None
    translated_dir: Optional[str] = None
    deduped_dir: Optional[str] = None
    audio_dir: Optional[str] = None

    # Statistics
    total_chunks: int = 0
    translated_chunks: int = 0
    audio_files_generated: int = 0

    # Timestamps
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def save(self, state_file: Path):
        """Save state to JSON file"""
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, state_file: Path) -> 'PipelineState':
        """Load state from JSON file"""
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)


class BookProcessingPipeline:
    """Complete book processing pipeline with resume capability"""

    def __init__(
        self,
        book_path: str,
        source_lang: str,
        target_lang: str,
        voice_ref: str = "voice_ref_clean.wav",
        auto_chunk_threshold: int = 50000,  # 50KB
        words_per_chunk: int = 10000
    ):
        """
        Initialize pipeline.

        Args:
            book_path: Path to book markdown file
            source_lang: Source language (e.g., "Russian", "Chinese", "English")
            target_lang: Target language (e.g., "Modern English", "Spanish")
            voice_ref: Path to reference voice WAV file
            auto_chunk_threshold: Auto-chunk if file larger than this (chars)
            words_per_chunk: Target words per chunk
        """
        self.book_path = Path(book_path)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.voice_ref = voice_ref
        self.auto_chunk_threshold = auto_chunk_threshold
        self.words_per_chunk = words_per_chunk

        if not self.book_path.exists():
            raise FileNotFoundError(f"Book not found: {book_path}")

        # Create state file path
        self.state_file = self.book_path.parent / f".pipeline_state_{self.book_path.stem}.json"

        # Load or create state
        if self.state_file.exists():
            self.state = PipelineState.load(self.state_file)
            print(f"📌 Resuming previous pipeline run")
            print(f"   Started: {self.state.started_at}")
            self._show_state()
        else:
            self.state = PipelineState(
                book_path=str(book_path),
                source_lang=source_lang,
                target_lang=target_lang,
                voice_ref=voice_ref,
                started_at=datetime.now().isoformat()
            )
            self.state.save(self.state_file)

    def _show_state(self):
        """Display current pipeline state"""
        print("\n" + "="*70)
        print("PIPELINE STATUS")
        print("="*70)
        print(f"✓ Chunking:       {'DONE' if self.state.chunking_complete else 'PENDING'}")
        print(f"✓ Translation:    {'DONE' if self.state.translation_complete else 'PENDING'} ({self.state.translated_chunks}/{self.state.total_chunks} chunks)")
        print(f"✓ Deduplication:  {'DONE' if self.state.deduplication_complete else 'PENDING'}")
        print(f"✓ Audio:          {'DONE' if self.state.audio_complete else 'PENDING'} ({self.state.audio_files_generated} files)")
        print("="*70)
        print()

    def _save_state(self):
        """Save current state"""
        self.state.save(self.state_file)

    def _show_progress_bar(self, current: int, total: int, stage: str, elapsed: float = 0):
        """Show a progress bar"""
        percentage = (current / total) * 100 if total > 0 else 0

        # Calculate ETA
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = total - current
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "calculating..."

        # Progress bar
        bar_width = 40
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        print(f"\n{stage}: [{bar}] {current}/{total} ({percentage:.1f}%)")
        if elapsed > 0:
            print(f"Elapsed: {self._format_time(elapsed)} | ETA: {eta_str}")

    def _format_time(self, seconds: float) -> str:
        """Format seconds to human-readable time"""
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

    def run(self) -> dict:
        """
        Run complete pipeline with resume capability.

        Returns:
            Dictionary with results
        """
        start_time = time.time()

        print("\n" + "="*70)
        print("LOCAL BOOK PROCESSING PIPELINE")
        print("="*70)
        print(f"Book: {self.book_path.name}")
        print(f"Source language: {self.source_lang}")
        print(f"Target language: {self.target_lang}")
        print(f"Voice reference: {self.voice_ref}")
        print("="*70)
        print()

        try:
            # STAGE 1: Chunking
            if not self.state.chunking_complete:
                self._stage_chunking()
                self._save_state()
            else:
                print("✓ Chunking already complete, skipping...\n")

            # STAGE 2: Translation
            if not self.state.translation_complete:
                self._stage_translation()
                self._save_state()
            else:
                print("✓ Translation already complete, skipping...\n")

            # STAGE 3: Deduplication
            if not self.state.deduplication_complete:
                self._stage_deduplication()
                self._save_state()
            else:
                print("✓ Deduplication already complete, skipping...\n")

            # STAGE 4: Audio Generation
            if not self.state.audio_complete:
                self._stage_audio()
                self._save_state()
            else:
                print("✓ Audio generation already complete, skipping...\n")

            # Mark complete
            self.state.completed_at = datetime.now().isoformat()
            self._save_state()

            total_time = time.time() - start_time

            # Final summary
            print("\n" + "="*70)
            print("🎉 PIPELINE COMPLETE!")
            print("="*70)
            print(f"Total time: {self._format_time(total_time)}")
            print(f"Chunks: {self.state.total_chunks}")
            print(f"Audio files: {self.state.audio_files_generated}")
            print(f"\nOutputs:")
            print(f"  Translated: {self.state.deduped_dir}")
            print(f"  Audio: {self.state.audio_dir}")
            print("="*70)

            # Clean up state file on success
            if self.state_file.exists():
                self.state_file.unlink()

            return {
                'success': True,
                'total_time': total_time,
                'chunks': self.state.total_chunks,
                'audio_files': self.state.audio_files_generated,
                'audio_dir': self.state.audio_dir
            }

        except KeyboardInterrupt:
            print("\n\n⚠️  Pipeline interrupted by user")
            print(f"\nProgress saved to: {self.state_file}")
            print(f"Resume by running the same command again.")
            self._save_state()
            sys.exit(0)

        except Exception as e:
            print(f"\n❌ Pipeline error: {e}")
            print(f"\nState saved to: {self.state_file}")
            print(f"Fix the issue and resume by running the same command.")
            self._save_state()
            raise

    def _stage_chunking(self):
        """Stage 1: Split book into chunks if needed"""
        print("\n" + "="*70)
        print("STAGE 1: CHUNKING")
        print("="*70)

        # Check if chunking needed
        with open(self.book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        file_size = len(content)

        if file_size < self.auto_chunk_threshold:
            print(f"Book size: {file_size:,} chars (under {self.auto_chunk_threshold:,} threshold)")
            print("No chunking needed - will process as single file")

            # Create single-file "chunks" directory
            chunks_dir = self.book_path.parent / "chunks"
            chunks_dir.mkdir(exist_ok=True)

            # Copy book as single chunk
            single_chunk = chunks_dir / "chunk_001.md"
            with open(single_chunk, 'w', encoding='utf-8') as f:
                f.write(content)

            self.state.chunks_dir = str(chunks_dir)
            self.state.total_chunks = 1
        else:
            print(f"Book size: {file_size:,} chars (over {self.auto_chunk_threshold:,} threshold)")
            print(f"Splitting into chunks (~{self.words_per_chunk} words each)...\n")

            # Run smart splitter
            chunks_dir = self.book_path.parent / "chunks"
            chunks = analyze_and_split(
                str(self.book_path),
                output_dir=str(chunks_dir),
                words_per_chunk=self.words_per_chunk
            )

            self.state.chunks_dir = str(chunks_dir)
            self.state.total_chunks = len(chunks)

        self.state.chunking_complete = True
        print(f"\n✅ Chunking complete: {self.state.total_chunks} chunks")

    def _stage_translation(self):
        """Stage 2: Translate chunks"""
        print("\n" + "="*70)
        print("STAGE 2: TRANSLATION")
        print("="*70)
        print(f"Translating {self.state.total_chunks} chunks...")
        print(f"This may take 4-8 hours depending on book size.")
        print("="*70)
        print()

        chunks_dir = Path(self.state.chunks_dir)

        # Create translator
        translator = BatchTranslator(self.source_lang, self.target_lang)

        # Run batch translation (has built-in resume)
        results = translator.translate_directory(
            str(chunks_dir),
            output_dir=None,  # Creates translated/ subdirectory
            file_pattern="*.md",
            resume=True,
            auto_deduplicate=False  # We'll do this separately
        )

        self.state.translated_dir = results['output_directory']
        self.state.translated_chunks = results['successful']
        self.state.translation_complete = True

        print(f"\n✅ Translation complete: {results['successful']}/{self.state.total_chunks} chunks")

    def _stage_deduplication(self):
        """Stage 3: Remove duplicates"""
        print("\n" + "="*70)
        print("STAGE 3: DEDUPLICATION")
        print("="*70)
        print("Removing duplicate text at chunk boundaries...")
        print("="*70)
        print()

        if self.state.total_chunks == 1:
            print("Only one chunk - deduplication not needed")

            # Copy single file to deduped directory
            translated_dir = Path(self.state.translated_dir)
            deduped_dir = translated_dir / "deduplicated"
            deduped_dir.mkdir(exist_ok=True)

            # Find the translated file
            translated_files = list(translated_dir.glob("*.md"))
            if translated_files:
                import shutil
                shutil.copy(translated_files[0], deduped_dir / f"{translated_files[0].stem}_DEDUPED.md")

            self.state.deduped_dir = str(deduped_dir)
        else:
            translated_dir = Path(self.state.translated_dir)
            deduped_dir = translated_dir / "deduplicated"

            # Find translated chunks
            chunk_files = sorted(translated_dir.glob("chunk_*.md"))
            chunk_files = [f for f in chunk_files if '_DEDUPED' not in f.name]

            if not chunk_files:
                raise ValueError(f"No translated chunks found in {translated_dir}")

            # Run deduplication
            deduped_files = deduplicate_chunks(chunk_files, deduped_dir)

            self.state.deduped_dir = str(deduped_dir)

        self.state.deduplication_complete = True
        print(f"\n✅ Deduplication complete")

    def _stage_audio(self):
        """Stage 4: Generate audio files"""
        print("\n" + "="*70)
        print("STAGE 4: AUDIO GENERATION")
        print("="*70)
        print("Generating audiobook with XTTS-v2...")
        print("This may take several hours for long books.")
        print("="*70)
        print()

        # Verify voice reference
        if not Path(self.voice_ref).exists():
            raise FileNotFoundError(f"Voice reference not found: {self.voice_ref}")

        deduped_dir = Path(self.state.deduped_dir)
        audio_dir = deduped_dir / "audio_xtts"
        audio_dir.mkdir(exist_ok=True)

        # Find deduplicated chunks
        chunk_files = sorted(deduped_dir.glob("*_DEDUPED.md"))

        if not chunk_files:
            raise ValueError(f"No deduplicated chunks found in {deduped_dir}")

        # Determine language code for XTTS
        lang_map = {
            'english': 'en',
            'modern english': 'en',
            'spanish': 'es',
            'modern spanish': 'es',
            'french': 'fr',
            'german': 'de',
            'italian': 'it',
            'portuguese': 'pt',
            'russian': 'ru',
            'chinese': 'zh-cn',
            'japanese': 'ja'
        }

        target_lang_lower = self.target_lang.lower()
        language_code = lang_map.get(target_lang_lower, 'en')

        print(f"Language code: {language_code}")
        print(f"Processing {len(chunk_files)} chunks...\n")

        # Create XTTS generator
        generator = XTTSAudioGenerator(
            reference_voice=self.voice_ref,
            language=language_code
        )

        # Process each chunk
        all_audio_files = []
        stage_start = time.time()

        for i, chunk_file in enumerate(chunk_files, 1):
            print(f"\n{'='*70}")
            print(f"CHUNK {i}/{len(chunk_files)}: {chunk_file.name}")
            print(f"{'='*70}")

            chunk_start = time.time()

            try:
                # Generate audio for this chunk
                # XTTS has 400 token limit (~250 chars max)
                result = generator.generate_audiobook(
                    str(chunk_file),
                    output_dir=str(audio_dir),
                    chunk_size=200,  # Conservative limit for XTTS
                    speed=1.15,
                    normalize=True,
                    to_mp3=True
                )

                all_audio_files.extend(result['audio_files'])
                self.state.audio_files_generated = len(all_audio_files)

                chunk_time = time.time() - chunk_start
                elapsed = time.time() - stage_start

                print(f"\n✓ Chunk {i} complete in {self._format_time(chunk_time)}")

                # Show overall progress
                self._show_progress_bar(i, len(chunk_files), "Audio Progress", elapsed)

                # Save progress after each chunk
                self._save_state()

            except Exception as e:
                print(f"\n❌ Error processing chunk {i}: {e}")
                raise

        # Create master playlist
        print("\n\nCreating master playlist...")
        master_playlist = audio_dir / f"{self.book_path.stem}_complete_audiobook.m3u"
        with open(master_playlist, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for audio_file in sorted(all_audio_files):
                audio_path = Path(audio_file)
                f.write(f"#EXTINF:-1,{audio_path.stem}\n")
                f.write(f"{audio_path.name}\n")

        print(f"✓ Master playlist: {master_playlist.name}")

        self.state.audio_dir = str(audio_dir)
        self.state.audio_complete = True

        print(f"\n✅ Audio generation complete: {len(all_audio_files)} files")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Complete local book processing pipeline: translate and generate audiobook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process Russian book to Modern English
  python local_book_pipeline.py books/crime_punishment/book.md \\
      --source Russian --target "Modern English"

  # Process German book to Spanish
  python local_book_pipeline.py books/faust/faust.md \\
      --source German --target Spanish

  # Custom voice and chunking
  python local_book_pipeline.py books/book.md \\
      --source Chinese --target English \\
      --voice my_voice.wav \\
      --words-per-chunk 5000

The pipeline will:
  1. Auto-chunk the book if needed
  2. Translate using Ollama (gemma3-translator:4b)
  3. Remove duplicate text at boundaries
  4. Generate audiobook with XTTS-v2
  5. Save progress at each stage (resumable)

Estimated time:
  - Translation: 4-8 hours (depends on book size)
  - Audio generation: 6-12 hours (depends on length)
  - Total: 10-20 hours for a full novel

The process is fully resumable - if interrupted, run the same
command again and it will continue from where it left off.
        """
    )

    parser.add_argument(
        'book',
        help='Path to book markdown file'
    )

    parser.add_argument(
        '--source', '-s',
        required=True,
        help='Source language (e.g., Russian, Chinese, German, Spanish)'
    )

    parser.add_argument(
        '--target', '-t',
        required=True,
        help='Target language (e.g., "Modern English", Spanish)'
    )

    parser.add_argument(
        '--voice', '-v',
        default='voice_ref_clean.wav',
        help='Path to reference voice WAV file (default: voice_ref_clean.wav)'
    )

    parser.add_argument(
        '--words-per-chunk',
        type=int,
        default=10000,
        help='Target words per chunk (default: 10000)'
    )

    parser.add_argument(
        '--no-auto-chunk',
        action='store_true',
        help='Disable auto-chunking (always chunk regardless of size)'
    )

    args = parser.parse_args()

    # Create and run pipeline
    try:
        pipeline = BookProcessingPipeline(
            book_path=args.book,
            source_lang=args.source,
            target_lang=args.target,
            voice_ref=args.voice,
            auto_chunk_threshold=0 if args.no_auto_chunk else 50000,
            words_per_chunk=args.words_per_chunk
        )

        results = pipeline.run()

        print("\n🎧 Your audiobook is ready!")
        print(f"\nTo play: cd {results['audio_dir']} && afplay *.m3u")

        sys.exit(0)

    except KeyboardInterrupt:
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
