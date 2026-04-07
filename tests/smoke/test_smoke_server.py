#!/usr/bin/env python3
"""
Smoke Test: Server API Routes

Quick gate: verifies the server starts and basic endpoints respond.
Detailed route testing lives in tests/integration/test_server_api.py.
"""

import sys
import pytest
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from fastapi.testclient import TestClient
    from server.audiobook_server import app
    SERVER_AVAILABLE = True
except Exception:
    SERVER_AVAILABLE = False

pytestmark = pytest.mark.smoke


@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not available")
class TestSmokeServerAPI:
    """Smoke: Server starts and core endpoints respond."""

    @pytest.fixture(autouse=True)
    def setup_client(self, init_job_queue):
        self.client = TestClient(app)

    def test_root_returns_html(self):
        """GET / should return the catalog/player page."""
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_api_health(self):
        """GET /api/health should return ok status."""
        resp = self.client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_api_books_returns_list(self):
        """GET /api/books should return JSON with a books list."""
        resp = self.client.get("/api/books")
        assert resp.status_code == 200
        data = resp.json()
        assert "books" in data
        assert isinstance(data["books"], list)

    def test_nonexistent_book_returns_404(self):
        """GET /api/books/{nonexistent} should return 404."""
        resp = self.client.get("/api/books/nonexistent-book-id-12345")
        assert resp.status_code == 404
