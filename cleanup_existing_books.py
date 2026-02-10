#!/usr/bin/env python3
"""
Cleanup Existing Books - Normalize all markdown files in books directory

This script normalizes all existing book markdown files by:
1. Removing anchor tags {#...}
2. Standardizing chapter headers
3. Converting Roman numerals to Arabic in chapter titles
4. Normalizing whitespace

Usage:
    python3 cleanup_existing_books.py [--dry-run] [--verbose] [book_name]

Examples:
    # Clean all books
    python3 cleanup_existing_books.py

    # Preview changes without modifying files
    python3 cleanup_existing_books.py --dry-run

    # Clean only Cthulhu book
    python3 cleanup_existing_books.py call_cthulhu

    # Verbose output
    python3 cleanup_existing_books.py --verbose
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from markdown_normalizer import normalize_markdown


def cleanup_book(book_dir: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Normalize all markdown files in a book directory.

    Args:
        book_dir: Path to book directory
        dry_run: If True, preview changes without modifying files
        verbose: Print detailed transformation logs

    Returns:
        Dictionary with cleanup results
    """
    result = {
        'book': book_dir.name,
        'files_processed': 0,
        'files_modified': 0,
        'errors': []
    }

    # Find all markdown files (exclude backups)
    md_files = [f for f in book_dir.glob("*.md") if not f.name.endswith('.backup')]

    if not md_files:
        result['errors'].append("No markdown files found")
        return result

    for md_file in md_files:
        try:
            # Read original
            with open(md_file, 'r', encoding='utf-8') as f:
                original = f.read()

            result['files_processed'] += 1

            # Normalize
            if verbose:
                print(f"\n{'='*60}")
                print(f"Processing: {md_file.name}")
                print(f"{'='*60}")

            normalized = normalize_markdown(original, verbose=verbose)

            # Check if changes were made
            if normalized != original:
                result['files_modified'] += 1

                chars_diff = len(normalized) - len(original)
                lines_before = len(original.split('\n'))
                lines_after = len(normalized.split('\n'))

                print(f"\n  ✏️  Changes detected:")
                print(f"     File: {md_file.name}")
                print(f"     Characters: {len(original):,} → {len(normalized):,} ({chars_diff:+,})")
                print(f"     Lines: {lines_before} → {lines_after} ({lines_after - lines_before:+})")

                if not dry_run:
                    # Create backup
                    backup_name = f"{md_file.stem}.md.backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_file = md_file.parent / backup_name
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        f.write(original)

                    # Save normalized version
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(normalized)

                    print(f"     Backup: {backup_name}")
                    print(f"     ✓ Updated: {md_file.name}")
                else:
                    print(f"     [DRY RUN] Would create backup and update file")
            else:
                print(f"  ℹ️  No changes needed: {md_file.name}")

        except Exception as e:
            error_msg = f"{md_file.name}: {e}"
            result['errors'].append(error_msg)
            print(f"  ❌ Error: {error_msg}")

    return result


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Normalize all markdown files in books directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean all books
  python3 cleanup_existing_books.py

  # Preview changes without modifying files
  python3 cleanup_existing_books.py --dry-run

  # Clean only Cthulhu book
  python3 cleanup_existing_books.py call_cthulhu

  # Verbose output with transformation details
  python3 cleanup_existing_books.py --verbose

  # Dry run with verbose output
  python3 cleanup_existing_books.py --dry-run --verbose
        """
    )

    parser.add_argument(
        'book_name',
        nargs='?',
        help='Specific book directory to clean (optional, cleans all if not specified)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed transformation logs'
    )

    args = parser.parse_args()

    # Find books directory
    books_dir = Path(__file__).parent / "books"
    if not books_dir.exists():
        print(f"❌ Error: Books directory not found: {books_dir}")
        sys.exit(1)

    print("\n" + "="*60)
    print("BOOK MARKDOWN CLEANUP UTILITY")
    print("="*60)
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No files will be modified")
    print(f"Books directory: {books_dir}")
    print()

    # Determine which books to process
    if args.book_name:
        # Process specific book
        book_dir = books_dir / args.book_name
        if not book_dir.exists() or not book_dir.is_dir():
            print(f"❌ Error: Book directory not found: {book_dir}")
            sys.exit(1)

        book_dirs = [book_dir]
        print(f"Processing single book: {args.book_name}")
    else:
        # Process all books
        book_dirs = [d for d in books_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        book_dirs.sort()
        print(f"Processing all books ({len(book_dirs)} directories)")

    print()

    # Process each book
    all_results = []
    for book_dir in book_dirs:
        print(f"\n📚 {book_dir.name}")
        print("-" * 60)

        result = cleanup_book(book_dir, dry_run=args.dry_run, verbose=args.verbose)
        all_results.append(result)

    # Summary
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)

    total_processed = sum(r['files_processed'] for r in all_results)
    total_modified = sum(r['files_modified'] for r in all_results)
    total_errors = sum(len(r['errors']) for r in all_results)
    books_with_changes = sum(1 for r in all_results if r['files_modified'] > 0)

    print(f"Books scanned:       {len(all_results)}")
    print(f"Books with changes:  {books_with_changes}")
    print(f"Files processed:     {total_processed}")
    print(f"Files modified:      {total_modified}")
    print(f"Errors:              {total_errors}")

    if total_errors > 0:
        print("\n⚠️  Errors encountered:")
        for result in all_results:
            for error in result['errors']:
                print(f"  - {result['book']}: {error}")

    print()

    if args.dry_run:
        print("⚠️  DRY RUN - No files were modified")
        print("   Run without --dry-run to apply changes")
    elif total_modified > 0:
        print("✅ Cleanup complete!")
        print(f"   {total_modified} file(s) normalized")
        print(f"   Backups created with timestamp suffix")
    else:
        print("✅ All files already normalized!")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
