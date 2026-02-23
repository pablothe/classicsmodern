#!/usr/bin/env python3
"""
Unit Tests for Chapter Detection

Tests the chapter detection functionality used across the codebase.
"""

import json
import pytest
from pathlib import Path

from lib.book.processor import BookProcessor


class TestChapterDetector:
    """Test suite for ChapterDetector class"""

    def test_detect_roman_numeral_chapters(self, chapter_patterns):
        """Test detection of Roman numeral chapter format (## headers)"""
        text = "\n\n".join(chapter_patterns['roman_numerals'])
        detector = BookProcessor(verbose=False)

        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].number == 1
        assert chapters[1].number == 2
        assert chapters[2].number == 3
        assert "Down the Rabbit-Hole" in chapters[0].marker

    def test_detect_fallback_chapter_keyword(self):
        """Test detection of bare Chapter N lines via fallback regex"""
        text = """Some preamble text here.

Chapter I. The Horror in Clay

Content of the first chapter with enough words to be meaningful and real.

Chapter II. The Tale of Inspector Legrasse

Content of the second chapter with enough words to be meaningful.

Chapter III. The Madness from the Sea

Content of the third chapter with enough words to be meaningful.
"""
        detector = BookProcessor(verbose=False)

        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].number == 1
        assert chapters[1].number == 2
        assert chapters[2].number == 3
        assert chapters[0].detection_type == 'chapter_keyword'

    def test_detect_markdown_header_chapters(self, chapter_patterns):
        """Test detection of markdown header chapter format"""
        text = "\n\n".join(chapter_patterns['markdown_headers'])
        detector = BookProcessor(verbose=False)

        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].number == 1
        assert chapters[1].number == 2
        assert "Beginning" in chapters[0].marker

    def test_detect_multiple_markdown_headers(self):
        """Test detection with multiple ## header styles"""
        text = """# Book Title

## Introduction

Some intro text here.

## Chapter 1: Development

Development content here.

## The Conclusion

Final content here.
"""
        detector = BookProcessor(verbose=False)

        chapters = detector.detect_chapters(text)

        # Should detect all three ## headers (Introduction, Chapter 1, Conclusion)
        assert len(chapters) == 3
        assert chapters[0].detection_type == 'markdown_header'

    def test_validate_sequential_chapters(self):
        """Test sequential chapter validation"""
        text = """
## CHAPTER I. First Chapter

Content here.

## CHAPTER II. Second Chapter

More content.

## CHAPTER III. Third Chapter

Final content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)
        validation = detector.validate_chapter_sequence(chapters)

        assert validation['valid'] is True
        assert len(validation['missing']) == 0
        assert len(validation['duplicates']) == 0

    def test_detect_missing_chapters(self):
        """Test detection of missing chapters in sequence"""
        text = """
## CHAPTER I. First Chapter

Content here.

## CHAPTER III. Third Chapter

Skipped chapter 2!

## CHAPTER IV. Fourth Chapter

More content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)
        validation = detector.validate_chapter_sequence(chapters)

        assert validation['valid'] is False
        assert 2 in validation['missing']

    def test_detect_duplicate_chapters(self):
        """Test detection of duplicate chapter numbers"""
        text = """
## CHAPTER I. First Chapter

Content here.

## CHAPTER II. Second Chapter

Content.

## CHAPTER II. Another Second Chapter

Duplicate!
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)
        validation = detector.validate_chapter_sequence(chapters)

        assert validation['valid'] is False
        assert 2 in validation['duplicates']

    def test_detect_table_of_contents(self, sample_book_content):
        """Test TOC detection in book"""
        detector = BookProcessor(verbose=False)
        toc = detector.detect_toc(sample_book_content)

        assert len(toc) > 0
        # Should detect markdown link format
        assert any("Rabbit-Hole" in entry.get('title', '') for entry in toc)

    def test_no_chapters_detected(self):
        """Test when no chapters are present"""
        text = """
# Just a Title

Some content without any chapters.

More content here.

The end.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 0

    def test_chapter_count_matches_toc(self, sample_book_content):
        """Test that chapter count matches TOC entries"""
        detector = BookProcessor(verbose=False)

        toc = detector.detect_toc(sample_book_content)
        chapters = detector.detect_chapters(sample_book_content)

        # TOC and content should have same number of chapters
        assert len(toc) == len(chapters)

    def test_detect_chapters_in_alice_sample(self, sample_book_clean):
        """Test chapter detection on Alice sample fixture"""
        with open(sample_book_clean, 'r') as f:
            text = f.read()

        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].number == 1
        assert chapters[1].number == 2
        assert chapters[2].number == 3

        # Validate sequence
        validation = detector.validate_chapter_sequence(chapters)
        assert validation['valid'] is True


