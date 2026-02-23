#!/usr/bin/env python3
"""
Smoke Test: Translation via Ollama

Translates text using the real Ollama service with gemma3-translator model.
"""

import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.requires_ollama,
    pytest.mark.slow,
]


class TestSmokeTranslation:
    """Smoke: Translate text with real Ollama."""

    def test_ollama_model_available(self):
        """Ollama should be reachable and the translation model loaded."""
        from lib.translation.engine import OllamaTranslator

        translator = OllamaTranslator()
        assert translator.check_model_available() is True, (
            "Ollama not reachable or model not found. "
            "Run: ollama pull zongwei/gemma3-translator:4b"
        )

    def test_translate_short_paragraph(self):
        """Translate a short Latin paragraph to English."""
        from lib.translation.engine import OllamaTranslator

        translator = OllamaTranslator()
        result = translator.translate_document(
            text="Gallia est omnis divisa in partes tres, quarum unam incolunt Belgae.",
            target_lang="Modern English"
        )

        assert result.translated_text is not None
        assert len(result.translated_text.strip()) > 10, (
            f"Translation too short: '{result.translated_text}'"
        )
        assert result.chunks_processed >= 1

    @pytest.mark.timeout(180)
    def test_structured_translation_preserves_chapters(self, smoke_book_in_temp):
        """BlockTranslator should preserve chapter structure."""
        from lib.translation.structured import (
            BookParser, BlockTranslator, TranslationConfig
        )

        # Parse the book
        parser = BookParser()
        structure = parser.parse(smoke_book_in_temp)
        assert len(structure.chapters) == 3, (
            f"Expected 3 chapters, got {len(structure.chapters)}"
        )

        # Translate (English → "Modern English" is basically a pass-through
        # but still exercises the full pipeline)
        config = TranslationConfig(
            target_lang="Modern English",
            model_name="zongwei/gemma3-translator:4b"
        )

        translator = BlockTranslator(config)
        translated = translator.translate_structure(structure)

        # All 3 chapters must be preserved
        assert len(translated.chapters) == 3, (
            f"Expected 3 chapters after translation, got {len(translated.chapters)}"
        )

        # Each chapter should have content
        for i, ch in enumerate(translated.chapters):
            assert len(ch.content.strip()) > 20, (
                f"Chapter {i+1} has too little content after translation: "
                f"'{ch.content[:50]}...'"
            )
