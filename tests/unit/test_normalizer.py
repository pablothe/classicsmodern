#!/usr/bin/env python3
"""
Unit tests for lib/book/normalizer.py

Tests MarkdownNormalizer: anchor removal, chapter header normalization,
Roman→Arabic conversion, whitespace normalization.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.book.normalizer import MarkdownNormalizer, normalize_markdown


class TestStripAnchorTags:

    def test_curly_brace_anchor(self):
        n = MarkdownNormalizer()
        result = n._strip_anchor_tags("## Chapter 1 {#chapter-1}")
        assert "{#" not in result
        assert "Chapter 1" in result

    def test_html_id_anchor(self):
        n = MarkdownNormalizer()
        result = n._strip_anchor_tags('<a id="ch1"></a>Chapter 1')
        assert "<a" not in result
        assert "Chapter 1" in result

    def test_html_name_anchor(self):
        n = MarkdownNormalizer()
        result = n._strip_anchor_tags('<a name="ch1"></a>Chapter 1')
        assert "<a" not in result

    def test_span_id_anchor(self):
        n = MarkdownNormalizer()
        result = n._strip_anchor_tags('<span id="ch1"></span>Chapter 1')
        assert "<span" not in result
        assert "Chapter 1" in result

    def test_no_anchors_unchanged(self):
        n = MarkdownNormalizer()
        text = "Just plain text"
        result = n._strip_anchor_tags(text)
        assert result.strip() == text


class TestNormalizeChapterHeader:

    def test_numbered_header(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## 1. The Beginning")
        assert result == "## Chapter 1: The Beginning"

    def test_numbered_with_colon(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## 3: The End")
        assert result == "## Chapter 3: The End"

    def test_roman_header(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## IV. The Middle")
        assert result == "## Chapter 4: The Middle"

    def test_roman_with_colon(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## X: Discovery")
        assert result == "## Chapter 10: Discovery"

    def test_already_chapter_no_double_transform(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## Chapter 1: Title")
        # Should not become "## Chapter Chapter 1: Title"
        assert result.count("Chapter") == 1

    def test_chapter_cleanup_spacing(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## Chapter 1 : Title")
        assert "1:" in result or "1: " in result

    def test_chapter_roman_to_arabic_conversion(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## CHAPTER III: The Voyage")
        assert "3" in result

    def test_anchor_stripped_from_header(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## Chapter 1: Title {#chapter-1}")
        assert "{#" not in result

    def test_part_keyword_preserved(self):
        n = MarkdownNormalizer()
        result = n._normalize_chapter_header("## 1. Part One Content")
        # "Part" in the title should not prevent transformation
        # but check it doesn't double-prefix
        assert "Part" in result


class TestRomanToArabic:

    def test_basic_values(self):
        n = MarkdownNormalizer()
        assert n._roman_to_arabic("I") == 1
        assert n._roman_to_arabic("V") == 5
        assert n._roman_to_arabic("X") == 10
        assert n._roman_to_arabic("L") == 50
        assert n._roman_to_arabic("C") == 100

    def test_compound_values(self):
        n = MarkdownNormalizer()
        assert n._roman_to_arabic("IV") == 4
        assert n._roman_to_arabic("IX") == 9
        assert n._roman_to_arabic("XIV") == 14
        assert n._roman_to_arabic("XXV") == 25

    def test_invalid_returns_none(self):
        n = MarkdownNormalizer()
        assert n._roman_to_arabic("INVALID") is None
        assert n._roman_to_arabic("ABC") is None

    def test_case_insensitive(self):
        n = MarkdownNormalizer()
        assert n._roman_to_arabic("iv") == 4
        assert n._roman_to_arabic("xii") == 12


class TestNormalizeWhitespace:

    def test_trailing_whitespace_removed(self):
        n = MarkdownNormalizer()
        result = n._normalize_whitespace("hello   \nworld  ")
        lines = result.split("\n")
        for line in lines:
            assert line == line.rstrip()

    def test_excessive_newlines_collapsed(self):
        n = MarkdownNormalizer()
        result = n._normalize_whitespace("first\n\n\n\n\nsecond")
        assert "\n\n\n" not in result
        assert "first\n\nsecond" in result

    def test_sentence_spacing_fixed(self):
        n = MarkdownNormalizer()
        result = n._normalize_whitespace("End.Start")
        assert "End. Start" in result


class TestNormalizeFullDocument:

    def test_full_normalization(self):
        doc = "## I. The Beginning {#ch1}\n\nSome text.\n\n\n\n## II. The End"
        result = normalize_markdown(doc)
        assert "{#" not in result
        assert "Chapter 1:" in result
        assert "Chapter 2:" in result
        assert "\n\n\n" not in result

    def test_no_changes_needed(self):
        doc = "## Chapter 1: Title\n\nClean text here."
        result = normalize_markdown(doc)
        assert "Chapter 1: Title" in result

    def test_verbose_logging(self):
        n = MarkdownNormalizer(verbose=False)
        result = n.normalize("## I. Title")
        assert len(n.transformations) >= 1

    def test_convenience_function(self):
        result = normalize_markdown("## 1. Test")
        assert "Chapter 1:" in result
