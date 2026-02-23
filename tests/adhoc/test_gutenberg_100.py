#!/usr/bin/env python3
"""
Test chapter detection on 100 Gutenberg books (fetch-only, no full download).

Fetches only the HTML page for each book, extracts TOC, converts to markdown,
and verifies chapter detection works via the new priority chain.

Usage:
    python3 tests/adhoc/test_gutenberg_100.py [--count 100] [--delay 1.5]
"""

import sys
import time
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from bs4 import BeautifulSoup

from server.gutenberg_downloader import GutenbergDownloader
from lib.book.processor import BookProcessor


# 100 well-known Gutenberg books (ID, expected_title, expected_min_chapters)
GUTENBERG_BOOKS = [
    # English classics
    (11, "Alice's Adventures in Wonderland", 12),
    (1342, "Pride and Prejudice", 40),
    (84, "Frankenstein", 20),
    (1661, "Sherlock Holmes", 10),
    (345, "Dracula", 20),
    (2701, "Moby Dick", 100),
    (1952, "The Yellow Wallpaper", 1),
    (98, "A Tale of Two Cities", 30),
    (2542, "The Count of Monte Cristo", 50),
    (76, "Huckleberry Finn", 30),
    (74, "Tom Sawyer", 25),
    (1400, "Great Expectations", 40),
    (46, "A Christmas Carol", 3),
    (219, "Heart of Darkness", 2),
    (174, "Picture of Dorian Gray", 15),
    (64, "The Time Machine", 10),
    (36, "War of the Worlds", 20),
    (1232, "The Prince", 20),
    (4300, "Ulysses", 10),
    (996, "Don Quixote", 40),
    (120, "Treasure Island", 20),
    (5200, "Metamorphosis", 3),
    (1080, "A Modest Proposal", 1),
    (2591, "Grimm's Fairy Tales", 50),
    (2600, "War and Peace", 100),
    (55, "Wizard of Oz", 20),
    (514, "Little Women", 30),
    (1260, "Jane Eyre", 30),
    (768, "Wuthering Heights", 25),
    (16, "Peter Pan", 10),
    (6130, "The Iliad", 20),
    (1727, "The Odyssey", 20),
    (135, "Les Misérables", 50),
    (244, "A Study in Scarlet", 10),
    (2852, "The Hound of the Baskervilles", 10),
    (1184, "The Importance of Being Earnest", 3),
    (5230, "The Heads of Cerberus", 10),
    (3207, "Leviathan", 30),
    (2680, "Meditations", 10),
    (1497, "Republic", 8),
    (205, "Walden", 10),
    (1322, "Leaves of Grass", 10),
    (158, "Emma", 40),
    (161, "Sense and Sensibility", 40),
    (105, "Persuasion", 20),
    (141, "Mansfield Park", 40),
    (42, "The Strange Case of Dr Jekyll and Mr Hyde", 8),
    (215, "The Call of the Wild", 5),
    (910, "White Fang", 20),
    (27827, "The Kama Sutra", 5),
    (1250, "Anthem", 10),
    (5740, "Tractatus Logico-Philosophicus", 5),
    (43, "The Strange Case of Dr Jekyll and Mr Hyde", 5),
    (2814, "Dubliners", 10),
    (45, "Anne of Green Gables", 30),
    (3600, "Edgar Allan Poe's Tales", 5),
    (408, "The Souls of Black Folk", 10),
    (236, "The Jungle Book", 10),
    (35, "The Time Machine", 10),
    (1727, "The Odyssey (Butler)", 20),
    (6593, "History of Tom Jones", 10),
    (20203, "Autobiography of Benjamin Franklin", 5),
    (844, "The Importance of Being Earnest", 3),
    (2500, "Siddhartha", 5),
    (829, "Gulliver's Travels", 20),
    (3296, "The Confessions of St. Augustine", 10),
    (30254, "The Romance of Lust", 5),
    (1513, "Romeo and Juliet", 3),
    (2264, "Macbeth", 3),
    (1524, "Hamlet", 3),
    (23, "Narrative of the Life of Frederick Douglass", 10),
    (1998, "Thus Spake Zarathustra", 30),
    (4363, "Beyond Good and Evil", 5),
    (62, "A Princess of Mars", 20),
    (28054, "The Brothers Karamazov", 50),
    (600, "Notes from the Underground", 5),
    (2554, "Crime and Punishment", 30),
    (7370, "Second Treatise of Government", 10),
    (4280, "The Art of War", 10),
    (730, "Oliver Twist", 40),
    (1023, "Bleak House", 40),
    (766, "David Copperfield", 40),
    (580, "The Pickwick Papers", 40),
    (786, "Hard Times", 20),
    (19337, "A Doll's House", 3),
    (2148, "The Works of Edgar Allan Poe", 5),
    (2097, "The Autobiography of Benjamin Franklin", 5),
    (25344, "The Scarlet Letter", 20),
    (209, "The Turn of the Screw", 20),
    (1399, "Anna Karenina", 50),
    (1934, "Songs of Innocence", 5),
    (2160, "The Awakening", 30),
    (4517, "Ethan Frome", 5),
    (160, "The Awakening", 20),
    (514, "Little Women", 30),
    (3825, "Pygmalion", 3),
    (1260, "Jane Eyre", 30),
    (1259, "Twenty Thousand Leagues Under the Sea", 40),
    (103, "Around the World in Eighty Days", 30),
    (164, "Twenty Thousand Leagues Under the Seas", 30),
]


