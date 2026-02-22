#!/usr/bin/env python3
"""
Structured Book Translator v2 - Uses manifest system for perfect chapter alignment.

This version uses the unified manifest system from book_processor.py to ensure
consistent chapter detection across the entire pipeline.

Key improvements:
- Uses BookManifest for single source of truth
- Checkpoints saved in manifest (not separate file)
- Can resume from exact chapter
- Backwards compatible with .md files (auto-generates manifest)

Usage:
    # From book file (auto-generates manifest)
    python3 structured_translator_v2.py books/mybook/book.md --target-lang Spanish

    # From manifest (with checkpoints)
    python3 structured_translator_v2.py books/mybook/book_manifest.json --target-lang Spanish
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

# Import manifest utilities
from manifest_utils import ManifestManager
from book_processor import BookManifest

# Import existing translator classes
from local_reader_translation import OllamaTranslator
from local_reader_config import get_config


class ManifestTranslator:
    """Translator that works with book manifests."""

    def __init__(self,
                 manifest: BookManifest,
                 manifest_path: Path,
                 target_lang: str,
                 source_lang: Optional[str] = None,
                 model_name: str = "gemma3-translator:4b",
                 translator_type: str = "ollama",
                 translate_metadata: bool = True,
                 verbose: bool = True):
        """
        Initialize translator with manifest.

        Args:
            manifest: The book manifest to translate
            manifest_path: Path to save manifest updates
            target_lang: Target language for translation
            source_lang: Source language (optional, auto-detect if None)
            model_name: Model to use for translation
            translator_type: 'ollama'
            translate_metadata: Whether to translate title/metadata
            verbose: Print progress messages
        """
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.model_name = model_name
        self.translator_type = translator_type
        self.translate_metadata = translate_metadata
        self.verbose = verbose

        # Create translator instance
        self.translator = self._create_translator()

    def _create_translator(self):
        """Create Ollama translator."""
        ollama_config = get_config()
        return OllamaTranslator(
            model_name=self.model_name,
            ollama_host=ollama_config.models.ollama_host
        )

    def translate(self) -> Path:
        """
        Translate all chapters in the manifest.

        Returns:
            Path to the output translated file
        """
        print(f"\n🌐 TRANSLATION USING MANIFEST")
        print("=" * 60)
        print(f"📖 Book: {self.manifest.metadata.get('title', 'Unknown')}")
        print(f"📚 Chapters: {len(self.manifest.chapters)}")
        print(f"🌍 Target language: {self.target_lang}")
        if self.source_lang:
            print(f"🌍 Source language: {self.source_lang}")
        else:
            print(f"🌍 Source language: Auto-detect")
        print(f"🤖 Model: {self.model_name}")
        print("=" * 60)
        print()

        # Check for existing progress
        incomplete = ManifestManager.get_incomplete_chapters(self.manifest, 'translation')

        if len(incomplete) < len(self.manifest.chapters):
            completed = len(self.manifest.chapters) - len(incomplete)
            print(f"📂 Found existing progress: {completed}/{len(self.manifest.chapters)} chapters completed")

            # Check if target language matches
            for ch in self.manifest.chapters:
                checkpoint = ch.checkpoints.get('translation', {})
                if checkpoint.get('complete') and checkpoint.get('target_lang') != self.target_lang:
                    print(f"⚠️  WARNING: Previous translation was to {checkpoint.get('target_lang')}")
                    print(f"   Starting fresh translation to {self.target_lang}")
                    incomplete = list(range(1, len(self.manifest.chapters) + 1))
                    break

        # Translate metadata if requested
        translated_metadata = self.manifest.metadata.copy()
        if self.translate_metadata and 'title' in translated_metadata:
            print("📝 Translating metadata...")
            original_title = translated_metadata['title']
            translated_title = self._translate_text(original_title)
            translated_metadata['translated_title'] = translated_title
            print(f"   Title: {original_title} → {translated_title}")

        # Translate each incomplete chapter
        translated_contents = []

        for chapter_num in range(1, len(self.manifest.chapters) + 1):
            chapter = self.manifest.chapters[chapter_num - 1]

            # Check if already complete for this target language
            checkpoint = chapter.checkpoints.get('translation', {})
            if checkpoint.get('complete') and checkpoint.get('target_lang') == self.target_lang:
                # Load existing translation
                if 'translated_content' in checkpoint:
                    translated_contents.append(checkpoint['translated_content'])
                    if self.verbose:
                        print(f"✓ Chapter {chapter_num} ({chapter.marker}): Using cached translation")
                continue

            # Translate this chapter
            print(f"\n📖 Chapter {chapter_num}/{len(self.manifest.chapters)}: {chapter.marker}")
            print(f"   Words: {chapter.word_count}")

            try:
                # Translate the content
                start_time = datetime.now()
                translated_text = self._translate_text(chapter.content)
                elapsed = (datetime.now() - start_time).total_seconds()

                translated_words = len(translated_text.split())
                print(f"   ✅ Translated in {elapsed:.1f}s ({translated_words} words)")

                # Store in list for output
                translated_contents.append(translated_text)

                # Update checkpoint in manifest
                ManifestManager.update_translation_checkpoint(
                    self.manifest,
                    self.manifest_path,
                    chapter_num,
                    complete=True,
                    target_lang=self.target_lang,
                    partial_content=translated_text  # Store in manifest for resumability
                )

                # Also save translated content in checkpoint for caching
                self.manifest.chapters[chapter_num - 1].checkpoints['translation']['translated_content'] = translated_text
                self.manifest.save(self.manifest_path)

            except KeyboardInterrupt:
                print(f"\n⚠️  Translation interrupted at chapter {chapter_num}")
                print(f"   Progress saved. Resume with same command.")
                raise

            except Exception as e:
                print(f"\n❌ Error translating chapter {chapter_num}: {e}")
                print(f"   Progress saved. Fix issue and resume.")
                raise

        # Generate output file
        output_path = self._save_translation(translated_metadata, translated_contents)

        print(f"\n✅ TRANSLATION COMPLETE")
        print(f"📄 Output: {output_path}")
        print(f"📊 Total chapters: {len(self.manifest.chapters)}")

        # Update manifest with output file reference
        self.manifest.metadata['translated_file'] = str(output_path)
        self.manifest.metadata['translation_target'] = self.target_lang
        self.manifest.metadata['translation_completed'] = datetime.now().isoformat()
        self.manifest.save(self.manifest_path)

        return output_path

    def _translate_text(self, text: str) -> str:
        """Translate a single text block."""
        if not text.strip():
            return text

        # Use Ollama translator
        result = self.translator.translate_document(
            text,
            self.source_lang,
            self.target_lang
        )
        return result.translated_text

    def _save_translation(self, metadata: dict, chapter_contents: list) -> Path:
        """
        Save translated content to markdown file.

        Args:
            metadata: Translated metadata
            chapter_contents: List of translated chapter contents

        Returns:
            Path to output file
        """
        # Generate output filename
        base_name = Path(self.manifest.original_file).stem
        lang_code = self.target_lang.replace(' ', '_').lower()
        timestamp = datetime.now().strftime("%Y%m%d")
        output_name = f"{base_name}_{lang_code}_{timestamp}.md"
        output_path = Path(self.manifest.original_file).parent / output_name

        # Assemble the output
        lines = []

        # Add metadata
        if 'translated_title' in metadata:
            lines.append(f"# {metadata['translated_title']}")
        elif 'title' in metadata:
            lines.append(f"# {metadata['title']}")

        if 'author' in metadata:
            lines.append(f"**{metadata['author']}**")

        lines.append("")
        lines.append(f"*Translated to {self.target_lang}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add table of contents if available
        if self.manifest.toc_markdown:
            lines.append(self.manifest.toc_markdown)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Add chapters
        for i, chapter in enumerate(self.manifest.chapters):
            # Add chapter marker (preserved from original)
            lines.append(chapter.marker)
            lines.append("")

            # Add translated content
            if i < len(chapter_contents):
                lines.append(chapter_contents[i])
                lines.append("")
                lines.append("")  # Extra blank line between chapters

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Structured Book Translator v2 - Uses manifest system for perfect chapter alignment"
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to book file (.md) or manifest (.json)'
    )

    parser.add_argument(
        '--source-lang',
        required=False,
        default=None,
        help='[OPTIONAL] Source language - auto-detected if not specified'
    )

    parser.add_argument(
        '--target-lang',
        required=True,
        help='Target language (e.g., "Modern English", "Spanish")'
    )

    parser.add_argument(
        '--model',
        default='gemma3-translator:4b',
        help='Model name (default: gemma3-translator:4b)'
    )

    parser.add_argument(
        '--translator',
        choices=['ollama'],
        default='ollama',
        help='Translator backend (Ollama, 100%% local)'
    )

    parser.add_argument(
        '--no-translate-metadata',
        action='store_true',
        help='Do not translate title/author metadata'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )

    args = parser.parse_args()

    try:
        # Get or create manifest
        print(f"\n📖 STRUCTURED TRANSLATOR v2")
        print("=" * 60)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            args.input_file,
            auto_fix=True,
            verbose=not args.quiet
        )

        # Create translator
        translator = ManifestTranslator(
            manifest=manifest,
            manifest_path=manifest_path,
            target_lang=args.target_lang,
            source_lang=args.source_lang,
            model_name=args.model,
            translator_type=args.translator,
            translate_metadata=not args.no_translate_metadata,
            verbose=not args.quiet
        )

        # Translate
        output_path = translator.translate()

        # Show final progress
        if not args.quiet:
            ManifestManager.print_progress_report(manifest)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Translation interrupted by user")
        print("   Progress has been saved in the manifest")
        print("   Run the same command to resume")
        return 130

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())