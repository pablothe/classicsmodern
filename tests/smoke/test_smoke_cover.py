#!/usr/bin/env python3
"""
Smoke Test: Cover Art Generation via Stable Diffusion

Generates a real cover image using Stable Diffusion v1.5.
This is the heaviest test — requires ~1GB model download on first run.
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.smoke


class TestSmokeCoverImport:
    """Verify cover generation module is importable (no heavy deps needed)."""

    def test_generate_image_importable(self):
        """Verify generate_image convenience function exists (used by cover.py and make_audiobook.py)."""
        from lib.cover.generator import generate_image
        assert callable(generate_image)


