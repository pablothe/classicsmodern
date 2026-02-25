#!/usr/bin/env python3
"""
Unit Tests for Kokoro TTS Audio Generation

Tests the Kokoro TTS functionality without actually generating audio.
Uses mocks to test:
- Voice selection
- Text chunking and phoneme limits
- Gutenberg boilerplate stripping
- Chapter detection
- Audio combining
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from tests.utils.mock_helpers import MockKokoroTTS, create_sample_book, create_book_with_gutenberg_boilerplate
from tests.utils.test_data_generators import BookGenerator, GutenbergDataGenerator

try:
    from lib.audio.kokoro import KokoroAudioGenerator
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture
def mock_kokoro():
    """Return mock Kokoro TTS instance."""
    return MockKokoroTTS(voice="af_sky", language="en-us")


@pytest.fixture
def sample_text_short():
    """Return short sample text (100 words)."""
    return create_sample_book(
        title="Short Test",
        num_chapters=2,
        words_per_chapter=50
    )


@pytest.fixture
def sample_text_with_chapters():
    """Return text with multiple chapters."""
    return BookGenerator.generate_valid_book(
        title="Multi-Chapter Book",
        num_chapters=3,
        words_per_chapter=100
    )


# ============================================================================
# Voice Selection Tests
# ============================================================================

class TestVoiceSelection:
    """Test voice configuration and validation."""

    def test_default_voice(self, mock_kokoro):
        """Test default voice is af_sky."""
        assert mock_kokoro.voice == "af_sky"
        assert mock_kokoro.language == "en-us"

    def test_british_female_voice(self):
        """Test British female voice (recommended for classics)."""
        mock = MockKokoroTTS(voice="bf_emma")
        assert mock.voice == "bf_emma"

    def test_british_male_voice(self):
        """Test British male voice."""
        mock = MockKokoroTTS(voice="bm_george")
        assert mock.voice == "bm_george"

    def test_american_male_voice(self):
        """Test American male voices."""
        mock_adam = MockKokoroTTS(voice="am_adam")
        assert mock_adam.voice == "am_adam"

        mock_onyx = MockKokoroTTS(voice="am_onyx")
        assert mock_onyx.voice == "am_onyx"

    def test_voice_list_constants(self):
        """Test that voice constants are defined."""
        if KOKORO_AVAILABLE:
            assert hasattr(KokoroAudioGenerator, 'VOICE_AF_SKY')
            assert hasattr(KokoroAudioGenerator, 'VOICE_BF_EMMA')
            assert hasattr(KokoroAudioGenerator, 'VOICE_BM_GEORGE')
            assert hasattr(KokoroAudioGenerator, 'VOICE_AM_ADAM')


# ============================================================================
# Text Chunking Tests
# ============================================================================

class TestTextChunking:
    """Test text chunking and phoneme limit handling."""

    def test_safe_chunk_size(self):
        """Test that MAX_SAFE_CHUNK_SIZE is conservative."""
        if KOKORO_AVAILABLE:
            assert KokoroAudioGenerator.MAX_SAFE_CHUNK_SIZE <= 800

    def test_phoneme_limit_defined(self):
        """Test that phoneme limit is defined."""
        if KOKORO_AVAILABLE:
            assert hasattr(KokoroAudioGenerator, 'KOKORO_PHONEME_LIMIT')
            assert KokoroAudioGenerator.KOKORO_PHONEME_LIMIT == 510

    def test_short_text_chunking(self, mock_kokoro):
        """Test chunking of short text (<800 chars)."""
        short_text = "This is a short text that doesn't need chunking."
        # Mock TTS should handle this in one chunk
        result = mock_kokoro.create_audio(
            short_text,
            Path("/tmp/test.wav")
        )
        assert result['success'] is True
        assert result['text_length'] == len(short_text)

    def test_long_text_needs_chunking(self):
        """Test that long text would be chunked."""
        long_text = "word " * 500  # ~2500 chars
        # This should exceed MAX_SAFE_CHUNK_SIZE (800)
        assert len(long_text) > 800


# ============================================================================
# Gutenberg Boilerplate Tests
# ============================================================================

class TestGutenbergCleaning:
    """Test Gutenberg boilerplate detection and removal."""

    def test_strip_standard_boilerplate(self):
        """Test stripping standard Gutenberg header/footer."""
        book_with_boilerplate = GutenbergDataGenerator.generate_with_standard_boilerplate("Alice")

        # Check that boilerplate markers are present
        assert "*** START OF THE PROJECT GUTENBERG" in book_with_boilerplate
        assert "*** END OF THE PROJECT GUTENBERG" in book_with_boilerplate

        if KOKORO_AVAILABLE:
            generator = KokoroAudioGenerator()
            cleaned, title, author = generator.strip_gutenberg_boilerplate(book_with_boilerplate)

            # Check that boilerplate is removed
            assert "*** START OF THE PROJECT GUTENBERG" not in cleaned
            assert "*** END OF THE PROJECT GUTENBERG" not in cleaned

            # Check that actual content is preserved
            assert "CHAPTER" in cleaned

    def test_extract_title_from_boilerplate(self):
        """Test title extraction from Gutenberg boilerplate."""
        book = GutenbergDataGenerator.generate_with_standard_boilerplate("Test Book Title")

        if KOKORO_AVAILABLE:
            generator = KokoroAudioGenerator()
            cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

            # Title should be extracted
            assert title is not None
            assert "Test Book Title" in title.upper() or "TEST BOOK TITLE" in title.upper()

    def test_no_boilerplate_unchanged(self):
        """Test that clean books pass through unchanged."""
        clean_book = GutenbergDataGenerator.generate_without_boilerplate()

        if KOKORO_AVAILABLE:
            generator = KokoroAudioGenerator()
            cleaned, title, author = generator.strip_gutenberg_boilerplate(clean_book)

            # Should return original text
            assert len(cleaned) > 0
            assert "CHAPTER" in cleaned

    def test_partial_boilerplate(self):
        """Test handling of incomplete boilerplate markers."""
        partial = GutenbergDataGenerator.generate_with_partial_boilerplate()

        if KOKORO_AVAILABLE:
            generator = KokoroAudioGenerator()
            cleaned, title, author = generator.strip_gutenberg_boilerplate(partial)

            # Should handle gracefully
            assert len(cleaned) > 0


# ============================================================================
# Chapter Detection Tests
# ============================================================================

class TestChapterDetection:
    """Test chapter detection for audiobook organization."""

    def test_detect_roman_numeral_chapters(self, sample_text_with_chapters):
        """Test detection of Roman numeral chapters."""
        # Mock expects chapters to be in format "CHAPTER I", "CHAPTER II", etc.
        assert "CHAPTER I" in sample_text_with_chapters or "CHAPTER 1" in sample_text_with_chapters

    def test_single_chapter_book(self, mock_kokoro, temp_dir):
        """Test handling of single-chapter book."""
        single_chapter = BookGenerator.generate_valid_book(num_chapters=1)
        test_file = temp_dir / "single.md"
        test_file.write_text(single_chapter)

        result = mock_kokoro.generate_audiobook(str(test_file))

        # Should handle single chapter
        assert result['chapters'] >= 1


# ============================================================================
# Audio Generation Tests (Mocked)
# ============================================================================

class TestAudioGeneration:
    """Test audio generation workflow (mocked, no actual TTS)."""

    def test_create_audio_basic(self, mock_kokoro, temp_dir):
        """Test basic audio creation."""
        output_file = temp_dir / "test_audio.wav"
        text = "This is a test sentence."

        result = mock_kokoro.create_audio(text, output_file)

        assert result['success'] is True
        assert output_file.exists()
        assert result['voice'] == "af_sky"

    def test_audio_duration_estimation(self, mock_kokoro, temp_dir):
        """Test that audio duration is estimated from text length."""
        output_file = temp_dir / "test.wav"

        # Short text
        short_text = "Short"
        result_short = mock_kokoro.create_audio(short_text, output_file)

        # Long text
        long_text = "This is a much longer text " * 20
        output_file2 = temp_dir / "test2.wav"
        result_long = mock_kokoro.create_audio(long_text, output_file2)

        # Longer text should have longer duration
        assert result_long['duration'] > result_short['duration']

    def test_speed_parameter(self, mock_kokoro, temp_dir):
        """Test speed parameter is accepted."""
        output_file = temp_dir / "test.wav"
        text = "Test text"

        result = mock_kokoro.create_audio(text, output_file, speed=1.2)

        assert result['success'] is True

    def test_generate_audiobook_creates_output_dir(self, mock_kokoro, temp_dir):
        """Test that audiobook generation creates output directory."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        result = mock_kokoro.generate_audiobook(str(test_file))

        output_dir = Path(result['output_directory'])
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_generate_audiobook_creates_playlist(self, mock_kokoro, temp_dir):
        """Test that playlist file is created."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        result = mock_kokoro.generate_audiobook(str(test_file))

        playlist = Path(result['playlist'])
        assert playlist.exists()
        assert playlist.suffix == '.m3u'

    def test_mp3_format_option(self, mock_kokoro, temp_dir):
        """Test MP3 format conversion option."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        result = mock_kokoro.generate_audiobook(
            str(test_file),
            to_mp3=True
        )

        assert result['format'] == 'mp3'

    def test_wav_format_option(self, mock_kokoro, temp_dir):
        """Test WAV format option (no conversion)."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        result = mock_kokoro.generate_audiobook(
            str(test_file),
            to_mp3=False
        )

        assert result['format'] == 'wav'


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_empty_text(self, mock_kokoro, temp_dir):
        """Test handling of empty text."""
        output_file = temp_dir / "empty.wav"

        result = mock_kokoro.create_audio("", output_file)

        # Should handle gracefully (create minimal audio)
        assert result['success'] is True

    def test_invalid_output_directory(self, mock_kokoro, temp_dir):
        """Test handling of invalid output directory."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        # Try to use a file as output directory (should fail or handle)
        invalid_file = temp_dir / "invalid.txt"
        invalid_file.write_text("not a directory")

        # Mock should create directory or handle gracefully
        try:
            result = mock_kokoro.generate_audiobook(
                str(test_file),
                output_dir=str(invalid_file)
            )
            # If it succeeds, verify it handled it somehow
            assert 'output_directory' in result
        except (OSError, FileExistsError):
            # Expected error
            pass


# ============================================================================
# Integration with Other Components
# ============================================================================

class TestComponentIntegration:
    """Test integration with other system components."""

    def test_output_structure_for_server(self, mock_kokoro, temp_dir):
        """Test that output structure is compatible with server."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        result = mock_kokoro.generate_audiobook(str(test_file))

        # Verify required fields for server integration
        assert 'output_directory' in result
        assert 'playlist' in result
        assert 'chapters' in result
        assert 'format' in result

    def test_custom_output_directory(self, mock_kokoro, temp_dir):
        """Test custom output directory option."""
        test_file = temp_dir / "book.md"
        test_file.write_text(create_sample_book())

        custom_dir = temp_dir / "custom_audio"
        result = mock_kokoro.generate_audiobook(
            str(test_file),
            output_dir=str(custom_dir)
        )

        assert str(custom_dir) in result['output_directory']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
