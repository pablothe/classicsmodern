#!/usr/bin/env python3
"""Unit tests for server/job_database.py"""

import sys
import threading
from pathlib import Path
from datetime import datetime
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.job_database import JobDatabase


@pytest.fixture
def db(temp_dir):
    return JobDatabase(temp_dir / "test_jobs.db")


def _make_job(job_id="job_1", job_type="translate", status="pending", **kwargs):
    data = {
        "job_id": job_id,
        "job_type": job_type,
        "status": status,
        "created_at": datetime.now().isoformat(),
    }
    data.update(kwargs)
    return data


class TestInit:
    def test_creates_tables(self, db):
        # Should not raise
        stats = db.get_stats()
        assert stats['total'] == 0


class TestCreateAndGet:
    def test_create_job(self, db):
        job_id = db.create_job(_make_job("j1"))
        assert job_id == "j1"

    def test_get_job(self, db):
        db.create_job(_make_job("j1", config={"book_id": "alice"}))
        job = db.get_job("j1")
        assert job is not None
        assert job['job_id'] == "j1"
        assert job['config']['book_id'] == "alice"

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_job("nonexistent") is None


class TestUpdate:
    def test_update_status(self, db):
        db.create_job(_make_job("j1"))
        db.update_job("j1", {"status": "running", "started_at": datetime.now().isoformat()})
        job = db.get_job("j1")
        assert job['status'] == "running"
        assert job['started_at'] is not None

    def test_update_progress(self, db):
        db.create_job(_make_job("j1"))
        db.update_job("j1", {"progress": 50})
        job = db.get_job("j1")
        assert job['progress'] == 50

    def test_update_json_fields(self, db):
        db.create_job(_make_job("j1"))
        db.update_job("j1", {"result": {"output_file": "test.md"}})
        job = db.get_job("j1")
        assert job['result']['output_file'] == "test.md"


class TestListJobs:
    def test_list_by_type(self, db):
        db.create_job(_make_job("j1", job_type="translate"))
        db.create_job(_make_job("j2", job_type="audiobook"))
        db.create_job(_make_job("j3", job_type="translate"))

        translate_jobs = db.get_all_jobs(job_type="translate")
        assert len(translate_jobs) == 2

    def test_list_by_status(self, db):
        db.create_job(_make_job("j1", status="pending"))
        db.create_job(_make_job("j2", status="running"))
        db.create_job(_make_job("j3", status="completed"))

        pending = db.get_all_jobs(status="pending")
        assert len(pending) == 1
        assert pending[0]['job_id'] == "j1"


class TestDelete:
    def test_delete_job(self, db):
        db.create_job(_make_job("j1"))
        assert db.delete_job("j1") is True
        assert db.get_job("j1") is None

    def test_delete_nonexistent(self, db):
        assert db.delete_job("nope") is False


class TestCleanup:
    def test_cleanup_old_jobs(self, db):
        old_time = "2020-01-01T00:00:00"
        db.create_job(_make_job("old1", status="completed", created_at=old_time))
        db.create_job(_make_job("old2", status="failed", created_at=old_time))
        db.create_job(_make_job("new1", status="pending"))

        deleted = db.cleanup_old_jobs(max_age_hours=1)
        assert deleted == 2
        assert db.get_job("new1") is not None


class TestStats:
    def test_stats(self, db):
        db.create_job(_make_job("j1", job_type="translate", status="pending"))
        db.create_job(_make_job("j2", job_type="audiobook", status="completed"))

        stats = db.get_stats()
        assert stats['total'] == 2
        assert stats['by_type']['translate'] == 1
        assert stats['by_status']['completed'] == 1


class TestThreadSafety:
    def test_concurrent_writes(self, db):
        errors = []

        def write_job(i):
            try:
                db.create_job(_make_job(f"thread_job_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_job, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = db.get_stats()
        assert stats['total'] == 10
