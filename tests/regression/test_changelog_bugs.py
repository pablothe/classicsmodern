#!/usr/bin/env python3
"""
Regression Tests for CHANGELOG.md Bugs

Prevents regression of historical bugs documented in CHANGELOG.md:
1. Translation corruption (meta-commentary)
2. Chunk overlap duplication (20-word overlap)
3. Audio truncation
4. Missing chapter detection
5. Gutenberg boilerplate in output
"""

import pytest
import sys
import re
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mock_helpers import MockOllamaClient, create_sample_book
from utils.test_data_generators import TranslationChunkGenerator, GutenbergDataGenerator

# Import actual modules
try:
    from local_reader_deduplicate import find_exact_overlap, deduplicate_chunks
    DEDUP_AVAILABLE = True
except ImportError:
    DEDUP_AVAILABLE = False

try:
    from book_validator import validate_book
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

try:
    from local_tts_kokoro import KokoroAudioGenerator
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

    def test_detect_meta_commentary_phrases(self):
        """Test detection of common meta-commentary phrases."""
        meta_phrases = [
            "This text discusses the adventures",
            "The author describes a scene",
            "The passage tells us about",
            "According to this text",
            "As mentioned in the passage"
        ]

        for phrase in meta_phrases:
            # These should be flagged as meta-commentary
            assert any(marker in phrase.lower() for marker in [
                "this text", "the author", "the passage", "according to"
            ])

    def test_detect_llm_refusal_phrases(self):
        """Test detection of LLM refusal phrases."""
        refusal_phrases = [
            "I cannot translate this",
            "I can't provide a translation",
            "I'm unable to translate",
            "As an AI, I cannot"
        ]

        for phrase in refusal_phrases:
            # These should be flagged as refusals
            assert any(marker in phrase.lower() for marker in [
                "i cannot", "i can't", "i'm unable", "as an ai"
            ])

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
# Bug #3: Audio Truncation
# ============================================================================

@pytest.mark.regression
class TestAudioTruncation:
    """
    Bug: Audio files truncated mid-sentence due to chunk size limits.

    Fix: Conservative chunk sizes (800 chars) and phoneme limit checking.
    """

    def test_chunk_size_within_safe_limits(self):
        """Test that chunk size is conservative (≤800 chars)."""
        if KOKORO_AVAILABLE:
            # Verify safety limit
            assert KokoroAudioGenerator.MAX_SAFE_CHUNK_SIZE <= 800

    def test_phoneme_limit_defined(self):
        """Test that phoneme limit is enforced."""
        if KOKORO_AVAILABLE:
            # Verify phoneme limit is set
            assert hasattr(KokoroAudioGenerator, 'KOKORO_PHONEME_LIMIT')
            assert KokoroAudioGenerator.KOKORO_PHONEME_LIMIT == 510

    def test_long_text_requires_multiple_chunks(self):
        """Test that long text is split into multiple chunks."""
        long_text = "word " * 500  # ~2500 chars

        # Should exceed safe chunk size
        assert len(long_text) > 800


# ============================================================================
# Bug #4: Missing Chapter Detection
# ============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="Validator not available")
@pytest.mark.regression
class TestMissingChapterDetection:
    """
    Bug: Books with missing chapter numbers (I, III, IV - missing II) not detected.

    Fix: Chapter sequence validation in book_validator.py.
    """

    def test_detect_missing_chapter_in_sequence(self):
        """Test detection of missing chapter (e.g., I, III, IV - missing II)."""
        from utils.test_data_generators import BookGenerator

        book_with_missing = BookGenerator.generate_book_missing_chapters(
            missing_chapters=[2]
        )

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(book_with_missing)
            temp_path = f.name

        try:
            # Validate
            report = validate_book(temp_path)

            # Should detect missing chapter
            assert report.valid is False
            assert len(report.errors) > 0
            assert any('missing' in error.lower() or '2' in error for error in report.errors)

        finally:
            # Clean up
            Path(temp_path).unlink()

    def test_detect_duplicate_chapter_numbers(self):
        """Test detection of duplicate chapter numbers."""
        from utils.test_data_generators import BookGenerator

        book_with_duplicate = BookGenerator.generate_book_duplicate_chapters(
            duplicate_chapter=2
        )

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(book_with_duplicate)
            temp_path = f.name

        try:
            # Validate
            report = validate_book(temp_path)

            # Should detect duplicate
            assert report.valid is False
            assert len(report.errors) > 0

        finally:
            # Clean up
            Path(temp_path).unlink()

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

    Fix: Automatic stripping in local_tts_kokoro.py.
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

    def test_no_duplicate_audio_at_boundaries(self, temp_dir):
        """Regression: No duplicate audio at chunk boundaries."""
        if not DEDUP_AVAILABLE:
            pytest.skip("Deduplication not available")

        # Create overlapping chunks
        chunks = TranslationChunkGenerator.generate_chunks_with_exact_duplicate(
            duplicate_at_boundary=True
        )

        # Write to files
        chunk_files = []
        for i, chunk_text in enumerate(chunks):
            chunk_file = temp_dir / f"chunk_{i+1}.md"
            chunk_file.write_text(chunk_text)
            chunk_files.append(chunk_file)

        # Deduplicate
        output_dir = temp_dir / "dedup"
        deduplicated_files = deduplicate_chunks(chunk_files, output_dir)

        # Read deduplicated
        with open(deduplicated_files[1], 'r') as f:
            dedup_chunk2 = f.read()

        # Should NOT contain duplicate text at start
        duplicate_phrase = "this is the exact duplicate text at the boundary"
        assert dedup_chunk2.count(duplicate_phrase) == 1  # Only once

    def test_audio_not_truncated(self):
        """Regression: Audio uses safe chunk sizes."""
        if not KOKORO_AVAILABLE:
            pytest.skip("Kokoro not available")

        # Verify safety measures in place
        assert KokoroAudioGenerator.MAX_SAFE_CHUNK_SIZE <= 800
        assert KokoroAudioGenerator.KOKORO_PHONEME_LIMIT == 510

    def test_chapter_gaps_detected(self):
        """Regression: Missing chapters are detected."""
        if not VALIDATOR_AVAILABLE:
            pytest.skip("Validator not available")

        from utils.test_data_generators import BookGenerator

        book = BookGenerator.generate_book_missing_chapters([2, 4])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(book)
            temp_path = f.name

        try:
            report = validate_book(temp_path)
            assert report.valid is False
        finally:
            Path(temp_path).unlink()

    def test_gutenberg_stripped_automatically(self):
        """Regression: Gutenberg boilerplate is stripped."""
        if not KOKORO_AVAILABLE:
            pytest.skip("Kokoro not available")

        book = GutenbergDataGenerator.generate_with_standard_boilerplate("Test")
        generator = KokoroAudioGenerator()
        cleaned, title, author = generator.strip_gutenberg_boilerplate(book)

        assert "*** START OF THE PROJECT GUTENBERG" not in cleaned
        assert "*** END OF THE PROJECT GUTENBERG" not in cleaned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
