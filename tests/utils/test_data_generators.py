#!/usr/bin/env python3
"""
Test Data Generators

Generate realistic test data for various scenarios:
- Books with specific issues (missing chapters, duplicates)
- Translation chunks with overlaps
- Invalid/corrupted data
- Edge cases
"""

import random
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================================
# Book Generators
# ============================================================================

class BookGenerator:
    """Generate test books with configurable properties."""

    SAMPLE_WORDS = [
        "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
        "Lorem", "ipsum", "dolor", "sit", "amet", "consectetur",
        "alice", "rabbit", "wonderland", "queen", "king", "cheshire",
        "chapter", "story", "tale", "adventure", "journey", "quest"
    ]

    @classmethod
    def generate_valid_book(
        cls,
        title: str = "Valid Test Book",
        author: str = "Test Author",
        num_chapters: int = 3,
        words_per_chapter: int = 100,
        add_toc: bool = True
    ) -> str:
        """Generate a valid, well-formatted book."""
        lines = [
            f"# {title}",
            f"Author: {author}",
            ""
        ]

        if add_toc:
            lines.append("## Table of Contents")
            for i in range(1, num_chapters + 1):
                lines.append(f"{i}. [Chapter {i}](#chapter-{i})")
            lines.append("\n---\n")

        # Generate chapters
        for i in range(1, num_chapters + 1):
            lines.append(f"## CHAPTER {cls._int_to_roman(i)}. Chapter {i} Title")
            lines.append("")
            lines.append(cls._generate_paragraph(words_per_chapter))
            lines.append("")

        return '\n'.join(lines)

    @classmethod
    def generate_book_missing_chapters(
        cls,
        title: str = "Book with Missing Chapters",
        missing_chapters: List[int] = None
    ) -> str:
        """Generate book with missing chapter numbers (e.g., I, III, IV - missing II)."""
        if missing_chapters is None:
            missing_chapters = [2]

        lines = [f"# {title}", ""]

        chapter_numbers = [1, 2, 3, 4, 5]
        for i in chapter_numbers:
            if i not in missing_chapters:
                lines.append(f"## CHAPTER {cls._int_to_roman(i)}")
                lines.append(cls._generate_paragraph(50))
                lines.append("")

        return '\n'.join(lines)

    @classmethod
    def generate_book_duplicate_chapters(
        cls,
        title: str = "Book with Duplicate Chapters",
        duplicate_chapter: int = 2
    ) -> str:
        """Generate book with duplicate chapter numbers."""
        lines = [f"# {title}", ""]

        for i in range(1, 4):
            lines.append(f"## CHAPTER {cls._int_to_roman(i)}")
            lines.append(cls._generate_paragraph(50))
            lines.append("")

            # Add duplicate
            if i == duplicate_chapter:
                lines.append(f"## CHAPTER {cls._int_to_roman(i)} (Duplicate)")
                lines.append(cls._generate_paragraph(50))
                lines.append("")

        return '\n'.join(lines)

    @classmethod
    def generate_book_no_chapters(
        cls,
        title: str = "Book Without Chapters",
        word_count: int = 200
    ) -> str:
        """Generate book with no chapter markers."""
        lines = [
            f"# {title}",
            "",
            cls._generate_paragraph(word_count)
        ]
        return '\n'.join(lines)

    @classmethod
    def generate_book_mixed_chapter_formats(cls) -> str:
        """Generate book with mixed chapter format styles."""
        return """# Mixed Format Book

## CHAPTER I. Roman Numerals

Content for chapter one.

# Chapter 2: Arabic Numbers

Content for chapter two.

3. Numbered List Format

Content for chapter three.

## Part IV

Content for chapter four.
"""

    @classmethod
    def _generate_paragraph(cls, num_words: int) -> str:
        """Generate paragraph with random words."""
        words = [random.choice(cls.SAMPLE_WORDS) for _ in range(num_words)]

        # Break into sentences (every 10-15 words)
        sentences = []
        i = 0
        while i < len(words):
            sentence_length = random.randint(10, 15)
            sentence_words = words[i:i+sentence_length]
            if sentence_words:
                sentence = ' '.join(sentence_words)
                sentence = sentence[0].upper() + sentence[1:] + '.'
                sentences.append(sentence)
            i += sentence_length

        return ' '.join(sentences)

    @classmethod
    def _int_to_roman(cls, num: int) -> str:
        """Convert integer to Roman numeral."""
        val = [
            1000, 900, 500, 400,
            100, 90, 50, 40,
            10, 9, 5, 4,
            1
        ]
        syms = [
            "M", "CM", "D", "CD",
            "C", "XC", "L", "XL",
            "X", "IX", "V", "IV",
            "I"
        ]
        roman_num = ''
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman_num += syms[i]
                num -= val[i]
            i += 1
        return roman_num


