#!/usr/bin/env python3
"""
Unit Tests for Deduplication System

Tests the two-layer anti-duplication system that prevents overlapping
text at chunk boundaries.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from lib.translation.deduplicate import deduplicate_files, find_duplicate_text


class TestDuplicationDetection:
    """Test suite for duplicate text detection"""

    def test_find_exact_duplicate_at_boundary(self):
        """Test detection of exact duplicate text between chunks"""
        chunk1 = "This is the first chunk ending with this phrase."
        chunk2 = "ending with this phrase. This is the second chunk."

        duplicate = find_duplicate_text(chunk1, chunk2)

        assert duplicate is not None
        assert "ending with this phrase" in duplicate
        assert len(duplicate) > 0

    def test_no_duplicate_when_different(self):
        """Test that no duplicate is found when chunks are different"""
        chunk1 = "This is completely different text."
        chunk2 = "And this is also different text."

        duplicate = find_duplicate_text(chunk1, chunk2)

        assert duplicate == "" or duplicate is None

    def test_find_multi_word_duplicate(self):
        """Test detection of multi-word duplicates"""
        chunk1 = "The quick brown fox jumps over the lazy dog today."
        chunk2 = "over the lazy dog today. Tomorrow will be different."

        duplicate = find_duplicate_text(chunk1, chunk2)

        assert duplicate is not None
        assert len(duplicate.split()) >= 4  # At least 4 words overlap

    def test_case_sensitive_detection(self):
        """Test that duplicate detection is case-sensitive"""
        chunk1 = "This ends with UPPERCASE TEXT."
        chunk2 = "uppercase text. This continues."

        duplicate = find_duplicate_text(chunk1, chunk2)

        # Should NOT match because of case difference
        assert duplicate == "" or duplicate is None or len(duplicate) < 10

    def test_punctuation_handling(self):
        """Test duplicate detection with punctuation"""
        chunk1 = "First chunk, ending here."
        chunk2 = "ending here. Second chunk."

        duplicate = find_duplicate_text(chunk1, chunk2)

        assert duplicate is not None
        assert "ending here" in duplicate


class TestDeduplicationProcess:
    """Test suite for full deduplication process"""

    def test_deduplicate_two_chunks_with_overlap(self, temp_dir):
        """Test deduplication of two chunks with known overlap"""
        # Create test chunks
        chunk1_path = temp_dir / "chunk_001_test.md"
        chunk2_path = temp_dir / "chunk_002_test.md"

        chunk1_content = """# Chapter 1

This is the first chunk with some content.
It ends with this specific phrase for testing."""

        chunk2_content = """this specific phrase for testing. The second chunk continues here.
