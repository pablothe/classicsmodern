#!/usr/bin/env python3
"""
Download Handler - Gutenberg book download worker

Wraps GutenbergDownloader for unified job queue.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Callable

from server.gutenberg_downloader import GutenbergDownloader


def download_handler(job: Dict, progress_callback: Callable) -> Dict:
    """
    Handle Gutenberg book download job.

    Args:
        job: Job data dictionary with:
            - config.gutenberg_id: Gutenberg book ID
            - config.book_slug: Book directory name
            - config.language: ISO 639-1 language code (optional)
        progress_callback: Function to report progress
            Signature: progress_callback(progress: int, state: Dict)

    Returns:
        Result dictionary with:
            - output_file: Path to downloaded file
            - validation: Validation results
            - book_slug: Book directory name

    Raises:
        Exception on download/conversion failure
    """
    config = job['config']
    gutenberg_id = config['gutenberg_id']
    book_slug = config['book_slug']
    language = config.get('language')  # ISO 639-1 code from Gutenberg catalog

    # Create downloader
    downloader = GutenbergDownloader()

    # Custom download method with progress hooks
    try:
        # Stage 1: Download HTML (0-40%)
        progress_callback(10, {'message': 'Downloading from Gutenberg...', 'stage': 'download'})
        html_content = downloader._fetch_html(gutenberg_id)

        progress_callback(40, {'message': 'Download complete', 'stage': 'download'})

        # Stage 2: Convert to Markdown (40-60%)
        progress_callback(45, {'message': 'Converting to Markdown...', 'stage': 'convert'})
        markdown = downloader._html_to_markdown(html_content)

        progress_callback(60, {'message': 'Conversion complete', 'stage': 'convert'})

        # Stage 3: Strip boilerplate (60-80%)
        progress_callback(65, {'message': 'Cleaning Gutenberg boilerplate...', 'stage': 'clean'})
        cleaned = downloader._strip_boilerplate(markdown)

        # Save file
        book_dir = downloader.books_dir / book_slug
        book_dir.mkdir(parents=True, exist_ok=True)
        output_file = book_dir / "book.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        # Save Gutenberg metadata (language source of truth)
        if language:
            gutenberg_meta = {
                'gutenberg_id': gutenberg_id,
                'language': language,
                'downloaded_at': datetime.now().isoformat()
            }
            meta_path = book_dir / "gutenberg_metadata.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(gutenberg_meta, f, indent=2)

        progress_callback(80, {'message': 'File saved', 'stage': 'save'})

        # Stage 4: Validate (80-100%)
        progress_callback(85, {'message': 'Validating structure...', 'stage': 'validate'})
        validation = downloader._validate_book(output_file)

        progress_callback(95, {'message': 'Validation complete', 'stage': 'validate'})

        # Done
        progress_callback(100, {'message': 'Download complete', 'stage': 'done'})

        return {
            'output_file': str(output_file),
            'validation': validation,
            'book_slug': book_slug,
            'gutenberg_id': gutenberg_id
        }

    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")
