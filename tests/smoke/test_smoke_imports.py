#!/usr/bin/env python3
"""
Smoke Test: CLI Import Validation

Verifies that all CLI scripts can import their dependencies from lib/.
Catches "function exists but wasn't exported" bugs that break CLI tools
while unit tests (which test internal classes directly) pass.
"""

import pytest

pytestmark = pytest.mark.smoke


class TestSmokeImports:
    """Verify all CLI scripts can import their lib/ dependencies."""

    def test_translate_cli_imports(self):
        """translate.py imports translate_book and TranslationConfig."""
        from lib.translation.structured import translate_book, TranslationConfig
        assert callable(translate_book)
        assert TranslationConfig is not None

    def test_validate_cli_imports(self):
        """validate.py imports validate_book, auto_fix_book, validate_directory."""
        from lib.book.validator import validate_book, auto_fix_book, validate_directory
        assert callable(validate_book)
        assert callable(auto_fix_book)
        assert callable(validate_directory)

    def test_summarize_cli_imports(self):
        """summarize.py imports BookSummarizer."""
        from lib.summarize.engine import BookSummarizer
        assert BookSummarizer is not None

    def test_make_audiobook_cli_imports(self):
        """make_audiobook.py imports from lib.audio, lib.book, lib.cover."""
        from lib.book.validator import validate_book
        from lib.book.processor import BookProcessor
        from lib.cover.prompts import get_book_prompt
        assert callable(validate_book)
        assert BookProcessor is not None
        assert callable(get_book_prompt)

    @pytest.mark.requires_kokoro
    def test_audiobook_cli_imports(self):
        """audiobook.py imports KokoroAudioGenerator (requires kokoro-onnx)."""
        from lib.audio.kokoro import KokoroAudioGenerator
        assert KokoroAudioGenerator is not None

    def test_cover_cli_imports(self):
        """cover.py imports generate_image (lazy import, no diffusers needed)."""
        from lib.cover.generator import generate_image
        assert callable(generate_image)

    def test_book_catalog_imports(self):
        """Book catalog is importable and has entries."""
        from lib.book.catalog import get_book_info, BOOK_CATALOG
        assert callable(get_book_info)
        assert len(BOOK_CATALOG) > 0

    def test_chapter_metadata_imports(self):
        """Chapter metadata generation is importable."""
        from lib.audio.chapter_metadata import generate_chapter_metadata, save_chapter_metadata
        assert callable(generate_chapter_metadata)
        assert callable(save_chapter_metadata)
