#!/usr/bin/env python3
"""
Smoke Test: Server API Routes

Tests all critical API endpoints using FastAPI TestClient (in-process, no port binding).
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
    """Smoke: All critical API routes respond correctly."""

    @pytest.fixture(autouse=True)
    def setup_client(self, init_job_queue):
        self.client = TestClient(app)

    def test_root_returns_html(self):
        """GET / should return the catalog/player page."""
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_jobs_page_returns_html(self):
        """GET /jobs should return the jobs dashboard."""
        resp = self.client.get("/jobs")
        assert resp.status_code == 200

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

    def test_api_jobs_list(self):
        """GET /api/jobs should return JSON with jobs list."""
        resp = self.client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data

    def test_api_jobs_stats_not_captured_by_job_id(self):
        """
        Regression: /api/jobs/stats must NOT be captured by /api/jobs/{job_id}.
        If route ordering is wrong, FastAPI treats 'stats' as a job_id → 404.
        """
        resp = self.client.get("/api/jobs/stats")
        assert resp.status_code == 200, (
            f"Expected 200 but got {resp.status_code}. "
            "Route ordering bug: /api/jobs/stats captured by /api/jobs/{{job_id}}."
        )

    def test_api_jobs_cleanup(self):
        """POST /api/jobs/cleanup should be accessible."""
        resp = self.client.post("/api/jobs/cleanup")
        assert resp.status_code == 200

    def test_nonexistent_book_returns_404(self):
        """GET /api/books/{nonexistent} should return 404."""
        resp = self.client.get("/api/books/nonexistent-book-id-12345")
        assert resp.status_code == 404

    def test_nonexistent_job_returns_404(self):
        """GET /api/jobs/{nonexistent} should return 404."""
        resp = self.client.get("/api/jobs/nonexistent-job-id-12345")
        assert resp.status_code == 404
