#!/usr/bin/env python3
"""
Unit Tests for Book Validation

Tests the book validation system that ensures books meet quality standards
for Karaoke, AI Chat, and Web Player features.
"""

import pytest
from pathlib import Path

from lib.book.validator import (
    validate_book,
    check_chapter_structure,
    check_text_quality,
    check_metadata,
    check_feature_readiness,
    auto_fix_book,
    ValidationReport
)


class TestBookValidation:
    """Test suite for book validation"""

    def test_validate_clean_book(self, sample_book_clean):
        """Test validation of a clean, well-formatted book"""
        report = validate_book(sample_book_clean)

        assert report.valid is True
        assert len(report.errors) == 0
        assert report.feature_support['karaoke'] is True
        assert report.feature_support['ai_chat'] is True
        assert report.feature_support['web_player'] is True

    def test_validate_gutenberg_book(self, sample_book_gutenberg):
        """Test validation of book with Gutenberg boilerplate"""
        report = validate_book(sample_book_gutenberg)

        # Should have warnings about boilerplate
        assert any('Gutenberg' in w for w in report.warnings)
        assert report.metrics['has_gutenberg_boilerplate'] is True

    def test_validate_invalid_book(self, temp_dir):
        """Test validation of invalid book (no chapters, too short)"""
        invalid_book = temp_dir / "invalid.md"
        invalid_book.write_text("Too short.")

        report = validate_book(str(invalid_book))

        assert report.valid is False
        assert len(report.errors) > 0
        assert report.feature_support['karaoke'] is False
        assert report.feature_support['ai_chat'] is False


class TestChapterStructureValidation:
    """Test chapter structure validation"""

    def test_check_valid_chapter_structure(self, sample_book_content):
        """Test validation of valid chapter structure"""
        valid, errors, warnings, metrics = check_chapter_structure(
            sample_book_content, "test.md"
        )

        assert valid is True
        assert len(errors) == 0
        assert metrics['chapter_count'] == 3
        assert metrics['sequential_chapters'] is True

    def test_check_no_chapters(self):
        """Test book with no chapters"""
        text = "Just some text without any chapters."

        valid, errors, warnings, metrics = check_chapter_structure(text, "test.md")

        assert valid is False
        assert any("No chapters detected" in e for e in errors)
        assert metrics['chapter_count'] == 0


class TestTextQualityValidation:
    """Test text quality validation"""

    def test_check_clean_text_quality(self, sample_book_content):
        """Test validation of clean text"""
        valid, errors, warnings, metrics = check_text_quality(sample_book_content)

        assert valid is True
        assert len(errors) == 0
        assert metrics['has_gutenberg_boilerplate'] is False
        assert metrics['word_count'] > 100

    def test_check_gutenberg_boilerplate(self, sample_book_gutenberg):
        """Test detection of Gutenberg boilerplate"""
        with open(sample_book_gutenberg, 'r') as f:
            text = f.read()

        valid, errors, warnings, metrics = check_text_quality(text)

        assert metrics['has_gutenberg_boilerplate'] is True
        assert any('Gutenberg' in w for w in warnings)

    def test_check_too_short(self):
        """Test detection of text that's too short"""
        text = "Very short text."

        valid, errors, warnings, metrics = check_text_quality(text)

        assert valid is False
        assert any("too short" in e for e in errors)
        assert metrics['word_count'] < 100

    def test_check_excessive_empty_lines(self):
        """Test detection of excessive empty paragraphs"""
        text = "\n\n\n\n".join(["Line"] * 10)  # Many empty lines

        valid, errors, warnings, metrics = check_text_quality(text)

        # Should have warning about formatting
        assert any('empty' in w.lower() for w in warnings)


class TestMetadataValidation:
    """Test metadata validation"""

    def test_check_metadata_present(self, sample_book_content):
        """Test detection of title and author"""
        valid, errors, warnings, metrics = check_metadata(sample_book_content, "test.md")

        assert valid is True  # Metadata is optional, so always valid
        assert metrics['has_title'] is True
        assert metrics['has_author'] is True
        assert "Alice" in metrics['title']
        assert "Carroll" in metrics['author']

