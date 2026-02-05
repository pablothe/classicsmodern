# Test Suite Quick Start

Get up and running with tests in 5 minutes.

## 1. Install Dependencies

```bash
# Option A: Install test dependencies only
pip install -r tests/requirements-test.txt

# Option B: Install in user space (if system Python)
pip install --user -r tests/requirements-test.txt

# Option C: Create virtual environment (recommended)
python3 -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate
pip install -r tests/requirements-test.txt
```

## 2. Run Tests

```bash
# Run all tests
pytest

# Run just unit tests (fastest)
pytest tests/unit/

# Run with verbose output
pytest -v

# Run in parallel (much faster)
pytest -n auto
```

## 3. Check Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## 4. Run Specific Tests

```bash
# Run one test file
pytest tests/unit/test_deduplication.py

# Run one test class
pytest tests/unit/test_deduplication.py::TestDuplicationDetection

# Run one test function
pytest tests/unit/test_deduplication.py::TestDuplicationDetection::test_find_exact_duplicate_at_boundary

# Run tests matching pattern
pytest -k "duplicate"
```

## 5. Skip Slow Tests

```bash
# Skip slow tests
pytest -m "not slow"

# Skip tests requiring external services
pytest -m "not requires_ollama and not requires_gpu"
```

## 🎯 Most Useful Commands

```bash
# Fast unit tests with coverage
pytest tests/unit/ -n auto --cov=. --cov-report=term-missing

# Run last failed tests
pytest --lf

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Show slowest 10 tests
pytest --durations=10
```

## 🐛 Troubleshooting

**"ModuleNotFoundError"**
```bash
# Make sure you're in the project root
cd /path/to/classicsmodern

# Run tests from project root
pytest tests/
```

**"No module named pytest"**
```bash
# Install pytest
pip install pytest pytest-cov
```

**"Tests fail but should pass"**
```bash
# Check Python version (need 3.10+)
python3 --version

# Update dependencies
pip install -r tests/requirements-test.txt --upgrade
```

## 📚 More Info

- Full guide: [TESTING.md](../TESTING.md)
- Test README: [README.md](README.md)
- Summary: [TEST_SUITE_SUMMARY.md](../TEST_SUITE_SUMMARY.md)

## 🚀 Quick Examples

### Run Chapter Detection Tests
```bash
pytest tests/unit/test_chapter_detection.py -v
```

### Run Deduplication Tests
```bash
pytest tests/unit/test_deduplication.py -v
```

### Run Book Validation Tests
```bash
pytest tests/unit/test_book_validation.py -v
```

### Run All Unit Tests with Coverage
```bash
pytest tests/unit/ --cov=. --cov-report=html
```

---

**Need Help?** See [TESTING.md](../TESTING.md) for complete documentation.
