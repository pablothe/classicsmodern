#!/usr/bin/env python3
"""
Reset Books — Wipe all book data and redownload from Gutenberg.

This is a ONE-TIME migration script for the storage architecture refactor.
It preserves cover images and de_brevitate_vitae/book.md, then:
1. Backs up covers + de_brevitate_vitae/book.md to /tmp
2. Deletes everything under books/
3. Recreates directories and restores covers
4. Downloads each book from Gutenberg (16 books)
5. Validates each book to generate clean book_manifest.json

Usage:
    python3 scripts/reset_books.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BOOKS_DIR = PROJECT_ROOT / "books"
BACKUP_DIR = Path("/tmp/classicsmodern_backup")

# Import catalog
sys.path.insert(0, str(PROJECT_ROOT))
from lib.book.catalog import BOOK_CATALOG


def backup_covers_and_special_files():
    """Back up all cover.png files and de_brevitate_vitae/book.md."""
    print("\n=== Phase 1: Backing up covers and special files ===\n")

    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    BACKUP_DIR.mkdir(parents=True)

    backed_up = 0
    for book_id in BOOK_CATALOG:
        book_dir = BOOKS_DIR / book_id
        if not book_dir.exists():
            continue

        backup_book_dir = BACKUP_DIR / book_id
        backup_book_dir.mkdir(parents=True, exist_ok=True)

        # Back up cover
        cover = book_dir / "cover.png"
        if cover.exists():
            shutil.copy2(cover, backup_book_dir / "cover.png")
            print(f"  Backed up {book_id}/cover.png")
            backed_up += 1

    # Special: de_brevitate_vitae/book.md (no Gutenberg source)
    dbv_book = BOOKS_DIR / "de_brevitate_vitae" / "book.md"
    if dbv_book.exists():
        dbv_backup = BACKUP_DIR / "de_brevitate_vitae"
        dbv_backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dbv_book, dbv_backup / "book.md")
        print(f"  Backed up de_brevitate_vitae/book.md")

    print(f"\n  Total covers backed up: {backed_up}")
    return backed_up


def wipe_books():
    """Delete everything under books/."""
    print("\n=== Phase 2: Wiping books directory ===\n")

    if not BOOKS_DIR.exists():
        print("  books/ directory doesn't exist, nothing to wipe")
        return

    deleted = 0
    for item in BOOKS_DIR.iterdir():
        if item.name.startswith('.'):
            continue
        if item.is_dir():
            shutil.rmtree(item)
            print(f"  Deleted {item.name}/")
            deleted += 1
        elif item.is_file():
            item.unlink()
            print(f"  Deleted {item.name}")
            deleted += 1

    print(f"\n  Deleted {deleted} items")


def restore_covers():
    """Recreate book directories and restore cover images."""
    print("\n=== Phase 3: Restoring covers ===\n")

    restored = 0
    for book_id in BOOK_CATALOG:
        book_dir = BOOKS_DIR / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        # Restore cover
        backup_cover = BACKUP_DIR / book_id / "cover.png"
        if backup_cover.exists():
            shutil.copy2(backup_cover, book_dir / "cover.png")
            print(f"  Restored {book_id}/cover.png")
            restored += 1

    # Restore de_brevitate_vitae/book.md
    dbv_backup = BACKUP_DIR / "de_brevitate_vitae" / "book.md"
    if dbv_backup.exists():
        dest = BOOKS_DIR / "de_brevitate_vitae" / "book.md"
        shutil.copy2(dbv_backup, dest)
        print(f"  Restored de_brevitate_vitae/book.md")

    print(f"\n  Restored {restored} covers")


def download_books():
    """Download each book from Gutenberg."""
    print("\n=== Phase 4: Downloading from Gutenberg ===\n")

    from server.gutenberg_downloader import GutenbergDownloader
    downloader = GutenbergDownloader()

    succeeded = 0
    failed = []

    for book_id, info in BOOK_CATALOG.items():
        gid = info.get('gutenberg_id')
        if gid is None:
            print(f"  Skipping {book_id} (no Gutenberg ID)")
            continue

        print(f"\n  Downloading {book_id} (Gutenberg #{gid})...")
        try:
            result = downloader.download_book(gid, book_id)
            if result.get('status') == 'error':
                print(f"  FAILED: {result.get('error', 'unknown error')}")
                failed.append(book_id)
            else:
                succeeded += 1
                print(f"  OK: {book_id}")
        except Exception as e:
            print(f"  FAILED: {e}")
            failed.append(book_id)

    print(f"\n  Downloaded: {succeeded}/{len(BOOK_CATALOG) - 1}")
    if failed:
        print(f"  Failed: {', '.join(failed)}")

    return failed


def validate_books():
    """Validate each book and generate book_manifest.json."""
    print("\n=== Phase 5: Validating books ===\n")

    validated = 0
    for book_id in BOOK_CATALOG:
        book_file = BOOKS_DIR / book_id / "book.md"
        if not book_file.exists():
            print(f"  Skipping {book_id} (no book.md)")
            continue

        print(f"  Validating {book_id}...", end=" ")
        try:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "validate.py"),
                 str(book_file), "--auto-fix"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_ROOT)
            )
            if result.returncode == 0:
                print("OK")
                validated += 1
            else:
                print(f"WARN (exit {result.returncode})")
                if result.stderr:
                    for line in result.stderr.strip().split('\n')[-3:]:
                        print(f"    {line}")
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\n  Validated: {validated}/{len(BOOK_CATALOG)}")


def verify_results():
    """Print final state of books directory."""
    print("\n=== Verification ===\n")

    for book_id in sorted(BOOK_CATALOG.keys()):
        book_dir = BOOKS_DIR / book_id
        has_book = (book_dir / "book.md").exists()
        has_manifest = (book_dir / "book_manifest.json").exists()
        has_cover = (book_dir / "cover.png").exists()
        status = "OK" if (has_book and has_cover) else "INCOMPLETE"
        print(f"  {book_id:45s} book.md={'Y' if has_book else 'N'}  "
              f"manifest={'Y' if has_manifest else 'N'}  "
              f"cover={'Y' if has_cover else 'N'}  [{status}]")


def main():
    print("=" * 60)
    print("  BOOK RESET — Storage Architecture Refactor")
    print("=" * 60)
    print(f"\n  Books directory: {BOOKS_DIR}")
    print(f"  Backup directory: {BACKUP_DIR}")
    print(f"  Books in catalog: {len(BOOK_CATALOG)}")

    # Confirm
    response = input("\n  This will DELETE all book data (covers will be preserved).\n"
                     "  Type 'yes' to continue: ")
    if response.strip().lower() != 'yes':
        print("  Aborted.")
        return

    backup_covers_and_special_files()
    wipe_books()
    restore_covers()
    failed = download_books()
    validate_books()
    verify_results()

    # Cleanup backup
    print(f"\n  Backup at {BACKUP_DIR} can be deleted if everything looks good.")

    if failed:
        print(f"\n  WARNING: {len(failed)} downloads failed: {', '.join(failed)}")
        print("  You can retry manually with:")
        for book_id in failed:
            gid = BOOK_CATALOG[book_id].get('gutenberg_id')
            print(f"    python3 server/gutenberg_downloader.py {gid} {book_id}")

    print("\n  Done!")


if __name__ == "__main__":
    main()
