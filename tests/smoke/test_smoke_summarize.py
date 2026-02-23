#!/usr/bin/env python3
"""
Smoke Test: Summarization via Ollama

Summarizes text using the real Ollama service.
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_ollama,
    pytest.mark.slow,
]


class TestSmokeSummarization:
    """Smoke: Summarize text with real Ollama."""

    def test_summarize_at_50_percent(self, smoke_book_path):
        """Summarize text at 50% target — verifies Ollama + summarizer work end-to-end."""
        from lib.summarize.engine import BookSummarizer

        # Use a longer text (repeat smoke book content) so the summarizer
        # has enough material to actually compress.
        with open(smoke_book_path) as f:
            text = f.read()

        # Triple the content to give the summarizer ~1500 words to work with.
        # The smoke book is only ~500 words, which is often below the chunk
        # threshold and LLMs don't compress tiny texts effectively.
        expanded_text = text + "\n\n" + text + "\n\n" + text
        original_words = len(expanded_text.split())

        summarizer = BookSummarizer(target_percentage=50)
        result = summarizer.summarize_document(expanded_text, target_percentage=50)

        assert result.translated_text is not None
        assert len(result.translated_text.strip()) > 50, (
            f"Summary too short: '{result.translated_text[:100]}...'"
        )

        summarized_words = len(result.translated_text.split())
        ratio = summarized_words / original_words

        # The key check: the summarizer actually ran through Ollama and produced output.
        # Compression ratio is variable with LLMs, so we're lenient.
        assert ratio < 0.95, (
            f"Summarizer did not compress: {ratio:.0%} "
            f"({summarized_words}/{original_words} words). "
            "Ollama may not be summarizing correctly."
        )
        assert result.chunks_processed >= 1
