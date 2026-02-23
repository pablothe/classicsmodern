#!/usr/bin/env python3
"""
Job Database - Persistent storage for job queue

Provides SQLite-based storage for all job types with:
- Atomic operations
- Thread-safe access
- Migration from legacy JSON files
- Automatic cleanup
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager


class JobDatabase:
    """Thread-safe SQLite database for job storage"""

    def __init__(self, db_path: Path):
        """
        Initialize job database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.lock = threading.Lock()

        # Create database if needed
        self._init_database()

    def _init_database(self):
        """Create tables if they don't exist"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    config TEXT,
                    state TEXT,
                    result TEXT,
                    error TEXT,
                    parent_job_id TEXT,
                    priority INTEGER DEFAULT 0,
                    worker_id TEXT
                )
            ''')

            # Create indexes for common queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id)')

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection"""
        with self.lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            try:
                yield conn
            finally:
                conn.close()

    def create_job(self, job_data: Dict) -> str:
        """
        Create a new job.

        Args:
            job_data: Job data dictionary

        Returns:
            Job ID
        """
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO jobs (
                    job_id, job_type, status, progress, created_at,
                    config, state, priority, parent_job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_data['job_id'],
                job_data['job_type'],
                job_data.get('status', 'pending'),
                job_data.get('progress', 0),
                job_data.get('created_at', datetime.now().isoformat()),
                json.dumps(job_data.get('config', {})),
                json.dumps(job_data.get('state', {})),
                job_data.get('priority', 0),
                job_data.get('parent_job_id')
            ))
            conn.commit()

        return job_data['job_id']

    def update_job(self, job_id: str, updates: Dict) -> bool:
        """
        Update job fields.

        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update

        Returns:
            True if job was updated
        """
        # Build dynamic UPDATE query
        fields = []
        values = []

        for field, value in updates.items():
            if field in ['config', 'state', 'result']:
                # JSON fields
                fields.append(f"{field} = ?")
                values.append(json.dumps(value) if value is not None else None)
            elif field in ['status', 'progress', 'started_at', 'completed_at', 'error', 'worker_id']:
                fields.append(f"{field} = ?")
                values.append(value)

        if not fields:
            return False

        values.append(job_id)
        query = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?"

        with self._get_connection() as conn:
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM jobs WHERE job_id = ?',
                (job_id,)
            ).fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

    def get_all_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get jobs with optional filters.

        Args:
            job_type: Filter by job type
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of job dictionaries
        """
        query = 'SELECT * FROM jobs WHERE 1=1'
        params = []

        if job_type:
            query += ' AND job_type = ?'
            params.append(job_type)

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY created_at DESC'

        if limit:
            query += f' LIMIT {limit}'

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job by ID.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def has_active_job_for_book(self, book_identifier: str) -> Optional[Dict]:
        """
        Check if there's a pending/running job for a given book.

        Searches both config.book_id and config.book_slug since download
        jobs use book_slug while translate/audiobook jobs use book_id.

        Args:
            book_identifier: Book ID or slug to check

        Returns:
            Dict with job info if active job exists, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT job_id, job_type, status, progress
                FROM jobs
                WHERE status IN ('pending', 'running')
                AND (
                    json_extract(config, '$.book_id') = ?
                    OR json_extract(config, '$.book_slug') = ?
                )
                LIMIT 1
            ''', [book_identifier, book_identifier])
            row = cursor.fetchone()
            if row:
                return {
                    'job_id': row[0],
                    'job_type': row[1],
                    'status': row[2],
                    'progress': row[3]
                }
            return None

    def cleanup_old_jobs(self, max_age_hours: int = 24, keep_status: List[str] = None) -> int:
        """
        Delete old completed/failed jobs.

        Args:
            max_age_hours: Maximum age in hours
            keep_status: List of statuses to keep (default: ['running', 'pending'])

        Returns:
            Number of jobs deleted
        """
        if keep_status is None:
            keep_status = ['running', 'pending']

        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()

        with self._get_connection() as conn:
            # Build exclusion clause
            placeholders = ','.join('?' * len(keep_status))
            query = f'''
                DELETE FROM jobs
                WHERE created_at < ?
                AND status NOT IN ({placeholders})
            '''

            cursor = conn.execute(query, [cutoff] + keep_status)
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Statistics dictionary
        """
        with self._get_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]

            by_status = {}
            for row in conn.execute('SELECT status, COUNT(*) as count FROM jobs GROUP BY status'):
                by_status[row[0]] = row[1]

            by_type = {}
            for row in conn.execute('SELECT job_type, COUNT(*) as count FROM jobs GROUP BY job_type'):
                by_type[row[0]] = row[1]

            return {
                'total': total,
                'by_status': by_status,
                'by_type': by_type
            }

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """
        Convert SQLite row to dictionary.

        Args:
            row: SQLite row object

        Returns:
            Job dictionary
        """
        data = {
            'job_id': row['job_id'],
            'job_type': row['job_type'],
            'status': row['status'],
            'progress': row['progress'],
            'created_at': row['created_at'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'error': row['error'],
            'parent_job_id': row['parent_job_id'],
            'priority': row['priority'],
            'worker_id': row['worker_id']
        }

        # Parse JSON fields
        if row['config']:
            data['config'] = json.loads(row['config'])
        else:
            data['config'] = {}

        if row['state']:
            data['state'] = json.loads(row['state'])
        else:
            data['state'] = {}

        if row['result']:
            data['result'] = json.loads(row['result'])
        else:
            data['result'] = {}

        return data

    def migrate_from_json(self, json_dir: Path):
        """
        Migrate jobs from legacy JSON files to database.

        Args:
            json_dir: Directory containing JSON job files
        """
        if not json_dir.exists():
            return

        migrated = 0
        for json_file in json_dir.glob('*.json'):
            try:
                with open(json_file, 'r') as f:
                    job_data = json.load(f)

                # Check if already exists
                existing = self.get_job(job_data['job_id'])
                if existing:
                    continue

                # Create job
                self.create_job(job_data)
                migrated += 1

            except Exception as e:
                print(f"⚠️  Failed to migrate {json_file.name}: {e}")

        if migrated > 0:
            print(f"✓ Migrated {migrated} jobs from JSON files")
