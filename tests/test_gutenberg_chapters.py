#!/usr/bin/env python3
"""
Integration test: Gutenberg chapter detection on 10 diverse books.

Downloads books from Gutenberg, converts to markdown, and verifies
chapter detection produces clean, non-redundant results.

Usage:
    pytest tests/test_gutenberg_chapters.py -v
    pytest tests/test_gutenberg_chapters.py -v -k "alice"

    # Run standalone (no pytest needed)
    python3 tests/test_gutenberg_chapters.py
"""

import re
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.gutenberg_downloader import GutenbergDownloader
from lib.book.processor import BookProcessor


# Cache directory for downloaded books (reused across test sessions)
CACHE_DIR = Path(tempfile.gettempdir()) / "gutenberg_chapter_test_cache"


# (gutenberg_id, slug, min_chapters, expected_section_types)
GUTENBERG_TEST_BOOKS = [
    pytest.param(11, "alice_wonderland", 12, {"chapter"}, id="alice-11"),
    pytest.param(1661, "sherlock_holmes", 10, {"chapter"}, id="sherlock-1661"),
    pytest.param(84, "frankenstein", 5, {"chapter"}, id="frankenstein-84"),
    pytest.param(1342, "pride_prejudice", 40, {"chapter"}, id="pride-1342"),
    pytest.param(2701, "moby_dick", 100, {"chapter"}, id="moby-2701"),
    pytest.param(98, "tale_two_cities", 30, {"chapter"}, id="tale-98"),
    pytest.param(174, "dorian_gray", 15, {"chapter"}, id="dorian-174"),
    pytest.param(76, "huck_finn", 30, {"chapter"}, id="huck-76"),
    pytest.param(1513, "romeo_juliet", 3, set(), id="romeo-1513"),
    pytest.param(19942, "candide", 25, {"chapter"}, id="candide-19942"),
]


@pytest.fixture(scope="session")
def downloader():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return GutenbergDownloader(books_dir=CACHE_DIR)


@pytest.fixture(scope="session")
def processor():
    return BookProcessor(verbose=False)


def _get_cached_markdown(downloader, gutenberg_id, slug):
    """Download and cache a book's markdown, or return cached version."""
    cache_file = CACHE_DIR / slug / "book.md"
    if cache_file.exists():
        return cache_file.read_text(encoding='utf-8')

    result = downloader.download_book(gutenberg_id, slug)
    assert result['success'], f"Download failed for {slug}: {result.get('error')}"
    return cache_file.read_text(encoding='utf-8')


def _get_chapters(downloader, processor, gutenberg_id, slug):
    """Get cached chapters for a book."""
    markdown = _get_cached_markdown(downloader, gutenberg_id, slug)
    cleaned, _ = processor.strip_gutenberg(markdown)
    return processor.detect_chapters(cleaned)


