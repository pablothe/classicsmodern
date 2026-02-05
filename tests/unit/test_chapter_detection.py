#!/usr/bin/env python3
"""
Unit Tests for Chapter Detection

Tests the chapter detection functionality used across the codebase.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from book_preprocessor import ChapterDetector


class TestChapterDetector:
    """Test suite for ChapterDetector class"""

    def test_detect_roman_numeral_chapters(self, chapter_patterns):
        """Test detection of Roman numeral chapter format"""
        text = "\n\n".join(chapter_patterns['roman_numerals'])
        detector = ChapterDetector(text, "test.md")

        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 3
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2
        assert chapters[2]['number'] == 3
        assert "Down the Rabbit-Hole" in chapters[0]['marker']

    def test_detect_numbered_list_chapters(self, chapter_patterns):
        """Test detection of numbered list chapter format"""
        text = "\n\n".join(chapter_patterns['numbered_list'])
        detector = ChapterDetector(text, "test.md")

        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 3
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2
        assert chapters[2]['number'] == 3
        assert "Horror in Clay" in chapters[0]['marker']

    def test_detect_markdown_header_chapters(self, chapter_patterns):
        """Test detection of markdown header chapter format"""
        text = "\n\n".join(chapter_patterns['markdown_headers'])
        detector = ChapterDetector(text, "test.md")

        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 3
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2
        assert "Beginning" in chapters[0]['marker']

    def test_detect_mixed_chapter_formats(self, chapter_patterns):
        """Test detection with mixed chapter formats"""
        text = "\n\n".join(chapter_patterns['mixed_formats'])
        detector = ChapterDetector(text, "test.md")

        chapters = detector.detect_chapters_in_content()

        # Should detect all three despite different formats
        assert len(chapters) == 3

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
        detector = ChapterDetector(text, "test.md")
        validation = detector.validate_chapter_sequence()

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
        detector = ChapterDetector(text, "test.md")
        validation = detector.validate_chapter_sequence()

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
        detector = ChapterDetector(text, "test.md")
        validation = detector.validate_chapter_sequence()

        assert validation['valid'] is False
        assert 2 in validation['duplicates']

    def test_detect_table_of_contents(self, sample_book_content):
        """Test TOC detection in book"""
        detector = ChapterDetector(sample_book_content, "test.md")
        toc = detector.detect_toc()

        assert len(toc) > 0
        # Should detect markdown link format
        assert any("Rabbit-Hole" in entry for entry in toc)

    def test_no_chapters_detected(self):
        """Test when no chapters are present"""
        text = """
# Just a Title

Some content without any chapters.

More content here.

The end.
"""
        detector = ChapterDetector(text, "test.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 0

    def test_chapter_count_matches_toc(self, sample_book_content):
        """Test that chapter count matches TOC entries"""
        detector = ChapterDetector(sample_book_content, "test.md")

        toc = detector.detect_toc()
        chapters = detector.detect_chapters_in_content()

        # TOC and content should have same number of chapters
        assert len(toc) == len(chapters)

    def test_detect_chapters_in_alice_sample(self, sample_book_clean):
        """Test chapter detection on Alice sample fixture"""
        with open(sample_book_clean, 'r') as f:
            text = f.read()

        detector = ChapterDetector(text, "alice_sample.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 3
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2
        assert chapters[2]['number'] == 3

        # Validate sequence
        validation = detector.validate_chapter_sequence()
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
        detector = ChapterDetector(text, "test.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 3

    def test_whitespace_tolerance(self):
        """Test that extra whitespace doesn't break detection"""
        text = """
##    CHAPTER   I.    Extra     Spaces

Content.

##CHAPTER II.NoSpaces

Content.
"""
        detector = ChapterDetector(text, "test.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) >= 1  # Should detect at least the first one

    def test_unicode_chapter_titles(self):
        """Test chapter titles with unicode characters"""
        text = """
## CHAPTER I. Café und Bücher

Content with unicode.

## CHAPTER II. 日本語タイトル

Japanese title.
"""
        detector = ChapterDetector(text, "test.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 2
        assert "Café" in chapters[0]['marker'] or "Caf" in chapters[0]['marker']

    def test_very_long_chapter_title(self):
        """Test chapter with extremely long title"""
        long_title = "A" * 500
        text = f"""
## CHAPTER I. {long_title}

Content.
"""
        detector = ChapterDetector(text, "test.md")
        chapters = detector.detect_chapters_in_content()

        assert len(chapters) == 1
        assert len(chapters[0]['marker']) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
