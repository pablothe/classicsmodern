# Unified Job Queue System

A centralized job management system for all background tasks in the audiobook server.

## Overview

The unified job queue replaces the previous fragmented job systems (Gutenberg downloader, audiobook pipeline) with a single, consistent interface for managing all long-running tasks.

### Features

✅ **Single Source of Truth** - All jobs stored in SQLite database
✅ **Real-time Progress** - Track job progress and ETA
✅ **Persistent State** - Survives server restarts
✅ **Priority Queue** - Higher priority jobs run first
✅ **Concurrency Limits** - Per-type limits (3 downloads, 1 translation, 2 audiobooks)
✅ **Resumable** - Failed jobs can be retried
✅ **Web Dashboard** - Beautiful UI for monitoring

## Architecture

```
server/
├── job_database.py         # SQLite persistence layer
├── job_queue.py            # Core queue manager
├── job_handlers/           # Job type handlers
│   ├── __init__.py
│   ├── download_handler.py     # Gutenberg downloads
│   ├── translate_handler.py    # Book translation
│   └── pipeline_handler.py     # Full audiobook pipeline
└── static/
    ├── jobs.html           # Dashboard UI
    ├── jobs.css            # Dashboard styles
    └── jobs.js             # Dashboard logic
```

## Job Types

### 1. Download (`JobType.DOWNLOAD`)
Downloads books from Project Gutenberg.

**Config:**
```json
{
    "gutenberg_id": 11,
    "book_slug": "alice_adventures"
}
```

**Result:**
```json
{
    "output_file": "books/alice_adventures/source.md",
    "validation": { "chapter_count": 12, "word_count": 27500 }
}
```

### 2. Translate (`JobType.TRANSLATE`)
Standalone translation job (for already-downloaded books).

**Config:**
```json
{
    "book_id": "crime_punishment",
    "source_file": "source.md",
    "source_language": "Russian",
    "target_language": "Modern English",
    "translation_model": "zongwei/gemma3-translator:4b"
}
```

**Result:**
```json
{
    "output_file": "books/crime_punishment/source_Modern_English_20260208.md",
    "chapter_count": 36
}
```

### 3. Audiobook (`JobType.AUDIOBOOK`)
Full audiobook pipeline: translation → summarization → audio → cover → registration.

**Config:**
```json
{
    "book_id": "crime_punishment",
    "source_file": "translated.md",
    "translate": false,
    "summarize": 50,          // Optional: 10-90
    "voice": "bf_emma",
    "speed": 1.0,
    "generate_cover": true
}
```

**Result:**
```json
{
    "output_files": {
        "audio": "books/crime_punishment/audio_kokoro/",
        "cover": "books/crime_punishment/cover.png"
    }
}
```

## API Endpoints

### List Jobs
```http
GET /api/jobs?job_type=download&status=running&limit=10
```

**Query Parameters:**
- `job_type` - Filter by type (`download`, `translate`, `audiobook`)
- `status` - Filter by status (`pending`, `running`, `completed`, `failed`, `cancelled`)
- `limit` - Max results

**Response:**
```json
{
    "jobs": [
        {
            "job_id": "abc123",
            "job_type": "download",
            "status": "running",
            "progress": 45,
            "created_at": "2026-02-08T20:00:00",
            "eta_seconds": 120,
            "config": { "gutenberg_id": 11 },
            "state": { "message": "Downloading HTML..." }
        }
    ],
    "total": 1
}
```

### Get Job Details
```http
GET /api/jobs/{job_id}
```

**Response:**
```json
{
    "job_id": "abc123",
    "job_type": "download",
    "status": "completed",
    "progress": 100,
    "result": { "output_file": "books/alice/source.md" }
}
```

### Create Download Job
```http
POST /api/jobs/download
Content-Type: application/json

{
    "gutenberg_id": 11,
    "book_slug": "alice_adventures"
}
```

