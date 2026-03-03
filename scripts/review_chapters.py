#!/usr/bin/env python3
"""
Chapter Review Tool

Review and approve chapter detection results from gutenberg_chapters.json.
Sets review_status to 'reviewed' on approval.

Usage:
    python3 scripts/review_chapters.py books/little_women/
    python3 scripts/review_chapters.py books/ --batch     # Show all unreviewed
    python3 scripts/review_chapters.py books/ --summary   # Summary of all books
"""

import json
import sys
from pathlib import Path


def display_chapters(book_dir: Path) -> dict:
    """Display chapter structure for a single book and return the data."""
    gutenberg_json = book_dir / "gutenberg_chapters.json"
    if not gutenberg_json.exists():
        print(f"  No gutenberg_chapters.json found in {book_dir.name}")
        return None

    with open(gutenberg_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    version = data.get('version', '1.0')
    chapters = data.get('chapters', [])
    review_status = data.get('review_status', 'unknown')
    front_matter = data.get('front_matter', {})
    hierarchy = data.get('hierarchy', [])

    print(f"\n{'='*60}")
    print(f"  {book_dir.name}")
    print(f"{'='*60}")
    print(f"  Source: gutenberg_chapters.json v{version}")
    print(f"  Status: {review_status}")
    print(f"  Chapters: {len(chapters)}")

    if front_matter and front_matter.get('sections'):
        fm_types = [s['section_type'] for s in front_matter['sections']]
        print(f"  Front matter: {', '.join(fm_types)}")
    else:
        print(f"  Front matter: None")

    if hierarchy:
        h_types = [f"{h['title']}" for h in hierarchy]
        print(f"  Hierarchy: {', '.join(h_types)}")

    print()
    print(f"  {'#':>3} | {'Type':<12} | {'Line':>5} | Title")
    print(f"  {'---':>3}-+-{'----------':<12}-+-{'-----':>5}-+{''+'-'*40}")

    warnings = []
    for i, ch in enumerate(chapters):
        ordinal = ch.get('ordinal', i + 1)
        section_type = ch.get('section_type', 'chapter')
        title = ch.get('title', '???')
        line_num = ch.get('header_line_number', '?')

        # Truncate long titles
        display_title = title[:50] + '...' if len(title) > 50 else title

        print(f"  {ordinal:>3} | {section_type:<12} | {str(line_num):>5} | {display_title}")

    # Check for potential issues
    if version == '1.0':
        warnings.append("v1.0 format - run migration to upgrade to v2.0")

    # Check for duplicate ordinals
    ordinals = [ch.get('ordinal', i+1) for i, ch in enumerate(chapters)]
    dupes = [o for o in set(ordinals) if ordinals.count(o) > 1]
    if dupes:
        warnings.append(f"Duplicate ordinals: {dupes}")

    # Check for missing line numbers (v2.0 only)
    if version == '2.0':
        missing = sum(1 for ch in chapters if 'header_line_number' not in ch)
        if missing:
            warnings.append(f"{missing} chapters missing line numbers")

    # Check for high chapter count
    if len(chapters) > 50:
        warnings.append(f"High chapter count ({len(chapters)}) - verify accuracy")

    if warnings:
        print(f"\n  Warnings:")
        for w in warnings:
            print(f"    ! {w}")

    return data


def approve_book(book_dir: Path) -> bool:
    """Set review_status to 'reviewed' for a book."""
    gutenberg_json = book_dir / "gutenberg_chapters.json"
    if not gutenberg_json.exists():
        return False

    with open(gutenberg_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['review_status'] = 'reviewed'

    with open(gutenberg_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Approved: {book_dir.name}")
    return True


def show_summary(books_dir: Path):
    """Show summary of all books' review status."""
    stats = {'reviewed': 0, 'auto': 0, 'needs_review': 0, 'v1.0': 0, 'v2.0': 0, 'none': 0}

    for book_dir in sorted(books_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        gutenberg_json = book_dir / "gutenberg_chapters.json"
        if not gutenberg_json.exists():
            stats['none'] += 1
            continue

        with open(gutenberg_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        version = data.get('version', '1.0')
        status = data.get('review_status', 'auto')
        ch_count = len(data.get('chapters', []))

        stats[f'v{version}'] = stats.get(f'v{version}', 0) + 1
        stats[status] = stats.get(status, 0) + 1

        marker = {'reviewed': '+', 'auto': ' ', 'needs_review': '!', 'unknown': '?'}.get(status, '?')
        print(f"  [{marker}] {book_dir.name:<45} v{version}  {ch_count:>3} ch  {status}")

    print(f"\n  Summary:")
    print(f"    Reviewed:     {stats.get('reviewed', 0)}")
    print(f"    Auto:         {stats.get('auto', 0)}")
    print(f"    Needs review: {stats.get('needs_review', 0)}")
    print(f"    No chapters:  {stats.get('none', 0)}")
    print(f"    v1.0:         {stats.get('v1.0', 0)}")
    print(f"    v2.0:         {stats.get('v2.0', 0)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/review_chapters.py <book_dir_or_books_dir>")
        print("       python3 scripts/review_chapters.py books/ --summary")
        print("       python3 scripts/review_chapters.py books/ --batch")
        sys.exit(1)

    target = Path(sys.argv[1])
    flags = sys.argv[2:]

    if not target.exists():
        print(f"Path not found: {target}")
        sys.exit(1)

    # Summary mode
    if '--summary' in flags:
        show_summary(target)
        return

    # Batch mode: show all unreviewed books
    if '--batch' in flags:
        for book_dir in sorted(target.iterdir()):
            if not book_dir.is_dir():
                continue
            gutenberg_json = book_dir / "gutenberg_chapters.json"
            if not gutenberg_json.exists():
                continue
            with open(gutenberg_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('review_status') != 'reviewed':
                display_chapters(book_dir)
        return

    # Single book mode
    if (target / "gutenberg_chapters.json").exists():
        book_dir = target
    elif (target / "book.md").exists():
        book_dir = target
    else:
        # Try as parent directory with single book
        candidates = [d for d in target.iterdir() if d.is_dir() and (d / "gutenberg_chapters.json").exists()]
        if len(candidates) == 1:
            book_dir = candidates[0]
        else:
            print(f"Specify a single book directory, or use --summary / --batch for multiple books")
            sys.exit(1)

    data = display_chapters(book_dir)
    if data is None:
        sys.exit(1)

    if data.get('review_status') == 'reviewed':
        print(f"\n  Already reviewed. Re-approve? [y/N] ", end='')
    else:
        print(f"\n  [a] Approve  [q] Quit: ", end='')

    try:
        choice = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if choice in ('a', 'y', 'yes'):
        approve_book(book_dir)


if __name__ == '__main__':
    main()
