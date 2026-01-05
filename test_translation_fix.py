#!/usr/bin/env python3
"""
Test the translation bug fix with a small sample
"""

from local_reader_translation import OllamaTranslator
from local_reader_config import get_config

# Test text (small Russian sample)
test_text = """# Преступление_и_наказание_cleaned - Part 1

В начале июля, в чрезвычайно жаркое время, под вечер, один молодой человек вышел из своей каморки, которую нанимал от жильцов в С-м переулке, на улицу и медленно, как бы в нерешимости, отправился к К-ну мосту.

Он благополучно избегнул встречи с своею хозяйкой на лестнице. Каморка его приходилась под самою кровлей высокого пятиэтажного дома и походила более на шкаф, чем на квартиру."""

print("="*70)
print("TESTING TRANSLATION BUG FIX")
print("="*70)
print("This test verifies that the validator catches garbage output")
print()

# Get config and create translator
config = get_config()
translator = OllamaTranslator(
    model_name=config.models.default_translation_model,
    ollama_host=config.models.ollama_host,
    chunk_size_words=50  # Small chunks for faster testing
)

print(f"Model: {translator.model_name}")
print(f"Test text: {len(test_text)} characters")
print()
print("Translating...")
print()

# Translate
result = translator.translate_document(
    text=test_text,
    source_lang="Russian",
    target_lang="Modern English"
)

print()
print("="*70)
print("RESULT")
print("="*70)
print(result.translated_text)
print()
print("="*70)
print(f"Chunks: {result.chunks_processed}")
print(f"Time: {result.total_time_seconds:.1f}s")
print()

# Check for garbage
if "I'll read and translate" in result.translated_text or "I will read and translate" in result.translated_text:
    print("❌ FAIL: Garbage detected in output!")
    exit(1)
else:
    print("✅ PASS: No garbage detected")
    print()
    print("The fix is working! Now you can safely re-translate chunk_001:")
    print("  python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian 'Modern English'")
    exit(0)
