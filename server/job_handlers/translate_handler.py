#!/usr/bin/env python3
"""
Translate Handler - Standalone translation worker

Handles translation-only jobs (for already-downloaded books).
Uses structured_translator.py to preserve chapter structure.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Callable

from lib.translation.structured import (
    BookParser,
    StructureValidator,
    BlockTranslator,
    MarkdownAssembler,
    TranslationConfig
)


def translate_handler(job: Dict, progress_callback: Callable) -> Dict:
    """
    Handle standalone translation job.

    Args:
        job: Job data dictionary with:
            - config.book_id: Book directory name
            - config.source_file: Source markdown filename
            - config.source_language: Source language (e.g., 'Russian')
            - config.target_language: Target language (e.g., 'Modern English')
            - config.translation_model: Model name (default: 'zongwei/gemma3-translator:4b')
        progress_callback: Function to report progress
            Signature: progress_callback(progress: int, state: Dict)

    Returns:
        Result dictionary with:
            - output_file: Path to translated file
            - source_language: Detected/specified source language
            - target_language: Target language
            - chapter_count: Number of chapters translated

    Raises:
        Exception on translation failure
    """
    config = job['config']
    book_id = config['book_id']
    source_file = config['source_file']
    source_lang = config.get('source_language', 'Russian')
    target_lang = config.get('target_language', 'Modern English')
    model = config.get('translation_model', 'zongwei/gemma3-translator:4b')

    # Build file paths
    books_dir = Path(__file__).parent.parent.parent / "books"
    book_dir = books_dir / book_id
    source_path = book_dir / source_file

    if not source_path.exists():
        raise Exception(f"Source file not found: {source_path}")

    # Create translation config
    trans_config = TranslationConfig(
        source_lang=source_lang,
        target_lang=target_lang,
        translator_type='ollama',
        model_name=model,
        translate_metadata=True,
        preserve_markers=True
    )

    # Custom progress callback that wraps chapter-by-chapter updates
    def chapter_progress_callback(current: int, total: int):
        chapter_pct = int((current / total) * 100)
        overall_progress = 10 + int(chapter_pct * 0.80)  # Translation is 10-90%

        progress_callback(overall_progress, {
            'stage': 'translation',
            'message': f'Translating chapter {current}/{total}...',
            'current_chapter': current,
            'total_chapters': total
        })

    try:
        # STEP 1: Parse structure (0-5%)
        progress_callback(2, {'stage': 'parse', 'message': 'Parsing book structure...'})
        parser = BookParser()
        structure = parser.parse(source_path)

        # STEP 2: Validate structure (5-10%)
        progress_callback(6, {
            'stage': 'validate',
            'message': f'Validating structure ({len(structure.chapters)} chapters)...'
        })

        validator = StructureValidator()
        try:
            validation_report = validator.validate(structure)
        except ValueError as e:
            raise Exception(f"Source book validation failed: {e}")

        # STEP 3: Translate blocks (10-90%)
        progress_callback(10, {
            'stage': 'translate',
            'message': f'Starting translation of {len(structure.chapters)} chapters...'
        })

        # Create checkpoint file for resumability
        checkpoint_file = book_dir / f".translation_checkpoint_{source_path.stem}.json"

        translator = BlockTranslator(
            trans_config,
            progress_callback=chapter_progress_callback,
            checkpoint_file=checkpoint_file
        )

        translated_structure = translator.translate_structure(structure)

        # STEP 4: Assemble output (90-100%)
        progress_callback(92, {'stage': 'assemble', 'message': 'Assembling translated markdown...'})

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = book_dir / f"{source_path.stem}_{target_lang.replace(' ', '_')}_{timestamp}.md"

        assembler = MarkdownAssembler()
        output_path = assembler.assemble(translated_structure, output_file)

        # Done
        progress_callback(100, {'stage': 'done', 'message': 'Translation complete'})

        return {
            'output_file': str(output_path),
            'source_language': source_lang,
            'target_language': target_lang,
            'chapter_count': len(structure.chapters),
            'book_id': book_id,
            'source_file': source_file
        }

    except Exception as e:
        raise Exception(f"Translation failed: {str(e)}")
