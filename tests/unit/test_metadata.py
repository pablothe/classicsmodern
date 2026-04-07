#!/usr/bin/env python3
"""
Unit Tests for Book Metadata Management

Tests metadata creation, serialization, and accumulation.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from lib.book.metadata import (
    MetadataManager, BookMetadata, TranslationMetadata,
    SummarizationMetadata, AudioMetadata,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_translation():
    return TranslationMetadata(
        source_language="Latin",
        target_language="Modern English",
        model="gemma3-translator:4b",
        timestamp=datetime.now().isoformat(),
        original_file="book.md",
        word_count_original=5000,
        word_count_translated=5200,
        chunks_processed=10,
        duration_seconds=120.5,
    )


@pytest.fixture
def sample_audio():
    return AudioMetadata(
        voice_reference="bf_emma",
        language="en-us",
        model="kokoro",
        timestamp=datetime.now().isoformat(),
        source_file="translated.md",
        audio_chunks=5,
        duration_seconds=3600.0,
        speed_multiplier=1.0,
    )


# ============================================================================
# MetadataManager Tests
# ============================================================================

class TestMetadataManager:
    """Test metadata file operations."""

    def test_metadata_path_convention(self, temp_dir):
        book_file = temp_dir / "alice.md"
        meta_path = MetadataManager.get_metadata_path(book_file)
        assert meta_path == temp_dir / "alice.meta.json"

    def test_create_or_update_new(self, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        metadata = MetadataManager.create_or_update(book_file, book_title="Test Book")
        assert metadata.book_title == "Test Book"
        assert metadata.translations == []
        assert metadata.has_audio is False

    def test_save_and_load_roundtrip(self, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        original = BookMetadata(
            book_title="Round Trip",
            original_file=str(book_file),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            current_language="English",
            is_summarized=True,
        )

        MetadataManager.save(book_file, original)
        loaded = MetadataManager.load(book_file)

        assert loaded is not None
        assert loaded.book_title == "Round Trip"
        assert loaded.current_language == "English"
        assert loaded.is_summarized is True

    def test_load_returns_none_when_missing(self, temp_dir):
        book_file = temp_dir / "nonexistent.md"
        assert MetadataManager.load(book_file) is None

    def test_add_translation_updates_state(self, temp_dir, sample_translation):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        MetadataManager.add_translation(book_file, sample_translation, "Test Book")

        loaded = MetadataManager.load(book_file)
        assert len(loaded.translations) == 1
        assert loaded.current_language == "Modern English"
        assert loaded.current_word_count == 5200

    def test_add_audio_updates_state(self, temp_dir, sample_audio):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        MetadataManager.add_audio(book_file, sample_audio, "Test Book")

        loaded = MetadataManager.load(book_file)
        assert len(loaded.audio_generations) == 1
        assert loaded.has_audio is True

    def test_multiple_translations_accumulate(self, temp_dir, sample_translation):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        MetadataManager.add_translation(book_file, sample_translation, "Test Book")

        second = TranslationMetadata(
            source_language="Modern English",
            target_language="Spanish",
            model="gemma3-translator:4b",
            timestamp=datetime.now().isoformat(),
            original_file="translated.md",
            word_count_original=5200,
            word_count_translated=5100,
            chunks_processed=10,
            duration_seconds=100.0,
        )
        MetadataManager.add_translation(book_file, second, "Test Book")

        loaded = MetadataManager.load(book_file)
        assert len(loaded.translations) == 2
        assert loaded.current_language == "Spanish"

    def test_add_summarization_updates_state(self, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("content")

        summ = SummarizationMetadata(
            target_percentage=50,
            actual_percentage=48.5,
            model="gemma3-translator:4b",
            timestamp=datetime.now().isoformat(),
            original_file="book.md",
            word_count_original=10000,
            word_count_summarized=4850,
            chunks_processed=5,
            duration_seconds=60.0,
        )
        MetadataManager.add_summarization(book_file, summ, "Test Book")

        loaded = MetadataManager.load(book_file)
        assert loaded.is_summarized is True
        assert loaded.current_word_count == 4850


# ============================================================================
# BookMetadata Tests
# ============================================================================

class TestBookMetadata:
    """Test BookMetadata dataclass."""

    def test_post_init_creates_empty_lists(self):
        meta = BookMetadata(
            book_title="Test", original_file="test.md",
            created_at="2026-01-01", updated_at="2026-01-01"
        )
        assert meta.translations == []
        assert meta.summarizations == []
        assert meta.audio_generations == []

    def test_defaults(self):
        meta = BookMetadata(
            book_title="Test", original_file="test.md",
            created_at="2026-01-01", updated_at="2026-01-01"
        )
        assert meta.has_audio is False
        assert meta.is_summarized is False
        assert meta.current_language is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
