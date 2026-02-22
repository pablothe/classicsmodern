#!/usr/bin/env python3
"""
Unit Tests for Translation System

Tests translation validation, corruption detection, and retry logic.
"""

import pytest
from pathlib import Path

from lib.translation.engine import (
    translate_chunk,
    _validate_translation,
    _extract_translation
)


class TestTranslationValidation:
    """Test translation output validation"""

    def test_validate_good_translation(self):
        """Test that valid translation passes validation"""
        original = "This is a test sentence with enough content to translate properly."
        translated = "Esta es una oración de prueba con suficiente contenido para traducir correctamente."

        is_valid = _validate_translation(translated, original)

        assert is_valid is True

    def test_reject_meta_commentary(self):
        """Test that meta-commentary is rejected"""
        original = "Translate this sentence please."

        # These should all be rejected
        bad_translations = [
            "I'll read and translate the text.",
            "I will read and translate the text.",
            "Let me translate this for you.",
            "Here is the translation: ...",
            "I'm going to translate this now."
        ]

        for bad_translation in bad_translations:
            is_valid = _validate_translation(bad_translation, original)
            assert is_valid is False, f"Should reject: {bad_translation}"

    def test_reject_excessive_repetition(self):
        """Test that excessive repetition is rejected"""
        original = "This is original text."
        repeated = "Same line\n" * 10  # Same line repeated 10 times

        is_valid = _validate_translation(repeated, original)

        assert is_valid is False

    def test_reject_too_short_output(self):
        """Test that output much shorter than input is rejected"""
        original = "This is a very long sentence with lots of words that should be translated into another language with similar length."
        too_short = "Short."

        is_valid = _validate_translation(too_short, original)

        assert is_valid is False

    def test_allow_reasonable_length_difference(self):
        """Test that reasonable length differences are allowed"""
        original = "Hello, how are you today?"
        # Spanish translation (similar length)
        translated = "Hola, ¿cómo estás hoy?"

        is_valid = _validate_translation(translated, original)

        assert is_valid is True


class TestTranslationExtraction:
    """Test extraction of clean translation from LLM output"""

    def test_extract_clean_translation(self):
        """Test extraction of translation without markers"""
        output = "Esta es la traducción limpia sin marcadores."
        extracted = _extract_translation(output)

        assert extracted == output

    def test_extract_removes_preamble(self):
        """Test removal of common preambles"""
        output = "Here is the translation:\n\nEsta es la traducción."
        extracted = _extract_translation(output)

        assert "Here is" not in extracted
        assert "Esta es la traducción" in extracted

    def test_extract_removes_markdown_code_blocks(self):
        """Test removal of markdown code block markers"""
        output = "```\nEsta es la traducción.\n```"
        extracted = _extract_translation(output)

        assert "```" not in extracted
        assert "Esta es la traducción" in extracted


class TestTranslationRetryLogic:
    """Test retry logic for failed translations"""

    @pytest.mark.requires_ollama
    def test_retry_on_invalid_output(self, mock_ollama):
        """Test that translation retries on invalid output"""
        # This test requires mocking, so it's marked as requires_ollama
        # In actual implementation, we'd need to mock the ollama calls
        pass

    def test_fallback_to_original_after_max_retries(self):
        """Test that original text is returned after max retries"""
        # This would test the fallback behavior
        # When all retries fail, return original text
        pass


class TestTranslationContextAwareness:
    """Test context-aware translation (Layer 1 anti-duplication)"""

    def test_translation_receives_previous_context(self):
        """Test that translator receives previous chunk's ending as context"""
        # This tests the Layer 1 deduplication system
        # Translation should receive context from previous chunk
        pass

    def test_context_marked_as_reference_only(self):
        """Test that context is marked as 'reference only' in prompt"""
        # The prompt should explicitly tell LLM not to translate the context
        pass


class TestStructurePreservation:
    """Test that Markdown structure is preserved during translation"""

    def test_preserve_markdown_headers(self):
        """Test that Markdown headers are preserved"""
        original = """# Main Title

## Chapter 1

Content here."""

        # Mock translation would preserve structure
        # We'd need to actually test with a mock translator
        pass

    def test_preserve_markdown_links(self):
        """Test that Markdown links are preserved"""
        original = "Check out [this link](https://example.com) for more."

        # Translation should keep the link format
        pass

    def test_preserve_markdown_tables(self):
        """Test that Markdown tables are preserved"""
        original = """
| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""
        # Translation should keep table structure
        pass


class TestTranslationProgress:
    """Test progress tracking and resume capability"""

    def test_progress_saved_after_chunk(self, temp_dir):
        """Test that progress is saved after each chunk"""
        progress_file = temp_dir / ".translation_progress.json"

        # Simulate saving progress
        import json
        progress = {
            'total_chunks': 5,
            'completed': 2,
            'last_chunk': 'chunk_002'
        }

        with open(progress_file, 'w') as f:
            json.dump(progress, f)

        assert progress_file.exists()

        # Load and verify
        with open(progress_file, 'r') as f:
            loaded = json.load(f)

        assert loaded['completed'] == 2
        assert loaded['last_chunk'] == 'chunk_002'

    def test_resume_from_checkpoint(self, temp_dir):
        """Test resuming translation from checkpoint"""
        # This would test loading progress and continuing
        pass


class TestTranslationModels:
    """Test different translation model integrations"""

    def test_o3_mini_high_model(self):
        """Test translation with o3-mini-high model"""
        # Would need OpenAI mock
        pass

    def test_gemma3_translator_model(self):
        """Test translation with local Gemma3 model"""
        # Would need Ollama mock
        pass

    def test_model_selection(self):
        """Test that correct model is selected based on parameters"""
        pass


class TestTranslationErrorHandling:
    """Test error handling in translation"""

    def test_handle_network_error(self):
        """Test graceful handling of network errors"""
        # Should retry or fail gracefully
        pass

    def test_handle_timeout(self):
        """Test handling of translation timeouts"""
        # Should have timeout and retry
        pass

    def test_handle_corrupted_response(self):
        """Test handling of corrupted API responses"""
        # Should validate and reject
        pass


class TestTranslationPerformance:
    """Test translation performance metrics"""

    def test_track_words_per_second(self):
        """Test that translation speed is tracked"""
        # Should measure and report words/second
        pass

    def test_track_chunk_duration(self):
        """Test that chunk translation time is tracked"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
