#!/usr/bin/env python3
"""
Book Health Monitor - scans all books for problems and auto-recovers what it can.

Runs on server startup and every hour. Auto-fixes recoverable issues (e.g. missing
chapter metadata), logs everything else so those logs drive future improvements.
"""

import re
import threading
from pathlib import Path
from typing import Dict, List

BOOKS_DIR = Path(__file__).parent.parent / "books"
HEALTH_INTERVAL = 3600  # 1 hour


def check_book_health(book_dir: Path) -> Dict:
    """
    Check a single book directory for problems.

    Returns dict with:
      - book_id: str
      - has_source, has_audio, has_playlist, has_chapter_meta, has_cover: bool
      - issues: list of issue strings
      - recovered: list of recovery actions taken
    """
    book_id = book_dir.name
    issues = []
    recovered = []

    # 1. Source text
    md_files = list(book_dir.glob("*.md"))
    has_source = len(md_files) > 0
    if not has_source:
        issues.append("no_source_text")

    # 2. Audio files
    audio_dirs = [d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith("audio")]
    has_audio = False
    zero_byte_files = []
    for audio_dir in audio_dirs:
        chapter_files = list(audio_dir.glob("*chapter*.mp3"))
        if chapter_files:
            has_audio = True
            for f in chapter_files:
                if f.stat().st_size == 0:
                    zero_byte_files.append(f.name)
    if zero_byte_files:
        issues.append(f"zero_byte_audio:{len(zero_byte_files)}_files")

    # 3. Playlist (prefer *audiobook*.m3u over *chunks*.m3u)
    playlists = []
    for audio_dir in audio_dirs:
        for p in audio_dir.glob("*.m3u"):
            if not re.search(r'_\d{8}_\d{6}\.m3u$', p.name):
                playlists.append(p)
    # Sort so audiobook playlists come first (chunks playlists reference deleted raw WAVs)
    playlists.sort(key=lambda p: (0 if 'audiobook' in p.name else 1, p.name))
    has_playlist = len(playlists) > 0

    # 4. Book manifest (single source of truth for chapter data)
    has_chapter_meta = (book_dir / "book_manifest.json").exists()
    if not has_chapter_meta:
        issues.append("missing_book_manifest")

    # 5. Cover image
    has_cover = (book_dir / "cover.png").exists()
    if not has_cover and has_audio:
        issues.append("missing_cover")

    return {
        "book_id": book_id,
        "has_source": has_source,
        "has_audio": has_audio,
        "has_playlist": has_playlist,
        "has_chapter_meta": has_chapter_meta,
        "has_cover": has_cover,
        "issues": issues,
        "recovered": recovered,
    }


def cleanup_stale_jobs():
    """
    Mark zombie jobs as cancelled. On server startup, any job still marked
    'running' is from a previous session and will never complete.
    Uses 'cancelled' so the UI skips them (it already filters out cancelled jobs).

    Also cleans up old 'failed' jobs that were from previous server restarts
    (before cleanup was changed to use 'cancelled' status).
    """
    try:
        from server.job_queue import get_queue
        queue = get_queue()
        count = 0

        # 1. Mark stale running jobs as cancelled
        running_jobs = queue.db.get_all_jobs(status='running')
        for job in (running_jobs or []):
            queue.db.update_job(job['job_id'], {
                'status': 'cancelled',
                'error': 'Server restarted — job was interrupted'
            })
            count += 1

        # 2. Fix old failed jobs that were from server restarts
        failed_jobs = queue.db.get_all_jobs(status='failed')
        for job in (failed_jobs or []):
            if job.get('error') and 'Server restarted' in job['error']:
                queue.db.update_job(job['job_id'], {
                    'status': 'cancelled'
                })
                count += 1

        if count:
            print(f"  * Cleaned up {count} stale job(s) from previous session")
        return count
    except Exception:
        return 0


def run_health_check() -> List[Dict]:
    """
    Scan all books and report/fix issues.
    Returns list of per-book health reports.
    """
    if not BOOKS_DIR.exists():
        return []

    reports = []
    total_issues = 0
    total_recovered = 0

    print("\n" + "=" * 60)
    print("Book Health Check")
    print("=" * 60)

    # Clean up zombie jobs from previous server session
    cleanup_stale_jobs()

    for book_dir in sorted(BOOKS_DIR.iterdir()):
        if not book_dir.is_dir() or book_dir.name.startswith("."):
            continue
        report = check_book_health(book_dir)
        reports.append(report)

        if report["recovered"]:
            total_recovered += len(report["recovered"])
            for action in report["recovered"]:
                print(f"  * {report['book_id']}: auto-recovered {action}")

        if report["issues"]:
            total_issues += len(report["issues"])
            for issue in report["issues"]:
                print(f"  ! {report['book_id']}: {issue}")

    healthy = sum(1 for r in reports if not r["issues"])
    print(f"\n  {healthy}/{len(reports)} books healthy", end="")
    if total_recovered:
        print(f", {total_recovered} auto-recovered", end="")
    if total_issues:
        print(f", {total_issues} issues remaining", end="")
    print()
    print("=" * 60 + "\n")

    return reports


# --- Periodic scheduling ---

_timer = None


def _periodic_health_check():
    """Run health check and schedule next one."""
    global _timer
    try:
        run_health_check()
    except Exception as e:
        print(f"  Health check error: {e}")
    _timer = threading.Timer(HEALTH_INTERVAL, _periodic_health_check)
    _timer.daemon = True
    _timer.start()


def start_periodic_health_check():
    """Start the hourly health check timer."""
    global _timer
    _timer = threading.Timer(HEALTH_INTERVAL, _periodic_health_check)
    _timer.daemon = True
    _timer.start()


def stop_periodic_health_check():
    """Stop the periodic timer."""
    global _timer
    if _timer:
        _timer.cancel()
        _timer = None
