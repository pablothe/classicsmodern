#!/usr/bin/env python3
"""
Smoke Test Configuration and Fixtures

Service availability checks and shared fixtures for smoke tests.
Tests auto-skip when required services are unavailable.
"""

import shutil
import tempfile
import pytest
from pathlib import Path


# ============================================================================
# Service Availability Checks
# ============================================================================

def _ollama_available():
    """Check if Ollama is running and has a translation model."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            # Check for any gemma3-translator variant
            return any('gemma3-translator' in name for name in model_names)
    except Exception:
        pass
    return False


def _kokoro_available():
    """Check if kokoro-onnx is importable and model files exist."""
    try:
        from kokoro_onnx import Kokoro  # noqa: F401
        cache = Path.home() / ".cache" / "kokoro"
        return (cache / "kokoro-v1.0.onnx").exists() and (cache / "voices-v1.0.bin").exists()
    except ImportError:
        return False


def _ffmpeg_available():
    """Check if ffmpeg is installed."""
    return shutil.which("ffmpeg") is not None


def _diffusion_available():
    """Check if diffusers + torch are importable."""
    try:
        from diffusers import StableDiffusionPipeline  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def _network_available():
    """Check if we can reach gutenberg.org."""
    try:
        import requests
        resp = requests.head("https://www.gutenberg.org", timeout=10)
        return resp.status_code < 500
    except Exception:
        return False


# Cache results at module level (checked once per test session)
_service_cache = {}


def _check_service(name, checker):
    """Check service availability with caching."""
    if name not in _service_cache:
        _service_cache[name] = checker()
    return _service_cache[name]


# ============================================================================
# Auto-skip Logic
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Auto-skip smoke tests when required services are unavailable."""
    marker_checks = {
        'requires_ollama': ('Ollama not running or translation model not loaded', _ollama_available),
        'requires_kokoro': ('kokoro-onnx not installed or model files missing', _kokoro_available),
        'requires_ffmpeg': ('ffmpeg not installed', _ffmpeg_available),
        'requires_diffusion': ('diffusers/torch not installed', _diffusion_available),
        'requires_network': ('Network not available (cannot reach gutenberg.org)', _network_available),
    }

    for item in items:
        for marker_name, (reason, checker) in marker_checks.items():
            if marker_name in item.keywords:
                if not _check_service(marker_name, checker):
                    item.add_marker(pytest.mark.skip(reason=reason))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def smoke_book_path():
    """Path to the tiny book used for all smoke tests."""
    path = Path(__file__).parent.parent / "fixtures" / "sample_books" / "smoke_test_book.md"
    assert path.exists(), f"Smoke test book not found: {path}"
    return path


@pytest.fixture
def smoke_book_in_temp(smoke_book_path, tmp_path):
    """Copy smoke test book into a temp directory so tests can write next to it."""
    dest = tmp_path / "smoke_book"
    dest.mkdir()
    book_file = dest / "book.md"
    shutil.copy(smoke_book_path, book_file)
    return book_file


@pytest.fixture(scope="module")
def init_job_queue():
    """Initialize job queue with a temp database for server tests."""
    try:
        from server.job_queue import init_queue
        import server.job_queue as job_queue_module
    except Exception:
        yield
        return

    if job_queue_module._global_queue is None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_jobs.db"
            init_queue(db_path, max_workers=1)
            yield
            job_queue_module._global_queue = None
    else:
        yield
