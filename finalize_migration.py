#!/usr/bin/env python3
"""
Finalize Book Migration

Replaces old book structure with new clean structure.

IMPORTANT: This script will DELETE the old structure!
Make sure you've reviewed the .new_structure/ directories first.
"""

import shutil
from pathlib import Path
import sys


def finalize_book(book_dir: Path, dry_run: bool = False):
    """Finalize migration for a single book"""

    new_structure = book_dir / '.new_structure'

    if not new_structure.exists():
        print(f"  ⚠️  No .new_structure found - skipping")
        return False

    if dry_run:
        print(f"  ✓ Would replace old structure with new")
        return True

    # Backup old structure
    backup_dir = book_dir / '.old_structure_backup'

    # Move everything except .new_structure to backup
    for item in book_dir.iterdir():
        if item.name in ['.new_structure', '.old_structure_backup', '.old_duplicates']:
            continue

        backup_dir.mkdir(exist_ok=True)
        dest = backup_dir / item.name

        # Remove destination if it exists
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()

        shutil.move(str(item), str(dest))

    # Move new structure to root
    for item in new_structure.iterdir():
        shutil.move(str(item), str(book_dir / item.name))

    # Remove empty .new_structure directory
    new_structure.rmdir()

    print(f"  ✅ Finalized! Old structure backed up to .old_structure_backup/")
    return True


def main():
    dry_run = '--execute' not in sys.argv

    print("=" * 60)
    print("FINALIZE MIGRATION")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE (will modify files)'}")
    print()

    if not dry_run:
        confirm = input("⚠️  This will REPLACE the old structure. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return

    books_dir = Path('books')
    book_dirs = [d for d in books_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

    finalized_count = 0

    for book_dir in sorted(book_dirs):
        print(f"\n{book_dir.name}:")
        if finalize_book(book_dir, dry_run):
            finalized_count += 1

    print("\n" + "=" * 60)
    print(f"Books finalized: {finalized_count}/{len(book_dirs)}")
    print("=" * 60)

    if dry_run:
        print("\n⚠️  This was a DRY RUN")
        print("Run with --execute to finalize migration")
    else:
        print("\n✅ Migration finalized!")
        print("\nOld structure backed up in each book's .old_structure_backup/")
        print("You can safely delete these backups after verifying everything works.")


if __name__ == '__main__':
    main()
