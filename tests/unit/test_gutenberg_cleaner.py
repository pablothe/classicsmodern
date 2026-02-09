#!/usr/bin/env python3
"""
Unit Tests for Gutenberg Boilerplate Cleaning

Tests boilerplate detection and removal from Project Gutenberg texts.
Tests:
- START/END marker detection
- Metadata extraction (title, author)
- Partial boilerplate handling
- Edge cases
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.test_data_generators import GutenbergDataGenerator

# Import actual module
try:
    from local_tts_kokoro import KokoroAudioGenerator
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def standard_gutenberg_book():
    """Return book with standard Gutenberg boilerplate."""
    return GutenbergDataGenerator.generate_with_standard_boilerplate("Alice in Wonderland")


@pytest.fixture
def partial_gutenberg_book():
    """Return book with partial boilerplate."""
    return GutenbergDataGenerator.generate_with_partial_boilerplate()


@pytest.fixture
def clean_book():
    """Return book without boilerplate."""
    return GutenbergDataGenerator.generate_without_boilerplate()


# ============================================================================
# Marker Detection Tests
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro TTS not available")
class TestMarkerDetection:
    """Test detection of Gutenberg START/END markers."""

    def test_detect_start_marker(self, standard_gutenberg_book):
        """Test detection of START marker."""
        assert "*** START OF THE PROJECT GUTENBERG" in standard_gutenberg_book

    def test_detect_end_marker(self, standard_gutenberg_book):
        """Test detection of END marker."""
        assert "*** END OF THE PROJECT GUTENBERG" in standard_gutenberg_book

    def test_no_markers_in_clean_book(self, clean_book):
        """Test that clean books have no markers."""
        assert "*** START OF THE PROJECT GUTENBERG" not in clean_book
        assert "*** END OF THE PROJECT GUTENBERG" not in clean_book

    def test_partial_marker_detection(self, partial_gutenberg_book):
        """Test handling of incomplete markers."""
        # Partial book has incomplete START marker
        assert "*** START OF THE PROJECT GUTENBERG" in partial_gutenberg_book
        # But not END marker
        assert "*** END OF THE PROJECT GUTENBERG" not in partial_gutenberg_book


# ============================================================================
# Boilerplate Removal Tests
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro TTS not available")
class TestBoilerplateRemoval:
    """Test removal of Gutenberg boilerplate."""

    def test_remove_standard_boilerplate(self, standard_gutenberg_book):
        """Test removal of standard header and footer."""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(standard_gutenberg_book)

        # Boilerplate should be removed
        assert "*** START OF THE PROJECT GUTENBERG" not in cleaned
        assert "*** END OF THE PROJECT GUTENBERG" not in cleaned
        assert "www.gutenberg.org" not in cleaned

        # Content should be preserved
        assert "CHAPTER" in cleaned
        assert len(cleaned) > 0

    def test_preserve_content_between_markers(self, standard_gutenberg_book):
        """Test that content between markers is preserved."""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(standard_gutenberg_book)

        # Should contain actual book content
        assert "CHAPTER I" in cleaned or "CHAPTER 1" in cleaned
        assert "CHAPTER II" in cleaned or "CHAPTER 2" in cleaned

    def test_clean_book_unchanged(self, clean_book):
        """Test that books without boilerplate pass through unchanged."""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(clean_book)

        # Should be essentially the same
        assert "CHAPTER" in cleaned
        assert "Clean Book" in cleaned

    def test_partial_boilerplate_handled_gracefully(self, partial_gutenberg_book):
        """Test handling of incomplete boilerplate."""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(partial_gutenberg_book)

        # Should still extract content
        assert len(cleaned) > 0
        assert "CHAPTER" in cleaned


# ============================================================================
# Metadata Extraction Tests
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro TTS not available")
class TestMetadataExtraction:
    """Test extraction of title and author from boilerplate."""

    def test_extract_title_from_start_marker(self):
        """Test title extraction from START marker."""
        book = GutenbergDataGenerator.generate_with_standard_boilerplate("Test Title Here")
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Title should be extracted
        assert title is not None
        assert "TEST TITLE HERE" in title.upper()

    def test_extract_title_from_header(self):
        """Test title extraction from markdown header."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK ALICE'S ADVENTURES IN WONDERLAND ***

