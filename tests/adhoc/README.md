# Ad-hoc Test Scripts

This directory contains manual/exploratory test scripts that were previously in the root directory.

## Purpose

These scripts are:
- **Manual tests** - Run by developers for debugging/exploration
- **One-off experiments** - Testing specific features or edge cases
- **Not part of CI** - Don't run in automated test suite

## Usage

Run these scripts directly from this directory:

```bash
cd tests/adhoc
python3 test_chapter_detection.py
python3 test_hybrid_rag_demo.py
# etc.
```

## Proper Test Suite

For production tests, use the structured test suite:

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/

# All tests
pytest
```

## Files in This Directory

- `test_all_books.py` - Manual test for all books in catalog
- `test_chapter_detection.py` - Manual chapter detection testing
- `test_chapter_fix.py` - Testing chapter fix logic
- `test_chunking*.py` - Various chunking algorithm tests
- `test_clean_architecture.py` - Architecture validation
- `test_hybrid_rag_demo.py` - RAG system demo/testing
- `test_job_queue.py` - Job queue manual testing
- `test_sentence_chunking.py` - Sentence chunking tests
- `test_translation_fix.py` - Translation bug fix validation
- `test_tts_preprocessing.py` - TTS preprocessing tests
- `tts_comparison_test.py` - TTS engine comparison
- `tts_simple_test.py` - Simple TTS test

## Contributing

When adding new ad-hoc tests:
1. Give them descriptive names
2. Add docstrings explaining purpose
3. If they prove valuable, migrate to proper test suite

See [../CLAUDE.md](../CLAUDE.md) for project documentation.
