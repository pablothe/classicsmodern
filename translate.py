#!/usr/bin/env python3
"""Translate a book using local Ollama LLM (100% offline)."""

import sys
import argparse
from pathlib import Path

from lib.translation.structured import translate_book, TranslationConfig


def main():
    parser = argparse.ArgumentParser(
        description="Translate a book using local Ollama LLM (100% offline)"
    )
    parser.add_argument('input_file', type=Path, help='Book markdown file')
    parser.add_argument(
        '--target-lang', required=True,
        help='Target language (e.g., "Modern English", "Spanish")'
    )
    parser.add_argument(
        '--source-lang', default=None,
        help='Source language (auto-detected if omitted)'
    )
    parser.add_argument(
        '--model', default='zongwei/gemma3-translator:4b',
        help='Ollama model name (default: gemma3-translator:4b)'
    )
    parser.add_argument(
        '--no-translate-metadata', action='store_true',
        help='Do not translate title/author metadata'
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    config = TranslationConfig(
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        model_name=args.model,
        translate_metadata=not args.no_translate_metadata
    )

    try:
        output = translate_book(args.input_file, config)
        print(f"\nOutput: {output}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
