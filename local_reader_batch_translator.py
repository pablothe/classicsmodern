#!/usr/bin/env python3
"""
Batch Translator for Local Reader

Translates multiple files (chunks) with progress tracking and error recovery.
Includes automatic deduplication to remove any overlapping text.
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Tuple, Set
from datetime import datetime
from local_reader_translation import OllamaTranslator
from local_reader_utils import FileManager
from local_reader_config import get_config
from local_reader_deduplicate import deduplicate_chunks


class BatchTranslator:
    """Handles batch translation of multiple files with progress tracking"""

    def __init__(self, source_lang: str, target_lang: str):
        """
        Initialize batch translator.

        Args:
            source_lang: Source language
            target_lang: Target language
        """
        self.source_lang = source_lang
        self.target_lang = target_lang

        # Get config and create translator
        config = get_config()
        self.translator = OllamaTranslator(
            model_name=config.models.default_translation_model,
            ollama_host=config.models.ollama_host,
            chunk_size_words=config.translation.chunk_size_words
        )

        self.start_time = None
        self.completed_files = 0
        self.total_files = 0
        self.failed_files = []
        self.previous_file_translation = None  # Track context across files

    def _load_progress(self, output_dir: Path) -> Set[str]:
        """Load list of already-translated files from checkpoint"""
        checkpoint_file = output_dir / ".translation_progress.json"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('completed_files', []))
        return set()

    def _save_progress(self, output_dir: Path, completed_files: Set[str]):
        """Save translation progress to checkpoint file"""
        checkpoint_file = output_dir / ".translation_progress.json"
        data = {
            'completed_files': list(completed_files),
            'last_updated': datetime.now().isoformat(),
            'source_lang': self.source_lang,
            'target_lang': self.target_lang
        }
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def translate_directory(
        self,
        input_dir: str,
        output_dir: str = None,
        file_pattern: str = "*.md",
        resume: bool = True,
        auto_deduplicate: bool = True
    ) -> dict:
        """
        Translate all files in a directory.

        Args:
            input_dir: Directory containing files to translate
            output_dir: Output directory (creates 'translated/' if None)
            file_pattern: File pattern to match (default: *.md)

        Returns:
            Dictionary with translation results
        """
        input_path = Path(input_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"Directory not found: {input_dir}")

        # Find all matching files
        files = sorted(list(input_path.glob(file_pattern)))
        files = [f for f in files if f.is_file() and f.name != "chunks_manifest.txt"]

        if not files:
            raise ValueError(f"No files matching '{file_pattern}' found in {input_dir}")

        self.total_files = len(files)
        self.start_time = time.time()

        # Create output directory
        if output_dir is None:
            output_dir = input_path / "translated"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Load progress if resuming
        completed_set = set()
        if resume:
            completed_set = self._load_progress(output_path)
            if completed_set:
                print(f"📌 Resuming previous translation: {len(completed_set)} files already completed")

        # Filter out already-completed files
        files_to_process = [f for f in files if f.name not in completed_set]
        skipped_count = len(files) - len(files_to_process)

        print("="*70)
        print(f"BATCH TRANSLATION")
        print("="*70)
        print(f"Input directory:  {input_path}")
        print(f"Output directory: {output_path}")
        print(f"Total files: {self.total_files}")
        if skipped_count > 0:
            print(f"Already completed: {skipped_count}")
            print(f"Remaining to translate: {len(files_to_process)}")
        else:
            print(f"Files to translate: {len(files_to_process)}")
        print(f"Source language: {self.source_lang}")
        print(f"Target language: {self.target_lang}")
        print(f"Model: {self.translator.model_name}")
        print("="*70)
        print()

        if not files_to_process:
            print("✓ All files already translated!")
            return {
                'total_files': self.total_files,
                'successful': len(completed_set),
                'failed': 0,
                'failed_files': [],
                'output_directory': str(output_path)
            }

        # Translate each file
        results = []
        total_processed = len(completed_set)

        for i, file_path in enumerate(files_to_process, 1):
            overall_index = total_processed + i

            print(f"\n[{overall_index}/{self.total_files}] Processing: {file_path.name}")
            print("-" * 70)

            try:
                result = self._translate_file(file_path, output_path)
                results.append(result)

                # Save progress after each successful translation
                completed_set.add(file_path.name)
                self._save_progress(output_path, completed_set)

                self._show_progress(overall_index, self.total_files, success=True)

            except KeyboardInterrupt:
                print("\n\n⚠️  Translation interrupted by user")
                print(f"Progress saved. {len(completed_set)} files completed.")
                print(f"Resume by running the same command again.")
                self._save_progress(output_path, completed_set)
                sys.exit(0)

            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                self.failed_files.append((file_path.name, str(e)))
                self._show_progress(overall_index, self.total_files, success=False)

        # Summary
        self._print_summary(results, output_path)

        # Run automatic deduplication if enabled
        if auto_deduplicate and results:
            print("\n" + "="*70)
            print("RUNNING AUTOMATIC DEDUPLICATION (FAILSAFE)")
            print("="*70)
            print("This removes any duplicate text that may have slipped through...")
            print()

            try:
                # Find all translated files
                translated_files = sorted(output_path.glob("*.md"))

                if len(translated_files) > 1:
                    # Create deduplicated subdirectory
                    dedup_dir = output_path / "deduplicated"

                    # Run deduplication
                    dedup_files = deduplicate_chunks(translated_files, dedup_dir)

                    print(f"\n✅ Deduplication complete!")
                    print(f"   Clean files: {dedup_dir}/")
                    print(f"   Use these for audio generation to avoid repetition.")
                else:
                    print("ℹ️  Only one file translated - deduplication not needed")

            except Exception as e:
                print(f"⚠️  Deduplication failed: {e}")
                print(f"   Original translations are still available in: {output_path}")

        return {
            'total_files': self.total_files,
            'successful': len(results),
            'failed': len(self.failed_files),
            'failed_files': self.failed_files,
            'output_directory': str(output_path)
        }

    def _translate_file(self, input_file: Path, output_dir: Path) -> dict:
        """Translate a single file with cross-file context awareness"""

        # Read file
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()

        word_count = len(text.split())
        print(f"File size: {len(text):,} characters, {word_count:,} words")

        # Translate with context from previous file
        file_start = time.time()
        result = self.translator.translate_document_with_context(
            text=text,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            previous_context=self.previous_file_translation
        )
        file_time = time.time() - file_start

        # Store translation for next file's context
        self.previous_file_translation = result.translated_text

        # Generate output filename
        output_filename = FileManager.generate_filename(
            book_title=input_file.stem,
            target_language=self.target_lang,
            model_name=result.model_used,
            include_timestamp=False
        )

        output_path = output_dir / output_filename

        # Save translated file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.translated_text)

        print(f"✓ Saved: {output_filename}")
        print(f"  Chunks: {result.chunks_processed}, Time: {file_time:.1f}s ({file_time/60:.1f}min)")

        return {
            'input_file': str(input_file),
            'output_file': str(output_path),
            'chunks': result.chunks_processed,
            'time_seconds': file_time,
            'word_count': word_count
        }

    def _show_progress(self, current: int, total: int, success: bool = True):
        """Show progress bar"""
        percentage = (current / total) * 100
        elapsed = time.time() - self.start_time

        # Calculate ETA
        if current > 0:
            rate = current / elapsed
            remaining = total - current
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "calculating..."

        # Progress bar
        bar_width = 40
        filled = int(bar_width * current / total)
        bar = "█" * filled + "░" * (bar_width - filled)

        status = "✓" if success else "✗"
        print(f"\n{status} Progress: [{bar}] {current}/{total} ({percentage:.1f}%)")
        print(f"  Elapsed: {self._format_time(elapsed)} | ETA: {eta_str}")

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

    def _print_summary(self, results: List[dict], output_dir: Path):
        """Print translation summary"""
        total_time = time.time() - self.start_time
        total_chunks = sum(r['chunks'] for r in results)
        total_words = sum(r['word_count'] for r in results)

        print("\n" + "="*70)
        print("TRANSLATION COMPLETE")
        print("="*70)
        print(f"Total files: {self.total_files}")
        print(f"Successful: {len(results)}")
        print(f"Failed: {len(self.failed_files)}")

        if self.failed_files:
            print("\nFailed files:")
            for filename, error in self.failed_files:
                print(f"  ✗ {filename}: {error}")

        print(f"\nStatistics:")
        print(f"  Total words translated: {total_words:,}")
        print(f"  Total chunks processed: {total_chunks}")
        print(f"  Total time: {self._format_time(total_time)}")

        if results:
            avg_time_per_file = total_time / len(results)
            avg_words_per_file = total_words / len(results)
            words_per_second = total_words / total_time if total_time > 0 else 0

            print(f"  Average time per file: {self._format_time(avg_time_per_file)}")
            print(f"  Average words per file: {avg_words_per_file:,.0f}")
            print(f"  Translation speed: {words_per_second:.1f} words/second")

        print(f"\nOutput directory: {output_dir}")
        print("="*70)


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 4:
        print("Usage: python local_reader_batch_translator.py <input_dir> <source_lang> <target_lang> [output_dir]")
        print("\nExample:")
        print("  python local_reader_batch_translator.py books/crime_punishment/chunks/ Russian 'Modern Spanish'")
        print("  python local_reader_batch_translator.py books/alice/chapters/ English Spanish output/")
        print("\nThis will:")
        print("  1. Find all .md files in the input directory")
        print("  2. Translate each file from source to target language")
        print("  3. Save translated files to 'translated/' subdirectory")
        print("  4. Show progress bar with ETA")
        print("  5. Generate summary report")
        sys.exit(1)

    input_dir = sys.argv[1]
    source_lang = sys.argv[2]
    target_lang = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else None

    # Create translator
    translator = BatchTranslator(source_lang, target_lang)

    # Run batch translation
    try:
        results = translator.translate_directory(input_dir, output_dir)

        # Exit code based on results
        if results['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
