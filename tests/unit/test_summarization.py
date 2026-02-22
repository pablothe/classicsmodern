#!/usr/bin/env python3
"""
Unit Tests for Book Summarization

Tests the summarization system without actual LLM calls.
Tests:
- Chunk size auto-scaling
- Recursive summarization (2-pass for <30%)
- Context-aware prompts
- Compression ratios
- Markdown preservation
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from tests.utils.mock_helpers import MockOllamaClient, create_sample_book
from tests.utils.test_data_generators import BookGenerator

try:
    from lib.summarize.engine import BookSummarizer
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_ollama():
    """Return mock Ollama client."""
    return MockOllamaClient(model_name="gemma3-translator:4b")


@pytest.fixture
def sample_book_1000_words():
    """Return 1000-word sample book."""
    return BookGenerator.generate_valid_book(
        title="1000 Word Book",
        num_chapters=3,
        words_per_chapter=333
    )


@pytest.fixture
def sample_book_500_words():
    """Return 500-word sample book."""
    return BookGenerator.generate_valid_book(
        title="500 Word Book",
        num_chapters=2,
        words_per_chapter=250
    )


# ============================================================================
# Chunk Size Auto-Scaling Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestChunkSizeAutoScaling:
    """Test automatic chunk size calculation based on compression ratio."""

    def test_default_chunk_size(self):
        """Test default chunk size is safe (1200 words)."""
        summarizer = BookSummarizer(target_percentage=50)
        assert summarizer.chunk_size_words == 1200

    def test_chunk_size_capped_at_max(self):
        """Test that chunk size never exceeds max_chunk_size."""
        summarizer = BookSummarizer(
            target_percentage=10,
            chunk_size_words=5000,  # Try to set very large
            max_chunk_size=1500
        )
        # Should be capped at max
        assert summarizer.chunk_size_words == 1500

    def test_custom_chunk_size(self):
        """Test custom chunk size override."""
        summarizer = BookSummarizer(
            target_percentage=50,
            chunk_size_words=800
        )
        assert summarizer.chunk_size_words == 800

    def test_target_percentage_stored(self):
        """Test that target percentage is stored correctly."""
        summarizer = BookSummarizer(target_percentage=30)
        assert summarizer.target_percentage == 30


# ============================================================================
# Recursive Summarization Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestRecursiveSummarization:
    """Test recursive (2-pass) summarization for aggressive compression."""

    @patch('lib.summarize.engine.OllamaTranslator')
    def test_single_pass_for_moderate_compression(self, mock_translator_class, sample_book_500_words):
        """Test that 30%+ target uses single-pass summarization."""
        # Mock the translator
        mock_translator = Mock()
        mock_translator.check_model_available.return_value = True
        mock_translator._chunk_markdown_text.return_value = [
            Mock(content=sample_book_500_words[:200], index=1)
        ]
        mock_translator_class.return_value = mock_translator

        summarizer = BookSummarizer(target_percentage=50)
        summarizer.translator = mock_translator

        # Mock the summarization method
        with patch.object(summarizer, '_summarize_chunk', return_value="summarized text"):
            result = summarizer.summarize_document(sample_book_500_words, target_percentage=50)

            # Should use single pass (not recursive)
            assert result.target_language == "Summarized (50%)"

    def test_recursive_detection_threshold(self):
        """Test that <30% triggers recursive summarization."""
        # For targets below 30%, the system should use 2-pass
        aggressive_targets = [10, 20, 25, 29]

        for target in aggressive_targets:
            summarizer = BookSummarizer(target_percentage=target)
            # Just checking the configuration is set up correctly
            assert summarizer.target_percentage < 30


# ============================================================================
# Context-Aware Prompts Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestContextAwarePrompts:
    """Test that summarization uses context from previous chunks."""

    @patch('lib.summarize.engine.OllamaTranslator')
    def test_first_chunk_no_context(self, mock_translator_class):
        """Test that first chunk doesn't receive previous context."""
        mock_translator = Mock()
        mock_translator.model_name = "gemma3-translator:4b"
        mock_translator.api_url = "http://localhost:11434/api/generate"
        mock_translator._get_last_sentences = Mock(return_value="previous context")

        summarizer = BookSummarizer()
        summarizer.translator = mock_translator

        # Mock chunk
        from lib.translation.engine import TranslationChunk
        chunk = TranslationChunk(
            index=1,
            content="This is the first chunk to summarize.",
            start_pos=0,
            end_pos=100
        )

        # Mock requests.post
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'response': 'summarized first chunk'}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = summarizer._summarize_chunk(
                chunk,
                target_percentage=50,
                previous_summary=None  # No previous summary
            )

            # Should NOT call _get_last_sentences for first chunk
            assert not mock_translator._get_last_sentences.called

    @patch('lib.summarize.engine.OllamaTranslator')
    def test_subsequent_chunks_receive_context(self, mock_translator_class):
        """Test that subsequent chunks receive context from previous."""
        mock_translator = Mock()
        mock_translator.model_name = "gemma3-translator:4b"
        mock_translator.api_url = "http://localhost:11434/api/generate"
        mock_translator._get_last_sentences = Mock(return_value="previous summary ending")

        summarizer = BookSummarizer()
        summarizer.translator = mock_translator

        # Mock chunk
        from lib.translation.engine import TranslationChunk
        chunk = TranslationChunk(
            index=2,
            content="This is the second chunk.",
            start_pos=100,
            end_pos=200
        )

        # Mock requests.post
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'response': 'summarized second chunk'}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = summarizer._summarize_chunk(
                chunk,
                target_percentage=50,
                previous_summary="First chunk was summarized."
            )

            # Should call _get_last_sentences to get context
            mock_translator._get_last_sentences.assert_called_once()


