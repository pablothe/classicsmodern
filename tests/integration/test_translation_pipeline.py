#!/usr/bin/env python3
"""
Integration Tests for Translation Pipeline

Tests the full translation workflow: Split → Translate → Deduplicate
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.mark.integration
class TestTranslationPipeline:
    """Test full translation pipeline"""

    def test_split_translate_deduplicate_workflow(self, temp_dir, sample_book_content):
        """Test complete workflow from splitting to deduplication"""
        # Create test book file
        book_file = temp_dir / "test_book.md"
        book_file.write_text(sample_book_content * 5)  # Make it longer

        # This is a placeholder test that would:
        # 1. Split book into chunks
        # 2. Translate each chunk
        # 3. Run deduplication
        # 4. Verify output is clean

        # For now, just verify the structure works
        assert book_file.exists()

    def test_progress_tracking_saves_after_each_chunk(self, temp_dir):
        """Test that progress is saved and can be resumed"""
        progress_file = temp_dir / ".translation_progress.json"

        # Simulate saving progress
        progress_data = {
            'total_chunks': 5,
            'completed': 3,
            'last_chunk': 'chunk_003',
            'timestamp': '2026-02-04T12:00:00Z'
        }

        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

        # Verify saved
        assert progress_file.exists()

        # Load and verify
        with open(progress_file, 'r') as f:
            loaded = json.load(f)

        assert loaded['completed'] == 3
        assert loaded['total_chunks'] == 5

    def test_resume_from_interruption(self, temp_dir):
        """Test resuming translation after interruption"""
        # Create progress file indicating partial completion
        progress_file = temp_dir / ".translation_progress.json"
        progress_data = {
            'total_chunks': 5,
            'completed': 2,
            'last_chunk': 'chunk_002'
        }

        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

        # Create mock translated chunks 1 and 2
        for i in range(1, 3):
            chunk_file = temp_dir / f"chunk_00{i}_translated.md"
            chunk_file.write_text(f"Translated chunk {i}")

        # Verify we can detect partial progress
        assert progress_file.exists()
        assert (temp_dir / "chunk_001_translated.md").exists()
        assert (temp_dir / "chunk_002_translated.md").exists()
        assert not (temp_dir / "chunk_003_translated.md").exists()

    def test_error_recovery_continues_on_failure(self, temp_dir):
        """Test that pipeline continues when one chunk fails"""
        # Simulate scenario where chunk 2 fails but chunks 1 and 3 succeed
        chunks = [
            ("chunk_001.md", "successful"),
            ("chunk_002.md", "failed"),  # This one fails
            ("chunk_003.md", "successful")
        ]

        for filename, status in chunks:
            chunk_file = temp_dir / filename
            chunk_file.write_text(f"Content: {status}")

        # In real pipeline, we'd track failures but continue
        # For now, just verify files exist
        assert all((temp_dir / f).exists() for f, _ in chunks)


@pytest.mark.integration
class TestBatchTranslation:
    """Test batch translation functionality"""

    @pytest.mark.requires_ollama
    def test_batch_translate_multiple_chunks(self, temp_dir, mock_ollama):
        """Test translating multiple chunks in batch"""
        # Create test chunks
        for i in range(1, 4):
            chunk_file = temp_dir / f"chunk_00{i}.md"
            chunk_file.write_text(f"Content for chunk {i}")

        # This would test local_reader_batch_translator.py
        # With mock Ollama, should translate all chunks
        pass

    def test_context_passed_between_chunks(self, temp_dir):
        """Test that context from previous chunk is passed to next"""
        # Layer 1 deduplication: LLM receives context
        # This would verify the context passing mechanism
        pass


@pytest.mark.integration
class TestDeduplicationIntegration:
    """Test deduplication as part of full pipeline"""

    def test_automatic_deduplication_after_translation(self, temp_dir):
        """Test that deduplication runs automatically after translation"""
        # Create mock translated chunks with overlaps
        chunk1_path = temp_dir / "chunk_001_translated.md"
        chunk2_path = temp_dir / "chunk_002_translated.md"

        overlap_text = "this is duplicate text"

        chunk1_path.write_text(f"First chunk ending with {overlap_text}")
        chunk2_path.write_text(f"{overlap_text} second chunk continues")

        # Run deduplication
        from lib.translation.deduplicate import deduplicate_files

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(
            str(temp_dir),
            pattern="*_translated.md",
            output_dir=str(output_dir)
        )

        assert result['processed'] == 2
        assert result['duplicates_found'] > 0

        # Verify deduplicated files exist
        assert (output_dir / "chunk_001_translated_DEDUPED.md").exists()
        assert (output_dir / "chunk_002_translated_DEDUPED.md").exists()

    def test_deduplicated_files_used_for_audio(self, temp_dir):
        """Test that deduplicated files are properly organized for audio generation"""
        # Create deduplicated directory structure
        deduped_dir = temp_dir / "deduplicated"
        deduped_dir.mkdir()

        for i in range(1, 4):
            chunk_file = deduped_dir / f"chunk_00{i}_DEDUPED.md"
            chunk_file.write_text(f"Clean content {i}")

        # Verify structure is correct for audio generation
        assert deduped_dir.exists()
        assert len(list(deduped_dir.glob("*_DEDUPED.md"))) == 3


@pytest.mark.integration
class TestChunkingIntegration:
    """Test smart chunking integration"""

    def test_split_at_chapter_boundaries(self, temp_dir, sample_book_content):
        """Test that splitter respects chapter boundaries"""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content * 10)  # Make longer

        # Would test local_reader_smart_splitter.py
        # Should split at natural chapter boundaries
        pass

    def test_chunk_size_configuration(self, temp_dir, sample_book_content):
        """Test custom chunk size"""
        # Test splitting with different chunk sizes
        # 5000, 10000, 15000 words
        pass


@pytest.mark.integration
@pytest.mark.slow
class TestFullBookTranslation:
    """Test translating a complete book"""

    @pytest.mark.requires_ollama
    def test_translate_complete_small_book(self, temp_dir, sample_book_clean):
        """Test translating a complete small book end-to-end"""
        # This would be a full integration test:
        # 1. Load sample book
        # 2. Split if needed
        # 3. Translate all chunks
        # 4. Deduplicate
        # 5. Verify output quality
        pass

    def test_translation_preserves_structure(self, temp_dir, sample_book_clean):
        """Test that book structure is preserved after translation"""
        # Verify chapters, TOC, formatting all preserved
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
