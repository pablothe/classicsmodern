#!/usr/bin/env python3
"""
Unit Tests for Kokoro TTS Audio Generation

Tests the Kokoro TTS functionality without actually generating audio.
Uses mocks to test:
- Text chunking
- Audio generation workflow
- Error handling
- Server integration
"""

import pytest
from pathlib import Path

from tests.utils.mock_helpers import MockKokoroTTS, create_sample_book


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture
def mock_kokoro():
    """Return mock Kokoro TTS instance."""
    return MockKokoroTTS(voice="af_sky", language="en-us")


# ============================================================================
# Text Chunking Tests
# ============================================================================

class TestTextChunking:
    """Test text chunking and phoneme limit handling."""

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
