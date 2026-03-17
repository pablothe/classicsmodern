#!/usr/bin/env python3
"""Unit tests for lib/cover/prompts.py"""

import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from lib.cover.prompts import (
        _read_excerpt_from_middle,
        _resolve_book_metadata,
        get_book_prompt,
        BOOK_PROMPTS_FALLBACK,
        GENERIC_FALLBACK,
    )
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PROMPTS_AVAILABLE, reason="lib.cover.prompts not available")


class TestReadExcerptFromMiddle:
    def test_reads_from_midpoint(self, temp_dir):
        book_file = temp_dir / "book.md"
        # Write enough content to have a meaningful midpoint
        content = "Start. " + " ".join(["word"] * 100) + " Middle marker here. " + " ".join(["word"] * 100) + " End."
        book_file.write_text(content)
        excerpt = _read_excerpt_from_middle(book_file)
        assert excerpt is not None
        assert len(excerpt.split()) > 0

    def test_handles_missing_file(self):
        excerpt = _read_excerpt_from_middle(Path("/nonexistent/book.md"))
        assert excerpt == ""

    def test_strips_markdown_artifacts(self, temp_dir):
        book_file = temp_dir / "book.md"
        content = "## " + " ".join(["word"] * 200)
        book_file.write_text(content)
        excerpt = _read_excerpt_from_middle(book_file)
        if excerpt:
            assert "#" not in excerpt


class TestResolveBookMetadata:
    def test_manifest_fallback(self, temp_dir):
        book_dir = temp_dir / "unknown_book"
        book_dir.mkdir()
        book_file = book_dir / "book.md"
        book_file.write_text("Content")
        manifest = {"metadata": {"title": "Test Book", "author": "Test Author"}}
        (book_dir / "book_manifest.json").write_text(json.dumps(manifest))
        result = _resolve_book_metadata(book_file)
        assert result['title'] == "Test Book"
        assert result['author'] == "Test Author"

    def test_gutenberg_metadata_fallback(self, temp_dir):
        book_dir = temp_dir / "some_book"
        book_dir.mkdir()
        book_file = book_dir / "book.md"
        book_file.write_text("Content")
        (book_dir / "gutenberg_metadata.json").write_text(
            json.dumps({"title": "Gutenberg Title", "author": "Gutenberg Author"})
        )
        result = _resolve_book_metadata(book_file)
        assert result['title'] == "Gutenberg Title"

    def test_directory_name_fallback(self, temp_dir):
        book_dir = temp_dir / "my_great_book"
        book_dir.mkdir()
        book_file = book_dir / "book.md"
        book_file.write_text("Content")
        result = _resolve_book_metadata(book_file)
        assert "my" in result['title'].lower()

    def test_returns_dict_with_title_and_author(self, temp_dir):
        book_dir = temp_dir / "test_book"
        book_dir.mkdir()
        book_file = book_dir / "book.md"
        book_file.write_text("Content")
        result = _resolve_book_metadata(book_file)
        assert 'title' in result
        assert 'author' in result


class TestGetBookPrompt:
    def test_fallback_catalog_for_alice(self):
        """Known book should hit fallback catalog when LLM is unavailable."""
        prompt = get_book_prompt("alice_adventures")
        assert "watercolor" in prompt.lower()
        assert "alice" in prompt.lower() or "girl" in prompt.lower()

    def test_generic_fallback_for_unknown(self):
        """Unknown book with no LLM should return generic fallback."""
        prompt = get_book_prompt("completely_unknown_xyz_12345")
        assert prompt == GENERIC_FALLBACK

    def test_all_fallback_prompts_have_watercolor(self):
        """All fallback prompts include watercolor when used."""
        for key in BOOK_PROMPTS_FALLBACK:
            prompt = get_book_prompt(key)
            assert "watercolor" in prompt.lower()
