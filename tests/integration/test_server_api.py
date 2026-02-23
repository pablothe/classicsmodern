#!/usr/bin/env python3
"""
Server API Route Tests

Tests that API routes are correctly registered and accessible.
Catches issues like route ordering bugs (e.g., /api/jobs/stats captured by /api/jobs/{job_id}).
"""

import pytest
import sys
import tempfile
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from fastapi.testclient import TestClient
    from server.audiobook_server import app
    from server.job_queue import init_queue, _global_queue
    import server.job_queue as job_queue_module
    SERVER_AVAILABLE = True
except Exception:
    SERVER_AVAILABLE = False


@pytest.fixture(scope="module")
def _init_job_queue():
    """Initialize job queue with a temp database for the test session."""
    if not SERVER_AVAILABLE:
        yield
        return
    # Only initialize if not already initialized
    if job_queue_module._global_queue is None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_jobs.db"
            init_queue(db_path, max_workers=1)
            yield
            # Cleanup: reset global queue
            job_queue_module._global_queue = None
    else:
        yield


@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not available")
class TestServerRoutes:
    """Test that key routes return expected status codes."""

    @pytest.fixture(autouse=True)
    def setup_client(self, _init_job_queue):
        self.client = TestClient(app)

    def test_root_returns_200(self):
        """GET / should return the player page."""
        response = self.client.get("/")
        assert response.status_code == 200

    def test_jobs_page_returns_200(self):
        """GET /jobs should return the jobs dashboard page."""
        response = self.client.get("/jobs")
        assert response.status_code == 200

    def test_api_books_returns_json(self):
        """GET /api/books should return a JSON object with a books list."""
        response = self.client.get("/api/books")
        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert isinstance(data["books"], list)

    def test_api_health_returns_200(self):
        """GET /api/health should return health status."""
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_api_jobs_list_returns_json(self):
        """GET /api/jobs should return a JSON object with jobs list."""
        response = self.client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data

    def test_api_jobs_stats_not_captured_by_job_id(self):
        """
        GET /api/jobs/stats must return 200, NOT 404.

        Regression test: If /api/jobs/{job_id} is defined before /api/jobs/stats,
        FastAPI treats 'stats' as a job_id and returns 404.
        """
        response = self.client.get("/api/jobs/stats")
        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}. "
            "Route ordering bug: /api/jobs/stats is being captured by /api/jobs/{{job_id}}. "
            "Move /api/jobs/stats BEFORE /api/jobs/{{job_id}} in audiobook_server.py."
        )

    def test_api_jobs_cleanup_is_accessible(self):
        """POST /api/jobs/cleanup should not be captured by {job_id}."""
        response = self.client.post("/api/jobs/cleanup")
        assert response.status_code == 200

    def test_nonexistent_job_returns_404(self):
        """GET /api/jobs/{nonexistent_id} should return 404."""
        response = self.client.get("/api/jobs/nonexistent-id-12345")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
