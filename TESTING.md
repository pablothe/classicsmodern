# Testing Guide

Comprehensive testing documentation for Modern Classics.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Test Structure](#test-structure)
4. [Running Tests](#running-tests)
5. [Writing Tests](#writing-tests)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Coverage Reports](#coverage-reports)
8. [Performance Benchmarks](#performance-benchmarks)

---

## Overview

Modern Classics uses pytest as its testing framework with a comprehensive three-tier test structure:

- **Unit Tests** - Test individual components in isolation
- **Integration Tests** - Test multi-component workflows
- **End-to-End Tests** - Test complete user scenarios

### Test Coverage Goals

- **Target**: 80%+ code coverage
- **Critical Path**: 100% coverage for translation, deduplication, and validation
- **CI/CD**: All tests must pass before merge to main

---

## Quick Start

### Installation

```bash
# Install testing dependencies
pip install -r tests/requirements-test.txt

# Or install with main requirements
pip install -r requirements.txt
```

### Run All Tests

```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_deduplication.py -v
```

### Run Fast Tests Only

```bash
# Skip slow tests
pytest -m "not slow"

# Run only unit tests (fastest)
pytest tests/unit/ -n auto
```

---

## Test Structure

```
tests/
├── unit/                       # Unit tests (isolated components)
│   ├── test_translation.py     # Translation validation & retry
│   ├── test_deduplication.py   # Anti-duplication system
│   ├── test_book_validation.py # Book quality validation
│   ├── test_chapter_detection.py # Chapter detection
│   ├── test_audio_generation.py # Audio generation
│   └── test_summarization.py   # Summarization system
│
├── integration/                # Integration tests (workflows)
│   ├── test_translation_pipeline.py # Split → Translate → Dedupe
│   ├── test_audio_pipeline.py     # Text → Audio → Combine
│   ├── test_one_command_workflow.py # make_audiobook.py
│   └── test_server_api.py         # Server endpoints
│
├── e2e/                        # End-to-end tests (full scenarios)
│   ├── test_full_audiobook_creation.py
│   ├── test_web_player.py
│   └── test_ai_chat.py
│
├── fixtures/                   # Test data and fixtures
│   ├── sample_books/           # Sample book files
│   │   ├── alice_sample.md     # Clean, 3-chapter sample
│   │   ├── gutenberg_book.md   # With boilerplate
│   │   └── complex_book.md     # Multi-chapter, realistic
│   ├── audio_samples/          # Sample audio files
│   └── expected_outputs/       # Expected test outputs
│
├── benchmarks/                 # Performance benchmarks
│   ├── bench_translation.py    # Translation speed tests
│   ├── bench_audio.py          # Audio generation speed
│   └── bench_deduplication.py  # Deduplication performance
│
├── conftest.py                 # Pytest configuration & fixtures
├── pytest.ini                  # Pytest settings
└── requirements-test.txt       # Testing dependencies
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test directory
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_deduplication.py

# Run specific test class
pytest tests/unit/test_deduplication.py::TestDuplicationDetection

# Run specific test function
pytest tests/unit/test_deduplication.py::TestDuplicationDetection::test_find_exact_duplicate_at_boundary
```

### Pytest Options

```bash
# Verbose output
pytest -v

# Show full traceback
pytest --tb=long

# Show local variables in traceback
pytest -l

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run in parallel (faster)
pytest -n auto

# Show print statements
pytest -s
```

### Markers

Tests can be marked with custom markers:

```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run only e2e tests
pytest -m e2e

# Skip tests requiring Ollama
pytest -m "not requires_ollama"

# Skip tests requiring GPU
pytest -m "not requires_gpu"
```

### Coverage

```bash
# Run with coverage
pytest --cov=.

# Generate HTML report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Generate XML report (for CI)
pytest --cov=. --cov-report=xml

# Show missing lines
pytest --cov=. --cov-report=term-missing
```

---

## Writing Tests

### Test File Structure

```python
#!/usr/bin/env python3
"""
Brief description of what this test module covers.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module_to_test import function_to_test


class TestFeatureName:
    """Test suite for specific feature"""

    def test_basic_functionality(self):
        """Test the basic happy path"""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case behavior"""
        result = function_to_test("")
        assert result is None


class TestErrorHandling:
    """Test error handling and exceptions"""

    def test_handles_invalid_input(self):
        """Test graceful handling of invalid input"""
        with pytest.raises(ValueError):
            function_to_test(None)
```

### Using Fixtures

```python
def test_with_temp_directory(temp_dir):
    """Test using temporary directory fixture"""
    test_file = temp_dir / "test.txt"
    test_file.write_text("content")
    assert test_file.exists()


def test_with_sample_book(sample_book_clean):
    """Test using sample book fixture"""
    with open(sample_book_clean, 'r') as f:
        content = f.read()
    assert "Alice" in content
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("test", "TEST"),
])
def test_uppercase(input, expected):
    """Test uppercase conversion with multiple inputs"""
    assert input.upper() == expected
```

### Markers

```python
@pytest.mark.slow
def test_long_running_operation():
    """This test takes a long time"""
    pass


@pytest.mark.requires_ollama
def test_translation_with_ollama():
    """This test requires Ollama to be running"""
    pass


@pytest.mark.integration
def test_full_workflow():
    """This is an integration test"""
    pass
```

### Mocking

```python
def test_with_mock(monkeypatch):
    """Test using monkeypatch to mock"""
    def mock_api_call():
        return "mocked response"

    monkeypatch.setattr("module.api_call", mock_api_call)

    result = function_that_calls_api()
    assert result == "mocked response"
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

Tests run automatically on:
- **Push to main/develop** - Full test suite
- **Pull requests** - Full test suite + code review
- **Daily schedule** - Full test suite at 2 AM UTC

### Test Matrix

Tests run across:
- **Python versions**: 3.10, 3.11, 3.12
- **Operating systems**: Ubuntu, macOS
- **Test types**: Unit, Integration, E2E

### Pipeline Stages

1. **Lint** - Code formatting and style checks
2. **Unit Tests** - Fast isolated tests
3. **Integration Tests** - Multi-component workflows
4. **Security Scan** - Dependency vulnerability checks
5. **Performance Benchmarks** - Speed regression tests
6. **Coverage Upload** - Upload coverage to Codecov

### CI Configuration

See [`.github/workflows/test.yml`](.github/workflows/test.yml) for full configuration.

---

## Coverage Reports

### Viewing Coverage

```bash
# Generate HTML coverage report
pytest --cov=. --cov-report=html

# Open in browser
open htmlcov/index.html

# Terminal summary
pytest --cov=. --cov-report=term
```

### Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Translation | 100% |
| Deduplication | 100% |
| Validation | 95% |
| Audio Generation | 90% |
| Server API | 85% |
| Overall | 80%+ |

### Excluded from Coverage

- Test files (`tests/*`)
- Virtual environments (`venv/`)
- Third-party libraries (`site-packages/`)
- Debug/development scripts

---

## Performance Benchmarks

### Running Benchmarks

```bash
# Run all benchmarks
pytest tests/benchmarks/ --benchmark-only

# Compare against baseline
pytest tests/benchmarks/ --benchmark-compare

# Save benchmark results
pytest tests/benchmarks/ --benchmark-save=baseline
```

### Benchmark Categories

**Translation Speed**
- Words per second
- Chunk processing time
- Model comparison (o3-mini vs gemma3)

**Audio Generation Speed**
- Realtime factor (processing time / audio duration)
- TTS engine comparison (Kokoro vs XTTS vs Edge)
- Chunk size impact

**Deduplication Performance**
- Chunks per second
- Memory usage
- Large file handling

### Performance Targets

| Operation | Target |
|-----------|--------|
| Translation | 16-20 words/sec |
| Deduplication | 100 chunks/sec |
| Audio (Kokoro) | 31× faster than Bark |
| Chapter Detection | <100ms |

---

## Regression Prevention

### Known Issues Tests

Based on [CHANGELOG.md](CHANGELOG.md), we have regression tests for:

1. ✅ **Translation corruption** - Meta-commentary detection
2. ✅ **Chunk overlap duplication** - Two-layer deduplication
3. ✅ **Audio truncation** - Sentence boundary handling
4. ✅ **Missing chapter detection** - Sequential validation
5. ✅ **Gutenberg boilerplate** - Auto-fix validation

### Adding Regression Tests

When fixing a bug:

1. Write a test that reproduces the bug
2. Verify the test fails
3. Fix the bug
4. Verify the test passes
5. Add test to regression suite

Example:

```python
def test_issue_123_translation_corruption():
    """
    Regression test for Issue #123

    Prevent LLM from returning meta-commentary
    instead of actual translation.
    """
    original = "Test text to translate."
    corrupted = "I'll read and translate the text."

    is_valid = _validate_translation(corrupted, original)
    assert is_valid is False
```

---

## Continuous Improvement

### Test Metrics

Track over time:
- Total test count
- Code coverage percentage
- Test execution time
- Failure rate
- Flaky test count

### Best Practices

✅ **DO:**
- Write tests before fixing bugs
- Keep tests fast and isolated
- Use descriptive test names
- Test edge cases and errors
- Update tests when changing code
- Run tests locally before pushing

❌ **DON'T:**
- Skip writing tests for "simple" changes
- Use sleeps in tests (use mocks/fixtures)
- Commit commented-out tests
- Test implementation details
- Leave failing tests in CI

---

## Troubleshooting

### Common Issues

**Tests fail locally but pass in CI:**
- Check Python version matches CI
- Verify all dependencies installed
- Check for OS-specific issues

**Slow test execution:**
- Run with `-n auto` for parallel execution
- Skip slow tests with `-m "not slow"`
- Profile with `--durations=10`

**Import errors:**
- Ensure parent directories in path
- Check `sys.path` modifications
- Verify virtual environment activated

**Fixture not found:**
- Check fixture is in `conftest.py`
- Verify fixture scope is correct
- Import fixture from conftest

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Ensure >80% coverage for new code
3. Run full test suite before submitting PR
4. Update this documentation as needed

---

**Last Updated**: February 4, 2026
