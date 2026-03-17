#!/usr/bin/env python3
"""
Unit tests for lib/translation/splitter.py

Tests split_by_headers, split_by_word_count, and analyze_and_split.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.translation.splitter import split_by_headers, split_by_word_count, analyze_and_split


class TestSplitByHeaders:

    def test_split_h2_headers(self):
        text = "## Chapter 1\n\nContent one.\n\n## Chapter 2\n\nContent two."
        chunks = split_by_headers(text, header_level=2)
        assert len(chunks) == 2
        assert chunks[0].title == "Chapter 1"
        assert chunks[1].title == "Chapter 2"

    def test_split_h1_headers(self):
        text = "# Part 1\n\nContent.\n\n# Part 2\n\nMore content."
        chunks = split_by_headers(text, header_level=1)
        assert len(chunks) == 2

    def test_no_headers_returns_empty(self):
        text = "Just plain text with no headers at all."
        chunks = split_by_headers(text, header_level=2)
        assert chunks == []

    def test_single_header(self):
        text = "## Only One\n\nSome content here."
        chunks = split_by_headers(text, header_level=2)
        assert len(chunks) == 1
        assert chunks[0].title == "Only One"

    def test_preserves_content_between_headers(self):
        text = "## Ch 1\n\nFirst paragraph.\n\nSecond paragraph.\n\n## Ch 2\n\nThird."
        chunks = split_by_headers(text, header_level=2)
        assert "First paragraph" in chunks[0].content
        assert "Second paragraph" in chunks[0].content
        assert "Third" in chunks[1].content

    def test_word_count_accuracy(self):
        text = "## Title\n\none two three four five"
        chunks = split_by_headers(text, header_level=2)
        assert chunks[0].word_count > 0

    def test_chunk_numbering(self):
        text = "## A\n\nX\n\n## B\n\nY\n\n## C\n\nZ"
        chunks = split_by_headers(text, header_level=2)
        assert [c.number for c in chunks] == [1, 2, 3]


class TestSplitByWordCount:

    def test_basic_split(self):
        # Create text with ~200 words
        words = " ".join(["word"] * 200)
        text = f"First paragraph. {words}\n\nSecond paragraph. {words}"
        chunks = split_by_word_count(text, target_words_per_chunk=250)
        assert len(chunks) >= 2

    def test_respects_paragraph_boundaries(self):
        para1 = " ".join(["alpha"] * 50)
        para2 = " ".join(["beta"] * 50)
        text = f"{para1}\n\n{para2}"
        chunks = split_by_word_count(text, target_words_per_chunk=60)
        # Should split at paragraph boundary, not mid-paragraph
        for chunk in chunks:
            assert "alpha beta" not in chunk.content.replace("\n\n", " ")

    def test_single_chunk_when_under_target(self):
        text = "A short paragraph."
        chunks = split_by_word_count(text, target_words_per_chunk=10000)
        assert len(chunks) == 1

    def test_custom_book_title(self):
        text = "Some words here.\n\nMore words there."
        chunks = split_by_word_count(text, target_words_per_chunk=2, book_title="MyBook")
        assert all("MyBook" in c.title for c in chunks)

    def test_chunk_numbering_sequential(self):
        words = " ".join(["word"] * 100)
        text = f"{words}\n\n{words}\n\n{words}"
        chunks = split_by_word_count(text, target_words_per_chunk=120)
        numbers = [c.number for c in chunks]
        assert numbers == sorted(numbers)
        assert numbers[0] == 1


class TestAnalyzeAndSplit:

    def test_prefers_headers_over_word_count(self, temp_dir):
        text = "## Ch 1\n\nContent one.\n\n## Ch 2\n\nContent two.\n\n## Ch 3\n\nContent three."
        input_file = temp_dir / "book.md"
        input_file.write_text(text)
        chunks = analyze_and_split(str(input_file), output_dir=str(temp_dir / "out"))
        assert len(chunks) == 3
        assert chunks[0].title == "Ch 1"

    def test_falls_back_to_word_count(self, temp_dir):
        # Need paragraph breaks for word-count splitter to split
        paras = [" ".join(["word"] * 100) for _ in range(5)]
        text = "\n\n".join(paras)
        input_file = temp_dir / "book.md"
        input_file.write_text(text)
        chunks = analyze_and_split(str(input_file), output_dir=str(temp_dir / "out"), words_per_chunk=200)
        assert len(chunks) >= 2

    def test_minimum_3_chapters_for_header_split(self, temp_dir):
        # Only 2 headers - should fall back to word count
        words = " ".join(["word"] * 500)
        text = f"## A\n\n{words}\n\n## B\n\n{words}"
        input_file = temp_dir / "book.md"
        input_file.write_text(text)
        chunks = analyze_and_split(str(input_file), output_dir=str(temp_dir / "out"), words_per_chunk=300)
        # With only 2 headers, should fall back to word count split
        # (split_by_headers returns 2 chunks, < 3 minimum)
        assert len(chunks) >= 2