# ============================================================================
# Translation Chunk Generators
# ============================================================================

class TranslationChunkGenerator:
    """Generate translation chunks with overlaps for testing deduplication."""

    @classmethod
    def generate_chunks_with_overlap(
        cls,
        num_chunks: int = 3,
        words_per_chunk: int = 100,
        overlap_words: int = 20
    ) -> List[str]:
        """
        Generate translation chunks with intentional overlaps.

        Args:
            num_chunks: Number of chunks to generate
            words_per_chunk: Words per chunk
            overlap_words: Number of overlapping words between chunks

        Returns:
            List of chunk texts with overlaps
        """
        all_words = [f"word{i}" for i in range(words_per_chunk * num_chunks)]

        chunks = []
        for i in range(num_chunks):
            start_idx = i * (words_per_chunk - overlap_words)
            end_idx = start_idx + words_per_chunk

            chunk_words = all_words[start_idx:end_idx]
            chunk_text = ' '.join(chunk_words)
            chunks.append(chunk_text)

        return chunks

    @classmethod
    def generate_chunks_without_overlap(
        cls,
        num_chunks: int = 3,
        words_per_chunk: int = 100
    ) -> List[str]:
        """Generate chunks with no overlaps (clean boundaries)."""
        chunks = []
        for i in range(num_chunks):
            words = [f"chunk{i}_word{j}" for j in range(words_per_chunk)]
            chunks.append(' '.join(words))
        return chunks

    @classmethod
    def generate_chunks_with_exact_duplicate(
        cls,
        duplicate_at_boundary: bool = True
    ) -> List[str]:
        """
        Generate chunks with exact duplicate text for testing deduplication.

        Args:
            duplicate_at_boundary: If True, duplicate is at chunk boundary.
                                   If False, duplicate is in middle of chunk.

        Returns:
            List of chunks with exact duplicates
        """
        if duplicate_at_boundary:
            # Classic overlap scenario
            overlap_text = "this is the exact duplicate text at the boundary"
            chunk1 = f"Beginning of chunk one. {overlap_text}"
            chunk2 = f"{overlap_text} Continuation in chunk two."
            return [chunk1, chunk2]
        else:
            # Duplicate in middle (shouldn't be removed)
            repeated_text = "this phrase appears twice in same chunk"
            chunk1 = f"Start. {repeated_text} Middle. {repeated_text} End."
            chunk2 = "This is the second chunk without duplicates."
            return [chunk1, chunk2]


# ============================================================================
# Invalid/Corrupted Data Generators
# ============================================================================

