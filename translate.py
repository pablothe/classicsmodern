#!/usr/bin/env python3
"""Translate a book using LLM (Ollama local, OpenAI, or Anthropic)."""

import sys
import argparse
from pathlib import Path

from lib.translation.structured import translate_book, TranslationConfig


def main():
    parser = argparse.ArgumentParser(
        description="Translate a book using LLM (default: local Ollama)"
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
        help='Model name (default: gemma3-translator:4b)'
    )
    parser.add_argument(
        '--provider', choices=['ollama', 'openai', 'anthropic'], default=None,
        help='LLM provider (default: from LLM_PROVIDER env var or ollama)'
    )
    parser.add_argument(
        '--api-key', default=None,
        help='API key for OpenAI/Anthropic (default: from env var)'
    )
    parser.add_argument(
        '--no-translate-metadata', action='store_true',
        help='Do not translate title/author metadata'
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # Create LLM provider if specified
    llm = None
    if args.provider and args.provider != 'ollama':
        from lib.llm import create_llm_provider
        llm = create_llm_provider(
            provider=args.provider,
            model=args.model if args.model != 'zongwei/gemma3-translator:4b' else None,
            api_key=args.api_key,
        )
    elif args.provider is None:
        # Check if env var is set to non-ollama
        import os
        env_provider = os.environ.get('LLM_PROVIDER', 'ollama')
        if env_provider != 'ollama':
            from lib.llm import create_llm_provider
            llm = create_llm_provider(provider=env_provider, api_key=args.api_key)

    config = TranslationConfig(
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        model_name=args.model,
        translate_metadata=not args.no_translate_metadata,
        llm=llm,
    )

    try:
        output = translate_book(args.input_file, config)
        print(f"\nOutput: {output}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
