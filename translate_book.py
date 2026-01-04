#!/usr/bin/env python3
"""
Simple script to translate a book using the local reader translation module.
Usage: python translate_book.py <input_file> <source_lang> <target_lang>
"""

import sys
from pathlib import Path
from local_reader_translation import OllamaTranslator
from local_reader_utils import FileManager
from local_reader_config import get_config

def main():
    if len(sys.argv) < 4:
        print("Usage: python translate_book.py <input_file> <source_lang> <target_lang>")
        print("Example: python translate_book.py books/crime_punishment/Преступление_и_наказание_cleaned.md Russian 'Modern Spanish'")
        sys.exit(1)

    input_file = sys.argv[1]
    source_lang = sys.argv[2]
    target_lang = sys.argv[3]

    # Read the input file
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"File loaded: {len(text)} characters")

    # Get config and create translator
    config = get_config()
    translator = OllamaTranslator(
        model_name=config.models.default_translation_model,
        ollama_host=config.models.ollama_host,
        chunk_size_words=config.translation.chunk_size_words
    )

    # Translate
    print(f"\nTranslating from {source_lang} to {target_lang}...")
    result = translator.translate_document(
        text=text,
        source_lang=source_lang,
        target_lang=target_lang
    )

    # Generate output filename
    input_path = Path(input_file)
    book_title = input_path.stem
    output_filename = FileManager.generate_filename(
        book_title=book_title,
        target_language=target_lang,
        model_name=result.model_used
    )

    # Save to same directory as input
    output_path = input_path.parent / output_filename

    print(f"\nSaving to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result.translated_text)

    print("\n" + "="*60)
    print("TRANSLATION COMPLETE")
    print("="*60)
    print(f"Input: {input_file}")
    print(f"Output: {output_path}")
    print(f"Source language: {result.source_language}")
    print(f"Target language: {result.target_language}")
    print(f"Model: {result.model_used}")
    print(f"Chunks processed: {result.chunks_processed}")
    print(f"Total time: {result.total_time_seconds/60:.1f} minutes")

if __name__ == "__main__":
    main()
