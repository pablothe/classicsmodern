#!/usr/bin/env python3
"""
Download the top 100 classic books from Project Gutenberg and verify chapter detection.

Downloads each book into books/{slug}/ with book.md + gutenberg_chapters.json,
then verifies that chapter detection uses the Gutenberg TOC (Priority 0).

Usage:
    python3 scripts/download_top100.py [--delay 2.0] [--skip-existing]
"""

import sys
import time
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.gutenberg_downloader import GutenbergDownloader
from lib.book.processor import BookProcessor


# Top 100 most important/popular Gutenberg books
# (gutenberg_id, slug, expected_title, min_chapters)
TOP_100_BOOKS = [
    # English Literature — Novels
    (11, "alice_adventures_in_wonderland", "Alice's Adventures in Wonderland", 12),
    (1342, "pride_and_prejudice", "Pride and Prejudice", 40),
    (84, "frankenstein", "Frankenstein", 20),
    (1661, "adventures_of_sherlock_holmes", "The Adventures of Sherlock Holmes", 10),
    (345, "dracula", "Dracula", 20),
    (2701, "moby_dick", "Moby Dick", 100),
    (98, "a_tale_of_two_cities", "A Tale of Two Cities", 30),
    (1400, "great_expectations", "Great Expectations", 40),
    (46, "a_christmas_carol", "A Christmas Carol", 3),
    (219, "heart_of_darkness", "Heart of Darkness", 2),
    (174, "picture_of_dorian_gray", "The Picture of Dorian Gray", 15),
    (35, "the_time_machine", "The Time Machine", 10),
    (36, "war_of_the_worlds", "The War of the Worlds", 20),
    (120, "treasure_island", "Treasure Island", 20),
    (5200, "metamorphosis", "Metamorphosis", 3),
    (2591, "grimms_fairy_tales", "Grimm's Fairy Tales", 50),
    (2600, "war_and_peace", "War and Peace", 100),
    (55, "wonderful_wizard_of_oz", "The Wonderful Wizard of Oz", 20),
    (514, "little_women", "Little Women", 30),
    (1260, "jane_eyre", "Jane Eyre", 30),
    (768, "wuthering_heights", "Wuthering Heights", 25),
    (16, "peter_pan", "Peter Pan", 10),
    (244, "a_study_in_scarlet", "A Study in Scarlet", 10),
    (2852, "hound_of_the_baskervilles", "The Hound of the Baskervilles", 10),
    (76, "adventures_of_huckleberry_finn", "Adventures of Huckleberry Finn", 30),
    (74, "adventures_of_tom_sawyer", "Adventures of Tom Sawyer", 25),
    (42, "dr_jekyll_and_mr_hyde", "The Strange Case of Dr Jekyll and Mr Hyde", 8),
    (215, "the_call_of_the_wild", "The Call of the Wild", 5),
    (910, "white_fang", "White Fang", 20),
    (45, "anne_of_green_gables", "Anne of Green Gables", 30),
    (236, "the_jungle_book", "The Jungle Book", 10),
    (829, "gullivers_travels", "Gulliver's Travels", 20),
    (25344, "the_scarlet_letter", "The Scarlet Letter", 20),
    (209, "the_turn_of_the_screw", "The Turn of the Screw", 20),
    (164, "twenty_thousand_leagues_under_the_sea", "Twenty Thousand Leagues Under the Sea", 40),
    (103, "around_the_world_in_eighty_days", "Around the World in Eighty Days", 30),
    (730, "oliver_twist", "Oliver Twist", 40),
    (1023, "bleak_house", "Bleak House", 40),
    (766, "david_copperfield", "David Copperfield", 40),
    (786, "hard_times", "Hard Times", 20),
    (158, "emma", "Emma", 40),
    (161, "sense_and_sensibility", "Sense and Sensibility", 40),
    (105, "persuasion", "Persuasion", 20),
    (141, "mansfield_park", "Mansfield Park", 40),
    (1399, "anna_karenina", "Anna Karenina", 50),
    (2554, "crime_and_punishment", "Crime and Punishment", 30),
    (28054, "the_brothers_karamazov", "The Brothers Karamazov", 50),
    (600, "notes_from_underground", "Notes from Underground", 5),
    (4300, "ulysses", "Ulysses", 10),
    (2814, "dubliners", "Dubliners", 10),

    # American Literature
    (1952, "the_yellow_wallpaper", "The Yellow Wallpaper", 1),
    (205, "walden", "Walden", 10),
    (23, "narrative_of_frederick_douglass", "Narrative of the Life of Frederick Douglass", 10),
    (408, "the_souls_of_black_folk", "The Souls of Black Folk", 10),
    (4517, "ethan_frome", "Ethan Frome", 5),
    (160, "the_awakening", "The Awakening", 30),
    (62, "a_princess_of_mars", "A Princess of Mars", 20),
    (1250, "anthem", "Anthem", 10),

    # Philosophy & Political Theory
    (1232, "the_prince", "The Prince", 20),
    (2680, "meditations", "Meditations", 10),
    (1497, "the_republic", "The Republic", 8),
    (3207, "leviathan", "Leviathan", 30),
    (7370, "second_treatise_of_government", "Second Treatise of Government", 10),
    (132, "the_art_of_war", "The Art of War", 10),
    (1998, "thus_spake_zarathustra", "Thus Spake Zarathustra", 30),
    (4363, "beyond_good_and_evil", "Beyond Good and Evil", 5),
    (5740, "tractatus_logico_philosophicus", "Tractatus Logico-Philosophicus", 5),
    (3296, "confessions_of_st_augustine", "The Confessions of St. Augustine", 10),

    # Drama & Poetry
    (1524, "hamlet", "Hamlet", 3),
    (1513, "romeo_and_juliet", "Romeo and Juliet", 3),
    (2264, "macbeth", "Macbeth", 3),
    (844, "importance_of_being_earnest", "The Importance of Being Earnest", 3),
    (2542, "a_dolls_house", "A Doll's House", 3),
    (3825, "pygmalion", "Pygmalion", 3),
    (1322, "leaves_of_grass", "Leaves of Grass", 10),

    # Ancient Literature
    (6130, "the_iliad", "The Iliad", 20),
    (1727, "the_odyssey", "The Odyssey", 20),

    # World Literature
    (135, "les_miserables", "Les Misérables", 50),
    (996, "don_quixote", "Don Quixote", 40),
    (1184, "count_of_monte_cristo", "The Count of Monte Cristo", 50),
    (2500, "siddhartha", "Siddhartha", 5),

    # Non-Fiction & Essays
    (1080, "a_modest_proposal", "A Modest Proposal", 1),
    (27827, "the_kama_sutra", "The Kama Sutra", 5),

    # Gothic & Horror
    (2147, "tales_of_edgar_allan_poe", "Tales of Edgar Allan Poe", 5),

    # More English Classics
    (580, "the_pickwick_papers", "The Pickwick Papers", 40),
    (6593, "history_of_tom_jones", "The History of Tom Jones", 10),
    (1934, "songs_of_innocence_and_experience", "Songs of Innocence and Experience", 5),

    # Additional well-known works
    (4363, "beyond_good_and_evil", "Beyond Good and Evil", 5),  # skip dup
    (20203, "autobiography_of_benjamin_franklin", "Autobiography of Benjamin Franklin", 5),
    (1661, "sherlock_holmes", "The Adventures of Sherlock Holmes", 10),  # skip dup

    # Science Fiction
    (35, "the_time_machine_v2", "The Time Machine", 10),  # skip dup
    (5230, "the_heads_of_cerberus", "The Heads of Cerberus", 10),  # Not on Gutenberg — ID 5230 is The Invisible Man

    # More American & British
    (2148, "works_of_edgar_allan_poe", "The Works of Edgar Allan Poe", 5),
    (1934, "songs_of_innocence", "Songs of Innocence", 5),  # skip dup
]


