#!/usr/bin/env python3
"""
Unit Tests for Structured Book Translator

Tests the structured translation pipeline: Parse -> Validate -> Translate -> Assemble.
Uses mock LLMs to test without requiring Ollama.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock

from lib.translation.structured import (
    BookParser, BookStructure, Chapter, TranslationConfig,
    BlockTranslator, MarkdownAssembler, StructureValidator,
)
from tests.utils.mock_helpers import MockRecordingLLM, MockCleanLLM


# ============================================================================
# BookParser Tests
# ============================================================================

class TestBookParser:
    """Test parsing markdown into structured format."""

    def test_parse_detects_chapters(self, temp_dir, sample_book_content):
        """Parser should detect chapters from markdown."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        parser = BookParser()
        structure = parser.parse(book_file)

        assert isinstance(structure, BookStructure)
        assert len(structure.chapters) >= 1
        assert structure.original_file == book_file

    def test_parse_extracts_metadata_title(self, temp_dir):
        """Parser should extract title from H1 header."""
        content = "# My Great Book\n\nAuthor: Jane Doe\n\n## CHAPTER 1\n\nContent here with enough words to pass.\n"
        book_file = temp_dir / "book.md"
        book_file.write_text(content)

        parser = BookParser()
        structure = parser.parse(book_file)

        assert structure.metadata.get('title') == 'My Great Book'

    def test_parse_extracts_metadata_author(self, temp_dir):
        """Parser should extract author from 'Author:' line."""
        content = "# My Book\n\nAuthor: John Smith\n\n## CHAPTER 1\n\nContent here with enough words.\n"
        book_file = temp_dir / "book.md"
        book_file.write_text(content)

        parser = BookParser()
        structure = parser.parse(book_file)

        assert structure.metadata.get('author') == 'John Smith'

    def test_parse_raises_on_no_chapters(self, temp_dir):
        """Parser should raise ValueError if no chapters detected."""
        content = "Just some random text without any chapter markers.\n"
        book_file = temp_dir / "book.md"
        book_file.write_text(content)

        parser = BookParser()
        with pytest.raises(ValueError, match="No chapters detected"):
            parser.parse(book_file)

    def test_chapter_numbers_preserved(self, temp_dir, sample_book_content):
        """Chapter numbers should be sequential integers."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        parser = BookParser()
        structure = parser.parse(book_file)

        for i, chapter in enumerate(structure.chapters):
            assert chapter.number == i + 1


# ============================================================================
# TranslationConfig Tests
# ============================================================================

class TestTranslationConfig:
    """Test translation configuration defaults."""

    def test_default_target_language(self):
        config = TranslationConfig()
        assert config.target_lang == "Modern English"

    def test_default_source_is_auto_detect(self):
        config = TranslationConfig()
        assert config.source_lang is None

    def test_custom_config(self):
        config = TranslationConfig(
            source_lang="Latin",
            target_lang="Spanish",
            model_name="custom-model"
        )
        assert config.source_lang == "Latin"
        assert config.target_lang == "Spanish"
        assert config.model_name == "custom-model"


# ============================================================================
# MarkdownAssembler Tests
# ============================================================================

class TestMarkdownAssembler:
    """Test reassembly of translated structure into markdown."""

    def test_assemble_creates_output_file(self, temp_dir):
        """Assembler should create the output file."""
        structure = BookStructure(
            metadata={'title': 'Test Book', 'author': 'Author'},
            chapters=[
                Chapter(number=1, marker="## CHAPTER 1", content="Translated content.", start_line=0, end_line=5),
            ],
            original_file=temp_dir / "source.md"
        )

        output_file = temp_dir / "output.md"
        assembler = MarkdownAssembler()
        result = assembler.assemble(structure, output_file)

        assert result.exists()
        text = result.read_text()
        assert "# Test Book" in text
        assert "Translated content." in text

    def test_assemble_includes_toc(self, temp_dir):
        """Assembler should generate a table of contents."""
        structure = BookStructure(
            metadata={'title': 'Book'},
            chapters=[
                Chapter(number=1, marker="## Ch 1", content="A.", start_line=0, end_line=1),
                Chapter(number=2, marker="## Ch 2", content="B.", start_line=2, end_line=3),
            ],
            original_file=temp_dir / "source.md"
        )

        output_file = temp_dir / "output.md"
        assembler = MarkdownAssembler()
        assembler.assemble(structure, output_file)

        text = output_file.read_text()
        assert "## Table of Contents" in text
        assert "1." in text
        assert "2." in text

    def test_assemble_preserves_chapter_markers(self, temp_dir):
        """Chapter markers should appear verbatim in output."""
        structure = BookStructure(
            metadata={},
            chapters=[
                Chapter(number=1, marker="## CHAPTER I", content="Content.", start_line=0, end_line=1),
            ],
            original_file=temp_dir / "source.md"
        )

        output_file = temp_dir / "output.md"
        assembler = MarkdownAssembler()
        assembler.assemble(structure, output_file)

        text = output_file.read_text()
        assert "## CHAPTER I" in text

    def test_assemble_preserves_author(self, temp_dir):
        """Author metadata should appear in output."""
        structure = BookStructure(
            metadata={'title': 'Book', 'author': 'Jane Doe'},
            chapters=[
                Chapter(number=1, marker="## Ch 1", content="A.", start_line=0, end_line=1),
            ],
            original_file=temp_dir / "source.md"
        )

        output_file = temp_dir / "output.md"
        assembler = MarkdownAssembler()
        assembler.assemble(structure, output_file)

        text = output_file.read_text()
        assert "Jane Doe" in text


# ============================================================================
# BlockTranslator Checkpoint Tests
# ============================================================================

class TestBlockTranslatorCheckpoints:
    """Test checkpoint save/resume in BlockTranslator."""

    def test_checkpoint_saved_after_translation(self, temp_dir, sample_book_content):
        """Checkpoint file should be created during translation."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        checkpoint_file = temp_dir / ".checkpoint.json"
        config = TranslationConfig(
            target_lang="English",
            llm=MockCleanLLM(),
        )
        translator = BlockTranslator(config, checkpoint_file=checkpoint_file)

        parser = BookParser()
        structure = parser.parse(book_file)

        # After successful translation, checkpoint should be cleaned up
        translator.translate_structure(structure)
        # Checkpoint is removed on success
        assert not checkpoint_file.exists()

    def test_checkpoint_resume_skips_completed_chapters(self, temp_dir, sample_book_content):
        """When a checkpoint exists, already-translated chapters should be skipped."""
        book_file = temp_dir / "book.md"
        book_file.write_text(sample_book_content)

        parser = BookParser()
        structure = parser.parse(book_file)

        # Create a fake checkpoint with 1 chapter done
        checkpoint_file = temp_dir / ".checkpoint.json"
        checkpoint_data = {
            'config': {'target_lang': 'English'},
            'progress': {'last_completed_chapter': 1, 'total_chapters_completed': 1},
            'translated_chapters': [{
                'number': 1,
                'marker': structure.chapters[0].marker,
                'content': 'Already translated chapter 1.',
                'start_line': 0, 'end_line': 5,
                'metadata': {}
            }]
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        config = TranslationConfig(target_lang="English", llm=MockCleanLLM())
        translator = BlockTranslator(config, checkpoint_file=checkpoint_file)

        result = translator.translate_structure(structure)

        # First chapter should have the checkpoint content
        assert result.chapters[0].content == 'Already translated chapter 1.'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
