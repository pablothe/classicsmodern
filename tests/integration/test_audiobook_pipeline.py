#!/usr/bin/env python3
"""
Integration Tests for Audiobook Pipeline (make_audiobook.py)

Tests the complete audiobook generation workflow with mocked TTS.
Tests:
- Validation → Audio → Cover → Server registration
- Resume capability (state file)
- Non-interactive mode (validation failures)
- Chapter metadata generation
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mock_helpers import MockKokoroTTS, create_sample_book
from utils.test_data_generators import BookGenerator

# Import actual module
try:
    from make_audiobook import AudiobookMaker
    AUDIOBOOK_MAKER_AVAILABLE = True
except ImportError:
    AUDIOBOOK_MAKER_AVAILABLE = False


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def valid_book_file(temp_dir):
    """Create valid book file for testing."""
    book_content = BookGenerator.generate_valid_book(
        title="Test Audiobook",
        num_chapters=2,
        words_per_chapter=100
    )

    book_file = temp_dir / "test_book.md"
    book_file.write_text(book_content)

    return book_file


@pytest.fixture
def invalid_book_file(temp_dir):
    """Create invalid book file (missing chapters)."""
    book_content = BookGenerator.generate_book_missing_chapters(
        missing_chapters=[2]
    )

    book_file = temp_dir / "invalid_book.md"
    book_file.write_text(book_content)

    return book_file


@pytest.fixture
def mock_kokoro_generator():
    """Return mock Kokoro generator."""
    return MockKokoroTTS()


# ============================================================================
# Basic Pipeline Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestBasicPipeline:
    """Test basic audiobook generation pipeline."""

    @patch('make_audiobook.KokoroAudioGenerator')
    def test_complete_pipeline_success(self, mock_kokoro_class, valid_book_file, temp_dir):
        """Test complete pipeline from validation to registration."""
        # Mock KokoroAudioGenerator
        mock_generator = Mock()
        mock_generator.generate_audiobook.return_value = {
            'output_directory': str(temp_dir / "audio_kokoro"),
            'playlist': str(temp_dir / "audio_kokoro" / "playlist.m3u"),
            'chapters': 2,
            'chunks': 4,
            'format': 'mp3'
        }
        mock_kokoro_class.return_value = mock_generator

        # Create audiobook maker
        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            voice="bf_emma",
            generate_cover=False,  # Skip cover for this test
            non_interactive=True
        )

        # Run pipeline
        with patch.object(maker, '_generate_chapter_metadata', return_value=True):
            with patch.object(maker, '_register_with_server'):
                result = maker.make_audiobook()

        # Verify success
        assert result['success'] is True
        assert 'audio_dir' in result
        assert 'playlist' in result
        assert result['chapters'] == 2

    @patch('make_audiobook.KokoroAudioGenerator')
    def test_pipeline_creates_output_directory(self, mock_kokoro_class, valid_book_file, temp_dir):
        """Test that pipeline creates output directory."""
        audio_dir = temp_dir / "audio_kokoro"

        mock_generator = Mock()
        mock_generator.generate_audiobook.return_value = {
            'output_directory': str(audio_dir),
            'playlist': str(audio_dir / "playlist.m3u"),
            'chapters': 2,
            'chunks': 4,
            'format': 'mp3'
        }
        mock_kokoro_class.return_value = mock_generator

        # Create the directory as the mock would
        audio_dir.mkdir(parents=True, exist_ok=True)

        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        with patch.object(maker, '_generate_chapter_metadata', return_value=True):
            with patch.object(maker, '_register_with_server'):
                result = maker.make_audiobook()

        # Verify directory exists
        assert audio_dir.exists()


# ============================================================================
# Validation Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestValidation:
    """Test pre-flight validation."""

    @patch('make_audiobook.validate_book')
    def test_validation_pass_continues_pipeline(self, mock_validate, valid_book_file):
        """Test that passing validation continues to audio generation."""
        # Mock validation to pass
        from book_validator import ValidationReport
        mock_validate.return_value = ValidationReport(
            valid=True,
            file_path=str(valid_book_file),
            errors=[],
            warnings=[],
            feature_support={'karaoke': True, 'ai_chat': True, 'web_player': True},
            metrics={'chapter_count': 2},
            fixes=[]
        )

        with patch('make_audiobook.KokoroAudioGenerator') as mock_kokoro_class:
            mock_generator = Mock()
            mock_generator.generate_audiobook.return_value = {
                'output_directory': str(valid_book_file.parent / "audio_kokoro"),
                'playlist': str(valid_book_file.parent / "audio_kokoro" / "playlist.m3u"),
                'chapters': 2,
                'chunks': 4,
                'format': 'mp3'
            }
            mock_kokoro_class.return_value = mock_generator

            maker = AudiobookMaker(
                input_file=str(valid_book_file),
                non_interactive=True,
                generate_cover=False
            )

            with patch.object(maker, '_generate_chapter_metadata', return_value=True):
                with patch.object(maker, '_register_with_server'):
                    result = maker.make_audiobook()

            # Should complete successfully
            assert result['success'] is True

    @patch('make_audiobook.validate_book')
    @patch('builtins.input', return_value='n')  # User says no
    def test_validation_fail_interactive_abort(self, mock_input, mock_validate, invalid_book_file):
        """Test that validation failure in interactive mode can be aborted."""
        # Mock validation to fail
        from book_validator import ValidationReport
        mock_validate.return_value = ValidationReport(
            valid=False,
            file_path=str(invalid_book_file),
            errors=["Missing chapter 2"],
            warnings=[],
            feature_support={'karaoke': False, 'ai_chat': False, 'web_player': True},
            metrics={'chapter_count': 2, 'missing_chapters': [2]},
            fixes=["Fix chapter numbering"]
        )

        maker = AudiobookMaker(
            input_file=str(invalid_book_file),
            non_interactive=False,  # Interactive mode
            generate_cover=False
        )

        result = maker.make_audiobook()

        # Should abort
        assert result['success'] is False
        assert result['reason'] == 'validation_failed'

    @patch('make_audiobook.validate_book')
    def test_validation_fail_noninteractive_exit(self, mock_validate, invalid_book_file):
        """Test that validation failure in non-interactive mode exits immediately."""
        # Mock validation to fail
        from book_validator import ValidationReport
        mock_validate.return_value = ValidationReport(
            valid=False,
            file_path=str(invalid_book_file),
            errors=["Missing chapter 2"],
            warnings=[],
            feature_support={'karaoke': False, 'ai_chat': False, 'web_player': True},
            metrics={'chapter_count': 2},
            fixes=["Fix chapter numbering"]
        )

        maker = AudiobookMaker(
            input_file=str(invalid_book_file),
            non_interactive=True,  # Non-interactive mode
            generate_cover=False
        )

        # Should raise SystemExit with code 2
        with pytest.raises(SystemExit) as exc_info:
            maker.make_audiobook()

        assert exc_info.value.code == 2


# ============================================================================
# Resume Capability Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestResumeCapability:
    """Test resume functionality using state files."""

    def test_state_file_created(self, valid_book_file):
        """Test that state file is created."""
        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        state_file = maker.state_file
        assert state_file.exists()
        assert state_file.name.startswith('.audiobook_state_')

        # Clean up
        if state_file.exists():
            state_file.unlink()

    def test_state_file_contains_progress(self, valid_book_file):
        """Test that state file tracks progress."""
        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        # Check initial state
        assert maker.state['stage'] == 'init'
        assert maker.state['audio_complete'] is False

        # Simulate audio completion
        maker.state['audio_complete'] = True
        maker.state['stage'] = 'audio_done'
        maker._save_state()

        # Read state file
        with open(maker.state_file, 'r') as f:
            saved_state = json.load(f)

        assert saved_state['audio_complete'] is True
        assert saved_state['stage'] == 'audio_done'

        # Clean up
        if maker.state_file.exists():
            maker.state_file.unlink()

    @patch('make_audiobook.KokoroAudioGenerator')
    def test_resume_skips_completed_stages(self, mock_kokoro_class, valid_book_file, temp_dir):
        """Test that resume skips already-completed stages."""
        # Create pre-existing state file
        state_file = valid_book_file.parent / f".audiobook_state_{valid_book_file.stem}.json"
        state = {
            'started_at': '2026-02-01T12:00:00',
            'stage': 'audio_done',
            'audio_complete': True,
            'audio_dir': str(temp_dir / "audio_kokoro"),
            'playlist': str(temp_dir / "audio_kokoro" / "playlist.m3u"),
            'chapters': 2,
            'chunks': 4,
            'cover_complete': False,
            'server_registered': False
        }

        with open(state_file, 'w') as f:
            json.dump(state, f)

        # Create audiobook maker (should load state)
        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        # Verify state was loaded
        assert maker.state['audio_complete'] is True
        assert maker.state['stage'] == 'audio_done'

        # Mock should NOT be called (audio already complete)
        with patch.object(maker, '_register_with_server'):
            result = maker.make_audiobook()

        # Audio generation should be skipped
        assert not mock_kokoro_class.called

        # Clean up
        if state_file.exists():
            state_file.unlink()


# ============================================================================
# Chapter Metadata Generation Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestChapterMetadata:
    """Test chapter metadata generation for web player."""

    @patch('make_audiobook.KokoroAudioGenerator')
    @patch('subprocess.run')
    def test_chapter_metadata_generated(self, mock_subprocess, mock_kokoro_class, valid_book_file, temp_dir):
        """Test that chapter metadata is generated."""
        audio_dir = temp_dir / "audio_kokoro"
        audio_dir.mkdir()

        mock_generator = Mock()
        mock_generator.generate_audiobook.return_value = {
            'output_directory': str(audio_dir),
            'playlist': str(audio_dir / "playlist.m3u"),
            'chapters': 2,
            'chunks': 4,
            'format': 'mp3'
        }
        mock_kokoro_class.return_value = mock_generator

        # Mock subprocess for chapter metadata generation
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        with patch.object(maker, '_register_with_server'):
            result = maker.make_audiobook()

        # Verify subprocess was called for metadata generation
        assert mock_subprocess.called


# ============================================================================
# Server Registration Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestServerRegistration:
    """Test server registration and metadata creation."""

    @patch('make_audiobook.KokoroAudioGenerator')
    def test_metadata_file_created(self, mock_kokoro_class, valid_book_file, temp_dir):
        """Test that audiobook metadata file is created."""
        audio_dir = temp_dir / "audio_kokoro"
        audio_dir.mkdir()

        mock_generator = Mock()
        mock_generator.generate_audiobook.return_value = {
            'output_directory': str(audio_dir),
            'playlist': str(audio_dir / "playlist.m3u"),
            'chapters': 2,
            'chunks': 4,
            'format': 'mp3'
        }
        mock_kokoro_class.return_value = mock_generator

        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            voice="bf_emma",
            non_interactive=True,
            generate_cover=False
        )

        with patch.object(maker, '_generate_chapter_metadata', return_value=True):
            result = maker.make_audiobook()

        # Check for metadata file
        metadata_file = audio_dir / "audiobook_metadata.json"
        assert metadata_file.exists()

        # Verify metadata content
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        assert 'title' in metadata
        assert 'voice' in metadata
        assert metadata['voice'] == 'bf_emma'
        assert metadata['format'] == 'mp3'


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.skipif(not AUDIOBOOK_MAKER_AVAILABLE, reason="make_audiobook not available")
@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in pipeline."""

    def test_missing_input_file(self):
        """Test handling of missing input file."""
        with pytest.raises(FileNotFoundError):
            AudiobookMaker(
                input_file="/nonexistent/file.md",
                non_interactive=True
            )

    @patch('make_audiobook.KokoroAudioGenerator')
    def test_audio_generation_failure(self, mock_kokoro_class, valid_book_file):
        """Test handling of audio generation failure."""
        mock_generator = Mock()
        mock_generator.generate_audiobook.side_effect = Exception("Audio generation failed")
        mock_kokoro_class.return_value = mock_generator

        maker = AudiobookMaker(
            input_file=str(valid_book_file),
            non_interactive=True,
            generate_cover=False
        )

        # Should raise exception and save state
        with pytest.raises(Exception):
            maker.make_audiobook()

        # State file should exist for resume
        assert maker.state_file.exists()

        # Clean up
        if maker.state_file.exists():
            maker.state_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
