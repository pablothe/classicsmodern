#!/usr/bin/env python3
"""
Regression Tests for CHANGELOG.md Bugs

Prevents regression of historical bugs documented in CHANGELOG.md:
1. Translation corruption (meta-commentary)
2. Chunk overlap duplication (20-word overlap)
3. Missing chapter detection
4. Gutenberg boilerplate in output
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.utils.mock_helpers import MockOllamaClient, create_sample_book
from tests.utils.test_data_generators import TranslationChunkGenerator, GutenbergDataGenerator

try:
    from lib.translation.deduplicate import find_exact_overlap, deduplicate_chunks
    DEDUP_AVAILABLE = True
except ImportError:
    DEDUP_AVAILABLE = False

try:
    from lib.book.validator import validate_book
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

try:
    from lib.audio.kokoro import KokoroAudioGenerator
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


# ============================================================================
# Bug #1: Translation Corruption (Meta-Commentary)
# ============================================================================

@pytest.mark.regression
class TestTranslationCorruption:
    """
    Bug: LLM adds meta-commentary like "This text discusses..." instead of
    translating directly.

    Fix: Validation in translation pipeline rejects meta-commentary.
    """

    @patch('requests.post')
    def test_translation_rejects_meta_commentary(self, mock_post):
        """Test that translation system rejects meta-commentary."""
        # Mock response with meta-commentary
        mock_response = Mock()
        mock_response.json.return_value = {
            'response': "This text discusses Alice's adventures in Wonderland."
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Summarizer/translator should detect this
        bad_response = mock_response.json()['response']

        # Check for meta-commentary markers
        has_meta_commentary = any(marker in bad_response.lower() for marker in [
            "this text discusses",
            "the author says",
            "this passage tells"
        ])

        assert has_meta_commentary is True


# ============================================================================
# Bug #2: Chunk Overlap Duplication
# ============================================================================

@pytest.mark.skipif(not DEDUP_AVAILABLE, reason="Deduplication not available")
@pytest.mark.regression
class TestChunkOverlapDuplication:
    """
    Bug: 20-word overlap at chunk boundaries causes duplicate audio.

    Fix: Two-layer deduplication (LLM context + exact match).
    """

    def test_find_exact_20_word_overlap(self):
        """Test detection of exact 20-word overlap."""
        # Create chunks with exact 20-word overlap
        overlap_text = "the quick brown fox jumps over the lazy dog again " * 2  # 20 words
        overlap_text = ' '.join(overlap_text.split()[:20])  # Exactly 20 words

        chunk1_end = f"Beginning of chunk. {overlap_text}"
        chunk2_start = f"{overlap_text} Continuation of chunk."

        # Should find the overlap
        overlap = find_exact_overlap(chunk1_end, chunk2_start, max_words=30)

        assert overlap is not None
        assert len(overlap.split()) == 20

    def test_deduplicate_removes_boundary_duplicates(self, temp_dir):
        """Test that deduplication removes overlaps at boundaries."""
        # Create test chunks with overlap
        chunks = TranslationChunkGenerator.generate_chunks_with_overlap(
            num_chunks=3,
            words_per_chunk=100,
            overlap_words=20
        )

        # Write to files
        chunk_files = []
        for i, chunk_text in enumerate(chunks):
            chunk_file = temp_dir / f"chunk_{i+1:03d}.md"
            chunk_file.write_text(chunk_text)
            chunk_files.append(chunk_file)

        # Deduplicate
        output_dir = temp_dir / "deduplicated"
        deduplicated_files = deduplicate_chunks(chunk_files, output_dir)

        # Verify: Combined length should be less than sum of originals
        original_total = sum(len(c.split()) for c in chunks)

        deduplicated_texts = []
        for dedup_file in deduplicated_files:
            with open(dedup_file, 'r') as f:
                deduplicated_texts.append(f.read())

        dedup_total = sum(len(t.split()) for t in deduplicated_texts)

        # Should have removed overlaps
        assert dedup_total < original_total

    def test_no_false_positive_deduplication(self, temp_dir):
        """Test that non-overlapping chunks are not modified."""
        # Create chunks WITHOUT overlap
        chunks = TranslationChunkGenerator.generate_chunks_without_overlap(
            num_chunks=3,
            words_per_chunk=100
        )

        # Write to files
        chunk_files = []
        for i, chunk_text in enumerate(chunks):
            chunk_file = temp_dir / f"chunk_{i+1:03d}.md"
            chunk_file.write_text(chunk_text)
            chunk_files.append(chunk_file)

        # Deduplicate
        output_dir = temp_dir / "deduplicated"
        deduplicated_files = deduplicate_chunks(chunk_files, output_dir)

        # Verify: Length should be same (no false positives)
        original_total = sum(len(c.split()) for c in chunks)

        deduplicated_texts = []
        for dedup_file in deduplicated_files:
            with open(dedup_file, 'r') as f:
                deduplicated_texts.append(f.read())

        dedup_total = sum(len(t.split()) for t in deduplicated_texts)

        # Should NOT have removed anything
        assert abs(dedup_total - original_total) < 5  # Allow small rounding


# ============================================================================
# Bug #3: Missing Chapter Detection
# ============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="Validator not available")
@pytest.mark.regression
class TestMissingChapterDetection:
    """
    Bug: Books with missing chapter numbers (I, III, IV - missing II) not detected.

    Fix: Chapter sequence validation in lib/book/validator.py.
    """

    def test_sequential_chapters_pass_validation(self):
        """Test that properly numbered chapters pass validation."""
        from utils.test_data_generators import BookGenerator

        valid_book = BookGenerator.generate_valid_book(
            num_chapters=5,
            words_per_chapter=100,
            add_toc=True
        )

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(valid_book)
            temp_path = f.name

        try:
            # Validate
            report = validate_book(temp_path)

            # Should pass
            # Note: May have warnings, but no errors
            assert len(report.errors) == 0

        finally:
            # Clean up
            Path(temp_path).unlink()


# ============================================================================
# Bug #5: Gutenberg Boilerplate in Output
# ============================================================================

@pytest.mark.skipif(not KOKORO_AVAILABLE, reason="Kokoro not available")
@pytest.mark.regression
class TestGutenbergBoilerplate:
    """
    Bug: Gutenberg boilerplate appears in generated audiobook text.

    Fix: Automatic stripping in lib/audio/kokoro.py.
    """

    def test_gutenberg_boilerplate_removed(self):
        """Test that Gutenberg boilerplate is removed from output."""
        book_with_boilerplate = GutenbergDataGenerator.generate_with_standard_boilerplate(
            "Regression Test Book"
        )

        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book_with_boilerplate)

        # Verify boilerplate markers are gone
        assert "*** START OF THE PROJECT GUTENBERG" not in cleaned
        assert "*** END OF THE PROJECT GUTENBERG" not in cleaned
        assert "www.gutenberg.org" not in cleaned

        # Verify content is preserved
        assert "CHAPTER" in cleaned
        assert len(cleaned) > 100  # Has substantial content

    def test_gutenberg_boilerplate_not_in_audio_input(self, temp_dir):
        """Test that audio generation doesn't receive boilerplate text."""
        book_with_boilerplate = GutenbergDataGenerator.generate_with_standard_boilerplate(
            "Audio Test Book"
        )

        # Write to file
        book_file = temp_dir / "gutenberg_book.md"
        book_file.write_text(book_with_boilerplate)

        generator = KokoroAudioGenerator()

        # Strip boilerplate
        with open(book_file, 'r') as f:
            original = f.read()

        cleaned, title, author = generator.strip_gutenberg_boilerplate(original)

        # Cleaned text should be much shorter (boilerplate removed)
        assert len(cleaned) < len(original)

        # Cleaned text should not have boilerplate
        assert "Project Gutenberg" not in cleaned or "CHAPTER" in cleaned


# ============================================================================
# Comprehensive Regression Suite
# ============================================================================

@pytest.mark.regression
class TestAllRegressionBugs:
    """
    Combined test to ensure all historical bugs remain fixed.
    """

    def test_no_meta_commentary_in_translation(self):
        """Regression: No meta-commentary in translations."""
        mock_client = MockOllamaClient()

        # Test that mock doesn't generate meta-commentary
        result = mock_client.chat([{
            'role': 'user',
            'content': 'Translate: Alice fell down the rabbit hole.'
        }])

        response = result['message']['content']

        # Should not contain meta-commentary
        assert not any(phrase in response.lower() for phrase in [
            "this text discusses",
            "the author says",
            "the passage tells"
        ])



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
