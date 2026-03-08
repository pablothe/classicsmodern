#!/usr/bin/env python3
"""
Book Catalog - Bibliographic Information

Centralized catalog of classic books with author, publication year,
and other bibliographic information for display in the audiobook player.
"""

BOOK_CATALOG = {
    'alice_adventures': {
        'title': "Alice's Adventures in Wonderland",
        'author': 'Lewis Carroll',
        'year': 1865,
        'original_language': 'English',
        'gutenberg_id': 11
    },
    'call_cthulhu': {
        'title': 'The Call of Cthulhu',
        'author': 'H.P. Lovecraft',
        'year': 1928,
        'original_language': 'English',
        'gutenberg_id': 68283
    },
    'candide_voltaire': {
        'title': 'Candide',
        'author': 'Voltaire',
        'year': 1759,
        'original_language': 'French',
        'gutenberg_id': 19942
    },
    'crime_punishment': {
        'title': 'Crime and Punishment',
        'author': 'Fyodor Dostoevsky',
        'year': 1866,
        'original_language': 'Russian',
        'gutenberg_id': 2554
    },
    'de_brevitate_vitae': {
        'title': 'On the Shortness of Life',
        'author': 'Seneca',
        'year': 49,  # AD
        'original_language': 'Latin',
        'gutenberg_id': None
    },
    'don_quijote': {
        'title': 'Don Quixote',
        'author': 'Miguel de Cervantes',
        'year': 1605,
        'original_language': 'Spanish',
        'gutenberg_id': 996
    },
    'great_gatsby': {
        'title': 'The Great Gatsby',
        'author': 'F. Scott Fitzgerald',
        'year': 1925,
        'original_language': 'English',
        'gutenberg_id': 64317
    },
    'metamorphosis': {
        'title': 'The Metamorphosis',
        'author': 'Franz Kafka',
        'year': 1915,
        'original_language': 'German',
        'gutenberg_id': 5200
    },
    'moby_dick': {
        'title': 'Moby-Dick',
        'author': 'Herman Melville',
        'year': 1851,
        'original_language': 'English',
        'gutenberg_id': 2701
    },
    'origin_species': {
        'title': 'On the Origin of Species',
        'author': 'Charles Darwin',
        'year': 1859,
        'original_language': 'English',
        'gutenberg_id': 1228
    },
    'pride_prejudice': {
        'title': 'Pride and Prejudice',
        'author': 'Jane Austen',
        'year': 1813,
        'original_language': 'English',
        'gutenberg_id': 1342
    },
    'sherlock_holmes': {
        'title': 'The Adventures of Sherlock Holmes',
        'author': 'Arthur Conan Doyle',
        'year': 1892,
        'original_language': 'English',
        'gutenberg_id': 1661
    },
    'the_strange_case_of_dr_jekyll_and_mr_hyde': {
        'title': 'The Strange Case of Dr Jekyll and Mr Hyde',
        'author': 'Robert Louis Stevenson',
        'year': 1886,
        'original_language': 'English',
        'gutenberg_id': 43
    },
    'time_machine': {
        'title': 'The Time Machine',
        'author': 'H.G. Wells',
        'year': 1895,
        'original_language': 'English',
        'gutenberg_id': 77847
    },
    'war_worlds': {
        'title': 'The War of the Worlds',
        'author': 'H.G. Wells',
        'year': 1898,
        'original_language': 'English',
        'gutenberg_id': 36
    },
    'winnie_pooh': {
        'title': 'Winnie-the-Pooh',
        'author': 'A.A. Milne',
        'year': 1926,
        'original_language': 'English',
        'gutenberg_id': 67098
    },
    'zarathustra': {
        'title': 'Thus Spoke Zarathustra',
        'author': 'Friedrich Nietzsche',
        'year': 1883,
        'original_language': 'German',
        'gutenberg_id': 1998
    },
}


def get_book_info(book_id: str) -> dict:
    """
    Get bibliographic information for a book by ID.

    Args:
        book_id: Book identifier (e.g., 'alice_adventures')

    Returns:
        Dictionary with title, author, year, etc., or empty dict if not found
    """
    return BOOK_CATALOG.get(book_id, {})


def format_year(year: int) -> str:
    """
    Format publication year for display.

    Args:
        year: Year as integer

    Returns:
        Formatted string (e.g., "1865" or "49 AD")
    """
    if year < 0:
        return f"{abs(year)} BC"
    if year < 1000:
        return f"{year} AD"
    return str(year)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python book_catalog.py <book_id>")
        print("\nAvailable books:")
        for book_id, info in sorted(BOOK_CATALOG.items()):
            print(f"  {book_id}: {info['title']} by {info['author']} ({info['year']})")
        sys.exit(1)

    book_id = sys.argv[1]
    info = get_book_info(book_id)

    if info:
        print(f"Title: {info['title']}")
        print(f"Author: {info['author']}")
        print(f"Year: {format_year(info['year'])}")
        print(f"Original Language: {info['original_language']}")
    else:
        print(f"No information found for '{book_id}'")