class CorruptedDataGenerator:
    """Generate invalid or corrupted data for error handling tests."""

    @classmethod
    def generate_empty_book(cls) -> str:
        """Generate empty book (should fail validation)."""
        return ""

    @classmethod
    def generate_too_short_book(cls) -> str:
        """Generate book that's too short (<100 words)."""
        return "# Short Book\n\nThis book is way too short."

    @classmethod
    def generate_book_with_excessive_whitespace(cls) -> str:
        """Generate book with excessive empty lines."""
        lines = ["# Book Title", ""]
        # Add 100 empty lines
        lines.extend([""] * 100)
        lines.append("## CHAPTER I")
        lines.extend([""] * 50)
        lines.append("Some content.")
        return '\n'.join(lines)

    @classmethod
    def generate_book_with_special_characters(cls) -> str:
        """Generate book with unicode and special characters."""
        return """# Book with Spëcïål Çhārāctêrs

## CHAPTER I. Café und Bücher

Content with émojis 🎭 and unicode ñ, ü, é.

## CHAPTER II. 日本語タイトル

Japanese content: これはテストです。

## CHAPTER III. Emoji Chapter 🚀

More content here! #hashtag @mention
"""

    @classmethod
    def generate_book_with_very_long_lines(cls) -> str:
        """Generate book with extremely long lines (>10k chars)."""
        long_line = "word " * 5000  # ~25k chars
        return f"# Long Line Book\n\n## CHAPTER I\n\n{long_line}"

    @classmethod
    def generate_malformed_markdown(cls) -> str:
        """Generate book with malformed markdown."""
        return """# Title

##CHAPTER I (missing space)

######## Too many hashes

** Bold without closing

[Link without closing paren(

Image without closing: ![alt](url
"""


# ============================================================================
# Gutenberg-Specific Generators
# ============================================================================

class GutenbergDataGenerator:
    """Generate books with various Gutenberg boilerplate patterns."""

    @classmethod
    def generate_with_standard_boilerplate(cls, title: str = "Test Book") -> str:
        """Generate book with standard Gutenberg header/footer."""
        return f"""The Project Gutenberg EBook of {title}

*** START OF THE PROJECT GUTENBERG EBOOK {title.upper()} ***

Transcriber's note: Various inconsistencies in spelling have been retained.

# {title}

## CHAPTER I

This is the actual content.

## CHAPTER II

More content here.

*** END OF THE PROJECT GUTENBERG EBOOK {title.upper()} ***

End of the Project Gutenberg EBook of {title}
www.gutenberg.org
"""

    @classmethod
    def generate_with_partial_boilerplate(cls) -> str:
        """Generate book with incomplete boilerplate (testing edge cases)."""
        return """The Project Gutenberg EBook of Test Book

*** START OF THE PROJECT GUTENBERG

## CHAPTER I

Content with incomplete header marker.

(No end marker)
"""

    @classmethod
    def generate_without_boilerplate(cls) -> str:
        """Generate clean book without Gutenberg boilerplate."""
        return """# Clean Book

## CHAPTER I

This book has no Gutenberg boilerplate.

## CHAPTER II

It should pass validation without cleanup.
"""


# ============================================================================
# Edge Case Generators
# ============================================================================

class EdgeCaseGenerator:
    """Generate edge cases for robust testing."""

    @classmethod
    def generate_book_with_numeric_only_chapters(cls) -> str:
        """Chapters using only numbers (no Roman numerals)."""
        return """# Numeric Chapters

## Chapter 1

Content.

## Chapter 2

Content.

## Chapter 10

Content.

## Chapter 100

Content.
"""

    @classmethod
    def generate_book_with_unnumbered_chapters(cls) -> str:
        """Chapters without numbers."""
        return """# Unnumbered Chapters

## Introduction

Content.

## The Beginning

Content.

## The Middle

Content.

## The End

Content.
"""

    @classmethod
    def generate_single_chapter_book(cls) -> str:
        """Book with only one chapter."""
        return """# Single Chapter Book

## CHAPTER I

This book has only one chapter. This is useful for testing
edge cases where chapter count is minimal.
"""

    @classmethod
    def generate_book_with_inconsistent_formatting(cls) -> str:
        """Book with inconsistent chapter formatting."""
        return """# Inconsistent Book

## CHAPTER   I.    Extra     Spaces

Content.

##CHAPTER II.NoSpaces

Content.

##     CHAPTER     III     .     Weird Spacing

Content.
"""
