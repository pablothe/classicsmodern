#!/usr/bin/env python3
"""Validate book structure for audiobook features."""

import sys
import argparse
from pathlib import Path

import json

from lib.book.validator import validate_book, auto_fix_book, validate_directory


def _migrate_paragraphs(path: Path, recursive: bool = False):
    """Add paragraph registry to book manifests that lack it."""
    from lib.book.processor import BookProcessor

    manifest_files = []
    if path.is_file() and path.name == 'book_manifest.json':
        manifest_files.append(path)
    elif path.is_dir():
        pattern = '**/book_manifest.json' if recursive else '*/book_manifest.json'
        manifest_files = sorted(path.glob(pattern))
    else:
        # Path is a book file — look for manifest in same directory
        manifest_path = path.parent / 'book_manifest.json'
        if manifest_path.exists():
            manifest_files.append(manifest_path)

    if not manifest_files:
        print("No book manifests found.")
        return

    migrated = 0
    skipped = 0
    for mf in manifest_files:
        try:
            with open(mf, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            chapters = manifest.get('chapters', [])
            needs_migration = False
            for ch in chapters:
                if not ch.get('paragraphs'):
                    needs_migration = True
                    break

            if not needs_migration:
                skipped += 1
                continue

            for ch in chapters:
                if ch.get('paragraphs'):
                    continue
                content = ch.get('content', '')
                if not content:
                    continue
                chapter_num = ch.get('number', 1)
                ch['paragraphs'] = BookProcessor._extract_paragraphs(content, chapter_num)

            manifest['version'] = '3.0'
            with open(mf, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            para_count = sum(len(ch.get('paragraphs', [])) for ch in chapters)
            print(f"  Migrated: {mf.parent.name} ({len(chapters)} chapters, {para_count} paragraphs)")
            migrated += 1

        except (json.JSONDecodeError, IOError) as e:
            print(f"  Error: {mf} - {e}")

    print(f"\nDone: {migrated} migrated, {skipped} already up-to-date")


def _recombine_prologues(path: Path, recursive: bool = False):
    """Recombine existing audio chunks to separate prologues into their own files."""
    from lib.audio.kokoro import KokoroAudioGenerator

    book_dirs = []
    if path.is_dir():
        # Check if this is a book directory (has book_manifest.json)
        if (path / 'book_manifest.json').exists():
            book_dirs.append(path)
        else:
            # It's a parent directory (e.g., books/)
            pattern = '**/*' if recursive else '*'
            for d in sorted(path.glob(pattern)):
                if d.is_dir() and (d / 'book_manifest.json').exists():
                    book_dirs.append(d)
    else:
        # Path is a file — use its parent directory
        if (path.parent / 'book_manifest.json').exists():
            book_dirs.append(path.parent)

    if not book_dirs:
        print("No book directories found.")
        return

    recombined = 0
    skipped = 0
    for book_dir in book_dirs:
        audio_dir = book_dir / 'audio_kokoro'
        if not audio_dir.exists():
            continue

        print(f"\n{book_dir.name}:")
        result = KokoroAudioGenerator.recombine_chapters(audio_dir, book_dir)
        if result:
            recombined += 1
        else:
            skipped += 1

    print(f"\nDone: {recombined} recombined, {skipped} skipped")


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
    parser.add_argument(
        '--migrate-paragraphs', action='store_true',
        help='Add paragraph registry to book manifests that lack it (v2.0 -> v3.0)'
    )
    parser.add_argument(
        '--recombine-prologues', action='store_true',
        help='Recombine existing audio chunks to separate prologues into their own files'
    )

    args = parser.parse_args()

    if args.migrate_paragraphs:
        _migrate_paragraphs(args.path, recursive=args.recursive)
        sys.exit(0)

    if args.recombine_prologues:
        _recombine_prologues(args.path, recursive=args.recursive)
        sys.exit(0)

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
