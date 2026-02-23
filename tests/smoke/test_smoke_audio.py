#!/usr/bin/env python3
"""
Smoke Test: Audio Generation via Kokoro TTS

Generates real audio using Kokoro TTS with ONNX Runtime.
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_kokoro,
    pytest.mark.requires_ffmpeg,
    pytest.mark.slow,
]


class TestSmokeAudioGeneration:
    """Smoke: Generate audio with real Kokoro TTS."""

    def test_kokoro_model_loads(self):
        """Kokoro model should initialize without errors."""
        from lib.audio.kokoro import KokoroAudioGenerator

        generator = KokoroAudioGenerator(voice="af_sky")
        assert generator.voice == "af_sky"

    @pytest.mark.timeout(300)
    def test_generate_audiobook_from_tiny_book(self, smoke_book_in_temp):
        """Generate a full audiobook from the tiny smoke test book."""
        from lib.audio.kokoro import KokoroAudioGenerator

        generator = KokoroAudioGenerator(voice="af_sky")
        output_dir = smoke_book_in_temp.parent / "audio_kokoro"

        result = generator.generate_audiobook(
            input_file=str(smoke_book_in_temp),
            output_dir=str(output_dir),
            chunk_size=800,
            speed=1.0,
            normalize=False,  # Skip normalization for speed
            to_mp3=True
        )

        # Basic result checks
        assert result is not None, "generate_audiobook returned None"
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Check audio files were created
        mp3_files = list(output_dir.glob("*.mp3"))
        wav_files = list(output_dir.glob("*.wav"))
        audio_files = mp3_files + wav_files

        assert len(audio_files) >= 1, (
            f"No audio files created in {output_dir}. "
            f"Contents: {list(output_dir.iterdir()) if output_dir.exists() else 'dir not found'}"
        )

        # Check files are non-trivial
        for f in audio_files:
            assert f.stat().st_size > 1000, (
                f"Audio file {f.name} is suspiciously small: {f.stat().st_size} bytes"
            )

        # Check playlist was created
        playlists = list(output_dir.glob("*.m3u"))
        assert len(playlists) >= 1, "No playlist (.m3u) file created"
