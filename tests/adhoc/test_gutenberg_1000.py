#!/usr/bin/env python3
"""
Test chapter detection on top 1,000 Gutenberg books.

Uses GutenbergCatalog to dynamically fetch the most popular books, then
runs the full chapter detection pipeline on each. Results are cached to
enable fast re-runs and regression tracking.

Usage:
    # Quick test (first 100 books)
    python3 tests/adhoc/test_gutenberg_1000.py --count 100

    # Full run (all 1000)
    python3 tests/adhoc/test_gutenberg_1000.py --count 1000

    # Resume from where you left off
    python3 tests/adhoc/test_gutenberg_1000.py --count 1000 --resume

    # Filter by language
    python3 tests/adhoc/test_gutenberg_1000.py --language en --count 500

    # Start from offset
    python3 tests/adhoc/test_gutenberg_1000.py --offset 200 --count 100

    # Save JSON results
    python3 tests/adhoc/test_gutenberg_1000.py --count 100 --json
"""

import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from bs4 import BeautifulSoup

from server.gutenberg_downloader import GutenbergDownloader
from server.gutenberg_catalog import GutenbergCatalog
from lib.book.processor import BookProcessor


RESULTS_FILE = Path(__file__).parent / "gutenberg_1000_results.json"


def load_cached_results() -> dict:
    """Load previously cached results."""
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_results(results: dict):
    """Save results to disk."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def test_book(downloader, processor, gutenberg_id, title):
    """Test chapter detection on a single Gutenberg book."""
    result = {
        'id': gutenberg_id,
        'title': title,
        'status': 'unknown',
        'toc_chapters': 0,
        'detected_chapters': 0,
        'detection_type': '',
        'detection_types': [],
        'italic_candidates': 0,
        'word_count': 0,
        'error': None,
        'tested_at': datetime.now().isoformat()
    }

    try:
        # Fetch HTML (just the page, no file saving)
        html_urls = [
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/{gutenberg_id}-h.htm",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.html",
        ]

        html_content = None
        for url in html_urls:
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    html_content = response.text
                    break
            except requests.RequestException:
                continue

        if not html_content:
            result['status'] = 'SKIP'
            result['error'] = 'No HTML available'
            return result

        # Extract TOC from HTML (same as downloader does)
        soup = BeautifulSoup(html_content, 'html.parser')
        toc_entries = downloader._extract_toc_from_html(soup)
        result['toc_chapters'] = len(toc_entries)

        # Inject chapter headers and convert to markdown
        if toc_entries:
            downloader._inject_chapter_headers(soup, toc_entries)

        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        body = soup.body if soup.body else soup
        markdown = downloader._convert_element_to_markdown(body)

        # Apply italic chapter promotion (same as downloader does when no TOC)
        if not toc_entries:
            markdown = downloader._promote_italic_chapter_lines(markdown)

        markdown = markdown.strip()

        if len(markdown) < 500:
            result['status'] = 'SKIP'
            result['error'] = f'Too short ({len(markdown)} chars)'
            return result

        result['word_count'] = len(markdown.split())

        # Count italic chapter candidates (before detection)
        import re
        italic_pattern = re.compile(
            r'^\*(?:(?:CHAPTER|Chapter|CHAPITRE|Chapitre)\s+)?'
            r'([IVXLCDM]+|\d+)\.\s+(.+?)\*$',
            re.MULTILINE | re.IGNORECASE
        )
        result['italic_candidates'] = len(italic_pattern.findall(markdown))

        # Run chapter detection
        chapters = processor.detect_chapters(markdown)
        result['detected_chapters'] = len(chapters)

        # Track all detection types used
        type_counts = Counter(ch.detection_type for ch in chapters)
        result['detection_types'] = dict(type_counts)
        result['detection_type'] = chapters[0].detection_type if chapters else 'none'

        # Evaluate: any book with 2+ chapters is a PASS
        if len(chapters) >= 2:
            result['status'] = 'PASS'
        elif len(chapters) == 1 and chapters[0].detection_type != 'single_chapter_fallback':
            result['status'] = 'PASS'
        elif len(chapters) == 1 and result['word_count'] < 5000:
            # Short works (essays, poems) legitimately have 1 chapter
            result['status'] = 'PASS'
        elif len(chapters) == 1:
            result['status'] = 'WARN'  # Long work with only 1 chapter detected
        else:
            result['status'] = 'FAIL'

    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)[:200]

    return result


def print_summary(results: list):
    """Print detailed summary statistics."""
    total = len(results)
    statuses = Counter(r['status'] for r in results)
    detection_types = Counter()
    italic_books = 0
    total_italic = 0

    for r in results:
        if isinstance(r.get('detection_types'), dict):
            for dtype, count in r['detection_types'].items():
                detection_types[dtype] += count
        if r.get('italic_candidates', 0) > 0:
            italic_books += 1
            total_italic += r['italic_candidates']

    tested = statuses.get('PASS', 0) + statuses.get('WARN', 0) + statuses.get('FAIL', 0)

    print(f"\n{'='*80}")
    print(f"SUMMARY ({total} books)")
    print(f"{'='*80}")
    print(f"  PASS:  {statuses.get('PASS', 0):>4}  (chapters detected correctly)")
    print(f"  WARN:  {statuses.get('WARN', 0):>4}  (long work, only 1 chapter)")
    print(f"  FAIL:  {statuses.get('FAIL', 0):>4}  (no chapters detected)")
    print(f"  SKIP:  {statuses.get('SKIP', 0):>4}  (no HTML / too short)")
    print(f"  ERROR: {statuses.get('ERROR', 0):>4}  (exception during processing)")
    if tested > 0:
        print(f"\n  Pass rate: {statuses.get('PASS', 0)}/{tested} ({100*statuses.get('PASS', 0)/tested:.1f}%)")

    print(f"\nDetection type distribution:")
    for dtype, count in detection_types.most_common():
        print(f"  {dtype:<25} {count:>5} chapters")

    if italic_books > 0:
        print(f"\nItalic chapter analysis:")
        print(f"  Books with italic candidates: {italic_books}")
        print(f"  Total italic chapter lines:   {total_italic}")

    # Show WARN/FAIL books for investigation
    problems = [r for r in results if r['status'] in ('WARN', 'FAIL')]
    if problems:
        print(f"\nBooks needing investigation ({len(problems)}):")
        for r in problems[:20]:
            print(f"  [{r['status']}] ID {r['id']:>6}  {r.get('detected_chapters', 0)} ch  "
                  f"{r.get('word_count', 0):>6} words  {r['title'][:45]}")
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")


def main():
    parser = argparse.ArgumentParser(description='Test chapter detection on top Gutenberg books')
    parser.add_argument('--count', type=int, default=100, help='Number of books to test (default: 100)')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between requests in seconds (default: 1.5)')
    parser.add_argument('--language', type=str, default=None, help='Filter by language code (e.g., en, fr, de)')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N books')
    parser.add_argument('--resume', action='store_true', help='Skip already-tested books from cache')
    parser.add_argument('--json', action='store_true', help='Save JSON results to file')
    parser.add_argument('--catalog-only', action='store_true', help='Just build/refresh the catalog and exit')
    args = parser.parse_args()

    # Load or build catalog
    catalog = GutenbergCatalog()
    if not catalog.catalog.get('books') or args.catalog_only:
        print("Building Gutenberg catalog (this takes ~15 minutes for 1000 books)...")
        catalog.build_catalog(limit=1000)
        if args.catalog_only:
            return 0

    books = catalog.catalog.get('books', [])
    if not books:
        print("No books in catalog. Run with --catalog-only first.")
        return 1

    # Filter by language
    if args.language:
        books = [b for b in books if b.get('language', '') == args.language]
        print(f"Filtered to {len(books)} {args.language} books")

    # Apply offset and count
    books = books[args.offset:args.offset + args.count]

    if not books:
        print("No books to test after applying filters.")
        return 1

    # Load cached results for resume
    cached = load_cached_results() if args.resume else {}
    cached_ids = set(cached.keys()) if isinstance(cached, dict) and 'results' in cached else set()
    if isinstance(cached, dict) and 'results' in cached:
        cached_ids = {str(r['id']) for r in cached['results']}

    downloader = GutenbergDownloader()
    processor = BookProcessor(verbose=False)

    results = []
    pass_count = warn_count = fail_count = skip_count = error_count = 0

    print(f"\nTesting chapter detection on {len(books)} Gutenberg books...")
    print(f"{'='*90}")
    print(f"{'#':>5}  {'ID':>6}  {'Status':<6}  {'TOC':>4}  {'Det':>4}  {'Italic':>6}  {'Type':<20}  Title")
    print(f"{'-'*90}")

    for i, book in enumerate(books, 1):
        book_id = book['gutenberg_id']
        title = book.get('title', 'Unknown')

        # Skip if already tested (resume mode)
        if args.resume and str(book_id) in cached_ids:
            # Find cached result
            cached_result = next((r for r in cached['results'] if r['id'] == book_id), None)
            if cached_result:
                results.append(cached_result)
                status = cached_result['status']
                if status == 'PASS': pass_count += 1
                elif status == 'WARN': warn_count += 1
                elif status == 'FAIL': fail_count += 1
                elif status == 'SKIP': skip_count += 1
                else: error_count += 1
                continue

        result = test_book(downloader, processor, book_id, title)
        results.append(result)

        status_icon = {
            'PASS': '\033[32mPASS\033[0m',
            'WARN': '\033[33mWARN\033[0m',
            'FAIL': '\033[31mFAIL\033[0m',
            'SKIP': '\033[90mSKIP\033[0m',
            'ERROR': '\033[31mERR!\033[0m',
        }.get(result['status'], result['status'])

        error_info = f"  ({result['error'][:40]})" if result['error'] else ''
        italic_str = str(result.get('italic_candidates', 0))
        print(f"{i:>5}  {book_id:>6}  {status_icon:<15}  {result['toc_chapters']:>4}  "
              f"{result['detected_chapters']:>4}  {italic_str:>6}  "
              f"{result['detection_type']:<20}  {title[:30]}{error_info}")

        if result['status'] == 'PASS': pass_count += 1
        elif result['status'] == 'WARN': warn_count += 1
        elif result['status'] == 'FAIL': fail_count += 1
        elif result['status'] == 'SKIP': skip_count += 1
        else: error_count += 1

        # Rate limit (only for non-cached)
        if i < len(books):
            time.sleep(args.delay)

    print_summary(results)

    if args.json:
        output = {
            'tested_at': datetime.now().isoformat(),
            'total': len(results),
            'pass': pass_count,
            'warn': warn_count,
            'fail': fail_count,
            'skip': skip_count,
            'error': error_count,
            'results': results
        }
        save_results(output)
        print(f"\nJSON results saved to {RESULTS_FILE}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
