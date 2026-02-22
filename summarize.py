#!/usr/bin/env python3
"""Summarize a book using local Ollama LLM (100% offline)."""

import sys
import argparse
from pathlib import Path

from lib.summarize.engine import BookSummarizer


def main():
    parser = argparse.ArgumentParser(
        description="Summarize a book using local Ollama LLM (100% offline)"
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

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        summarizer = BookSummarizer(
            target_percentage=args.target_percentage,
            chunk_size_words=args.chunk_size
        )
        output = summarizer.summarize_file(str(args.input_file))
        print(f"\nOutput: {output}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