def download_and_test(downloader, processor, gutenberg_id, slug, expected_title, min_chapters, skip_existing=False):
    """Download a book and test chapter detection."""
    book_dir = downloader.books_dir / slug
    book_file = book_dir / "book.md"
    gutenberg_json = book_dir / "gutenberg_chapters.json"

    result = {
        'id': gutenberg_id,
        'slug': slug,
        'expected_title': expected_title,
        'min_chapters': min_chapters,
        'status': 'unknown',
        'toc_chapters': 0,
        'detected_chapters': 0,
        'detection_type': 'none',
        'priority_0': False,
        'error': None,
    }

    try:
        # Download if needed
        if skip_existing and book_file.exists():
            result['skipped_download'] = True
        else:
            dl_result = downloader.download_book(gutenberg_id, slug)
            if not dl_result.get('success'):
                result['status'] = 'DOWNLOAD_FAIL'
                result['error'] = dl_result.get('error', 'Unknown download error')
                return result

        # Read the book
        text = book_file.read_text(encoding='utf-8')

        # Check gutenberg_chapters.json
        if gutenberg_json.exists():
            gc_data = json.loads(gutenberg_json.read_text(encoding='utf-8'))
            result['toc_chapters'] = gc_data.get('chapter_count', len(gc_data.get('chapters', [])))

        # Run chapter detection with book_file (should trigger Priority 0)
        cleaned, _ = processor.strip_gutenberg(text)
        chapters = processor.detect_chapters(cleaned, book_file=book_file)
        result['detected_chapters'] = len(chapters)
        result['detection_type'] = chapters[0].detection_type if chapters else 'none'
        result['priority_0'] = result['detection_type'] == 'gutenberg_toc'

        # Evaluate
        if len(chapters) >= min_chapters:
            result['status'] = 'PASS'
        elif len(chapters) >= 1:
            result['status'] = 'WARN'
        else:
            result['status'] = 'FAIL'

    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)[:150]

    return result


