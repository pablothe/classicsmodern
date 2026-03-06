#!/usr/bin/env python3
"""
Structured Book Translator - Architecture v2

Key principles:
1. Parse → Validate → Translate Blocks → Assemble
2. Validate ONCE before translation (not after)
3. Translate content blocks ONLY (preserve structure)
4. Generic design (works for any book with chapters)

Usage:
    python3 structured_translator.py INPUT.md \\
        --target-lang "Modern English" \\
        --model ollama:gemma3-translator

    Source language is auto-detected by the LLM (no --source-lang needed!)
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from lib.book.validator import validate_book, ValidationReport
from lib.book.processor import BookProcessor


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Chapter:
    """Single chapter with structure preservation"""
    number: int                   # 1, 2, 3, ...
    marker: str                   # "I.", "Chapter 1", etc. (never translated)
    content: str                  # Text to translate
    start_line: int               # Line number in source
    end_line: int                 # Line number in source
    metadata: Dict = field(default_factory=dict)


@dataclass
class BookStructure:
    """Parsed book with separated concerns"""
    metadata: Dict[str, str]      # title, author, etc.
    chapters: List[Chapter]       # All detected chapters
    original_file: Path           # Source file path
    validation_report: Optional[ValidationReport] = None


@dataclass
class TranslationConfig:
    """Translation configuration"""
    source_lang: Optional[str] = None  # DEPRECATED: LLM auto-detects source
    target_lang: str = "Modern English"
    translator_type: str = "ollama"
    model_name: str = "zongwei/gemma3-translator:4b"
    translate_metadata: bool = True
    preserve_markers: bool = True
    llm: object = None  # Optional LLMProvider instance


# ============================================================================
# Book Parser
# ============================================================================

class BookParser:
    """Extract structured data from markdown"""

    def parse(self, input_file: Path) -> BookStructure:
        """
        Parse markdown file into structured format.

        Args:
            input_file: Path to markdown file

        Returns:
            BookStructure with metadata and chapters
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()

        # Use BookProcessor (Gutenberg TOC → ## headers → regex fallback)
        processor = BookProcessor(verbose=False)
        cleaned_text, _ = processor.strip_gutenberg(text)
        bp_chapters = processor.detect_chapters(cleaned_text, book_file=input_file)

        if not bp_chapters:
            raise ValueError(f"No chapters detected in {input_file}")

        # Convert BookProcessor chapters to local Chapter format
        chapters = []
        lines = cleaned_text.split('\n')

        for bp_ch in bp_chapters:
            chapters.append(Chapter(
                number=bp_ch.number,
                marker=bp_ch.marker,
                content=bp_ch.content,
                start_line=bp_ch.start_line,
                end_line=bp_ch.end_line,
                metadata={'type': bp_ch.detection_type}
            ))

        # Extract metadata (everything before first chapter)
        first_chapter_line = chapters[0].start_line if chapters else 0
        metadata_lines = lines[:first_chapter_line]
        metadata = self._parse_metadata(metadata_lines)

        return BookStructure(
            metadata=metadata,
            chapters=chapters,
            original_file=input_file
        )

    def _parse_metadata(self, lines: List[str]) -> Dict[str, str]:
        """Extract title and author from header lines"""
        metadata = {}
        text = '\n'.join(lines)

        # Look for title (# Title or Title: value)
        for line in lines:
            if line.startswith('# '):
                metadata['title'] = line[2:].strip()
                break
            elif line.lower().startswith('title:'):
                metadata['title'] = line.split(':', 1)[1].strip()
                break

        # Look for author (Author: or by)
        for line in lines:
            if line.lower().startswith('author:'):
                metadata['author'] = line.split(':', 1)[1].strip()
                break
            elif line.lower().startswith('by '):
                metadata['author'] = line[3:].strip()
                break

        return metadata


# ============================================================================
# Structure Validator
# ============================================================================

class StructureValidator:
    """Validate book structure before translation"""

    def validate(self, structure: BookStructure) -> ValidationReport:
        """
        Validate that book structure is complete and ready for translation.

        Args:
            structure: Parsed book structure

        Returns:
            ValidationReport with validation results

        Raises:
            ValueError: If validation fails
        """
        # Use existing validator
        report = validate_book(str(structure.original_file))

        if not report.valid:
            error_msg = [
                f"❌ Source book validation failed:",
                ""
            ]
            for error in report.errors:
                error_msg.append(f"  - {error}")

            error_msg.extend([
                "",
                "💡 Fix these issues before translating:",
                f"  python3 validate.py {structure.original_file} --auto-fix"
            ])

            raise ValueError('\n'.join(error_msg))

        return report


# ============================================================================
# Block Translator
# ============================================================================

