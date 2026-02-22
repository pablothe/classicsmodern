#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures

This module provides common fixtures and configuration for all tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Generator
import json


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Get fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for test outputs."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


# ============================================================================
# Sample Book Fixtures
# ============================================================================

@pytest.fixture
def sample_book_clean(fixtures_dir) -> str:
    """
    Return path to clean, well-formatted sample book.

    Features:
    - 3 chapters with Roman numerals
    - Table of contents
    - Proper markdown formatting
    - No Gutenberg boilerplate
    """
    return str(fixtures_dir / "sample_books" / "alice_sample.md")


@pytest.fixture
def sample_book_gutenberg(fixtures_dir) -> str:
    """
    Return path to sample book with Gutenberg boilerplate.

    Features:
    - Contains Gutenberg header/footer
    - Needs cleaning
    """
    return str(fixtures_dir / "sample_books" / "gutenberg_book.md")


@pytest.fixture
def sample_book_complex(fixtures_dir) -> str:
    """
    Return path to complex multi-chapter book.

    Features:
    - 10+ chapters
    - Multiple chapter formats (Roman numerals, numbered lists)
    - TOC
    - Realistic length (~10k words)
    """
    return str(fixtures_dir / "sample_books" / "complex_book.md")


@pytest.fixture
def sample_book_content() -> str:
    """Return inline sample book content for quick tests."""
    return """# Alice's Adventures in Wonderland
Author: Lewis Carroll

## Table of Contents
1. [Down the Rabbit-Hole](#chapter-i)
2. [The Pool of Tears](#chapter-ii)
3. [A Caucus-Race](#chapter-iii)

---

## CHAPTER I. Down the Rabbit-Hole

Alice was beginning to get very tired of sitting by her sister on the
bank, and of having nothing to do: once or twice she had peeped into the
book her sister was reading, but it had no pictures or conversations in
it, "and what is the use of a book," thought Alice "without pictures or
conversations?"

So she was considering in her own mind (as well as she could, for the
hot day made her feel very sleepy and stupid), whether the pleasure
of making a daisy-chain would be worth the trouble of getting up and
picking the daisies, when suddenly a White Rabbit with pink eyes ran
close by her.

## CHAPTER II. The Pool of Tears

"Curiouser and curiouser!" cried Alice (she was so much surprised, that
for the moment she quite forgot how to speak good English); "now I'm
opening out like the largest telescope that ever was! Good-bye, feet!"
(for when she looked down at her feet, they seemed to be almost out of
sight, they were getting so far off).

## CHAPTER III. A Caucus-Race and a Long Tale

They were indeed a queer-looking party that assembled on the bank—the
birds with draggled feathers, the animals with their fur clinging close
to them, and all dripping wet, cross, and uncomfortable.
"""


# ============================================================================
# Audio Fixtures
# ============================================================================

@pytest.fixture
def mock_audio_output(temp_dir) -> Dict:
    """Create mock audio output structure."""
    audio_dir = temp_dir / "audio_kokoro"
    audio_dir.mkdir()

    # Create mock MP3 files
    for i in range(1, 4):
        chapter_file = audio_dir / f"chapter_{i:02d}.mp3"
        chapter_file.write_bytes(b"MOCK_AUDIO_DATA")

    # Create playlist
    playlist = audio_dir / "audiobook_playlist.m3u"
    playlist.write_text("\n".join([
        f"chapter_{i:02d}.mp3" for i in range(1, 4)
    ]))

    return {
        'audio_dir': str(audio_dir),
        'playlist': str(playlist),
        'chapters': 3
    }


# ============================================================================
# Translation Fixtures
# ============================================================================

@pytest.fixture
def mock_translation_chunk() -> Dict:
    """Return mock translation chunk with overlap."""
    return {
        'chunk_id': 1,
        'text': "This is the first chunk with some overlap text at the end.",
        'overlap': "some overlap text at the end.",
        'translated': "Esto es el primer trozo con algún texto superpuesto al final."
    }