### Create Translation Job
```http
POST /api/jobs/translate
Content-Type: application/json

{
    "book_id": "crime_punishment",
    "source_file": "source.md",
    "source_language": "Russian",
    "target_language": "Modern English"
}
```

### Create Audiobook Job
```http
POST /api/jobs/audiobook
Content-Type: application/json

{
    "book_id": "crime_punishment",
    "source_file": "translated.md",
    "translate": false,
    "summarize": 50,
    "voice": "bf_emma",
    "generate_cover": true
}
```

### Cancel Job
```http
DELETE /api/jobs/{job_id}
```

### Queue Statistics
```http
GET /api/jobs/stats
```

**Response:**
```json
{
    "total": 15,
    "by_status": {
        "completed": 10,
        "running": 2,
        "pending": 3
    },
    "by_type": {
        "download": 5,
        "translate": 4,
        "audiobook": 6
    },
    "queue_size": 3,
    "running_count": 2
}
```

### Cleanup Old Jobs
```http
POST /api/jobs/cleanup?max_age_hours=24
```

## Web Dashboard

Access at: `http://localhost:8000/static/jobs.html`

### Features

- **Real-time Updates** - Auto-refresh every 2 seconds
- **Filters** - Filter by type and status
- **Progress Bars** - Visual progress indicators for running jobs
- **Job Details** - Click any job for detailed information
- **Cancel Jobs** - Cancel pending/running jobs
- **Statistics** - Queue overview and metrics
- **Toast Notifications** - Success/error messages

### Screenshots

#### Jobs List
```
┌─────────────────────────────────────────────────────┐
│ 📋 Jobs Queue              [🔄 Refresh] [🗑️ Cleanup] │
├─────────────────────────────────────────────────────┤
│ Total: 15  Running: 2  Pending: 3  Completed: 10   │
├─────────────────────────────────────────────────────┤
│ 📥 DOWNLOAD  Alice's Adventures      [RUNNING]     │
│ Downloading from Gutenberg #11                      │
│ ████████████░░░░░░░░░░░ 45% - Converting to Markdown│
│ Created: 2 min ago | ETA: ~2 min                   │
└─────────────────────────────────────────────────────┘
```

## Database Schema

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    config TEXT,        -- JSON
    state TEXT,         -- JSON
    result TEXT,        -- JSON
    error TEXT,
    parent_job_id TEXT,
    priority INTEGER DEFAULT 0,
    worker_id TEXT
);
```

## Python API

### Initialize Queue

```python
from server.job_queue import init_queue, get_queue, JobType

# Initialize (do this once in server startup)
queue = init_queue(db_path, max_workers=4)

# Register handlers
queue.register_handler(JobType.DOWNLOAD, download_handler)
queue.register_handler(JobType.TRANSLATE, translate_handler)
queue.register_handler(JobType.AUDIOBOOK, pipeline_handler)

# Get queue instance anywhere
queue = get_queue()
```

### Create Jobs

```python
# Create a job
job_id = queue.create_job(
    job_type=JobType.DOWNLOAD,
    config={'gutenberg_id': 11, 'book_slug': 'alice'},
    priority=1  # Higher = more important
)

# Monitor progress
job = queue.get_job(job_id)
print(f"Progress: {job['progress']}%")
print(f"Status: {job['status']}")
print(f"ETA: {job['eta_seconds']} seconds")
```

### Custom Job Handlers

```python
def my_handler(job, progress_callback):
    """
    Custom job handler.

    Args:
        job: Job data dict with config
        progress_callback: Function to report progress
            Signature: progress_callback(progress: int, state: dict)

    Returns:
        Result dict

    Raises:
        Exception on failure
    """
    # Do work
    progress_callback(50, {'message': 'Halfway done...'})

    # Return results
    return {
        'output_file': '/path/to/output.md',
        'metadata': {'key': 'value'}
    }

