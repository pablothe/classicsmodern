#!/usr/bin/env python3
"""
Unit tests for lib/audio/chapter_metadata.py

Tests parse_m3u_playlist, detect_chapter_pattern, and extract_chapter_titles_from_source.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.audio.chapter_metadata import parse_m3u_playlist, detect_chapter_pattern, extract_chapter_titles_from_source


class TestParseM3UPlaylist:

    def test_valid_playlist(self, temp_dir):
        # Create audio files
        (temp_dir / "chapter_01.mp3").write_bytes(b"AUDIO")
        (temp_dir / "chapter_02.mp3").write_bytes(b"AUDIO")
        playlist = temp_dir / "playlist.m3u"
        playlist.write_text("chapter_01.mp3\nchapter_02.mp3\n")

        result = parse_m3u_playlist(playlist)
        assert len(result) == 2
        assert result[0].name == "chapter_01.mp3"

    def test_comments_and_blanks_skipped(self, temp_dir):
        (temp_dir / "chapter_01.mp3").write_bytes(b"AUDIO")
        playlist = temp_dir / "playlist.m3u"
        playlist.write_text("#EXTM3U\n#EXTINF:10,Chapter 1\nchapter_01.mp3\n\n")

        result = parse_m3u_playlist(playlist)
        assert len(result) == 1

    def test_missing_files_skipped(self, temp_dir):
        playlist = temp_dir / "playlist.m3u"
        playlist.write_text("nonexistent.mp3\n")

        result = parse_m3u_playlist(playlist)
        assert len(result) == 0

    def test_empty_playlist(self, temp_dir):
        playlist = temp_dir / "playlist.m3u"
        playlist.write_text("")

        result = parse_m3u_playlist(playlist)
        assert len(result) == 0


class TestDetectChapterPattern:

    def test_chapter_underscore_number(self):
        assert detect_chapter_pattern("book_chapter_01.mp3") == 1

    def test_chapter_dash_number(self):
        assert detect_chapter_pattern("book_chapter-03.mp3") == 3

    def test_ch_prefix(self):
        assert detect_chapter_pattern("book_ch05.mp3") == 5

    def test_ch_underscore_prefix(self):
        assert detect_chapter_pattern("book_ch_12.mp3") == 12

    def test_no_pattern_returns_none(self):
        assert detect_chapter_pattern("random_audio_file.mp3") is None

    def test_case_insensitive(self):
        assert detect_chapter_pattern("Book_Chapter_07.mp3") == 7
        assert detect_chapter_pattern("BOOK_CH02.mp3") == 2


class TestExtractChapterTitlesFromSource:

    def test_extracts_markdown_chapter_headers(self, temp_dir):
        book_dir = temp_dir / "mybook"
        book_dir.mkdir()
        (book_dir / "book.md").write_text(
            "# My Book\n\n"
            "## Chapter 1: The Beginning\n\nText.\n\n"
            "## Chapter 2: The Middle\n\nMore text.\n\n"
            "## Chapter 3: The End\n\nFinal text."
        )

        titles = extract_chapter_titles_from_source(book_dir)
        assert titles[1] == "The Beginning"
        assert titles[2] == "The Middle"
        assert titles[3] == "The End"

    def test_no_markdown_files(self, temp_dir):
        book_dir = temp_dir / "empty"
        book_dir.mkdir()
        titles = extract_chapter_titles_from_source(book_dir)
        assert titles == {}

    def test_skips_gutenberg_boilerplate(self, temp_dir):
        book_dir = temp_dir / "gutenberg"
        book_dir.mkdir()
        (book_dir / "book.md").write_text(
            "*** START OF THE PROJECT GUTENBERG EBOOK ***\n\n"
            "## Chapter 1: Real Content\n\nText.\n\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK ***\n\n"
            "## Chapter 99: Footer Junk\n\nIgnore."
        )

        titles = extract_chapter_titles_from_source(book_dir)
        assert 1 in titles
        assert 99 not in titles