def test_book(downloader, processor, gutenberg_id, expected_title, min_chapters):
    """Test chapter detection on a single Gutenberg book."""
    result = {
        'id': gutenberg_id,
        'expected_title': expected_title,
        'min_chapters_expected': min_chapters,
        'status': 'unknown',
        'toc_chapters': 0,
        'detected_chapters': 0,
        'detection_type': '',
        'error': None
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
        markdown = markdown.strip()

        if len(markdown) < 500:
            result['status'] = 'SKIP'
            result['error'] = f'Too short ({len(markdown)} chars)'
            return result

        # Run chapter detection (Priority 2: markdown headers)
        chapters = processor.detect_chapters(markdown)
        result['detected_chapters'] = len(chapters)
        result['detection_type'] = chapters[0].detection_type if chapters else 'none'

        # Evaluate result
        if len(chapters) >= min_chapters:
            result['status'] = 'PASS'
        elif len(chapters) >= 1:
            result['status'] = 'WARN'  # Detected chapters but fewer than expected
        else:
            result['status'] = 'FAIL'

    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)[:100]

    return result


def main():
    parser = argparse.ArgumentParser(description='Test chapter detection on Gutenberg books')
    parser.add_argument('--count', type=int, default=100, help='Number of books to test')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between requests (seconds)')
    parser.add_argument('--json', action='store_true', help='Output JSON results')
    args = parser.parse_args()

    # Deduplicate by gutenberg_id
    seen_ids = set()
    books = []
    for book_id, title, min_ch in GUTENBERG_BOOKS:
        if book_id not in seen_ids:
            seen_ids.add(book_id)
            books.append((book_id, title, min_ch))
    books = books[:args.count]

    downloader = GutenbergDownloader()
    processor = BookProcessor(verbose=False)

    results = []
    pass_count = 0
    warn_count = 0
    fail_count = 0
    skip_count = 0
    error_count = 0

    print(f"Testing chapter detection on {len(books)} Gutenberg books...")
    print(f"{'='*80}")
    print(f"{'#':>5}  {'ID':>6}  {'Status':<6}  {'TOC':>4}  {'Det':>4}  {'Type':<16}  Title")
    print(f"{'-'*80}")

    for i, (book_id, title, min_ch) in enumerate(books, 1):
        result = test_book(downloader, processor, book_id, title, min_ch)
        results.append(result)

        status_icon = {
            'PASS': '\033[32mPASS\033[0m',
            'WARN': '\033[33mWARN\033[0m',
            'FAIL': '\033[31mFAIL\033[0m',
            'SKIP': '\033[90mSKIP\033[0m',
            'ERROR': '\033[31mERR!\033[0m',
        }.get(result['status'], result['status'])

        error_info = f"  ({result['error']})" if result['error'] else ''
        print(f"{i:>5}  {book_id:>6}  {status_icon:<15}  {result['toc_chapters']:>4}  {result['detected_chapters']:>4}  {result['detection_type']:<16}  {title[:35]}{error_info}")

        if result['status'] == 'PASS':
            pass_count += 1
        elif result['status'] == 'WARN':
            warn_count += 1
        elif result['status'] == 'FAIL':
            fail_count += 1
        elif result['status'] == 'SKIP':
            skip_count += 1
        else:
            error_count += 1

        # Rate limit
        if i < len(books):
            time.sleep(args.delay)

    print(f"{'='*80}")
    print(f"\nResults: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL, {skip_count} SKIP, {error_count} ERROR")
    print(f"Pass rate: {pass_count}/{pass_count + warn_count + fail_count} ({100*pass_count/max(1, pass_count+warn_count+fail_count):.0f}%)")

    if args.json:
        output_path = Path('tests/adhoc/gutenberg_100_results.json')
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nJSON results saved to {output_path}")

    # Return exit code based on results
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