class BlockTranslator:
    """Translate content blocks independently with checkpoint/resume support"""

    def __init__(self, config: TranslationConfig, progress_callback=None, checkpoint_file: Optional[Path] = None):
        self.config = config
        self.progress_callback = progress_callback
        self.checkpoint_file = checkpoint_file
        self.translator = self._create_translator()

    def _save_checkpoint(self, chapter_num: int, translated_chapters: List[Chapter]):
        """Save translation progress to checkpoint file"""
        if not self.checkpoint_file:
            return

        checkpoint_data = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'source_lang': self.config.source_lang,
                'target_lang': self.config.target_lang,
                'model_name': self.config.model_name
            },
            'progress': {
                'last_completed_chapter': chapter_num,
                'total_chapters_completed': len(translated_chapters)
            },
            'translated_chapters': [
                {
                    'number': ch.number,
                    'marker': ch.marker,
                    'content': ch.content,
                    'start_line': ch.start_line,
                    'end_line': ch.end_line,
                    'metadata': ch.metadata
                }
                for ch in translated_chapters
            ]
        }

        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

        print(f"  💾 Checkpoint saved: {len(translated_chapters)} chapters completed")

    def _load_checkpoint(self) -> Optional[List[Chapter]]:
        """Load previous translation progress from checkpoint file"""
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return None

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                import json
                checkpoint_data = json.load(f)

            # Verify checkpoint matches current config (only check target_lang now)
            saved_config = checkpoint_data.get('config', {})
            if saved_config.get('target_lang') != self.config.target_lang:
                print(f"  ⚠️  Checkpoint target language mismatch - starting fresh")
                return None

            # Rebuild chapters from checkpoint
            translated_chapters = []
            for ch_data in checkpoint_data['translated_chapters']:
                translated_chapters.append(Chapter(
                    number=ch_data['number'],
                    marker=ch_data['marker'],
                    content=ch_data['content'],
                    start_line=ch_data['start_line'],
                    end_line=ch_data['end_line'],
                    metadata=ch_data.get('metadata', {})
                ))

            progress = checkpoint_data.get('progress', {})
            print(f"  📂 Checkpoint loaded: {progress.get('total_chapters_completed', 0)} chapters completed")
            print(f"  ⏭️  Resuming from chapter {progress.get('last_completed_chapter', 0) + 1}")

            return translated_chapters

        except Exception as e:
            print(f"  ⚠️  Failed to load checkpoint: {e}")
            return None

    def _create_translator(self):
        """Create translator with configured LLM provider."""
        from lib.translation.engine import OllamaTranslator
        from lib.config import get_config

        ollama_config = get_config()
        llm = self.config.llm
        model = self.config.model_name

        # Use general-purpose model for English→English modernization
        is_modernization = (
            self.config.source_lang and self.config.target_lang
            and 'english' in self.config.source_lang.lower()
            and 'english' in self.config.target_lang.lower()
        )
        if is_modernization and not llm:
            model = "llama3.2:3b"
            print(f"  Using {model} for English modernization")

        return OllamaTranslator(
            model_name=model,
            ollama_host=ollama_config.models.ollama_host,
            llm=llm,
        )

    def translate_structure(self, structure: BookStructure) -> BookStructure:
        """
        Translate all content blocks paragraph-by-paragraph with checkpoint/resume.

        Each paragraph is translated individually with context from the previous
        translated paragraph. This guarantees 1:1 source-to-translated paragraph
        mapping, which is critical for audio sync and position tracking.

        Args:
            structure: Parsed book structure

        Returns:
            New BookStructure with translated content
        """
        print(f"\n🌐 Translating {len(structure.chapters)} chapters (paragraph-by-paragraph)...")
        if self.config.source_lang:
            print(f"   Source: {self.config.source_lang} (explicit)")
        else:
            print(f"   Source: Auto-detect")
        print(f"   Target: {self.config.target_lang}")
        print(f"   Model: {self.config.model_name}")
        print()

        # Try to load checkpoint
        translated_chapters = self._load_checkpoint()
        start_chapter_idx = len(translated_chapters) if translated_chapters else 0

        if translated_chapters is None:
            translated_chapters = []

        # Translate metadata
        translated_metadata = {}
        if self.config.translate_metadata:
            print("📝 Translating metadata...")
            if 'title' in structure.metadata:
                translated_metadata['title'] = self._translate_text(
                    structure.metadata['title']
                )
            if 'author' in structure.metadata:
                # Usually keep author names as-is
                translated_metadata['author'] = structure.metadata['author']
        else:
            translated_metadata = structure.metadata.copy()

        # Translate chapters (skip already completed ones)
        for i in range(start_chapter_idx, len(structure.chapters)):
            chapter = structure.chapters[i]
            chapter_num = i + 1

            print(f"  [{chapter_num}/{len(structure.chapters)}] Translating chapter {chapter.number} ({chapter.marker})...")

            # Progress callback for GUI integration
            if self.progress_callback:
                self.progress_callback(chapter_num, len(structure.chapters))

            try:
                # CRITICAL: Only content is translated, marker is preserved
                word_count = len(chapter.content.split())
                translated_content = self._translate_chapter_by_paragraphs(
                    chapter.content, chapter.number, word_count,
                    len(structure.chapters)
                )
                translated_word_count = len(translated_content.split())
                print(f"    ✓ Chapter {chapter.number} complete ({translated_word_count} words)")

                translated_chapters.append(Chapter(
                    number=chapter.number,
                    marker=chapter.marker,  # PRESERVED AS-IS
                    content=translated_content,
                    start_line=chapter.start_line,
                    end_line=chapter.end_line,
                    metadata=chapter.metadata
                ))

                # Save checkpoint after each chapter
                self._save_checkpoint(chapter.number, translated_chapters)

            except KeyboardInterrupt:
                print(f"\n⚠️  Translation interrupted by user")
                print(f"   Progress saved: {len(translated_chapters)}/{len(structure.chapters)} chapters")
                print(f"   Resume with same command to continue from chapter {len(translated_chapters) + 1}")
                raise

            except Exception as e:
                print(f"\n❌ Error translating chapter {chapter.number}: {e}")
                print(f"   Progress saved: {len(translated_chapters)}/{len(structure.chapters)} chapters")
                print(f"   Fix the issue and resume with same command")
                raise

        print(f"\n✅ Translation complete: {len(translated_chapters)} chapters")

        # Clean up checkpoint file on success
        if self.checkpoint_file and self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            print(f"  🗑️  Checkpoint removed (translation complete)")

        return BookStructure(
            metadata=translated_metadata,
            chapters=translated_chapters,
            original_file=structure.original_file
        )

    def _translate_chapter_by_paragraphs(
        self, content: str, chapter_number: int, word_count: int, total_chapters: int
    ) -> str:
        """
        Translate chapter content paragraph-by-paragraph with sliding context.

        Each paragraph is sent individually with the previous translated paragraph
        as context. This guarantees 1:1 paragraph mapping between source and
        translated text, which is essential for audio sync.

        Args:
            content: Chapter content text
            chapter_number: Chapter number for progress display
            word_count: Total word count for display
            total_chapters: Total chapters for display

        Returns:
            Translated content with paragraph structure preserved
        """
        # Split into paragraphs (same logic as BookProcessor._extract_paragraphs)
        raw_parts = re.split(r'\n\s*\n', content)
        paragraphs = [p.strip() for p in raw_parts if p.strip()]

        if not paragraphs:
            return content

        # For single-paragraph chapters or very short content, use direct translation
        if len(paragraphs) == 1:
            print(f"    → Sending to Ollama ({word_count} words, 1 paragraph)...")
            return self._translate_text(content)

        print(f"    → Translating {len(paragraphs)} paragraphs ({word_count} words)...")

        translated_paragraphs = []
        previous_translated = None

        for j, para in enumerate(paragraphs):
            if not para:
                continue

            # Translate with context from previous paragraph
            if previous_translated:
                translated = self._translate_text_with_context(para, previous_translated)
            else:
                translated = self._translate_text(para)

            translated_paragraphs.append(translated)
            previous_translated = translated

            # Progress for long chapters (every 5 paragraphs)
            if (j + 1) % 5 == 0 or j + 1 == len(paragraphs):
                print(f"      [{j + 1}/{len(paragraphs)}] paragraphs")

        # Reassemble with double newlines (preserves paragraph structure)
        return '\n\n'.join(translated_paragraphs)

    def _translate_text_with_context(self, text: str, previous_translation: str) -> str:
        """Translate a single text block with context from previous translation."""
        if not text.strip():
            return text

        result = self.translator.translate_document_with_context(
            text,
            self.config.source_lang,
            self.config.target_lang,
            previous_context=previous_translation
        )
        return result.translated_text

    def _translate_text(self, text: str) -> str:
        """Translate a single text block"""
        if not text.strip():
            return text

        result = self.translator.translate_document(
            text,
            self.config.source_lang,
            self.config.target_lang
        )
        return result.translated_text


