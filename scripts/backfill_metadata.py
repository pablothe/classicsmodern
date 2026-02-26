#!/usr/bin/env python3
"""
Backfill gutenberg_metadata.json for all existing books.

Matches each book directory to its Gutenberg ID using:
1. Existing gutenberg_metadata.json (if present)
2. download_top100.py slug → ID mapping
3. lib/book/catalog.py slug → ID mapping
4. server/gutenberg_catalog.json title matching

Then looks up title + author from:
- server/gutenberg_catalog.json (1000 books with title + author)
- Falls back to fetching the Gutenberg HTML <title> tag

Usage:
    python3 scripts/backfill_metadata.py
    python3 scripts/backfill_metadata.py --dry-run
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BOOKS_DIR = PROJECT_ROOT / "books"
CATALOG_JSON = PROJECT_ROOT / "server" / "gutenberg_catalog.json"

# Manual overrides for books where automated lookup fails
# (wrong Gutenberg IDs, not on Gutenberg, or unusual title formats)
MANUAL_METADATA = {
    'a_dolls_house': {'gutenberg_id': 2542, 'title': "A Doll's House", 'author': 'Henrik Ibsen'},
    'count_of_monte_cristo': {'gutenberg_id': 1184, 'title': 'The Count of Monte Cristo', 'author': 'Alexandre Dumas'},
    'tales_of_edgar_allan_poe': {'gutenberg_id': 2147, 'title': 'Tales of Edgar Allan Poe', 'author': 'Edgar Allan Poe'},
    'the_art_of_war': {'gutenberg_id': 132, 'title': 'The Art of War', 'author': 'Sun Tzu'},
    'the_awakening': {'gutenberg_id': 160, 'title': 'The Awakening', 'author': 'Kate Chopin'},
    'the_heads_of_cerberus': {'gutenberg_id': None, 'title': 'The Heads of Cerberus', 'author': 'Francis Stevens'},
    'the_time_machine': {'gutenberg_id': 35, 'title': 'The Time Machine', 'author': 'H.G. Wells'},
    'time_machine': {'gutenberg_id': 35, 'title': 'The Time Machine', 'author': 'H.G. Wells'},
    'twenty_thousand_leagues_under_the_sea': {'gutenberg_id': 164, 'title': 'Twenty Thousand Leagues Under the Sea', 'author': 'Jules Verne'},
    'the_pickwick_papers': {'gutenberg_id': 580, 'title': 'The Pickwick Papers', 'author': 'Charles Dickens'},
    'de_brevitate_vitae': {'gutenberg_id': None, 'title': 'On the Shortness of Life', 'author': 'Seneca'},
    'importance_of_being_earnest_v2': {'gutenberg_id': 844, 'title': 'The Importance of Being Earnest', 'author': 'Oscar Wilde'},
}


def load_slug_to_id_mapping() -> dict:
    """Build slug → gutenberg_id mapping from all available sources."""
    mapping = {}

    # Source 1: download_top100.py
    try:
        from scripts.download_top100 import TOP_100_BOOKS
        for gutenberg_id, slug, title, min_ch in TOP_100_BOOKS:
            mapping[slug] = gutenberg_id
    except ImportError:
        print("  Warning: Could not import download_top100.py")

    # Source 2: lib/book/catalog.py
    try:
        from lib.book.catalog import BOOK_CATALOG
        for slug, info in BOOK_CATALOG.items():
            if info.get('gutenberg_id'):
                mapping[slug] = info['gutenberg_id']
    except ImportError:
        print("  Warning: Could not import catalog.py")

    return mapping


def load_gutenberg_catalog() -> dict:
    """Load server/gutenberg_catalog.json → {gutenberg_id: {title, author}}."""
    if not CATALOG_JSON.exists():
        print(f"  Warning: {CATALOG_JSON} not found")
        return {}
    with open(CATALOG_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {b['gutenberg_id']: b for b in data.get('books', [])}


def fetch_metadata_from_html(gutenberg_id: int) -> dict:
    """Fetch title + author from Gutenberg HTML <title> tag."""
    try:
        import requests
        urls = [
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/{gutenberg_id}-h.htm",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.html",
        ]
        for url in urls:
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    # Just parse the <title> tag
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text[:5000], 'html.parser')
                    title_tag = soup.find('title')
                    if title_tag:
                        from server.gutenberg_downloader import GutenbergDownloader
                        return GutenbergDownloader._extract_metadata(soup)
            except Exception:
                continue
    except ImportError:
        pass
    return {'title': None, 'author': None}


def main():
    dry_run = '--dry-run' in sys.argv

    print(f"{'[DRY RUN] ' if dry_run else ''}Backfilling gutenberg_metadata.json")
    print("=" * 60)

    # Load all data sources
    slug_to_id = load_slug_to_id_mapping()
    print(f"Slug→ID mappings: {len(slug_to_id)}")

    catalog = load_gutenberg_catalog()
    print(f"Gutenberg catalog entries: {len(catalog)}")

    # Process each book directory
    if not BOOKS_DIR.exists():
        print(f"No books directory at {BOOKS_DIR}")
        return

    book_dirs = sorted(d for d in BOOKS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.'))
    print(f"Book directories: {len(book_dirs)}")
    print()

    created = 0
    updated = 0
    skipped = 0
    failed = 0

    for book_dir in book_dirs:
        slug = book_dir.name
        meta_path = book_dir / "gutenberg_metadata.json"

        # Load existing metadata if any
        existing = {}
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Already has title + author? Skip
        if existing.get('title') and existing.get('author'):
            skipped += 1
            continue

        # Check manual overrides first (fixes wrong IDs and non-Gutenberg books)
        if slug in MANUAL_METADATA:
            manual = MANUAL_METADATA[slug]
            meta = {
                'gutenberg_id': manual.get('gutenberg_id'),
                'title': manual['title'],
                'author': manual['author'],
                'downloaded_at': existing.get('downloaded_at', datetime.now().isoformat()),
            }
            if existing.get('language'):
                meta['language'] = existing['language']
            if dry_run:
                action = "UPDATE" if existing else "CREATE"
                print(f"  {slug}: [{action}] {meta['title']} by {meta['author']} (manual)")
            else:
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)
                action = "Updated" if existing else "Created"
                print(f"  {slug}: {action} — {meta['title']} by {meta['author']} (manual)")
            if existing:
                updated += 1
            else:
                created += 1
            continue

        # Find gutenberg_id
        gutenberg_id = existing.get('gutenberg_id') or slug_to_id.get(slug)

        if not gutenberg_id:
            print(f"  {slug}: No Gutenberg ID found")
            failed += 1
            continue

        # Look up in catalog, with sanity check
        catalog_entry = catalog.get(gutenberg_id, {})
        title = catalog_entry.get('title')
        author = catalog_entry.get('author')

        # Sanity check: catalog title should roughly match the slug
        # (the scraped catalog has some mismatched IDs)
        if title:
            slug_words = set(slug.replace('_', ' ').lower().split())
            # Replace hyphens with spaces before extracting words
            title_clean = title.lower().replace('-', ' ')
            title_words = set(re.sub(r'[^\w\s]', '', title_clean).split())
            # Need at least 2 significant word overlaps (or 1 if slug has <=2 words)
            stopwords = {'the', 'a', 'an', 'of', 'and', 'in', 'or', 'to', 'by', 'for', 'project', 'gutenberg'}
            overlap = (slug_words - stopwords) & (title_words - stopwords)
            min_overlap = 1 if len(slug_words - stopwords) <= 2 else 2
            if len(overlap) < min_overlap:
                print(f"  {slug}: Catalog mismatch (ID {gutenberg_id} = \"{title}\"), fetching HTML...")
                title = None
                author = None

        # If catalog doesn't have it or failed sanity check, try fetching HTML
        if not title or not author:
            print(f"  {slug}: {'Not in catalog' if not title else 'Missing author'}, fetching HTML...")
            html_meta = fetch_metadata_from_html(gutenberg_id)
            fetched_title = html_meta.get('title')
            fetched_author = html_meta.get('author')

            # Sanity check HTML result too
            if fetched_title:
                slug_words = set(slug.replace('_', ' ').lower().split())
                html_clean = fetched_title.lower().replace('-', ' ')
                html_words = set(re.sub(r'[^\w\s]', '', html_clean).split())
                stopwords = {'the', 'a', 'an', 'of', 'and', 'in', 'or', 'to', 'by', 'for', 'project', 'gutenberg'}
                overlap = (slug_words - stopwords) & (html_words - stopwords)
                min_overlap = 1 if len(slug_words - stopwords) <= 2 else 2
                if len(overlap) >= min_overlap:
                    title = fetched_title
                    author = fetched_author
                else:
                    print(f"  {slug}: HTML title mismatch (\"{fetched_title}\"), wrong Gutenberg ID {gutenberg_id}")

        if not title and not author:
            print(f"  {slug}: Could not find metadata (ID={gutenberg_id})")
            failed += 1
            continue

        # Build metadata
        meta = {
            'gutenberg_id': gutenberg_id,
            'title': title,
            'author': author,
            'downloaded_at': existing.get('downloaded_at', datetime.now().isoformat()),
        }
        # Preserve existing fields (language, etc.)
        if existing.get('language'):
            meta['language'] = existing['language']

        if dry_run:
            action = "UPDATE" if existing else "CREATE"
            print(f"  {slug}: [{action}] {title} by {author}")
        else:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            action = "Updated" if existing else "Created"
            print(f"  {slug}: {action} — {title} by {author}")

        if existing:
            updated += 1
        else:
            created += 1

    print()
    print(f"Results: {created} created, {updated} updated, {skipped} already complete, {failed} failed")
    print(f"Total: {created + updated + skipped + failed} / {len(book_dirs)} books")


if __name__ == '__main__':
    main()