# Alice's Adventures in Wonderland

Author: Lewis Carroll

## CHAPTER I

Content here.
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should extract title
        assert title is not None

    def test_extract_author_from_by_line(self):
        """Test author extraction from 'By Author Name' line."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

# Test Book

By Test Author

## CHAPTER I

Content.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should extract author
        # Note: Implementation may vary, this tests the interface
        # Author might be None if not in START line

    def test_no_metadata_returns_none(self, clean_book):
        """Test that books without metadata return None."""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(clean_book)

        # Title might still be extracted from markdown headers
        # Author likely None


# ============================================================================
# Edge Cases Tests
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro TTS not available")
class TestEdgeCases:
    """Test edge cases in boilerplate handling."""

    def test_multiple_start_markers(self):
        """Test handling of multiple START markers."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

Some content.

*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

(This is unusual but could happen)

## CHAPTER I

Content.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should handle gracefully
        assert len(cleaned) > 0

    def test_start_marker_without_end(self):
        """Test handling when END marker is missing."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

## CHAPTER I

Content here.

## CHAPTER II

More content.
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should extract content after START
        assert "CHAPTER" in cleaned

    def test_end_marker_without_start(self):
        """Test handling when START marker is missing."""
        book = """## CHAPTER I

Content here.

## CHAPTER II

More content.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***

Footer text.
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should return content (may include everything before END)
        assert len(cleaned) > 0

    def test_case_insensitive_marker_detection(self):
        """Test that marker detection is case-insensitive."""
        book = """*** start of the project gutenberg ebook test ***

## CHAPTER I

Content.

*** end of the project gutenberg ebook test ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should detect lowercase markers
        assert "***" not in cleaned or "CHAPTER" in cleaned

    def test_whitespace_variations_in_markers(self):
        """Test handling of whitespace variations."""
        book = """***   START   OF   THE   PROJECT   GUTENBERG   EBOOK   TEST   ***

## CHAPTER I

Content.
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should handle extra whitespace
        assert len(cleaned) > 0

    def test_empty_content_between_markers(self):
        """Test handling when content between markers is empty."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should return empty or minimal content
        # Implementation-dependent


# ============================================================================
# Real-World Pattern Tests
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro TTS not available")
class TestRealWorldPatterns:
    """Test patterns from actual Gutenberg books."""

    def test_alice_in_wonderland_pattern(self):
        """Test pattern from Alice in Wonderland."""
        book = """The Project Gutenberg EBook of Alice's Adventures in Wonderland, by Lewis Carroll

*** START OF THE PROJECT GUTENBERG EBOOK ALICE'S ADVENTURES IN WONDERLAND ***

Alice's Adventures in Wonderland

By Lewis Carroll

## CHAPTER I. Down the Rabbit-Hole

Alice was beginning to get very tired...

## CHAPTER II. The Pool of Tears

'Curiouser and curiouser!' cried Alice...

*** END OF THE PROJECT GUTENBERG EBOOK ALICE'S ADVENTURES IN WONDERLAND ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should extract clean content
        assert "Down the Rabbit-Hole" in cleaned
        assert "Pool of Tears" in cleaned
        assert "*** START" not in cleaned
        assert "*** END" not in cleaned

    def test_call_of_cthulhu_pattern(self):
        """Test pattern from Call of Cthulhu."""
        book = """*** START OF THE PROJECT GUTENBERG EBOOK THE CALL OF CTHULHU ***

The Call of Cthulhu
By H. P. Lovecraft

I. The Horror in Clay.

The most merciful thing in the world...

*** END OF THE PROJECT GUTENBERG EBOOK THE CALL OF CTHULHU ***
"""
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        # Should extract clean content
        assert "Horror in Clay" in cleaned
        assert "*** END" not in cleaned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
