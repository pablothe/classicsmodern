#!/usr/bin/env python3
"""Validate book structure for audiobook features."""

import sys
import argparse
from pathlib import Path

from lib.book.validator import validate_book, auto_fix_book, validate_directory


def main():
    parser = argparse.ArgumentParser(
        description="Validate book structure for audiobook features"
    )
    parser.add_argument('path', type=Path, help='Book file or directory')
    parser.add_argument(
        '--recursive', '-r', action='store_true',
        help='Recursively validate all books in directory'
    )
    parser.add_argument(
        '--auto-fix', action='store_true',
        help='Automatically fix common issues'
    )
    parser.add_argument(
        '--require', default=None,
        help='Required features (comma-separated: karaoke,ai_chat,web_player)'
    )
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--no-backup', action='store_true')

    args = parser.parse_args()

    if args.path.is_dir():
        reports = validate_directory(args.path, args.recursive)
        total = len(reports)
        valid = sum(1 for r in reports if r.valid)
        print(f"\nTotal: {total}, Valid: {valid}, Invalid: {total - valid}")
        sys.exit(0 if valid == total else 1)

    if args.auto_fix:
        auto_fix_book(str(args.path), backup=not args.no_backup)

    report = validate_book(str(args.path), verbose=args.verbose)

    if args.json:
        print(report.to_json())
    else:
        print(report)

    if args.require:
        required = [f.strip() for f in args.require.split(',')]
        missing = [f for f in required if not report.feature_support.get(f, False)]
        if missing:
            print(f"\nMissing required features: {', '.join(missing)}")
            sys.exit(1)

    sys.exit(0 if report.valid else 1)


if __name__ == "__main__":
    main()
