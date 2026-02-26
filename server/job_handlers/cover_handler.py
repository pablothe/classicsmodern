#!/usr/bin/env python3
"""
Cover Handler - Cover art generation worker

Wraps cover.py CLI for unified job queue.
Uses Stable Diffusion locally via lib/cover/generator.py.
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Callable


BOOKS_DIR = Path(__file__).parent.parent.parent / "books"
COVER_SCRIPT = Path(__file__).parent.parent.parent / "cover.py"


def cover_handler(job: Dict, progress_callback: Callable) -> Dict:
    """
    Handle cover art generation job.

    Args:
        job: Job data dictionary with:
            - config.book_id: Book directory name
        progress_callback: Function to report progress
            Signature: progress_callback(progress: int, state: Dict)

    Returns:
        Result dictionary with:
            - cover_path: Path to generated cover image
            - book_id: Book directory name

    Raises:
        Exception on generation failure
    """
    config = job['config']
    book_id = config['book_id']

    book_dir = BOOKS_DIR / book_id
    if not book_dir.exists():
        raise Exception(f"Book directory not found: {book_id}")

    # Stage 1: Get book prompt from content using LLM (0-10%)
    progress_callback(5, {'message': 'Analyzing book content for cover prompt...', 'stage': 'prepare'})

    from lib.cover.prompts import get_book_prompt
    # Pass actual book file path so LLM can read content
    book_files = list(book_dir.glob("*.md"))
    book_file = str(book_files[0]) if book_files else book_id
    prompt = get_book_prompt(book_file)

    progress_callback(10, {'message': 'Prompt ready', 'stage': 'prepare'})

    # Stage 2: Determine output path (10-20%)
    cover_path = book_dir / "cover.png"
    progress_callback(20, {'message': 'Loading Stable Diffusion model...', 'stage': 'generate'})

    # Stage 3: Generate cover via cover.py subprocess (20-90%)
    if not COVER_SCRIPT.exists():
        raise Exception("cover.py not found")

    cmd = [
        sys.executable,
        str(COVER_SCRIPT),
        prompt,
        '--output', str(cover_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else (
                result.stdout.strip() if result.stdout else 'Unknown error'
            )
            raise Exception(f"Cover generation failed: {error_msg}")

    except subprocess.TimeoutExpired:
        raise Exception("Cover generation timed out (5 minutes)")

    progress_callback(90, {'message': 'Cover generated', 'stage': 'verify'})

    # Stage 4: Verify output (90-100%)
    if not cover_path.exists():
        raise Exception("Cover file was not created")

    progress_callback(100, {'message': 'Cover art complete', 'stage': 'done'})

    return {
        'cover_path': str(cover_path),
        'book_id': book_id
    }
