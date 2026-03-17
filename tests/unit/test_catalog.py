#!/usr/bin/env python3
"""Unit tests for lib/book/catalog.py"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.book.catalog import get_book_info, format_year, BOOK_CATALOG


class TestGetBookInfo:
    def test_known_book(self):
        info = get_book_info('alice_adventures')
        assert info['title'] == "Alice's Adventures in Wonderland"
        assert info['author'] == 'Lewis Carroll'
        assert info['year'] == 1865

    def test_unknown_returns_empty(self):
        assert get_book_info('nonexistent_book') == {}

    def test_catalog_has_expected_books(self):
        assert 'alice_adventures' in BOOK_CATALOG
        assert 'moby_dick' in BOOK_CATALOG
        assert 'zarathustra' in BOOK_CATALOG

    def test_all_entries_have_required_fields(self):
        required = {'title', 'author', 'year', 'original_language'}
        for book_id, info in BOOK_CATALOG.items():
            for field in required:
                assert field in info, f"{book_id} missing '{field}'"


class TestFormatYear:
    def test_modern_year(self):
        assert format_year(1865) == "1865"

    def test_ancient_ad(self):
        assert format_year(49) == "49 AD"

    def test_bc_year(self):
        assert format_year(-44) == "44 BC"

    def test_year_999(self):
        assert format_year(999) == "999 AD"

    def test_year_1000(self):
        assert format_year(1000) == "1000"

    def test_year_zero_edge(self):
        # Year 0 is < 1000, so should get AD suffix
        assert format_year(0) == "0 AD"
