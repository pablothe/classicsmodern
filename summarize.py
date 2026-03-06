#!/usr/bin/env python3
"""Summarize a book using LLM (Ollama local, OpenAI, or Anthropic)."""

import sys
import argparse
from pathlib import Path

from lib.summarize.engine import BookSummarizer


def main():
    parser = argparse.ArgumentParser(
        description="Summarize a book using LLM (default: local Ollama)"
    )
    parser.add_argument('input_file', type=Path, help='Book markdown file')
    parser.add_argument(
        'target_percentage', type=int,
        help='Target length as percentage of original (e.g., 50 = 50%%)'
    )
    parser.add_argument(
        'chunk_size', type=int, nargs='?', default=None,
        help='Words per chunk (auto-calculated if omitted)'
    )
    parser.add_argument(
        '--provider', choices=['ollama', 'openai', 'anthropic'], default=None,
        help='LLM provider (default: from LLM_PROVIDER env var or ollama)'
    )
    parser.add_argument(
        '--model', default=None,
        help='Model name (default: provider default)'
    )
    parser.add_argument(
        '--api-key', default=None,
        help='API key for OpenAI/Anthropic (default: from env var)'
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # Create LLM provider if non-default
    llm = None
    provider = args.provider
    if provider is None:
        import os
        provider = os.environ.get('LLM_PROVIDER', 'ollama')
    if provider != 'ollama':
        from lib.llm import create_llm_provider
        llm = create_llm_provider(provider=provider, model=args.model, api_key=args.api_key)

    try:
        summarizer = BookSummarizer(
            target_percentage=args.target_percentage,
            chunk_size_words=args.chunk_size,
            llm=llm,
        )
        output = summarizer.summarize_file(str(args.input_file))
        print(f"\nOutput: {output}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
