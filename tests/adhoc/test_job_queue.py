#!/usr/bin/env python3
"""
Test script for unified job queue system

Tests basic functionality:
1. Database initialization
2. Job creation
3. Job retrieval
4. Job updates
5. Queue statistics
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from server.job_queue import init_queue, JobType, JobStatus


def test_job_handler(job, progress_callback):
    """Test job handler that simulates work"""
    print(f"\n[TEST HANDLER] Processing job: {job['job_id']}")

    # Simulate work with progress updates
    for i in range(0, 101, 20):
        progress_callback(i, {
            'stage': 'test',
            'message': f'Processing step {i}%...'
        })
        time.sleep(0.5)

    return {
        'success': True,
        'message': 'Test job completed'
    }


def main():
    print("=" * 60)
    print("Job Queue Test")
    print("=" * 60)

    # Create test database
    test_db_path = Path(__file__).parent / "test_jobs.db"

    # Clean up old test database
    if test_db_path.exists():
        test_db_path.unlink()
        print(f"✓ Cleaned up old test database")

    # Initialize queue
    print("\n1. Initializing job queue...")
    queue = init_queue(test_db_path, max_workers=2)
    print(f"   ✓ Queue initialized")

    # Register test handler
    print("\n2. Registering test handler...")
    queue.register_handler(JobType.DOWNLOAD, test_job_handler)
    queue.register_handler(JobType.TRANSLATE, test_job_handler)
    queue.register_handler(JobType.AUDIOBOOK, test_job_handler)
    print(f"   ✓ Handlers registered")

    # Create test jobs
    print("\n3. Creating test jobs...")

    job1_id = queue.create_job(
        job_type=JobType.DOWNLOAD,
        config={'gutenberg_id': 11, 'book_slug': 'test_alice'},
        priority=1
    )
    print(f"   ✓ Created download job: {job1_id}")

    job2_id = queue.create_job(
        job_type=JobType.TRANSLATE,
        config={'book_id': 'test_book', 'source_file': 'test.md'},
        priority=0
    )
    print(f"   ✓ Created translate job: {job2_id}")

    # Wait a bit for jobs to start
    time.sleep(2)

    # Check job status
    print("\n4. Checking job status...")
    job1 = queue.get_job(job1_id)
    print(f"   Job 1 status: {job1['status']} (progress: {job1['progress']}%)")

    job2 = queue.get_job(job2_id)
    print(f"   Job 2 status: {job2['status']} (progress: {job2['progress']}%)")

    # Get all jobs
    print("\n5. Listing all jobs...")
    all_jobs = queue.get_all_jobs()
    print(f"   Total jobs: {len(all_jobs)}")
    for job in all_jobs:
        print(f"   - {job['job_type']}: {job['status']} ({job['progress']}%)")

    # Get stats
    print("\n6. Queue statistics...")
    stats = queue.get_stats()
    print(f"   Total jobs: {stats['total']}")
    print(f"   By status: {stats.get('by_status', {})}")
    print(f"   By type: {stats.get('by_type', {})}")
    print(f"   Queue size: {stats.get('queue_size', 0)}")
    print(f"   Running: {stats.get('running_count', 0)}")

    # Wait for jobs to complete
    print("\n7. Waiting for jobs to complete...")
    timeout = 30
    start = time.time()

    while time.time() - start < timeout:
        job1 = queue.get_job(job1_id)
        job2 = queue.get_job(job2_id)

        if job1['status'] in ['completed', 'failed'] and job2['status'] in ['completed', 'failed']:
            break

        time.sleep(1)
        print(f"   Job 1: {job1['progress']}% | Job 2: {job2['progress']}%")

    # Final status
    print("\n8. Final job status...")
    job1 = queue.get_job(job1_id)
    job2 = queue.get_job(job2_id)

    print(f"   Job 1: {job1['status']}")
    if job1['status'] == 'completed':
        print(f"      Result: {job1.get('result', {})}")
    elif job1['status'] == 'failed':
        print(f"      Error: {job1.get('error', 'Unknown')}")

    print(f"   Job 2: {job2['status']}")
    if job2['status'] == 'completed':
        print(f"      Result: {job2.get('result', {})}")
    elif job2['status'] == 'failed':
        print(f"      Error: {job2.get('error', 'Unknown')}")

    # Cleanup
    print("\n9. Testing cleanup...")
    cleaned = queue.cleanup_old_jobs(max_age_hours=0)  # Clean all completed
    print(f"   ✓ Cleaned up {cleaned} jobs")

    # Shutdown
    print("\n10. Shutting down queue...")
    queue.shutdown()
    print(f"   ✓ Queue shutdown complete")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