@pytest.fixture
def mock_translation_chunks_with_duplicates() -> list:
    """Return list of translation chunks with intentional duplicates."""
    return [
        {
            'id': 1,
            'text': "First chunk ending with this phrase.",
            'translated': "Primer trozo terminando con esta frase."
        },
        {
            'id': 2,
            'text': "terminando con esta frase. Second chunk continues here.",
            'translated': "terminando con esta frase. El segundo trozo continúa aquí."
        }
    ]


# ============================================================================
# Server Fixtures
# ============================================================================

@pytest.fixture
def mock_playback_db(temp_dir) -> str:
    """Create mock playback database."""
    db_file = temp_dir / "playback_db.json"
    db_data = {
        "alice_adventures": {
            "device_123": {
                "position": 45.5,
                "chapter": 2,
                "last_updated": "2026-02-04T12:00:00Z"
            }
        }
    }
    db_file.write_text(json.dumps(db_data, indent=2))
    return str(db_file)


# ============================================================================
# Chapter Detection Fixtures
# ============================================================================

@pytest.fixture
def chapter_patterns() -> Dict:
    """Return various chapter format examples."""
    return {
        'roman_numerals': [
            "## CHAPTER I. Down the Rabbit-Hole",
            "## CHAPTER II. The Pool of Tears",
            "## CHAPTER III. A Caucus-Race"
        ],
        'numbered_list': [
            "1. The Horror in Clay",
            "2. The Tale of Inspector Legrasse",
            "3. The Madness from the Sea"
        ],
        'markdown_headers': [
            "# Chapter 1: The Beginning",
            "# Chapter 2: The Middle",
            "# Chapter 3: The End"
        ],
        'mixed_formats': [
            "## CHAPTER I. Introduction",
            "# Chapter 2: Development",
            "3. The Conclusion"
        ]
    }


# ============================================================================
# Validation Fixtures
# ============================================================================

@pytest.fixture
def valid_book_metrics() -> Dict:
    """Return metrics for a valid book."""
    return {
        'chapter_count': 12,
        'has_toc': True,
        'sequential_chapters': True,
        'word_count': 26167,
        'has_title': True,
        'has_author': True,
        'has_gutenberg_boilerplate': False
    }


@pytest.fixture
def invalid_book_metrics() -> Dict:
    """Return metrics for an invalid book."""
    return {
        'chapter_count': 0,
        'has_toc': False,
        'sequential_chapters': False,
        'word_count': 50,  # Too short
        'has_title': False,
        'has_author': False,
        'has_gutenberg_boilerplate': True
    }


# ============================================================================
# Mock External Services
# ============================================================================

@pytest.fixture
def mock_ollama(monkeypatch):
    """Mock Ollama API calls for translation tests."""
    class MockOllamaResponse:
        def __init__(self, content):
            self.content = content

        def __getitem__(self, key):
            if key == 'message':
                return {'content': self.content}
            return None

    def mock_chat(*args, **kwargs):
        # Extract source text from prompt
        prompt = kwargs.get('messages', [{}])[-1].get('content', '')

        # Simple mock translation (reverse words as a placeholder)
        words = prompt.split()[-20:]  # Take last 20 words
        mock_translation = " ".join(reversed(words))

        return MockOllamaResponse(mock_translation)

    # Patch ollama.chat
    try:
        import ollama
        monkeypatch.setattr(ollama, 'chat', mock_chat)
    except ImportError:
        pass  # Ollama not installed, tests will skip


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_ollama: marks tests that require Ollama to be running"
    )
    config.addinivalue_line(
        "markers", "requires_gpu: marks tests that require GPU acceleration"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks end-to-end tests"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests that require external services if not available."""
    import subprocess

    # Check if Ollama is available
    try:
        subprocess.run(['ollama', 'list'], capture_output=True, timeout=2)
        ollama_available = True
    except (subprocess.SubprocessError, FileNotFoundError):
        ollama_available = False

    skip_ollama = pytest.mark.skip(reason="Ollama not available")

    for item in items:
        if "requires_ollama" in item.keywords and not ollama_available:
            item.add_marker(skip_ollama)
