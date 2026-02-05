#!/usr/bin/env python3
"""
Gutenberg Catalog Builder & Search

Crawls Project Gutenberg's top 500 books and creates a searchable catalog.

Usage:
    # Build catalog (one-time operation)
    python3 server/gutenberg_catalog.py --build

    # Refresh catalog
    python3 server/gutenberg_catalog.py --refresh

    # Search from CLI
    python3 server/gutenberg_catalog.py --search "alice"
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install requests beautifulsoup4")
    sys.exit(1)


# Constants
CATALOG_FILE = Path(__file__).parent / "gutenberg_catalog.json"
TOP_URL = "https://www.gutenberg.org/browse/scores/top1000"
DELAY_BETWEEN_REQUESTS = 1.0  # seconds (be polite)


class GutenbergCatalog:
    """Gutenberg catalog builder and search"""

    def __init__(self, catalog_file: Path = CATALOG_FILE):
        self.catalog_file = catalog_file
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict:
        """Load existing catalog from disk"""
        if self.catalog_file.exists():
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"books": [], "total": 0, "updated_at": None}

    def _save_catalog(self):
        """Save catalog to disk"""
        self.catalog_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_file, 'w', encoding='utf-8') as f:
            json.dump(self.catalog, f, indent=2, ensure_ascii=False)
        print(f"✓ Catalog saved: {self.catalog_file}")

    def build_catalog(self, limit: int = 1000) -> List[Dict]:
        """
        Build catalog by scraping Project Gutenberg top books.

        Args:
            limit: Maximum number of books to catalog (default: 1000)

        Returns:
            List of book metadata dictionaries
        """
        print(f"\n📚 Building Gutenberg catalog (top {limit} books)...")
        print("=" * 70)

        books = []

        try:
            # Fetch top books page
            print(f"Fetching: {TOP_URL}")
            response = requests.get(TOP_URL, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the ordered list of top books
            # Structure: <ol> with <li> containing <a href="/ebooks/ID">Title by Author</a>
            book_list = soup.find('ol')
            if not book_list:
                print("❌ Could not find book list on page")
                return []

            items = book_list.find_all('li')[:limit]
            print(f"Found {len(items)} books\n")

            for i, item in enumerate(items, 1):
                try:
                    # Parse book entry
                    link = item.find('a', href=re.compile(r'/ebooks/\d+'))
                    if not link:
                        continue

                    # Extract Gutenberg ID from URL
                    href = link.get('href', '')
                    match = re.search(r'/ebooks/(\d+)', href)
                    if not match:
                        continue

                    gutenberg_id = int(match.group(1))

                    # Extract text: "Title by Author (downloads)"
                    text = link.get_text(strip=True)

                    # Parse title and author
                    # Format examples:
                    # "Alice's Adventures in Wonderland by Lewis Carroll"
                    # "Pride and Prejudice by Jane Austen"
                    title, author = self._parse_title_author(text)

                    # Get download count from next sibling text
                    downloads = self._extract_downloads(item)

                    book = {
                        'gutenberg_id': gutenberg_id,
                        'title': title,
                        'author': author,
                        'language': 'en',  # Will be updated if we fetch individual pages
                        'year': None,
                        'downloads': downloads,
                        'url': f"https://www.gutenberg.org/ebooks/{gutenberg_id}"
                    }

                    books.append(book)

                    # Progress indicator
                    if i % 10 == 0:
                        print(f"  [{i:3d}/{len(items)}] {title[:50]}")

                except Exception as e:
                    print(f"  ⚠️  Error parsing book #{i}: {e}")
                    continue

            print(f"\n✓ Cataloged {len(books)} books")

            # Update catalog
            self.catalog = {
                "books": books,
                "total": len(books),
                "updated_at": datetime.now().isoformat()
            }

            self._save_catalog()
            return books

        except requests.RequestException as e:
            print(f"❌ Network error: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_title_author(self, text: str) -> tuple:
        """
        Parse 'Title by Author' format.

        Args:
            text: Book listing text

        Returns:
            Tuple of (title, author)
        """
        # Remove download count if present (in parentheses at end)
        text = re.sub(r'\s*\(\d+\)\s*$', '', text)

        # Split on " by "
        parts = text.split(' by ', 1)
        if len(parts) == 2:
            title = parts[0].strip()
            author = parts[1].strip()
        else:
            # No author, treat entire text as title
            title = text.strip()
            author = "Unknown"

        return title, author

    def _extract_downloads(self, item) -> int:
        """
        Extract download count from list item.

        Args:
            item: BeautifulSoup list item element

        Returns:
            Download count as integer, or 0 if not found
        """
        # Look for pattern: "(12345)"
        text = item.get_text()
        match = re.search(r'\((\d+)\)', text)
        if match:
            return int(match.group(1))
        return 0

    def search(
        self,
        query: str = "",
        language: str = "all",
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Search catalog with filters.

        Args:
            query: Search term (matches title and author)
            language: Language filter ('all', 'en', 'fr', 'de', 'es', 'ru', etc.)
            limit: Maximum results to return

        Returns:
            List of matching books
        """
        books = self.catalog.get("books", [])

        # Text search
        if query:
            query_lower = query.lower()
            books = [
                book for book in books
                if query_lower in book['title'].lower() or
                   query_lower in book['author'].lower()
            ]

        # Language filter
        if language != "all":
            books = [book for book in books if book['language'] == language]

        # Sort by downloads (most popular first)
        books.sort(key=lambda b: b.get('downloads', 0), reverse=True)

        # Apply limit
        if limit:
            books = books[:limit]

        return books

    def get_book_by_id(self, gutenberg_id: int) -> Optional[Dict]:
        """
        Get book metadata by Gutenberg ID.

        Args:
            gutenberg_id: Gutenberg book ID

        Returns:
            Book metadata dict, or None if not found
        """
        for book in self.catalog.get("books", []):
            if book['gutenberg_id'] == gutenberg_id:
                return book
        return None

    def get_stats(self) -> Dict:
        """
        Get catalog statistics.

        Returns:
            Dictionary with stats (total books, languages, etc.)
        """
        books = self.catalog.get("books", [])

        # Count by language
        languages = {}
        for book in books:
            lang = book.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1

        # Top authors
        authors = {}
        for book in books:
            author = book.get('author', 'Unknown')
            authors[author] = authors.get(author, 0) + 1

        top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total_books': len(books),
            'languages': languages,
            'top_authors': top_authors,
            'updated_at': self.catalog.get('updated_at')
        }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Gutenberg catalog builder and search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build catalog (first time)
  python3 server/gutenberg_catalog.py --build

  # Refresh catalog
  python3 server/gutenberg_catalog.py --refresh

  # Search for books
  python3 server/gutenberg_catalog.py --search "alice"
  python3 server/gutenberg_catalog.py --search "shakespeare" --language en

  # Show statistics
  python3 server/gutenberg_catalog.py --stats
        """
    )

    parser.add_argument(
        '--build',
        action='store_true',
        help='Build catalog by scraping Gutenberg (one-time operation)'
    )

    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Refresh existing catalog'
    )

    parser.add_argument(
        '--search',
        metavar='QUERY',
        help='Search catalog by title or author'
    )

    parser.add_argument(
        '--language',
        default='all',
        help='Filter by language (default: all)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of results'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show catalog statistics'
    )

    args = parser.parse_args()

    # Create catalog instance
    catalog = GutenbergCatalog()

    # Build/refresh
    if args.build or args.refresh:
        catalog.build_catalog()
        return

    # Statistics
    if args.stats:
        stats = catalog.get_stats()
        print("\n📊 Catalog Statistics")
        print("=" * 70)
        print(f"Total books: {stats['total_books']}")
        print(f"Updated: {stats['updated_at']}")
        print(f"\nLanguages:")
        for lang, count in stats['languages'].items():
            print(f"  {lang}: {count}")
        print(f"\nTop authors:")
        for author, count in stats['top_authors']:
            print(f"  {author}: {count} books")
        return

    # Search
    if args.search:
        results = catalog.search(
            query=args.search,
            language=args.language,
            limit=args.limit
        )

        print(f"\n🔍 Search results: {len(results)} books")
        print("=" * 70)

        for book in results:
            print(f"\n{book['title']}")
            print(f"  by {book['author']}")
            print(f"  ID: {book['gutenberg_id']} | Language: {book['language']} | Downloads: {book['downloads']}")
            print(f"  URL: {book['url']}")

        return

    # No action specified
    if not CATALOG_FILE.exists():
        print("❌ Catalog not found. Build it first:")
        print("   python3 server/gutenberg_catalog.py --build")
    else:
        print(f"✓ Catalog exists: {CATALOG_FILE}")
        stats = catalog.get_stats()
        print(f"  Total books: {stats['total_books']}")
        print(f"  Updated: {stats['updated_at']}")
        print("\nRun with --help for usage options")


if __name__ == "__main__":
    main()