def main():
    parser = argparse.ArgumentParser(description='Download top 100 Gutenberg books and test chapter detection')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between downloads (seconds)')
    parser.add_argument('--skip-existing', action='store_true', help='Skip books that already exist in library')
    parser.add_argument('--count', type=int, default=100, help='Max number of books to download')
    parser.add_argument('--json', action='store_true', help='Save JSON results')
    args = parser.parse_args()

    # Deduplicate by gutenberg_id
    seen_ids = set()
    books = []
    for gutenberg_id, slug, title, min_ch in TOP_100_BOOKS:
        if gutenberg_id not in seen_ids:
            seen_ids.add(gutenberg_id)
            books.append((gutenberg_id, slug, title, min_ch))
    books = books[:args.count]

    downloader = GutenbergDownloader()
    processor = BookProcessor(verbose=False)

    results = []
    counts = {'PASS': 0, 'WARN': 0, 'FAIL': 0, 'ERROR': 0, 'DOWNLOAD_FAIL': 0}
    priority_0_count = 0

    print(f"\nDownloading and testing {len(books)} classic books from Project Gutenberg")
    print(f"{'=' * 100}")
    print(f"{'#':>4}  {'ID':>6}  {'Status':<6}  {'P0':>3}  {'TOC':>4}  {'Det':>4}  {'Type':<16}  Slug")
    print(f"{'-' * 100}")

    for i, (book_id, slug, title, min_ch) in enumerate(books, 1):
        result = download_and_test(downloader, processor, book_id, slug, title, min_ch,
                                   skip_existing=args.skip_existing)
        results.append(result)

        status = result['status']
        counts[status] = counts.get(status, 0) + 1
        if result['priority_0']:
            priority_0_count += 1

        status_color = {
            'PASS': '\033[32m', 'WARN': '\033[33m', 'FAIL': '\033[31m',
            'ERROR': '\033[31m', 'DOWNLOAD_FAIL': '\033[31m'
        }.get(status, '')
        reset = '\033[0m'

        p0 = 'YES' if result['priority_0'] else 'no'
        error_info = f"  ({result['error'][:50]})" if result.get('error') else ''
        print(f"{i:>4}  {book_id:>6}  {status_color}{status:<6}{reset}  {p0:>3}  {result['toc_chapters']:>4}  {result['detected_chapters']:>4}  {result['detection_type']:<16}  {slug[:40]}{error_info}")

        # Rate limit (skip delay for skipped downloads)
        if i < len(books) and not result.get('skipped_download'):
            time.sleep(args.delay)

    # Summary
    total_tested = counts['PASS'] + counts['WARN'] + counts['FAIL']
    print(f"\n{'=' * 100}")
    print(f"\nRESULTS SUMMARY")
    print(f"  Downloads:   {len(results)} attempted")
    print(f"  PASS:        {counts['PASS']}")
    print(f"  WARN:        {counts['WARN']} (chapters found but fewer than expected)")
    print(f"  FAIL:        {counts['FAIL']}")
    print(f"  ERROR:       {counts['ERROR'] + counts.get('DOWNLOAD_FAIL', 0)}")
    print(f"  Priority 0:  {priority_0_count}/{total_tested} used gutenberg_chapters.json")
    if total_tested > 0:
        print(f"  Pass rate:   {counts['PASS']}/{total_tested} ({100*counts['PASS']/total_tested:.0f}%)")
        print(f"  P0 rate:     {priority_0_count}/{total_tested} ({100*priority_0_count/total_tested:.0f}%)")

    if args.json:
        output_path = Path('scripts/top100_results.json')
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n  JSON results saved to {output_path}")

    return 0 if counts['FAIL'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
