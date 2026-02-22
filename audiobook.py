#!/usr/bin/env python3
"""Generate an audiobook using local Kokoro TTS (100% offline)."""

import sys
import argparse
from pathlib import Path

from lib.audio.kokoro import KokoroAudioGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate audiobook using local Kokoro TTS (100% offline)"
    )
    parser.add_argument('input_file', type=Path, help='Book markdown file')
    parser.add_argument(
        '--voice', default='af_sky',
        help='Voice name (default: af_sky). Top picks: bf_emma, bm_george, am_adam'
    )
    parser.add_argument(
        '--speed', type=float, default=1.0,
        help='Playback speed multiplier (default: 1.0)'
    )
    parser.add_argument(
        '--output-dir', type=Path, default=None,
        help='Output directory (default: auto from input path)'
    )
    parser.add_argument(
        '--language', default='en-us',
        help='Language code (default: en-us)'
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        generator = KokoroAudioGenerator(voice=args.voice, language=args.language)
        generator.generate_audiobook(
            str(args.input_file),
            speed=args.speed,
            output_dir=str(args.output_dir) if args.output_dir else None
        )
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