class TestChapterEdgeCases:
    """Test edge cases and unusual chapter formats"""

    def test_case_insensitive_detection(self):
        """Test that chapter detection is case-insensitive"""
        text = """
## chapter i. lowercase

Content.

## CHAPTER II. UPPERCASE

Content.

## Chapter III. Mixed Case

Content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3

    def test_whitespace_tolerance(self):
        """Test that extra whitespace doesn't break detection"""
        text = """
##    CHAPTER   I.    Extra     Spaces

Content.

##CHAPTER II.NoSpaces

Content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) >= 1  # Should detect at least the first one

    def test_unicode_chapter_titles(self):
        """Test chapter titles with unicode characters"""
        text = """
## CHAPTER I. Café und Bücher

Content with unicode.

## CHAPTER II. Japanese Content

Japanese title.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 2
        assert "Café" in chapters[0].marker or "Caf" in chapters[0].marker

    def test_very_long_chapter_title(self):
        """Test chapter with extremely long title"""
        long_title = "A" * 500
        text = f"""
## CHAPTER I. {long_title}

Content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 1
        assert len(chapters[0].marker) > 0


class TestPriorityChain:
    """Test the 3-step priority chain for chapter detection"""

    def test_gutenberg_json_takes_priority(self, tmp_path):
        """Priority 1: gutenberg_chapters.json should be used when available."""
        book_text = """# Test Book

## Chapter 1. First

Content here with enough words.

## Chapter 2. Second

More content with enough words.
"""
        # Create gutenberg_chapters.json
        gutenberg_data = {
            "source": "gutenberg_html_toc",
            "chapter_count": 2,
            "chapters": [
                {"number": 1, "title": "Chapter 1. First", "original_title": "CHAPITRE I"},
                {"number": 2, "title": "Chapter 2. Second", "original_title": "CHAPITRE II"}
            ]
        }
        json_file = tmp_path / "gutenberg_chapters.json"
        json_file.write_text(json.dumps(gutenberg_data))

        # Also write the book text so the file exists
        book_file = tmp_path / "source.md"
        book_file.write_text(book_text)

        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(book_text, book_dir=tmp_path)

        assert len(chapters) == 2
        assert chapters[0].detection_type == 'gutenberg_json'
        assert chapters[1].detection_type == 'gutenberg_json'

    def test_markdown_headers_when_no_json(self):
        """Priority 2: ## headers should work without gutenberg_chapters.json."""
        text = """# Test Book

## The Beginning

Content here with enough words.

## The Middle

More content here with enough words.

## The End

Final content here with enough words.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].detection_type == 'markdown_header'

    def test_fallback_regex_for_bare_chapter_lines(self):
        """Priority 3: Regex fallback for text without ## headers."""
        text = """Some preamble text.

Chapter I. The First Adventure

Content of chapter one here with enough words to be meaningful.

Chapter II. The Second Adventure

Content of chapter two here with enough words to be meaningful.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 2
        assert chapters[0].detection_type == 'chapter_keyword'

    def test_single_chapter_fallback(self):
        """Last resort: entire text treated as single chapter."""
        # Long text with no chapter markers
        text = "Just a long paragraph. " * 60
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 1
        assert chapters[0].detection_type == 'single_chapter_fallback'

    def test_corrupted_json_falls_through(self, tmp_path):
        """If gutenberg_chapters.json is corrupted, fall through to Priority 2."""
        book_text = """# Test Book

## Chapter 1. First

Content here.

## Chapter 2. Second

More content.
"""
        # Write corrupted JSON
        json_file = tmp_path / "gutenberg_chapters.json"
        json_file.write_text("{invalid json!!")

        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(book_text, book_dir=tmp_path)

        assert len(chapters) == 2
        assert chapters[0].detection_type == 'markdown_header'

    def test_act_scene_fallback(self):
        """Priority 3: Act/Scene patterns for plays."""
        text = """A play by Someone.

Act I

Content of act one.

Act II

Content of act two.

Act III

Content of act three.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].detection_type == 'act_scene'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
