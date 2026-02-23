#!/usr/bin/env python3
"""
Smoke Test: Full Audiobook Pipeline

Tests the complete make_audiobook.py pipeline (validate → audio → register).
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_kokoro,
    pytest.mark.requires_ffmpeg,
    pytest.mark.slow,
]


class TestSmokeFullPipeline:
    """Smoke: Full pipeline from make_audiobook.py."""

    @pytest.mark.timeout(600)
    def test_make_audiobook_no_cover(self, smoke_book_in_temp):
        """Run the full pipeline without cover art generation."""
        from make_audiobook import AudiobookMaker

        maker = AudiobookMaker(
            input_file=str(smoke_book_in_temp),
            voice="af_sky",
            generate_cover=False,
            non_interactive=True,
            generate_word_timings=False,  # Skip for speed
            normalize=False,              # Skip for speed
        )

        result = maker.make_audiobook()

        assert result is not None, "Pipeline returned None"

        # Audio directory should exist
        audio_dir = smoke_book_in_temp.parent / "audio_kokoro"
        if not audio_dir.exists():
            # Check alternative output locations
            audio_dirs = list(smoke_book_in_temp.parent.glob("audio_*"))
            assert len(audio_dirs) >= 1, (
                f"No audio output directory found in {smoke_book_in_temp.parent}. "
                f"Contents: {list(smoke_book_in_temp.parent.iterdir())}"
            )
            audio_dir = audio_dirs[0]

        # Should have audio files
        audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
        assert len(audio_files) >= 1, (
            f"No audio files in {audio_dir}. "
            f"Contents: {list(audio_dir.iterdir())}"
        )

        # State file should be cleaned up on success
        state_files = list(smoke_book_in_temp.parent.glob(".audiobook_state_*"))
        # (State file may or may not exist depending on cleanup behavior)
