#!/usr/bin/env python3
"""
Unit Tests for Manifest Manager

Tests manifest creation, checkpoint save/resume, and legacy conversion.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from lib.book.manifest import ManifestManager
from lib.book.processor import BookManifest, Chapter


# ============================================================================
# Manifest Creation Tests
# ============================================================================

class TestManifestCreation:
    """Test creating manifests from book files."""

    def test_create_manifest_from_book(self, temp_dir, sample_book_content):
        """Creating a manifest from a valid book should detect chapters."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        assert isinstance(manifest, BookManifest)
        assert len(manifest.chapters) >= 1
        assert manifest_path.exists()
        assert manifest_path.suffix == ".json"

    def test_load_existing_manifest(self, temp_dir, sample_book_content):
        """Loading an existing manifest should return the same data."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        # Create manifest
        manifest1, path1 = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        # Load it again via the JSON path
        manifest2, path2 = ManifestManager.get_or_create_manifest(
            path1, verbose=False
        )

        assert len(manifest2.chapters) == len(manifest1.chapters)

    def test_manifest_saved_as_json(self, temp_dir, sample_book_content):
        """Manifest file should be valid JSON."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        _, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        with open(manifest_path) as f:
            data = json.load(f)
        assert "chapters" in data


# ============================================================================
# Checkpoint Tests
# ============================================================================

class TestCheckpoints:
    """Test translation/audio checkpoint tracking."""

    def test_update_translation_checkpoint(self, temp_dir, sample_book_content):
        """Updating a translation checkpoint should persist."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        ManifestManager.update_translation_checkpoint(
            manifest, manifest_path,
            chapter_num=1,
            complete=True,
            target_lang="Modern English",
            translated_file="translated.md"
        )

        # Reload and verify - checkpoints are on Chapter objects
        reloaded = BookManifest.load(manifest_path)
        chapter_1 = reloaded.chapters[0]
        assert chapter_1.checkpoints['translation'] is not None
        assert chapter_1.checkpoints['translation']['complete'] is True

    def test_invalid_chapter_num_raises(self, temp_dir, sample_book_content):
        """Updating checkpoint with invalid chapter number should raise."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        with pytest.raises(ValueError, match="Invalid chapter number"):
            ManifestManager.update_translation_checkpoint(
                manifest, manifest_path,
                chapter_num=999,
                complete=True,
                target_lang="English"
            )

    def test_get_incomplete_chapters(self, temp_dir, sample_book_content):
        """Should return chapter numbers not yet completed."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        incomplete = ManifestManager.get_incomplete_chapters(manifest, 'translation')
        # All chapters should be incomplete initially (returns list of ints)
        assert len(incomplete) == len(manifest.chapters)

    def test_completed_chapter_not_in_incomplete(self, temp_dir, sample_book_content):
        """After marking a chapter complete, it should not appear in incomplete list."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        manifest, manifest_path = ManifestManager.get_or_create_manifest(
            book_file, verbose=False
        )

        ManifestManager.update_translation_checkpoint(
            manifest, manifest_path,
            chapter_num=1,
            complete=True,
            target_lang="English"
        )

        # Reload manifest after update
        manifest = BookManifest.load(manifest_path)
        incomplete = ManifestManager.get_incomplete_chapters(manifest, 'translation')
        # Returns list of chapter numbers (ints)
        assert 1 not in incomplete


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
