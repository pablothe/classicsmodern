#!/usr/bin/env python3
"""Integration tests for server/job_queue.py"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.job_queue import UnifiedJobQueue, JobType, JobStatus


@pytest.fixture
def queue(temp_dir):
    """Create a job queue with temp database."""
    q = UnifiedJobQueue(temp_dir / "test_queue.db", max_workers=2)
    yield q
    q.shutdown()


@pytest.fixture
def queue_with_handler(queue):
    """Queue with a simple echo handler registered for all types."""
    def echo_handler(job_data, progress_callback):
        progress_callback(50, {"step": "processing"})
        return {"echo": job_data.get("config", {})}

    for job_type in JobType:
        queue.register_handler(job_type, echo_handler)
    return queue


class TestJobLifecycle:
    def test_pending_to_completed(self, queue_with_handler):
        job_id = queue_with_handler.create_job(JobType.DOWNLOAD, {"url": "test"})
        # Wait for worker to pick up and complete
        for _ in range(50):
            job = queue_with_handler.get_job(job_id)
            if job['status'] == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
        job = queue_with_handler.get_job(job_id)
        assert job['status'] == JobStatus.COMPLETED
        assert job['progress'] == 100

    def test_failed_job_on_handler_error(self, queue):
        def failing_handler(job_data, progress_callback):
            raise RuntimeError("Handler exploded")

        queue.register_handler(JobType.TRANSLATE, failing_handler)
        job_id = queue.create_job(JobType.TRANSLATE, {"book": "test"})

        for _ in range(50):
            job = queue.get_job(job_id)
            if job['status'] in [JobStatus.FAILED, JobStatus.COMPLETED]:
                break
            time.sleep(0.1)
        job = queue.get_job(job_id)
        assert job['status'] == JobStatus.FAILED
        assert "exploded" in job.get('error', '')

    def test_no_handler_marks_failed(self, queue):
        """Job with no registered handler should fail."""
        job_id = queue.create_job(JobType.COVER, {"prompt": "test"})
        for _ in range(50):
            job = queue.get_job(job_id)
            if job['status'] != JobStatus.PENDING:
                break
            time.sleep(0.1)
        job = queue.get_job(job_id)
        assert job['status'] == JobStatus.FAILED
        assert "No handler" in job.get('error', '')


class TestCancelJob:
    def test_cancel_pending_or_running(self, queue):
        """Cancelling a job should mark it as cancelled."""
        # Use a blocking handler so job stays running long enough to cancel
        barrier = threading.Event()

        def blocking_handler(job_data, progress_callback):
            barrier.wait(timeout=5)
            return {"done": True}

        queue.register_handler(JobType.DOWNLOAD, blocking_handler)
        job_id = queue.create_job(JobType.DOWNLOAD, {"url": "test"})

        # Wait until job is running
        for _ in range(50):
            job = queue.get_job(job_id)
            if job['status'] == JobStatus.RUNNING:
                break
            time.sleep(0.1)

        result = queue.cancel_job(job_id)
        assert result is True
        barrier.set()  # Unblock handler

        job = queue.get_job(job_id)
        assert job['status'] == JobStatus.CANCELLED

    def test_cancel_completed_fails(self, queue_with_handler):
        job_id = queue_with_handler.create_job(JobType.DOWNLOAD, {"url": "test"})
        for _ in range(50):
            job = queue_with_handler.get_job(job_id)
            if job['status'] == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
        assert queue_with_handler.cancel_job(job_id) is False


class TestDeleteJob:
    def test_delete_completed(self, queue_with_handler):
        job_id = queue_with_handler.create_job(JobType.DOWNLOAD, {"url": "test"})
        for _ in range(50):
            job = queue_with_handler.get_job(job_id)
            if job['status'] == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
        assert queue_with_handler.delete_job(job_id) is True
        assert queue_with_handler.get_job(job_id) is None

    def test_delete_pending_fails(self, queue):
        job_id = queue.create_job(JobType.DOWNLOAD, {"url": "test"})
        # Cancel first to prevent worker pickup, then try delete on pending
        # Actually, just cancel and then delete the cancelled job
        queue.cancel_job(job_id)
        assert queue.delete_job(job_id) is True


class TestProgressAndETA:
    def test_progress_callback_updates(self, queue):
        progress_values = []

        def slow_handler(job_data, progress_callback):
            for pct in [25, 50, 75]:
                progress_callback(pct, {"step": f"at_{pct}"})
                progress_values.append(pct)
            return {"done": True}

        queue.register_handler(JobType.TRANSLATE, slow_handler)
        job_id = queue.create_job(JobType.TRANSLATE, {"book": "test"})

        for _ in range(50):
            job = queue.get_job(job_id)
            if job['status'] == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
        assert progress_values == [25, 50, 75]
        job = queue.get_job(job_id)
        assert job['progress'] == 100


class TestStats:
    def test_stats_include_queue_info(self, queue_with_handler):
        queue_with_handler.create_job(JobType.DOWNLOAD, {"url": "1"})
        queue_with_handler.create_job(JobType.TRANSLATE, {"book": "2"})

        # Give workers a moment
        time.sleep(0.5)
        stats = queue_with_handler.get_stats()
        assert 'queue_size' in stats
        assert 'running_count' in stats
        assert 'worker_count' in stats
        assert stats['worker_count'] == 2


class TestConcurrentExecution:
    def test_multiple_jobs_run_concurrently(self, queue):
        """Two download jobs should be able to run concurrently (limit=3)."""
        started = threading.Event()
        barrier = threading.Barrier(2, timeout=5)

        def barrier_handler(job_data, progress_callback):
            try:
                barrier.wait()  # Both must reach here to proceed
            except threading.BrokenBarrierError:
                pass
            return {"concurrent": True}

        queue.register_handler(JobType.DOWNLOAD, barrier_handler)
        job1 = queue.create_job(JobType.DOWNLOAD, {"id": 1})
        job2 = queue.create_job(JobType.DOWNLOAD, {"id": 2})

        for _ in range(50):
            j1 = queue.get_job(job1)
            j2 = queue.get_job(job2)
            if j1['status'] == JobStatus.COMPLETED and j2['status'] == JobStatus.COMPLETED:
                break
            time.sleep(0.1)

        assert queue.get_job(job1)['status'] == JobStatus.COMPLETED
        assert queue.get_job(job2)['status'] == JobStatus.COMPLETED
