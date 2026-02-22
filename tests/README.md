# Modern Classics Test Suite

Comprehensive tests for all product features.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run fast tests only
pytest -m "not slow" -n auto
```

## Test Organization

### Unit Tests (`unit/`)
Fast, isolated tests for individual components:
- `test_translation.py` - Translation validation & retry logic
- `test_deduplication.py` - Two-layer anti-duplication system
- `test_book_validation.py` - Book quality checks & feature readiness
- `test_chapter_detection.py` - Chapter detection algorithms
- `test_audio_generation.py` - Audio generation (Kokoro TTS)
- `test_summarization.py` - Summarization system

### Integration Tests (`integration/`)
Multi-component workflow tests:
- `test_translation_pipeline.py` - Split → Translate → Deduplicate
- `test_audio_pipeline.py` - Text → Audio → Combine → Compress
- `test_one_command_workflow.py` - make_audiobook.py end-to-end
- `test_server_api.py` - Server endpoints & streaming

### E2E Tests (`e2e/`)
Complete user scenarios:
- `test_full_audiobook_creation.py` - Gutenberg → Audio → Web player
- `test_web_player.py` - Player controls, progress, Karaoke mode
- `test_ai_chat.py` - AI assistant Q&A

### Fixtures (`fixtures/`)
Test data and sample files:
- `sample_books/` - Sample books (clean, Gutenberg, complex)
- `audio_samples/` - Sample audio files
- `expected_outputs/` - Expected test outputs

### Benchmarks (`benchmarks/`)
Performance regression tests:
- Translation speed (words/sec)
- Audio generation speed (realtime factor)
- Deduplication performance (chunks/sec)

## Features Tested

### ✅ Core Translation (40 features)
- Cloud translation (OpenAI: o1-mini, o3-mini, o3-mini-high, gpt-4o-mini)
- Local translation (Ollama: gemma3-translator:4b)
- Smart chunking (~10k words with overlap)
- Anti-duplication (2-layer: LLM context + exact match)
- Translation validation (rejects meta-commentary, repetition)
- Progress tracking & resume
- Structure preservation (Markdown)

### ✅ Audio Generation
- Kokoro TTS (52 voices, commercial-friendly)
- OpenAI Cloud TTS (6 voices, optional)
- Chapter-based audio
- Post-processing (speed, normalize, MP3)
- Audio combining & compression

### ✅ Book Processing
- Book validation (structure, quality, features)
- Auto-fix (Gutenberg stripping, TOC generation)
- Summarization (10-90% compression)
- Chapter detection (Roman numerals, headers, lists)
- Smart book splitting

### ✅ Cover Art
- AI cover generation (Stable Diffusion v1.5)
- Book-specific prompts
- Modular design

### ✅ Server & Playback
- Web audiobook player
- Progress persistence (per device)
- REST API (catalog, metadata, streaming)
- Karaoke mode (text sync)
- AI chat assistant (Ollama tool-calling)
- Chapter navigation

### ✅ Integration
- One-command workflow (make_audiobook.py)
- Resume capability
- Server registration
- Playlist generation
- Metadata export

## Test Markers

```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Skip tests requiring Ollama
pytest -m "not requires_ollama"

# Skip tests requiring GPU
pytest -m "not requires_gpu"
```

## CI/CD

Tests run automatically on:
- Push to main/develop
- Pull requests
- Daily at 2 AM UTC

Test matrix:
- Python: 3.10, 3.11, 3.12
- OS: Ubuntu, macOS

See [`.github/workflows/test.yml`](../.github/workflows/test.yml)

## Coverage Goals

| Component | Target |
|-----------|--------|
| Translation | 100% |
| Deduplication | 100% |
| Validation | 95% |
| Audio Generation | 90% |
| Server API | 85% |
| **Overall** | **80%+** |

## Common Commands

```bash
# Run specific test file
pytest tests/unit/test_deduplication.py -v

# Run specific test
pytest tests/unit/test_deduplication.py::TestDuplicationDetection::test_find_exact_duplicate_at_boundary

# Run with output
pytest -s

# Run in parallel
pytest -n auto

# Stop on first failure
pytest -x

# Run last failed
pytest --lf

# Show slowest tests
pytest --durations=10
```

## Documentation

For project documentation, see [CLAUDE.md](../CLAUDE.md)

## Regression Prevention

Based on [CHANGELOG.md](../CHANGELOG.md), we prevent:
1. ✅ Translation corruption (meta-commentary)
2. ✅ Chunk overlap duplication
3. ✅ Audio truncation
4. ✅ Missing chapter detection
5. ✅ Gutenberg boilerplate in output

---

**Last Updated**: February 4, 2026