# Register handler
queue.register_handler(JobType.DOWNLOAD, my_handler)
```

## Testing

Run the test suite:

```bash
python3 test_job_queue.py
```

This will:
1. Initialize the queue
2. Create test jobs
3. Monitor progress
4. Verify completion
5. Test cleanup
6. Shutdown gracefully

## Migration from Legacy Systems

### Gutenberg Downloader

**Before:**
```python
from server.gutenberg_downloader import create_download_job

job_id = create_download_job(gutenberg_id=11, book_slug='alice')
```

**After:**
```python
from server.job_queue import get_queue, JobType

queue = get_queue()
job_id = queue.create_job(
    job_type=JobType.DOWNLOAD,
    config={'gutenberg_id': 11, 'book_slug': 'alice'}
)
```

### Audiobook Pipeline

**Before:**
```python
from server.audiobook_pipeline import create_job

job_id = create_job(book_id='alice', source_file='source.md', config={...})
```

**After:**
```python
from server.job_queue import get_queue, JobType

queue = get_queue()
job_id = queue.create_job(
    job_type=JobType.AUDIOBOOK,
    config={
        'book_id': 'alice',
        'source_file': 'source.md',
        'voice': 'bf_emma',
        ...
    }
)
```

## Troubleshooting

### Jobs stuck in "pending"

**Cause:** Worker threads not started or queue semaphore full

**Fix:**
```python
# Check queue stats
stats = queue.get_stats()
print(f"Worker count: {stats['worker_count']}")
print(f"Running count: {stats['running_count']}")

# Restart server to reinitialize workers
```

### Jobs failing immediately

**Cause:** Handler not registered or throwing exceptions

**Fix:**
```python
# Check handler registration
queue.register_handler(JobType.DOWNLOAD, download_handler)

# Check job error
job = queue.get_job(job_id)
print(f"Error: {job['error']}")
```

### Database locked errors

**Cause:** Multiple processes accessing same database

**Fix:** Use only one server instance per database file

### Old jobs not cleaning up

**Cause:** Automatic cleanup disabled

**Fix:**
```python
# Manual cleanup
cleaned = queue.cleanup_old_jobs(max_age_hours=24)
print(f"Cleaned {cleaned} jobs")
```

## Performance

### Concurrency Limits

Configurable per job type in `job_queue.py`:

```python
self.type_limits = {
    JobType.DOWNLOAD: 3,     # Max 3 concurrent downloads
    JobType.TRANSLATE: 1,    # Max 1 translation (CPU intensive)
    JobType.AUDIOBOOK: 2     # Max 2 audiobook generations
}
```

### Database Indexing

Indexes on common queries:
- `job_type` - Fast filtering by type
- `status` - Fast filtering by status
- `created_at` - Fast sorting by date
- `parent_job_id` - Fast job chaining lookups

### Memory Usage

- ~10MB base overhead
- ~5KB per job in database
- ~50KB per running job (in-memory state)

**Example:** 1000 jobs = ~15MB total

## Future Enhancements

### Phase 2 Features

- ⏳ Job chaining (download → translate → audiobook)
- ⏳ WebSocket support for real-time updates
- ⏳ Job retry with exponential backoff
- ⏳ Resource usage tracking (CPU, disk warnings)
- ⏳ Job templates (save common configs)
- ⏳ Batch job creation (process multiple books)

### Planned API Endpoints

```http
# Job chaining
POST /api/jobs/chain
{
    "jobs": [
        {"type": "download", "config": {...}},
        {"type": "translate", "config": {...}},
        {"type": "audiobook", "config": {...}}
    ]
}

# WebSocket
WS /ws/jobs
```

## Contributing

When adding new job types:

1. Create handler in `server/job_handlers/`
2. Add enum to `JobType` in `job_queue.py`
3. Register handler in `audiobook_server.py`
4. Add API endpoint for job creation
5. Update dashboard UI to display new type
6. Write tests

## License

Part of the Modern Classics audiobook project.