# ============================================================================
# Markdown Assembler
# ============================================================================

class MarkdownAssembler:
    """Rebuild structured markdown from translated blocks"""

    def assemble(self, structure: BookStructure, output_file: Path) -> Path:
        """
        Assemble translated structure into markdown file.

        Args:
            structure: Translated book structure
            output_file: Path to output file

        Returns:
            Path to created output file
        """
        print(f"\n📝 Assembling translated markdown...")

        lines = []

        # 1. Metadata header
        if 'title' in structure.metadata:
            lines.append(f"# {structure.metadata['title']}")
            lines.append("")

        if 'author' in structure.metadata:
            lines.append(f"**by {structure.metadata['author']}**")
            lines.append("")

        # 2. Auto-generate Table of Contents
        lines.append("## Table of Contents")
        lines.append("")
        for ch in structure.chapters:
            anchor = f"chapter-{ch.number}"
            lines.append(f"{ch.number}. [{ch.marker}](#{anchor})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 3. Chapters (marker + translated content)
        for ch in structure.chapters:
            # Chapter marker (preserved from original)
            lines.append(ch.marker)
            lines.append("")

            # Translated content
            lines.append(ch.content)
            lines.append("")

        # Write output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"✅ Output written: {output_file}")
        print(f"   Chapters: {len(structure.chapters)}")
        size = len('\n'.join(lines))
        print(f"   Size: {size:,} characters")

        return output_file


# ============================================================================
# Main Workflow
# ============================================================================

def translate_book(input_file: Path, config: TranslationConfig) -> Path:
    """
    Main structured translation workflow.

    Args:
        input_file: Path to source markdown file
        config: Translation configuration

    Returns:
        Path to translated output file
    """
    print("="*70)
    print("STRUCTURED BOOK TRANSLATOR")
    print("="*70)
    print(f"Input: {input_file}")
    print(f"Source language: {config.source_lang or 'Auto-detect'}")
    print(f"Target language: {config.target_lang}")
    print(f"Model: {config.model_name}")
    print("="*70)

    # STEP 1: PARSE
    print("\n📖 Step 1: Parsing book structure...")
    parser = BookParser()
    structure = parser.parse(input_file)
    print(f"✅ Parsed: {len(structure.chapters)} chapters detected")

    # STEP 2: VALIDATE (BEFORE translation)
    print("\n🔍 Step 2: Validating structure...")
    validator = StructureValidator()
    validation_report = validator.validate(structure)
    structure.validation_report = validation_report
    print(f"✅ Validation passed:")
    print(f"   - Chapters: {validation_report.metrics['chapter_count']}")
    print(f"   - Sequential: {validation_report.metrics['sequential_chapters']}")
    print(f"   - Features ready: {sum(validation_report.feature_support.values())}/3")

    # STEP 3: TRANSLATE BLOCKS
    print("\n🌐 Step 3: Translating content blocks...")

    # Create checkpoint file path
    checkpoint_file = input_file.parent / f".translation_checkpoint_{input_file.stem}.json"

    translator = BlockTranslator(config, checkpoint_file=checkpoint_file)
    translated_structure = translator.translate_structure(structure)

    # STEP 4: ASSEMBLE
    print("\n📝 Step 4: Assembling markdown...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = input_file.parent / f"{input_file.stem}_{config.target_lang.replace(' ', '_')}_{timestamp}.md"

    assembler = MarkdownAssembler()
    output_path = assembler.assemble(translated_structure, output_file)

    print("\n" + "="*70)
    print("✅ TRANSLATION COMPLETE")
    print("="*70)
    print(f"Output: {output_path}")
    print(f"Chapters translated: {len(translated_structure.chapters)}")
    print("="*70)

    return output_path


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Structured Book Translator - Preserves chapter structure during translation"
    )
    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to source markdown file'
    )
    parser.add_argument(
        '--source-lang',
        required=False,
        default=None,
        help='[OPTIONAL] Source language - LLM will auto-detect if not specified'
    )
    parser.add_argument(
        '--target-lang',
        required=True,
        help='Target language (e.g., "Modern English", "Spanish")'
    )
    parser.add_argument(
        '--model',
        default='ollama:gemma3-translator:4b',
        help='Translation model (format: "ollama:model_name")'
    )
    parser.add_argument(
        '--no-translate-metadata',
        action='store_true',
        help='Do not translate title/author metadata'
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input_file.exists():
        print(f"❌ Error: File not found: {args.input_file}")
        sys.exit(1)

    # Parse model specification
    if ':' in args.model:
        translator_type, model_name = args.model.split(':', 1)
    else:
        # Default to ollama if no prefix
        translator_type = "ollama"
        model_name = args.model

    # Create config
    config = TranslationConfig(
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        translator_type=translator_type,
        model_name=model_name,
        translate_metadata=not args.no_translate_metadata
    )

    try:
        output_file = translate_book(args.input_file, config)
        print(f"\n✅ Success! Translated book: {output_file}")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Translation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
