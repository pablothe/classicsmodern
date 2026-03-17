#!/usr/bin/env python3
"""
Unit Tests for Book Summarization

Tests the summarization system without actual LLM calls.
"""

import pytest
from unittest.mock import Mock, patch

from tests.utils.test_data_generators import BookGenerator

try:
    from lib.summarize.engine import BookSummarizer
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False


@pytest.fixture
def sample_book_500_words():
    """Return 500-word sample book."""
    return BookGenerator.generate_valid_book(
        title="500 Word Book",
        num_chapters=2,
        words_per_chapter=250
    )


@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestChunkSizeAutoScaling:
    """Test automatic chunk size calculation based on compression ratio."""

    def test_chunk_size_capped_at_max(self):
        """Test that chunk size never exceeds max_chunk_size."""
        summarizer = BookSummarizer(
            target_percentage=10,
            chunk_size_words=5000,
            max_chunk_size=1500
        )
        assert summarizer.chunk_size_words == 1500

    def test_custom_chunk_size(self):
        """Test custom chunk size override."""
        summarizer = BookSummarizer(
            target_percentage=50,
            chunk_size_words=800
        )
        assert summarizer.chunk_size_words == 800


@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestRecursiveSummarization:
    """Test recursive (2-pass) summarization for aggressive compression."""

    @patch('lib.summarize.engine.OllamaTranslator')
    def test_single_pass_for_moderate_compression(self, mock_translator_class, sample_book_500_words):
        """Test that 30%+ target uses single-pass summarization."""
        mock_translator = Mock()
        mock_translator.check_model_available.return_value = True
        mock_translator._chunk_markdown_text.return_value = [
            Mock(content=sample_book_500_words[:200], index=1)
        ]
        mock_translator_class.return_value = mock_translator

        summarizer = BookSummarizer(target_percentage=50)
        summarizer.translator = mock_translator

        with patch.object(summarizer, '_summarize_chunk', return_value="summarized text"):
            result = summarizer.summarize_document(sample_book_500_words, target_percentage=50)
            assert result.target_language == "Summarized (50%)"


@pytest.mark.skipif(not SUMMARIZER_AVAILABLE, reason="book_summarizer not available")
class TestErrorHandling:
    """Test error handling in summarization."""

    def test_valid_target_percentage_range(self):
        """Test valid percentage range (10-90)."""
        valid_percentages = [10, 30, 50, 70, 90]

        for pct in valid_percentages:
            summarizer = BookSummarizer(target_percentage=pct)
            assert 10 <= summarizer.target_percentage <= 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
