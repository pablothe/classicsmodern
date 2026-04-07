#!/usr/bin/env python3
"""
Unit Tests for Translation Engine

Tests the core OllamaTranslator: chunking, prompt construction,
context passing, and markdown type detection.
"""

import pytest
from lib.translation.engine import OllamaTranslator, TranslationChunk, TranslationResult
from tests.utils.mock_helpers import MockRecordingLLM, MockCleanLLM


# ============================================================================
# Initialization Tests
# ============================================================================

class TestTranslatorInit:
    """Test translator initialization."""

    def test_init_with_llm_provider(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=50)
        assert translator.llm is llm
        assert translator.model_name == "clean-v1"
        assert translator.chunk_size_words == 50

    def test_init_with_defaults(self):
        translator = OllamaTranslator()
        assert translator.model_name == "zongwei/gemma3-translator:4b"
        assert translator.chunk_size_words == 150
        assert "localhost" in translator.ollama_host

    def test_check_model_with_mock_llm(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm)
        assert translator.check_model_available() is True


# ============================================================================
# Markdown Chunking Tests
# ============================================================================

class TestMarkdownChunking:
    """Test markdown-aware text chunking."""

    def test_short_text_single_chunk(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=100)

        chunks = translator._chunk_markdown_text("Short text here.")
        assert len(chunks) == 1
        assert chunks[0].content == "Short text here."

    def test_long_text_multiple_chunks(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=10)

        # Need enough words per paragraph to exceed chunk_size_words at break points
        text = (
            "The first paragraph has many words that fill up a chunk completely here now.\n\n"
            "The second paragraph also has many words that fill up another chunk completely here.\n\n"
            "The third paragraph has even more words to ensure splitting happens correctly here."
        )
        chunks = translator._chunk_markdown_text(text)
        assert len(chunks) >= 2

    def test_chunks_preserve_content(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=20)

        text = "Hello world.\n\nThis is a test.\n\nFinal words."
        chunks = translator._chunk_markdown_text(text)

        combined = '\n'.join(c.content for c in chunks)
        assert "Hello world." in combined
        assert "Final words." in combined

    def test_detect_markdown_header(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("# Title") == "header"
        assert translator._detect_markdown_type("## Chapter") == "header"

    def test_detect_markdown_code(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("```python") == "code"

    def test_detect_markdown_list(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("- item") == "list"
        assert translator._detect_markdown_type("* item") == "list"

    def test_detect_markdown_table(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("| col1 | col2 |") == "table"

    def test_detect_markdown_paragraph(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("Regular text.") == "paragraph"

    def test_detect_markdown_empty(self):
        translator = OllamaTranslator(llm=MockCleanLLM())
        assert translator._detect_markdown_type("") == "empty"
        assert translator._detect_markdown_type("   ") == "empty"


# ============================================================================
# Translation Tests
# ============================================================================

class TestTranslation:
    """Test translation execution with mock LLMs."""

    def test_translate_document_returns_result(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=50)

        result = translator.translate_document(
            "Some text to translate here.",
            "Latin", "Modern English"
        )

        assert isinstance(result, TranslationResult)
        assert len(result.translated_text) > 0
        assert result.target_language == "Modern English"

    def test_translate_with_context_passes_reference(self):
        """Second chunk should receive context from the first."""
        llm = MockRecordingLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=15)

        text = (
            "First sentence of the text here. Second sentence follows.\n\n"
            "Third sentence begins here. Fourth sentence concludes."
        )

        translator.translate_document_with_context(
            text, "Latin", "Modern English"
        )

        # First prompt should not have reference
        assert "Reference (do not repeat)" not in llm.prompts[0]

        # If there are multiple prompts, second should have reference
        if len(llm.prompts) > 1:
            assert "Reference (do not repeat)" in llm.prompts[1]

    def test_translate_empty_text(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=50)

        result = translator.translate_document("", "Latin", "English")
        assert result.translated_text == "" or result.chunks_processed == 0

    def test_health_check_with_mock_llm(self):
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm)

        health = translator.get_ollama_health()
        assert health['available'] is True
        assert health['provider'] == "mock-clean"


# ============================================================================
# Context Extraction Tests
# ============================================================================

class TestContextExtraction:
    """Test last-sentence extraction for context passing."""

    def test_get_last_sentences(self):
        translator = OllamaTranslator(llm=MockCleanLLM())

        text = "First sentence. Second sentence. Third sentence."
        result = translator._get_last_sentences(text, count=2)

        assert "Third sentence." in result
        assert "Second sentence." in result

    def test_get_last_sentences_max_chars(self):
        translator = OllamaTranslator(llm=MockCleanLLM())

        text = "A" * 600 + ". Short end."
        result = translator._get_last_sentences(text, count=2, max_chars=100)

        assert len(result) <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