@pytest.mark.requires_network
class TestGutenbergChapterDetection:
    """Test chapter detection on real Gutenberg books."""

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_chapter_count(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """Each book should detect at least min_chapters chapters."""
        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)
        assert len(chapters) >= min_chapters, (
            f"{slug}: expected >= {min_chapters} chapters, got {len(chapters)}. "
            f"Titles: {[ch.title[:50] for ch in chapters[:5]]}"
        )

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_no_redundant_titles(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """No title should have redundant 'Chapter N: CHAPTER N.' patterns."""
        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)

        redundant = re.compile(
            r'Chapter\s+\d+[.:]\s*(CHAPTER|Chapter)\s+[IVXLCDM\d]+', re.IGNORECASE
        )
        for ch in chapters:
            assert not redundant.search(ch.title), (
                f"{slug} ch{ch.number}: redundant title '{ch.title}'"
            )

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_no_broken_injection(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """No title should have '. ' as only content (broken normalization)."""
        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)

        for ch in chapters:
            assert not re.match(r'^Chapter\s+\d+[.:]\s*\.\s', ch.title), (
                f"{slug} ch{ch.number}: broken title '{ch.title}'"
            )

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_title_length(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """Titles should be reasonably short (no body text leakage)."""
        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)

        for ch in chapters:
            assert len(ch.title) < 150, (
                f"{slug} ch{ch.number}: title too long ({len(ch.title)} chars): "
                f"'{ch.title[:80]}...'"
            )

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_section_types(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """Books with special sections should detect correct section_type values."""
        if not expected_types:
            pytest.skip("No specific section types expected")

        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)
        detected_types = {ch.section_type for ch in chapters}
        for expected_type in expected_types:
            assert expected_type in detected_types, (
                f"{slug}: expected section_type '{expected_type}' not in {detected_types}"
            )

    @pytest.mark.parametrize("gutenberg_id,slug,min_chapters,expected_types", GUTENBERG_TEST_BOOKS)
    def test_no_adjacent_duplicates(self, downloader, processor, gutenberg_id, slug, min_chapters, expected_types):
        """No two adjacent chapters should have identical titles (double injection)."""
        chapters = _get_chapters(downloader, processor, gutenberg_id, slug)

        for i in range(len(chapters) - 1):
            a = re.sub(r'[^a-z0-9]', '', chapters[i].title.lower())
            b = re.sub(r'[^a-z0-9]', '', chapters[i + 1].title.lower())
            # Exact match after normalization catches double injection
            # (substring check has false positives on sequential Roman numerals)
            if len(a) > 5 and len(b) > 5:
                assert a != b, (
                    f"{slug}: adjacent duplicate ch{chapters[i].number} and "
                    f"ch{chapters[i+1].number}: '{chapters[i].title}' vs '{chapters[i+1].title}'"
                )


# --- Standalone runner ---

def main():
    """Run tests standalone without pytest."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dl = GutenbergDownloader(books_dir=CACHE_DIR)
    proc = BookProcessor(verbose=False)

    books = [
        (11, "alice_wonderland", 12),
        (1661, "sherlock_holmes", 10),
        (84, "frankenstein", 5),
        (1342, "pride_prejudice", 40),
        (2701, "moby_dick", 100),
        (98, "tale_two_cities", 30),
        (174, "dorian_gray", 15),
        (76, "huck_finn", 30),
        (1513, "romeo_juliet", 3),
        (19942, "candide", 25),
    ]

    passed = 0
    failed = 0

    for gid, slug, min_ch in books:
        print(f"\n{'='*60}")
        print(f"Testing: {slug} (Gutenberg #{gid})")
        print(f"{'='*60}")

        try:
            chapters = _get_chapters(dl, proc, gid, slug)
            issues = []

            # Check count
            if len(chapters) < min_ch:
                issues.append(f"Only {len(chapters)} chapters (expected >= {min_ch})")

            # Check quality
            redundant = re.compile(r'Chapter\s+\d+[.:]\s*(CHAPTER|Chapter)\s+[IVXLCDM\d]+', re.IGNORECASE)
            for ch in chapters:
                if redundant.search(ch.title):
                    issues.append(f"  Redundant: ch{ch.number} '{ch.title}'")
                if re.match(r'^Chapter\s+\d+[.:]\s*\.\s', ch.title):
                    issues.append(f"  Broken: ch{ch.number} '{ch.title}'")
                if len(ch.title) > 150:
                    issues.append(f"  Too long: ch{ch.number} ({len(ch.title)} chars)")

            # Check adjacent duplicates (exact match after normalization)
            for i in range(len(chapters) - 1):
                a = re.sub(r'[^a-z0-9]', '', chapters[i].title.lower())
                b = re.sub(r'[^a-z0-9]', '', chapters[i + 1].title.lower())
                if len(a) > 5 and len(b) > 5 and a == b:
                    issues.append(f"  Duplicate: '{chapters[i].title}' ~ '{chapters[i+1].title}'")

            if issues:
                print(f"FAIL ({len(chapters)} chapters)")
                for issue in issues:
                    print(f"  {issue}")
                failed += 1
            else:
                print(f"PASS ({len(chapters)} chapters)")
                # Show first 5 titles
                for ch in chapters[:5]:
                    print(f"  {ch.number}. [{ch.section_type}] {ch.title}")
                if len(chapters) > 5:
                    print(f"  ... and {len(chapters) - 5} more")
                passed += 1

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(books)}")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
