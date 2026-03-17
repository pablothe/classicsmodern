#!/usr/bin/env python3
"""Unit tests for server/text_extractor.py"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.text_extractor import (
    _normalize_language_name, detect_chapter_markers, extract_chapter_text,
    split_into_paragraphs, discover_text_tracks, roman_to_int, find_source_text,
)


class TestNormalizeLanguageName:
    def test_underscore_to_space(self):
        assert _normalize_language_name("modern_english") == "Modern English"

    def test_already_normal(self):
        assert _normalize_language_name("Spanish") == "Spanish"

    def test_lowercase_input(self):
        assert _normalize_language_name("french") == "French"

    def test_multiple_underscores(self):
        assert _normalize_language_name("old_church_slavonic") == "Old Church Slavonic"


class TestRomanToInt:
    def test_basic_numerals(self):
        assert roman_to_int("I") == 1
        assert roman_to_int("V") == 5
        assert roman_to_int("X") == 10
        assert roman_to_int("L") == 50
        assert roman_to_int("C") == 100

    def test_subtractive_notation(self):
        assert roman_to_int("IV") == 4
        assert roman_to_int("IX") == 9
        assert roman_to_int("XL") == 40
        assert roman_to_int("XC") == 90

    def test_compound(self):
        assert roman_to_int("XIV") == 14
        assert roman_to_int("XXIII") == 23

    def test_case_insensitive(self):
        assert roman_to_int("iv") == 4
        assert roman_to_int("xii") == 12


class TestDetectChapterMarkers:
    def test_markdown_chapter_headers(self):
        text = "## CHAPTER I. Down the Rabbit-Hole\n\nContent.\n\n## CHAPTER II. The Pool of Tears\n\nMore."
        chapters = detect_chapter_markers(text)
        assert len(chapters) == 2
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2

    def test_arabic_numeral_chapters(self):
        text = "## Chapter 1: Beginning\n\nText.\n\n## Chapter 2: Middle\n\nMore."
        chapters = detect_chapter_markers(text)
        assert len(chapters) == 2
        assert chapters[0]['number'] == 1

    def test_standalone_roman_chapters(self):
        text = "## I\n\nFirst.\n\n## II\n\nSecond.\n\n## III\n\nThird."
        chapters = detect_chapter_markers(text)
        assert len(chapters) == 3
        assert chapters[2]['number'] == 3

    def test_no_chapters_returns_empty(self):
        text = "Just plain text with no chapter markers."
        chapters = detect_chapter_markers(text)
        assert chapters == []

    def test_gutenberg_italic_chapters(self):
        text = "*1. The Horror in Clay.*\n\nContent here."
        chapters = detect_chapter_markers(text)
        assert len(chapters) == 1
        assert chapters[0]['number'] == 1

    def test_chapter_title_extraction(self):
        text = "## Chapter 1: The Beginning\n\nText."
        chapters = detect_chapter_markers(text)
        assert chapters[0]['title'] == "The Beginning"


class TestExtractChapterText:
    def test_extract_middle_chapter(self):
        text = "## CHAPTER I. First\n\nContent one.\n\n## CHAPTER II. Second\n\nContent two.\n\n## CHAPTER III. Third\n\nContent three."
        chapters = detect_chapter_markers(text)
        chapter_text = extract_chapter_text(text, chapters, 1)
        assert chapter_text is not None
        assert "Content two" in chapter_text
        assert "Content one" not in chapter_text

    def test_extract_last_chapter(self):
        text = "## CHAPTER I. First\n\nContent one.\n\n## CHAPTER II. Last\n\nContent two."
        chapters = detect_chapter_markers(text)
        chapter_text = extract_chapter_text(text, chapters, 1)
        assert "Content two" in chapter_text

    def test_invalid_index_returns_none(self):
        text = "## CHAPTER I. First\n\nContent."
        chapters = detect_chapter_markers(text)
        assert extract_chapter_text(text, chapters, 5) is None
        assert extract_chapter_text(text, chapters, -1) is None


class TestSplitIntoParagraphs:
    def test_double_newline_split(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        paragraphs = split_into_paragraphs(text)
        assert len(paragraphs) == 3
        assert paragraphs[0]['text'] == "First paragraph."

    def test_skip_empty_paragraphs(self):
        text = "Content.\n\n\n\n\n\nMore content."
        paragraphs = split_into_paragraphs(text)
        assert len(paragraphs) == 2

    def test_with_manifest_paragraphs(self):
        text = "First paragraph.Second paragraph."
        manifest_paras = [
            {'index': 0, 'para_id': 'ch01_p001', 'char_start': 0, 'char_end': 16},
            {'index': 1, 'para_id': 'ch01_p002', 'char_start': 16, 'char_end': 33},
        ]
        paragraphs = split_into_paragraphs(text, manifest_paras)
        assert len(paragraphs) == 2
        assert paragraphs[0]['para_id'] == 'ch01_p001'

    def test_without_manifest_sequential_ids(self):
        text = "Para one.\n\nPara two."
        paragraphs = split_into_paragraphs(text)
        assert paragraphs[0]['id'] == 0
        assert paragraphs[1]['id'] == 1


class TestDiscoverTextTracks:
    def test_discover_original_only(self, temp_dir):
        book_dir = temp_dir / "mybook"
        book_dir.mkdir()
        (book_dir / "book.md").write_text("# Book\n\nContent.")

        tracks = discover_text_tracks(book_dir)
        assert len(tracks) == 1
        assert tracks[0]['is_original'] is True

    def test_discover_translations(self, temp_dir):
        book_dir = temp_dir / "mybook"
        book_dir.mkdir()
        (book_dir / "book.md").write_text("# Book\n\nContent.")
        (book_dir / "book_Spanish_20260101_120000.md").write_text("Translated.")

        tracks = discover_text_tracks(book_dir)
        assert len(tracks) == 2
        non_orig = [t for t in tracks if not t['is_original']]
        assert len(non_orig) == 1
        assert non_orig[0]['language'] == 'Spanish'

    def test_deduplication_keeps_latest(self, temp_dir):
        book_dir = temp_dir / "mybook"
        book_dir.mkdir()
        (book_dir / "book.md").write_text("Original.")
        (book_dir / "book_Spanish_20260101_120000.md").write_text("Old translation.")
        (book_dir / "book_Spanish_20260201_120000.md").write_text("New translation.")

        tracks = discover_text_tracks(book_dir)
        spanish_tracks = [t for t in tracks if t.get('language') == 'Spanish']
        assert len(spanish_tracks) == 1  # Deduplicated

    def test_nonexistent_dir(self):
        tracks = discover_text_tracks(Path("/nonexistent/dir"))
        assert tracks == []


class TestFindSourceText:
    def test_finds_book_md(self, temp_dir):
        book_dir = temp_dir / "mybook"
        book_dir.mkdir()
        (book_dir / "book.md").write_text("Content.")
        assert find_source_text(book_dir) is not None

    def test_no_source_returns_none(self, temp_dir):
        book_dir = temp_dir / "empty"
        book_dir.mkdir()
        assert find_source_text(book_dir) is None

    def test_nonexistent_dir_returns_none(self):
        assert find_source_text(Path("/nonexistent")) is None
