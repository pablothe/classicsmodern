#!/usr/bin/env python3
"""
Smoke Test: Gutenberg Book Download

Downloads a real (small) book from Project Gutenberg and verifies the pipeline.
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_network,
    pytest.mark.slow,
]


class TestSmokeGutenbergDownload:
    """Smoke: Download a real book from Project Gutenberg."""

    def test_download_small_book(self, tmp_path):
        """Download Gutenberg #11 (Alice in Wonderland) and verify output."""
        from server.gutenberg_downloader import GutenbergDownloader

        downloader = GutenbergDownloader(books_dir=tmp_path)
        result = downloader.download_book(
            gutenberg_id=11,
            book_slug="alice_smoke_test"
        )

        assert result.get('success') is True, (
            f"Download failed: {result.get('error', 'unknown error')}"
        )

        output_file = Path(result['output_file'])
        assert output_file.exists(), f"Output file not created: {output_file}"

        content = output_file.read_text()
        assert len(content) > 1000, f"Output too small: {len(content)} chars"

        # Boilerplate should be stripped
        assert "START OF THE PROJECT GUTENBERG" not in content, (
            "Gutenberg header boilerplate was not stripped"
        )
        assert "END OF THE PROJECT GUTENBERG" not in content, (
            "Gutenberg footer boilerplate was not stripped"
        )

        # Should contain recognizable content
        content_upper = content.upper()
        assert "CHAPTER" in content_upper or "ALICE" in content_upper, (
            "Downloaded content doesn't look like Alice in Wonderland"
        )

    def test_download_invalid_id_fails_gracefully(self, tmp_path):
        """Download with a bogus Gutenberg ID should fail without crashing."""
        from server.gutenberg_downloader import GutenbergDownloader

        downloader = GutenbergDownloader(books_dir=tmp_path)
        result = downloader.download_book(
            gutenberg_id=9999999,
            book_slug="fake_book"
        )

        assert result.get('success') is False, (
            "Expected failure for invalid Gutenberg ID"
        )
