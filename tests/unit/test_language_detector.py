#!/usr/bin/env python3
"""Unit tests for server/language_detector.py"""

import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.language_detector import LanguageDetector


@pytest.fixture
def detector():
    return LanguageDetector()


class TestDetectFromGutenbergMetadata:
    def test_detects_from_metadata(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Some content")
        meta_file = temp_dir / "gutenberg_metadata.json"
        meta_file.write_text(json.dumps({"language": "fr", "title": "Test"}))

        result = detector._detect_from_gutenberg_metadata(book_file)
        assert result is not None
        assert result['language'] == 'French'
        assert result['code'] == 'fr'
        assert result['confidence'] == 1.0
        assert result['needs_translation'] is True

    def test_english_needs_no_translation(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Content")
        meta_file = temp_dir / "gutenberg_metadata.json"
        meta_file.write_text(json.dumps({"language": "en"}))

        result = detector._detect_from_gutenberg_metadata(book_file)
        assert result['needs_translation'] is False

    def test_no_metadata_returns_none(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Content")
        assert detector._detect_from_gutenberg_metadata(book_file) is None


class TestDetectFromScript:
    def test_cyrillic_detected_as_russian(self, detector):
        assert detector._detect_from_script("Преступление и наказание") == 'Russian'

    def test_chinese_detected(self, detector):
        assert detector._detect_from_script("这是一本中文书") == 'Chinese'

    def test_arabic_detected(self, detector):
        assert detector._detect_from_script("هذا كتاب عربي") == 'Arabic'

    def test_greek_detected(self, detector):
        assert detector._detect_from_script("Ιλιάδα Ομήρου") == 'Greek'

    def test_latin_script_returns_none(self, detector):
        assert detector._detect_from_script("Hello world in English") is None


class TestDetectFromFilename:
    def test_russian_pattern(self, detector):
        assert detector._detect_from_filename(Path("/books/russian_book/book.md")) == 'Russian'

    def test_french_pattern(self, detector):
        assert detector._detect_from_filename(Path("/books/french_novel/book.md")) == 'French'

    def test_latin_pattern(self, detector):
        assert detector._detect_from_filename(Path("/books/seneca_letters/book.md")) == 'Latin'

    def test_no_pattern_returns_none(self, detector):
        assert detector._detect_from_filename(Path("/books/alice_adventures/book.md")) is None


class TestDetectLanguage:
    def test_gutenberg_metadata_priority(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Преступление и наказание")  # Cyrillic
        meta_file = temp_dir / "gutenberg_metadata.json"
        meta_file.write_text(json.dumps({"language": "fr"}))  # French metadata

        result = detector.detect_language(book_file)
        # Gutenberg metadata should win over script detection
        assert result['language'] == 'French'
        assert result['method'] == 'gutenberg_metadata'

    def test_default_english(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Hello, this is a test book in English.")

        # Patch LLM detection to return None
        with patch.object(detector, '_detect_with_llm', return_value=None):
            result = detector.detect_language(book_file)
        assert result['language'] == 'English'
        assert result['method'] == 'english_default'
        assert result['needs_translation'] is False

    def test_script_detection_for_cyrillic(self, detector, temp_dir):
        book_file = temp_dir / "book.md"
        book_file.write_text("Преступление и наказание, великий роман Достоевского")

        result = detector.detect_language(book_file)
        assert result['language'] == 'Russian'
        assert result['method'] == 'script'


class TestGetLanguageCode:
    def test_known_languages(self, detector):
        assert detector._get_language_code('English') == 'en'
        assert detector._get_language_code('French') == 'fr'
        assert detector._get_language_code('Russian') == 'ru'
        assert detector._get_language_code('Latin') == 'la'

    def test_unknown_uses_prefix(self, detector):
        code = detector._get_language_code('Esperanto')
        assert code == 'es'  # First 2 chars
