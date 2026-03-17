#!/usr/bin/env python3
"""
Unit tests for lib/audio/preprocessor.py

Tests AudioTextPreprocessor: header→speech transformation, Roman numeral conversion,
bidirectional position mapping, and untranslated block stripping.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.audio.preprocessor import AudioTextPreprocessor, PreprocessingResult


class TestProcessMarkdownHeader:

    def test_numbered_header_to_spoken(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("## 1: The Horror in Clay", 0)
        assert result == "Chapter 1: The Horror in Clay"

    def test_roman_header_standalone(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("## I.", 0)
        assert result == "Chapter 1"

    def test_roman_header_with_title(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("## III. The Madness from the Sea", 0)
        assert result == "Chapter 3. The Madness from the Sea"

    def test_chapter_header_strips_hashes(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("## Chapter 5: The End", 0)
        assert result == "Chapter 5: The End"
        assert "#" not in result

    def test_generic_header_strips_hashes(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("## Conclusion", 0)
        assert result == "Conclusion"
        assert "#" not in result

    def test_no_transformation_plain_text(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("Just regular text", 0)
        assert result == "Just regular text"

    def test_h1_header(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("# Title of Book", 0)
        assert result == "Title of Book"

    def test_h3_header(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_markdown_header("### Subsection", 0)
        assert result == "Subsection"


class TestProcessStandaloneRoman:

    def test_standalone_roman_on_line(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_standalone_roman("I.", 0)
        assert result == "Chapter 1"

    def test_standalone_roman_with_space(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_standalone_roman("III.  ", 0)
        assert result == "Chapter 3"

    def test_no_transformation_for_non_roman(self):
        p = AudioTextPreprocessor()
        result, _, _ = p._process_standalone_roman("Regular text.", 0)
        assert result == "Regular text."


class TestRomanToArabic:

    def test_basic_values(self):
        p = AudioTextPreprocessor()
        assert p._roman_to_arabic("I") == 1
        assert p._roman_to_arabic("V") == 5
        assert p._roman_to_arabic("X") == 10
        assert p._roman_to_arabic("XX") == 20
        assert p._roman_to_arabic("C") == 100

    def test_invalid_returns_none(self):
        p = AudioTextPreprocessor()
        assert p._roman_to_arabic("INVALID") is None


class TestStripUntranslatedBlocks:

    def test_strips_untranslated_blocks(self):
        p = AudioTextPreprocessor()
        text = "Good text. [UNTRANSLATED]Bad stuff here[/UNTRANSLATED] More good text."
        result = p._strip_untranslated_blocks(text)
        assert "[UNTRANSLATED]" not in result
        assert "Good text." in result
        assert "More good text." in result

    def test_no_blocks_unchanged(self):
        p = AudioTextPreprocessor()
        text = "Just normal text here."
        result = p._strip_untranslated_blocks(text)
        assert result == text


class TestPreprocessForSpeech:

    def test_full_text_multiple_chapters(self):
        p = AudioTextPreprocessor()
        text = "## 1: First Chapter\n\nContent one.\n\n## 2: Second Chapter\n\nContent two."
        result = p.preprocess_for_speech(text)
        assert "Chapter 1: First Chapter" in result.spoken_text
        assert "Chapter 2: Second Chapter" in result.spoken_text
        assert "Content one." in result.spoken_text
        assert "##" not in result.spoken_text

    def test_transformations_logged(self):
        p = AudioTextPreprocessor()
        text = "## I. Title\n\nContent."
        result = p.preprocess_for_speech(text)
        assert len(result.transformations) >= 1
        assert result.transformations[0]['type'] in [
            'roman_title_header', 'numbered_header', 'roman_header',
            'chapter_header', 'generic_header'
        ]


class TestPreprocessingResultMapping:

    def test_get_spoken_pos_exact_match(self):
        p = AudioTextPreprocessor()
        text = "## 1: Title\n\nParagraph."
        result = p.preprocess_for_speech(text)
        # Position 0 should map to 0
        assert result.get_spoken_pos(0) == 0

    def test_get_spoken_pos_interpolated(self):
        p = AudioTextPreprocessor()
        text = "## 1: Title\n\nParagraph text here."
        result = p.preprocess_for_speech(text)
        # A position in the middle should return a valid int
        mid = len(text) // 2
        spoken = result.get_spoken_pos(mid)
        assert spoken is not None
        assert isinstance(spoken, int)

    def test_get_spoken_pos_no_mapping(self):
        result = PreprocessingResult(
            original_text="", spoken_text="",
            original_to_spoken={}, spoken_to_original={},
            transformations=[]
        )
        assert result.get_spoken_pos(100) is None

    def test_get_original_pos_exact_match(self):
        p = AudioTextPreprocessor()
        text = "## 1: Title\n\nParagraph."
        result = p.preprocess_for_speech(text)
        assert result.get_original_pos(0) == 0

    def test_get_original_pos_interpolated(self):
        p = AudioTextPreprocessor()
        text = "## 1: Title\n\nParagraph."
        result = p.preprocess_for_speech(text)
        mid = len(result.spoken_text) // 2
        orig = result.get_original_pos(mid)
        assert orig is not None
        assert isinstance(orig, int)

    def test_bidirectional_roundtrip(self):
        p = AudioTextPreprocessor()
        text = "Plain text with no headers"
        result = p.preprocess_for_speech(text)
        # For plain text, positions should be identity
        spoken = result.get_spoken_pos(5)
        original = result.get_original_pos(spoken)
        assert original == 5

    def test_end_of_text_mapped(self):
        p = AudioTextPreprocessor()
        text = "## 1: Title\n\nContent."
        result = p.preprocess_for_speech(text)
        # End positions should be mapped
        assert len(text) in result.original_to_spoken
        assert len(result.spoken_text) in result.spoken_to_original


class TestSaveMapping:

    def test_save_mapping_to_json(self, temp_dir):
        p = AudioTextPreprocessor()
        text = "## I. The Beginning\n\nSome content."
        result = p.preprocess_for_speech(text)

        output_path = str(temp_dir / "mapping.json")
        p.save_mapping(result, output_path)

        import json
        with open(output_path) as f:
            data = json.load(f)

        assert 'spoken_text' in data
        assert 'transformations' in data
        assert 'position_mapping' in data
