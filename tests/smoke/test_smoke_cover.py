#!/usr/bin/env python3
"""
Smoke Test: Cover Art Generation via Stable Diffusion

Generates a real cover image using Stable Diffusion v1.5.
This is the heaviest test — requires ~1GB model download on first run.
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_diffusion,
    pytest.mark.slow,
]


class TestSmokeCoverArt:
    """Smoke: Generate cover art with real Stable Diffusion."""

    def test_generate_image_importable(self):
        """Verify generate_image convenience function exists (used by cover.py and make_audiobook.py)."""
        from lib.cover.generator import generate_image
        assert callable(generate_image)

    @pytest.mark.timeout(600)
    def test_generate_cover_image(self, tmp_path):
        """Generate a single cover image and verify it's a valid PNG."""
        from lib.cover.generator import CoverArtGenerator

        generator = CoverArtGenerator()
        output_path = tmp_path / "test_cover.png"

        result = generator.generate_cover(
            prompt="Classic literature book cover, simple design",
            output_path=str(output_path),
            width=256,          # Smaller for speed
            height=256,
            num_inference_steps=10  # Fewer steps for speed
        )

        assert result.exists(), f"Cover image not created at {output_path}"
        assert result.stat().st_size > 1000, (
            f"Cover image too small: {result.stat().st_size} bytes"
        )

        # Verify PNG header
        with open(result, 'rb') as f:
            header = f.read(8)
        assert header[:4] == b'\x89PNG', (
            f"File does not have PNG header: {header[:4]}"
        )
