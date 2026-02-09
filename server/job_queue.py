#!/usr/bin/env python3
"""
Unified Job Queue - Central manager for all background tasks

Handles:
- Download jobs (Gutenberg)
- Translation jobs
- Audiobook pipeline jobs
- Job chaining and dependencies

Features:
- Thread-safe job execution
- Priority queue
- Concurrency limits per job type
- Real-time progress tracking
- Persistent state across restarts
"""

import threading
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable
from queue import PriorityQueue

from server.job_database import JobDatabase


class JobType(str, Enum):
    """Job type enumeration"""
    DOWNLOAD = "download"
    TRANSLATE = "translate"
    AUDIOBOOK = "audiobook"


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UnifiedJobQueue:
    """
    Central job queue manager.

    Manages all background tasks with:
    - Priority-based scheduling
    - Per-type concurrency limits
    - Persistent storage
    - Progress tracking
    """

    def __init__(self, db_path: Path, max_workers: int = 4):
        """
        Initialize job queue.

        Args:
            db_path: Path to SQLite database
            max_workers: Maximum concurrent workers
        """
        self.db = JobDatabase(db_path)
        self.max_workers = max_workers

        # Job handlers registry
        self.handlers: Dict[JobType, Callable] = {}

        # Worker threads
        self.workers: List[threading.Thread] = []
        self.job_queue = PriorityQueue()
        self.running_jobs: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()

        # Per-type concurrency limits
        self.type_limits = {
            JobType.DOWNLOAD: 3,     # Max 3 concurrent downloads
            JobType.TRANSLATE: 1,    # Max 1 translation (CPU intensive)
            JobType.AUDIOBOOK: 2     # Max 2 audiobook generations
        }

        # Per-type semaphores
        self.type_semaphores = {
            job_type: threading.Semaphore(limit)
            for job_type, limit in self.type_limits.items()
        }

        # Lock for thread-safe operations
        self.lock = threading.Lock()

        # Start worker threads
        self._start_workers()

        # Restore pending jobs from database
        self._restore_pending_jobs()

    def register_handler(self, job_type: JobType, handler: Callable):
        """
        Register a job handler function.

        Args:
            job_type: Type of job this handler processes
            handler: Function that processes the job
                     Signature: handler(job_data: Dict, progress_callback: Callable) -> Dict
        """
        self.handlers[job_type] = handler
        print(f"✓ Registered handler for {job_type}")

    def create_job(
        self,
        job_type: JobType,
        config: Dict,
        priority: int = 0,
        parent_job_id: Optional[str] = None
    ) -> str:
        """
        Create a new job.

        Args:
            job_type: Type of job
            config: Job configuration
            priority: Job priority (higher = more important)
            parent_job_id: Optional parent job ID (for chaining)

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())

        job_data = {
            'job_id': job_id,
            'job_type': job_type,
            'status': JobStatus.PENDING,
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'config': config,
            'state': {},
            'priority': priority,
            'parent_job_id': parent_job_id
        }

        # Save to database
        self.db.create_job(job_data)

        # Add to queue
        self.job_queue.put((-priority, datetime.now().timestamp(), job_id))

        print(f"✓ Created {job_type} job: {job_id}")

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job dictionary with calculated ETA
        """
        job = self.db.get_job(job_id)

        if job:
            # Calculate ETA if running
            if job['status'] == JobStatus.RUNNING and job['progress'] > 5:
                started_at = datetime.fromisoformat(job['started_at'])
                elapsed = (datetime.now() - started_at).total_seconds()
                estimated_total = elapsed / (job['progress'] / 100)
                eta_seconds = max(0, estimated_total - elapsed)
                job['eta_seconds'] = int(eta_seconds)
            else:
                job['eta_seconds'] = None

        return job

    def get_all_jobs(
        self,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get jobs with optional filters.

        Args:
            job_type: Filter by job type
            status: Filter by status
            limit: Maximum results

        Returns:
            List of jobs
        """
        return self.db.get_all_jobs(job_type, status, limit)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled
        """
        job = self.db.get_job(job_id)

        if not job or job['status'] not in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False

        # Update status
        self.db.update_job(job_id, {
            'status': JobStatus.CANCELLED,
            'completed_at': datetime.now().isoformat(),
            'error': 'Cancelled by user'
        })

        print(f"✓ Cancelled job: {job_id}")
        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job (only if completed/failed/cancelled).

        Args:
            job_id: Job identifier

        Returns:
            True if deleted
        """
        job = self.db.get_job(job_id)

        if not job or job['status'] in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False

        return self.db.delete_job(job_id)

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Delete old completed/failed jobs.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of jobs deleted
        """
        return self.db.cleanup_old_jobs(max_age_hours)

    def get_stats(self) -> Dict:
        """
        Get queue statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.db.get_stats()

        # Add queue info
        stats['queue_size'] = self.job_queue.qsize()
        stats['running_count'] = len(self.running_jobs)
        stats['worker_count'] = len(self.workers)

        return stats

    def _start_workers(self):
        """Start worker threads"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"JobWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

        print(f"✓ Started {self.max_workers} worker threads")

    def _worker_loop(self, worker_id: int):
        """
        Worker thread main loop.

        Args:
            worker_id: Worker thread identifier
        """
        while not self.shutdown_event.is_set():
            try:
                # Get job from queue (timeout to check shutdown)
                try:
                    _, _, job_id = self.job_queue.get(timeout=1.0)
                except:
                    continue

                # Get job data
                job = self.db.get_job(job_id)
                if not job:
                    continue

                # Skip if already running/completed/cancelled
                if job['status'] != JobStatus.PENDING:
                    continue

                # Get job type
                job_type = JobType(job['job_type'])

                # Check if handler registered
                if job_type not in self.handlers:
                    self.db.update_job(job_id, {
                        'status': JobStatus.FAILED,
                        'error': f'No handler registered for {job_type}'
                    })
                    continue

                # Acquire type-specific semaphore (limit concurrency per type)
                with self.type_semaphores[job_type]:
                    # Mark as running
                    with self.lock:
                        self.running_jobs[job_id] = threading.current_thread()

                    self.db.update_job(job_id, {
                        'status': JobStatus.RUNNING,
                        'started_at': datetime.now().isoformat(),
                        'worker_id': f'worker-{worker_id}'
                    })

                    # Execute job
                    try:
                        # Create progress callback
                        def progress_callback(progress: int, state: Dict):
                            # Check if cancelled
                            current_job = self.db.get_job(job_id)
                            if current_job and current_job['status'] == JobStatus.CANCELLED:
                                raise Exception("Job cancelled by user")

                            # Update progress
                            self.db.update_job(job_id, {
                                'progress': progress,
                                'state': state
                            })

                        # Call handler
                        handler = self.handlers[job_type]
                        result = handler(job, progress_callback)

                        # Mark as completed
                        self.db.update_job(job_id, {
                            'status': JobStatus.COMPLETED,
                            'progress': 100,
                            'completed_at': datetime.now().isoformat(),
                            'result': result
                        })

                        print(f"✅ Job {job_id} completed")

                    except Exception as e:
                        # Check if cancelled
                        current_job = self.db.get_job(job_id)
                        if current_job and current_job['status'] == JobStatus.CANCELLED:
                            print(f"⚠️  Job {job_id} cancelled")
                        else:
                            # Mark as failed
                            self.db.update_job(job_id, {
                                'status': JobStatus.FAILED,
                                'completed_at': datetime.now().isoformat(),
                                'error': str(e)
                            })
                            print(f"❌ Job {job_id} failed: {e}")

                    finally:
                        # Remove from running jobs
                        with self.lock:
                            self.running_jobs.pop(job_id, None)

            except Exception as e:
                print(f"⚠️  Worker {worker_id} error: {e}")
                time.sleep(1)

    def _restore_pending_jobs(self):
        """Restore pending jobs from database to queue"""
        pending_jobs = self.db.get_all_jobs(status=JobStatus.PENDING)

        for job in pending_jobs:
            priority = job.get('priority', 0)
            created_at = datetime.fromisoformat(job['created_at']).timestamp()
            self.job_queue.put((-priority, created_at, job['job_id']))

        if pending_jobs:
            print(f"✓ Restored {len(pending_jobs)} pending jobs")

    def shutdown(self):
        """Gracefully shutdown the queue"""
        print("\n⏹️  Shutting down job queue...")

        # Signal workers to stop
        self.shutdown_event.set()

        # Wait for workers
        for worker in self.workers:
            worker.join(timeout=5.0)

        print("✓ Job queue shutdown complete")


# Global queue instance (initialized by server)
_global_queue: Optional[UnifiedJobQueue] = None


def get_queue() -> UnifiedJobQueue:
    """
    Get global job queue instance.

    Returns:
        UnifiedJobQueue instance

    Raises:
        RuntimeError if queue not initialized
    """
    if _global_queue is None:
        raise RuntimeError("Job queue not initialized. Call init_queue() first.")
    return _global_queue


def init_queue(db_path: Path, max_workers: int = 4) -> UnifiedJobQueue:
    """
    Initialize global job queue.

    Args:
        db_path: Path to SQLite database
        max_workers: Maximum concurrent workers

    Returns:
        UnifiedJobQueue instance
    """
    global _global_queue

    if _global_queue is not None:
        print("⚠️  Job queue already initialized")
        return _global_queue

    _global_queue = UnifiedJobQueue(db_path, max_workers)
    return _global_queue