class TestFeatureReadiness:
    """Test feature readiness checks"""

    def test_check_karaoke_ready(self, valid_book_metrics):
        """Test Karaoke feature readiness"""
        chapter_metrics = {
            'chapter_count': valid_book_metrics['chapter_count'],
            'sequential_chapters': valid_book_metrics['sequential_chapters']
        }
        text_metrics = {
            'word_count': valid_book_metrics['word_count']
        }
        metadata_metrics = {}

        support = check_feature_readiness(
            chapter_metrics, text_metrics, metadata_metrics, Path("test.md")
        )

        assert support['karaoke'] is True

    def test_check_ai_chat_ready(self, valid_book_metrics):
        """Test AI Chat feature readiness"""
        chapter_metrics = {
            'chapter_count': valid_book_metrics['chapter_count'],
            'sequential_chapters': valid_book_metrics['sequential_chapters']
        }
        text_metrics = {'word_count': valid_book_metrics['word_count']}
        metadata_metrics = {}

        support = check_feature_readiness(
            chapter_metrics, text_metrics, metadata_metrics, Path("test.md")
        )

        assert support['ai_chat'] is True

    def test_check_insufficient_chapters_for_ai(self):
        """Test AI Chat not ready with too few chapters"""
        chapter_metrics = {
            'chapter_count': 2,  # Need at least 3
            'sequential_chapters': True
        }
        text_metrics = {'word_count': 10000}
        metadata_metrics = {}

        support = check_feature_readiness(
            chapter_metrics, text_metrics, metadata_metrics, Path("test.md")
        )

        assert support['ai_chat'] is False

    def test_check_web_player_ready(self):
        """Test Web Player feature readiness (least strict)"""
        chapter_metrics = {
            'chapter_count': 1,  # Just need 1 chapter
            'sequential_chapters': True
        }
        text_metrics = {'word_count': 1000}
        metadata_metrics = {}

        support = check_feature_readiness(
            chapter_metrics, text_metrics, metadata_metrics, Path("test.md")
        )

        assert support['web_player'] is True


class TestAutoFix:
    """Test automatic fixing functionality"""

    def test_auto_fix_gutenberg_boilerplate(self, sample_book_gutenberg, temp_dir):
        """Test auto-removal of Gutenberg boilerplate"""
        # Copy to temp location
        temp_book = temp_dir / "test_gutenberg.md"
        with open(sample_book_gutenberg, 'r') as f:
            temp_book.write_text(f.read())

        # Apply auto-fix
        result = auto_fix_book(str(temp_book), backup=False)

        assert result is True  # Fixes were applied

        # Validate it's cleaner now
        report = validate_book(str(temp_book))
        assert report.metrics['has_gutenberg_boilerplate'] is False

    def test_auto_fix_creates_backup(self, sample_book_gutenberg, temp_dir):
        """Test that auto-fix creates backup file"""
        temp_book = temp_dir / "test.md"
        with open(sample_book_gutenberg, 'r') as f:
            temp_book.write_text(f.read())

        # Apply auto-fix with backup
        auto_fix_book(str(temp_book), backup=True)

        # Check backup exists
        backup_file = temp_dir / "test.md.bak"
        assert backup_file.exists()

    def test_auto_fix_no_changes_needed(self, sample_book_clean, temp_dir):
        """Test auto-fix when no changes are needed"""
        temp_book = temp_dir / "test.md"
        with open(sample_book_clean, 'r') as f:
            temp_book.write_text(f.read())

        result = auto_fix_book(str(temp_book), backup=False)

        # Should return False (no fixes needed)
        assert result is False


class TestValidationReport:
    """Test ValidationReport data class"""

    def test_report_string_representation(self, sample_book_clean):
        """Test human-readable report output"""
        report = validate_book(sample_book_clean)

        report_str = str(report)

        assert "BOOK VALIDATION REPORT" in report_str
        assert "✅ VALID" in report_str
        assert "FEATURE SUPPORT" in report_str

    def test_report_json_export(self, sample_book_clean):
        """Test JSON export of report"""
        report = validate_book(sample_book_clean)

        json_str = report.to_json()

        assert isinstance(json_str, str)
        assert '"valid"' in json_str
        assert '"feature_support"' in json_str

    def test_invalid_report_shows_errors(self, temp_dir):
        """Test that invalid report shows errors clearly"""
        invalid_book = temp_dir / "invalid.md"
        invalid_book.write_text("Too short.")

        report = validate_book(str(invalid_book))

        report_str = str(report)
        assert "❌ INVALID" in report_str
        assert "ERRORS" in report_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
