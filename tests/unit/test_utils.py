#!/usr/bin/env python3
"""
Unit tests for lib/utils.py

Tests TextProcessor, FileManager, MarkdownHelper, ProgressTracker, and safe_json_write.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.utils import TextProcessor, FileManager, MarkdownHelper, ProgressTracker, safe_json_write


# ============================================================================
# TestTextProcessor
# ============================================================================

class TestTextProcessor:

    def test_count_words_simple_text(self):
        assert TextProcessor.count_words("hello world foo bar") == 4

    def test_count_words_empty_string(self):
        assert TextProcessor.count_words("") == 0

    def test_count_words_whitespace_only(self):
        assert TextProcessor.count_words("   \n\t  ") == 0

    def test_count_words_strips_markdown(self):
        text = "## Header\n\n**bold** and *italic* words"
        count = TextProcessor.count_words(text)
        # "Header bold and italic words" = 5
        assert count == 5

    def test_strip_markdown_removes_headers(self):
        result = TextProcessor.strip_markdown("## Chapter 1\n\nSome text")
        assert not result.startswith("#")
        assert "Chapter 1" in result

    def test_strip_markdown_removes_bold(self):
        result = TextProcessor.strip_markdown("**bold text**")
        assert result == "bold text"

    def test_strip_markdown_removes_italic(self):
        result = TextProcessor.strip_markdown("*italic text*")
        assert result == "italic text"

    def test_strip_markdown_removes_underscore_formatting(self):
        assert "bold" in TextProcessor.strip_markdown("__bold__")
        assert "italic" in TextProcessor.strip_markdown("_italic_")

    def test_strip_markdown_removes_links_keeps_text(self):
        result = TextProcessor.strip_markdown("[click here](https://example.com)")
        assert "click here" in result
        assert "https" not in result

    def test_strip_markdown_removes_images(self):
        result = TextProcessor.strip_markdown("![alt](image.png)")
        assert "image.png" not in result
        assert "![" not in result

    def test_strip_markdown_removes_code_blocks(self):
        result = TextProcessor.strip_markdown("```python\ncode\n```")
        assert "```" not in result

    def test_strip_markdown_removes_inline_code(self):
        result = TextProcessor.strip_markdown("use `code` here")
        assert "`" not in result
        assert "code" in result

    def test_strip_markdown_removes_list_markers(self):
        result = TextProcessor.strip_markdown("- item 1\n* item 2\n+ item 3")
        assert "item 1" in result
        assert not any(line.strip().startswith("-") for line in result.split("\n") if line.strip())

    def test_strip_markdown_removes_blockquotes(self):
        result = TextProcessor.strip_markdown("> quoted text")
        assert "quoted text" in result
        assert ">" not in result

    def test_estimate_reading_time_short_text(self):
        # 160 words at 160 wpm = 1 minute
        text = " ".join(["word"] * 160)
        hours, minutes = TextProcessor.estimate_reading_time(text)
        assert hours == 0
        assert minutes == 1

    def test_estimate_reading_time_long_text(self):
        # 19200 words at 160 wpm = 120 minutes = 2 hours
        text = " ".join(["word"] * 19200)
        hours, minutes = TextProcessor.estimate_reading_time(text)
        assert hours == 2
        assert minutes == 0

    def test_estimate_reading_time_custom_wpm(self):
        text = " ".join(["word"] * 200)
        hours, minutes = TextProcessor.estimate_reading_time(text, words_per_minute=200)
        assert hours == 0
        assert minutes == 1

    def test_calculate_compression_ratio_normal(self):
        # 10000 words, want 2h (120min) at 160wpm = 19200 target words
        ratio = TextProcessor.calculate_compression_ratio(2, 0, 10000)
        # 19200/10000 = 1.92, clamped to 0.9
        assert ratio == 0.9

    def test_calculate_compression_ratio_zero_words(self):
        ratio = TextProcessor.calculate_compression_ratio(1, 0, 0)
        assert ratio == 1.0

    def test_calculate_compression_ratio_clamped_min(self):
        # Very few target words relative to total
        ratio = TextProcessor.calculate_compression_ratio(0, 1, 100000)
        assert ratio >= 0.1

    def test_calculate_compression_ratio_clamped_max(self):
        # Target words > total words
        ratio = TextProcessor.calculate_compression_ratio(10, 0, 100)
        assert ratio <= 0.9

    def test_clean_gutenberg_text_standard_markers(self):
        text = (
            "Header stuff\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Actual content here.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Footer stuff"
        )
        result = TextProcessor.clean_gutenberg_text(text)
        assert "Actual content here." in result
        assert "Header stuff" not in result
        assert "Footer stuff" not in result

    def test_clean_gutenberg_text_no_markers(self):
        text = "Just a normal book with no markers."
        result = TextProcessor.clean_gutenberg_text(text)
        assert result == text

    def test_clean_gutenberg_text_case_insensitive(self):
        text = (
            "*** start of this project gutenberg ebook ***\n"
            "Content\n"
            "*** end of this project gutenberg ebook ***"
        )
        result = TextProcessor.clean_gutenberg_text(text)
        assert "Content" in result


# ============================================================================
# TestFileManager
# ============================================================================

class TestFileManager:

    def test_sanitize_filename_special_chars(self):
        result = FileManager.sanitize_filename("Hello! World? #$%")
        assert "!" not in result
        assert "?" not in result
        assert "#" not in result

    def test_sanitize_filename_spaces_to_underscores(self):
        result = FileManager.sanitize_filename("Hello World")
        assert " " not in result
        assert "_" in result

    def test_sanitize_filename_lowercase(self):
        result = FileManager.sanitize_filename("UPPER CASE")
        assert result == result.lower()

    def test_sanitize_filename_leading_trailing_underscores(self):
        result = FileManager.sanitize_filename("__test__")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_generate_filename_with_timestamp(self):
        result = FileManager.generate_filename(
            "Test Book", "Modern English", "zongwei/gemma3-translator:4b"
        )
        assert result.endswith(".md")
        assert "modern_english" in result
        assert "4b" in result

    def test_generate_filename_without_timestamp(self):
        result = FileManager.generate_filename(
            "Test Book", "English", "model:4b", include_timestamp=False
        )
        parts = result.replace(".md", "").split("_")
        # Should not have a YYYYMMDD-looking segment
        assert not any(len(p) == 8 and p.isdigit() for p in parts)

    def test_generate_filename_model_version_extraction(self):
        result = FileManager.generate_filename(
            "Book", "English", "zongwei/gemma3-translator:4b",
            include_timestamp=False
        )
        assert "4b" in result

    def test_get_file_hash_md5(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        result = FileManager.get_file_hash(str(test_file), "md5")
        assert len(result) == 32  # MD5 hex digest length

    def test_get_file_hash_sha256(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        result = FileManager.get_file_hash(str(test_file), "sha256")
        assert len(result) == 64  # SHA256 hex digest length

    def test_ensure_directory(self, temp_dir):
        new_dir = str(temp_dir / "sub" / "deep")
        result = FileManager.ensure_directory(new_dir)
        assert result.exists()
        assert result.is_dir()


# ============================================================================
# TestMarkdownHelper
# ============================================================================

class TestMarkdownHelper:

    def test_extract_title_from_h1(self):
        text = "# My Book Title\n\nSome content"
        assert MarkdownHelper.extract_title(text) == "My Book Title"

    def test_extract_title_none_when_missing(self):
        text = "No header here\nJust text"
        assert MarkdownHelper.extract_title(text) is None

    def test_extract_headers_multiple_levels(self):
        text = "# Title\n## Chapter 1\n### Section 1.1\n## Chapter 2"
        headers = MarkdownHelper.extract_headers(text)
        assert len(headers) == 4
        assert headers[0] == (1, "Title")
        assert headers[1] == (2, "Chapter 1")
        assert headers[2] == (3, "Section 1.1")
        assert headers[3] == (2, "Chapter 2")

    def test_create_table_of_contents(self):
        text = "# Book\n## Chapter 1\n## Chapter 2"
        toc = MarkdownHelper.create_table_of_contents(text)
        assert "Chapter 1" in toc
        assert "Chapter 2" in toc
        assert "[Chapter 1]" in toc

    def test_create_table_of_contents_empty(self):
        text = "No headers here"
        toc = MarkdownHelper.create_table_of_contents(text)
        assert toc == ""


# ============================================================================
# TestProgressTracker
# ============================================================================

class TestProgressTracker:

    def test_format_time_seconds(self):
        assert ProgressTracker._format_time(30) == "30s"

    def test_format_time_minutes(self):
        assert ProgressTracker._format_time(90) == "1m 30s"

    def test_format_time_hours(self):
        assert ProgressTracker._format_time(3660) == "1h 1m"


# ============================================================================
# TestSafeJsonWrite
# ============================================================================

class TestSafeJsonWrite:

    def test_writes_valid_json(self, temp_dir):
        path = temp_dir / "test.json"
        data = {"key": "value", "number": 42}
        safe_json_write(path, data)
        loaded = json.loads(path.read_text())
        assert loaded == data

    def test_no_tmp_file_remains(self, temp_dir):
        path = temp_dir / "test.json"
        safe_json_write(path, {"a": 1})
        tmp_path = path.with_suffix('.json.tmp')
        assert not tmp_path.exists()

    def test_unicode_content(self, temp_dir):
        path = temp_dir / "test.json"
        data = {"text": "Caf\u00e9 \u2603 \u00fc\u00f6\u00e4"}
        safe_json_write(path, data)
        loaded = json.loads(path.read_text(encoding='utf-8'))
        assert loaded["text"] == "Caf\u00e9 \u2603 \u00fc\u00f6\u00e4"

    def test_path_as_string(self, temp_dir):
        path = str(temp_dir / "test.json")
        safe_json_write(path, {"a": 1})
        assert Path(path).exists()

    def test_overwrites_existing_file(self, temp_dir):
        path = temp_dir / "test.json"
        safe_json_write(path, {"v": 1})
        safe_json_write(path, {"v": 2})
        loaded = json.loads(path.read_text())
        assert loaded["v"] == 2
