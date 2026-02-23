#!/usr/bin/env python3
"""
Smoke Test: Book Validation

Tests the real validation pipeline with no external dependencies.
"""

import shutil
import pytest
from pathlib import Path

pytestmark = pytest.mark.smoke


class TestSmokeValidation:
    """Smoke: Validate book structure with real validator."""

    def test_valid_book_passes(self, smoke_book_path):
        """A known-good book should pass validation."""
        from lib.book.validator import validate_book

        report = validate_book(str(smoke_book_path))

        assert report.valid is True, f"Validation failed: {report.errors}"
        assert report.metrics['chapter_count'] == 3
        assert report.metrics['sequential_chapters'] is True
        assert report.feature_support['web_player'] is True

    def test_valid_book_supports_ai_chat(self, smoke_book_path):
        """A 3-chapter book should support AI chat."""
        from lib.book.validator import validate_book

        report = validate_book(str(smoke_book_path))

        assert report.feature_support['ai_chat'] is True, (
            f"AI chat requires 3+ sequential chapters, got: "
            f"chapters={report.metrics['chapter_count']}, "
            f"sequential={report.metrics['sequential_chapters']}"
        )

    def test_empty_book_fails(self, tmp_path):
        """An empty file should fail validation."""
        from lib.book.validator import validate_book

        empty = tmp_path / "empty.md"
        empty.write_text("")
        report = validate_book(str(empty))

        assert report.valid is False

    def test_gutenberg_book_warns(self):
        """A book with Gutenberg boilerplate should produce warnings."""
        from lib.book.validator import validate_book

        fixtures = Path(__file__).parent.parent / "fixtures" / "sample_books"
        gutenberg_book = fixtures / "gutenberg_book.md"
        if not gutenberg_book.exists():
            pytest.skip("gutenberg_book.md fixture not found")

        report = validate_book(str(gutenberg_book))
        warning_texts = " ".join(report.warnings).lower()

        assert "gutenberg" in warning_texts or "boilerplate" in warning_texts, (
            f"Expected Gutenberg warning, got warnings: {report.warnings}"
        )

    def test_auto_fix_strips_boilerplate(self, tmp_path):
        """Auto-fix should strip Gutenberg boilerplate."""
        from lib.book.validator import auto_fix_book

        fixtures = Path(__file__).parent.parent / "fixtures" / "sample_books"
        gutenberg_book = fixtures / "gutenberg_book.md"
        if not gutenberg_book.exists():
            pytest.skip("gutenberg_book.md fixture not found")

        dest = tmp_path / "fixme.md"
        shutil.copy(gutenberg_book, dest)

        auto_fix_book(str(dest), backup=False)

        content = dest.read_text()
        assert "START OF THE PROJECT GUTENBERG" not in content
        assert "END OF THE PROJECT GUTENBERG" not in content

    def test_chapter_detection(self, smoke_book_path):
        """BookProcessor should detect exactly 3 chapters in smoke book."""
        from lib.book.processor import BookProcessor

        processor = BookProcessor(verbose=False)
        with open(smoke_book_path) as f:
            text = f.read()

        cleaned, _ = processor.strip_gutenberg(text)
        chapters = processor.detect_chapters(cleaned)

        assert len(chapters) == 3, (
            f"Expected 3 chapters, detected {len(chapters)}: "
            f"{[ch.marker for ch in chapters]}"
        )

    def test_nonexistent_file_fails(self):
        """Validation of a nonexistent file should fail cleanly."""
        from lib.book.validator import validate_book

        report = validate_book("/nonexistent/path/book.md")
        assert report.valid is False
        assert len(report.errors) > 0
