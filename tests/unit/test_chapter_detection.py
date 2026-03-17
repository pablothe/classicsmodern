#!/usr/bin/env python3
"""
Unit Tests for Chapter Detection

Tests the chapter detection functionality used across the codebase.
"""

import pytest

from lib.book.processor import BookProcessor

# Chapters need 5+ words of content to pass the near-empty filter
FILLER = "This chapter contains enough words to pass the minimum content filter easily."


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
        text = f"""Some preamble text here.

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
        text = f"""# Book Title

## Introduction

{FILLER} Some intro text here with additional words for the content filter.

## Chapter 1: Development

{FILLER} Development content here with more meaningful text to read.

## The Conclusion

{FILLER} Final content here with a proper ending to the story.
"""
        detector = BookProcessor(verbose=False)

        chapters = detector.detect_chapters(text)

        # Should detect all three ## headers (Introduction, Chapter 1, Conclusion)
        assert len(chapters) == 3
        assert chapters[0].detection_type == 'markdown_header'

    def test_validate_sequential_chapters(self):
        """Test sequential chapter validation"""
        text = f"""
## CHAPTER I. First Chapter

{FILLER} The first chapter starts with a detailed introduction to the story.

## CHAPTER II. Second Chapter

{FILLER} The second chapter continues with more exciting developments.

## CHAPTER III. Third Chapter

{FILLER} The third chapter wraps up the narrative arc beautifully.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)
        validation = detector.validate_chapter_sequence(chapters)

        assert validation['valid'] is True
        assert len(validation['missing']) == 0
        assert len(validation['duplicates']) == 0

    def test_detect_missing_chapters(self):
        """Test detection of missing chapters in sequence"""
        text = f"""
## CHAPTER I. First Chapter

{FILLER} The story begins here with plenty of interesting details.

## CHAPTER III. Third Chapter

{FILLER} We skipped chapter two and jumped straight to chapter three.

## CHAPTER IV. Fourth Chapter

{FILLER} The fourth chapter continues the story after the gap.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)
        validation = detector.validate_chapter_sequence(chapters)

        assert validation['valid'] is False
        assert 2 in validation['missing']

    def test_detect_duplicate_chapters(self):
        """Test detection of duplicate chapter numbers"""
        text = f"""
## CHAPTER I. First Chapter

{FILLER} The first chapter introduces the main characters in detail.

## CHAPTER II. Second Chapter

{FILLER} The second chapter develops the plot with many twists.

## CHAPTER II. Another Second Chapter

{FILLER} This duplicate chapter has the same number as the previous one.
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

Some short content.

More short content.

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
        text = f"""
## chapter i. lowercase

{FILLER} The lowercase chapter has content with enough words to be valid.

## CHAPTER II. UPPERCASE

{FILLER} The uppercase chapter also has content with enough words here.

## Chapter III. Mixed Case

{FILLER} The mixed case chapter rounds out our test with more content.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3

    def test_whitespace_tolerance(self):
        """Test that extra whitespace doesn't break detection"""
        text = f"""
##    CHAPTER   I.    Extra     Spaces

{FILLER} Extra whitespace in the header should not prevent chapter detection.

##CHAPTER II.NoSpaces

{FILLER} No spaces between hash and text might or might not be detected.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) >= 1  # Should detect at least the first one

    def test_unicode_chapter_titles(self):
        """Test chapter titles with unicode characters"""
        text = f"""
## CHAPTER I. Café und Bücher

{FILLER} Unicode characters in chapter titles should be handled gracefully.

## CHAPTER II. Japanese Content

{FILLER} Another chapter with a different language reference in the title.
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

{FILLER} Even with an extremely long title the chapter should still be detected.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 1
        assert len(chapters[0].marker) > 0


class TestPriorityChain:
    """Test the 2-step priority chain for chapter detection"""

    def test_markdown_headers_priority_1(self):
        """Priority 1: ## headers are the primary detection method."""
        text = f"""# Test Book

## The Beginning

{FILLER} Content here with enough words to pass the filter easily.

## The Middle

{FILLER} More content here with enough words to be a real chapter.

## The End

{FILLER} Final content here with enough words to complete the story.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].detection_type == 'markdown_header'

    def test_fallback_regex_for_bare_chapter_lines(self):
        """Priority 2: Regex fallback for text without ## headers."""
        text = f"""Some preamble text.

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

    def test_act_scene_fallback(self):
        """Priority 2: Act/Scene patterns for plays."""
        text = f"""A play by Someone.

Act I

{FILLER} The first act opens with a dramatic monologue by the protagonist.

Act II

{FILLER} The second act introduces the conflict and rising tension beautifully.

Act III

{FILLER} The third act brings the resolution and a satisfying conclusion.
"""
        detector = BookProcessor(verbose=False)
        chapters = detector.detect_chapters(text)

        assert len(chapters) == 3
        assert chapters[0].detection_type == 'act_scene'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