More content in the second chunk."""

        chunk1_path.write_text(chunk1_content)
        chunk2_path.write_text(chunk2_content)

        # Run deduplication
        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*_test.md", output_dir=str(output_dir))

        assert result['processed'] == 2
        assert result['duplicates_found'] > 0

        # Check output files
        deduped_chunk2 = output_dir / "chunk_002_test_DEDUPED.md"
        assert deduped_chunk2.exists()

        # Verify duplicate was removed
        deduped_content = deduped_chunk2.read_text()
        # Should not start with the duplicate phrase anymore
        assert not deduped_content.strip().startswith("this specific phrase for testing.")

    def test_deduplicate_preserves_non_duplicate_content(self, temp_dir):
        """Test that deduplication preserves unique content"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        unique_content = "THIS UNIQUE CONTENT MUST BE PRESERVED"

        chunk1_path.write_text("First chunk with no overlap.")
        chunk2_path.write_text(f"{unique_content}\nSecond chunk content.")

        output_dir = temp_dir / "deduplicated"
        deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        # Check that unique content is still there
        deduped_chunk2 = output_dir / "chunk_002_DEDUPED.md"
        content = deduped_chunk2.read_text()
        assert unique_content in content

    def test_deduplicate_multiple_chunks(self, temp_dir):
        """Test deduplication across multiple chunks"""
        chunks = [
            ("chunk_001.md", "First chunk ending with common text."),
            ("chunk_002.md", "common text. Second chunk ending differently."),
            ("chunk_003.md", "ending differently. Third chunk content."),
        ]

        for filename, content in chunks:
            (temp_dir / filename).write_text(content)

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        assert result['processed'] == 3
        # Should find duplicates between chunks
        assert result['duplicates_found'] >= 2

    def test_deduplicate_handles_no_overlap(self, temp_dir):
        """Test that deduplication works even with no overlaps"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        chunk1_path.write_text("Completely unique first chunk.")
        chunk2_path.write_text("Totally different second chunk.")

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        assert result['processed'] == 2
        assert result['duplicates_found'] == 0

        # Files should still be created (even if unchanged)
        assert (output_dir / "chunk_001_DEDUPED.md").exists()
        assert (output_dir / "chunk_002_DEDUPED.md").exists()


class TestDeduplicationEdgeCases:
    """Test edge cases in deduplication"""

    def test_empty_chunk(self, temp_dir):
        """Test handling of empty chunk files"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        chunk1_path.write_text("Normal content here.")
        chunk2_path.write_text("")  # Empty file

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        # Should handle gracefully
        assert result['processed'] == 2

    def test_very_short_chunks(self, temp_dir):
        """Test chunks that are too short to have meaningful duplicates"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        chunk1_path.write_text("Short.")
        chunk2_path.write_text("Also short.")

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        assert result['processed'] == 2
        assert result['duplicates_found'] == 0

    def test_entire_chunk_is_duplicate(self, temp_dir):
        """Test when entire chunk is a duplicate (edge case)"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        duplicate_content = "This exact content appears in both chunks."

        chunk1_path.write_text(duplicate_content)
        chunk2_path.write_text(duplicate_content)

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        # Should detect the massive duplicate
        assert result['duplicates_found'] > 0

        # Second chunk should be significantly smaller or empty
        deduped_chunk2 = output_dir / "chunk_002_DEDUPED.md"
        deduped_content = deduped_chunk2.read_text()
        assert len(deduped_content) < len(duplicate_content)

    def test_unicode_in_duplicates(self, temp_dir):
        """Test duplicate detection with unicode characters"""
        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        chunk1_path.write_text("Text with café and ümlaut characters.")
        chunk2_path.write_text("café and ümlaut characters. More text here.")

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        assert result['processed'] == 2
        # Should handle unicode correctly
        assert result['duplicates_found'] > 0


class TestDeduplicationAccuracy:
    """Test accuracy of deduplication system"""

    def test_20_word_overlap_scenario(self, temp_dir):
        """Test the exact scenario from CHANGELOG: 20-word overlap"""
        # Simulate the translation overlap scenario
        overlap_text = " ".join([f"word{i}" for i in range(1, 21)])  # 20 words

        chunk1_path = temp_dir / "chunk_001.md"
        chunk2_path = temp_dir / "chunk_002.md"

        chunk1_path.write_text(f"Start of first chunk with content. {overlap_text}")
        chunk2_path.write_text(f"{overlap_text} Continue with second chunk content.")

        output_dir = temp_dir / "deduplicated"
        result = deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        assert result['duplicates_found'] > 0

        # Verify the overlap was removed
        deduped_chunk2 = output_dir / "chunk_002_DEDUPED.md"
        content = deduped_chunk2.read_text()

        # Should not start with the overlap
        assert not content.strip().startswith("word1")

    def test_zero_repetition_guarantee(self, temp_dir):
        """Test that deduplication achieves zero repetition"""
        # Create chunks with known duplicates
        chunks = [
            ("chunk_001.md", "Alpha beta gamma delta epsilon."),
            ("chunk_002.md", "delta epsilon. Zeta eta theta."),
            ("chunk_003.md", "eta theta. Iota kappa lambda."),
        ]

        for filename, content in chunks:
            (temp_dir / filename).write_text(content)

        output_dir = temp_dir / "deduplicated"
        deduplicate_files(str(temp_dir), pattern="*.md", output_dir=str(output_dir))

        # Read all deduplicated chunks
        all_content = []
        for i in range(1, 4):
            chunk_file = output_dir / f"chunk_00{i}_DEDUPED.md"
            all_content.append(chunk_file.read_text())

        # Concatenate and check for no repeated phrases
        combined = " ".join(all_content)

        # "delta epsilon" should appear only once
        assert combined.count("delta epsilon") <= 1
        # "eta theta" should appear only once
        assert combined.count("eta theta") <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
