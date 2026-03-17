#!/usr/bin/env python3
"""
Unit tests for lib/translation/deduplicate.py

Tests find_exact_overlap, deduplicate_chunks, and find_translated_chunks.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.translation.deduplicate import find_exact_overlap, deduplicate_chunks, find_translated_chunks


class TestFindExactOverlap:

    def test_exact_overlap_detected(self):
        text1 = "beginning of text overlap words here"
        text2 = "overlap words here continuation of text"
        result = find_exact_overlap(text1, text2)
        assert result == "overlap words here"

    def test_no_overlap_returns_none(self):
        text1 = "completely different text"
        text2 = "nothing in common at all"
        result = find_exact_overlap(text1, text2)
        assert result is None

    def test_partial_overlap(self):
        text1 = "the end of chunk one words"
        text2 = "of chunk one words the start of chunk two"
        result = find_exact_overlap(text1, text2)
        assert result is not None
        assert "of chunk one words" in result

    def test_overlap_max_words_limit(self):
        # Create overlap larger than max_words
        overlap = " ".join(["word"] * 10)
        text1 = f"prefix {overlap}"
        text2 = f"{overlap} suffix"
        result = find_exact_overlap(text1, text2, max_words=5)
        # Should find at most 5-word overlap
        if result:
            assert len(result.split()) <= 5

    def test_single_word_overlap(self):
        text1 = "end with overlap"
        text2 = "overlap start of next"
        result = find_exact_overlap(text1, text2, max_words=5)
        assert result == "overlap"

    def test_empty_strings(self):
        assert find_exact_overlap("", "") is None
        assert find_exact_overlap("text", "") is None
        assert find_exact_overlap("", "text") is None


class TestDeduplicateChunks:

    def test_with_overlap(self, temp_dir):
        # Create chunks with overlap
        chunk1 = temp_dir / "chunk_001.md"
        chunk2 = temp_dir / "chunk_002.md"
        chunk1.write_text("First chunk content overlap text here")
        chunk2.write_text("overlap text here Second chunk content")

        output_dir = temp_dir / "deduped"
        result = deduplicate_chunks([chunk1, chunk2], output_dir)

        assert len(result) == 2
        # Second chunk should have overlap removed
        deduped_content = result[1].read_text()
        assert "Second chunk content" in deduped_content

    def test_no_overlap(self, temp_dir):
        chunk1 = temp_dir / "chunk_001.md"
        chunk2 = temp_dir / "chunk_002.md"
        chunk1.write_text("First chunk content")
        chunk2.write_text("Second chunk content")

        output_dir = temp_dir / "deduped"
        result = deduplicate_chunks([chunk1, chunk2], output_dir)

        assert len(result) == 2
        assert "Second chunk content" in result[1].read_text()

    def test_first_chunk_unchanged(self, temp_dir):
        chunk1 = temp_dir / "chunk_001.md"
        chunk1.write_text("First chunk content only")

        output_dir = temp_dir / "deduped"
        result = deduplicate_chunks([chunk1], output_dir)

        assert len(result) == 1
        assert result[0].read_text() == "First chunk content only"

    def test_output_files_created(self, temp_dir):
        chunk1 = temp_dir / "chunk_001.md"
        chunk2 = temp_dir / "chunk_002.md"
        chunk1.write_text("Content one")
        chunk2.write_text("Content two")

        output_dir = temp_dir / "deduped"
        result = deduplicate_chunks([chunk1, chunk2], output_dir)

        for f in result:
            assert f.exists()
            assert "_DEDUPED" in f.name


class TestFindTranslatedChunks:

    def test_find_chunks_default_pattern(self, temp_dir):
        (temp_dir / "chunk_001_spanish.md").write_text("a")
        (temp_dir / "chunk_002_spanish.md").write_text("b")
        (temp_dir / "other.txt").write_text("c")

        result = find_translated_chunks(temp_dir, "*_spanish.md")
        assert len(result) == 2

    def test_find_chunks_excludes_deduped(self, temp_dir):
        (temp_dir / "chunk_001_spanish.md").write_text("a")
        (temp_dir / "chunk_001_spanish_DEDUPED.md").write_text("b")

        result = find_translated_chunks(temp_dir, "*_spanish*.md")
        # Should exclude the DEDUPED file
        names = [f.name for f in result]
        assert not any("DEDUPED" in n for n in names)

    def test_sorted_order(self, temp_dir):
        (temp_dir / "chunk_003_spanish.md").write_text("c")
        (temp_dir / "chunk_001_spanish.md").write_text("a")
        (temp_dir / "chunk_002_spanish.md").write_text("b")

        result = find_translated_chunks(temp_dir, "*_spanish.md")
        names = [f.name for f in result]
        assert names == sorted(names)
