#!/usr/bin/env python3
"""Generate cover art using local Stable Diffusion (100% offline)."""

import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate cover art using local Stable Diffusion (100% offline)"
    )
    parser.add_argument('prompt', help='Text prompt for image generation')
    parser.add_argument(
        '--output', '-o', type=Path, default=Path('cover.png'),
        help='Output image path (default: cover.png)'
    )
    parser.add_argument('--width', type=int, default=512, help='Image width')
    parser.add_argument('--height', type=int, default=512, help='Image height')
    parser.add_argument('--steps', type=int, default=30, help='Diffusion steps')
    parser.add_argument(
        '--book', default=None,
        help='Book name for auto-prompt (e.g., "Alice in Wonderland")'
    )

    args = parser.parse_args()

    # If --book is provided, get a book-specific prompt
    if args.book:
        from lib.cover.prompts import get_book_prompt
        prompt = get_book_prompt(args.book)
        print(f"Using book prompt: {prompt[:80]}...")
    else:
        prompt = args.prompt

    try:
        from lib.cover.generator import generate_image
        generate_image(
            prompt=prompt,
            output_path=str(args.output),
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps
        )
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