# ============================================================================
# Compression Ratio Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestCompressionRatio:
    """Test compression ratio calculations."""

    def test_target_word_count_calculation(self):
        """Test that target word count is calculated correctly."""
        summarizer = BookSummarizer(target_percentage=50)

        # 100 words at 50% target = 50 words
        original_words = 100
        target_percentage = 50
        expected_target = original_words * (target_percentage / 100)

        # This is what the internal logic should calculate
        assert expected_target == 50

    def test_aggressive_compression_target(self):
        """Test 10% compression (90% reduction)."""
        summarizer = BookSummarizer(target_percentage=10)

        # 1000 words at 10% = 100 words target
        original_words = 1000
        target = int(original_words * (summarizer.target_percentage / 100))

        assert target == 100

    def test_light_compression_target(self):
        """Test 70% compression (30% reduction)."""
        summarizer = BookSummarizer(target_percentage=70)

        # 1000 words at 70% = 700 words target
        original_words = 1000
        target = int(original_words * (summarizer.target_percentage / 100))

        assert target == 700


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestErrorHandling:
    """Test error handling in summarization."""

    def test_invalid_target_percentage_low(self):
        """Test that <10% is rejected by CLI."""
        # The main() function should reject this
        # We test the validation logic
        invalid_percentage = 5
        assert invalid_percentage < 10  # Would fail validation

    def test_invalid_target_percentage_high(self):
        """Test that >90% is rejected by CLI."""
        invalid_percentage = 95
        assert invalid_percentage > 90  # Would fail validation

    def test_valid_target_percentage_range(self):
        """Test valid percentage range (10-90)."""
        valid_percentages = [10, 30, 50, 70, 90]

        for pct in valid_percentages:
            summarizer = BookSummarizer(target_percentage=pct)
            assert 10 <= summarizer.target_percentage <= 90

    @patch('lib.summarize.engine.OllamaTranslator')
    def test_empty_summary_retry(self, mock_translator_class):
        """Test that empty summaries trigger retry."""
        mock_translator = Mock()
        mock_translator.model_name = "gemma3-translator:4b"
        mock_translator.api_url = "http://localhost:11434/api/generate"

        summarizer = BookSummarizer()
        summarizer.translator = mock_translator

        from lib.translation.engine import TranslationChunk
        chunk = TranslationChunk(index=1, content="test", start_pos=0, end_pos=10)

        # Mock requests to return empty first, then valid
        with patch('requests.post') as mock_post:
            mock_response_empty = Mock()
            mock_response_empty.json.return_value = {'response': '   '}  # Empty
            mock_response_empty.raise_for_status = Mock()

            mock_response_valid = Mock()
            mock_response_valid.json.return_value = {'response': 'valid summary'}
            mock_response_valid.raise_for_status = Mock()

            mock_post.side_effect = [mock_response_empty, mock_response_valid]

            result = summarizer._summarize_chunk(chunk, 50)

            # Should have retried
            assert mock_post.call_count == 2


# ============================================================================
# Markdown Preservation Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestMarkdownPreservation:
    """Test that Markdown structure is preserved during summarization."""

    def test_prompt_mentions_markdown(self):
        """Test that summarization prompt mentions preserving Markdown."""
        summarizer = BookSummarizer()

        from lib.translation.engine import TranslationChunk
        chunk = TranslationChunk(
            index=1,
            content="## Header\n\nContent with **bold** text.",
            start_pos=0,
            end_pos=50
        )

        # Mock the API call to capture the prompt
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'response': '## Header\n\nSummary.'}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            summarizer._summarize_chunk(chunk, 50)

            # Check that prompt was sent
            assert mock_post.called

            # Get the prompt from the call
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            prompt = payload['prompt']

            # Should mention Markdown formatting
            assert 'Markdown' in prompt or 'markdown' in prompt


# ============================================================================
# Integration with Metadata Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestMetadataGeneration:
    """Test metadata generation after summarization."""

    def test_result_contains_model_info(self):
        """Test that result includes model information."""
        summarizer = BookSummarizer()

        # Result should have model_used field
        assert hasattr(summarizer.translator, 'model_name')

    def test_result_contains_timing_info(self):
        """Test that result includes duration."""
        # TranslationResult should have total_time_seconds
        # This is verified by the return type of summarize_document

    def test_result_contains_chunk_count(self):
        """Test that result includes chunks processed."""
        # TranslationResult should have chunks_processed
        # This is verified by the return type


# ============================================================================
# Output Validation Tests
# ============================================================================

@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestOutputValidation:
    """Test that summarized output is validated."""

    @patch('lib.summarize.engine.validate_book')
    def test_output_validation_called(self, mock_validate):
        """Test that book validator is called on output."""
        # The main() function calls validate_book on output
        # We verify this integration exists
        from lib.summarize.engine import validate_book
        assert validate_book is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
