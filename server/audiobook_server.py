#!/usr/bin/env python3
"""
Audiobook Server - Serve audiobooks over local WiFi

Features:
- Auto-discover books in ../books/ directory
- REST API for book catalog and metadata
- Stream audio files with range request support
- Track playback position per device
- CORS enabled for mobile access

Usage:
    python3 audiobook_server.py [--host HOST] [--port PORT]

Example:
    python3 audiobook_server.py --host 0.0.0.0 --port 8000
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import argparse

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import book catalog and text extractor
from lib.book.catalog import get_book_info
from server.text_extractor import find_source_text, get_chapter_text_data, get_book_chapters_list, discover_text_tracks
from server.users_db import (
    get_all_users, get_user, create_user, update_user, delete_user,
    ensure_initialized as ensure_users_initialized
)
from lib.utils import safe_json_write

# Import Gutenberg modules
try:
    from server.gutenberg_catalog import GutenbergCatalog
    from server.gutenberg_downloader import (
        create_download_job,
        get_job_status,
        get_all_jobs as get_all_gutenberg_jobs  # Use alias to avoid namespace collision
    )
    GUTENBERG_AVAILABLE = True
except ImportError:
    GUTENBERG_AVAILABLE = False
    print("⚠️  Gutenberg browser not available (catalog or downloader module missing)")

# Optional: Import LLM chat (only if AI assistant is available)
try:
    from server.llm_chat import BookTools, ask_with_tools, check_ollama_available
    AI_ASSISTANT_AVAILABLE = True
except ImportError:
    AI_ASSISTANT_AVAILABLE = False
    print("⚠️  AI Assistant not available (llm_chat.py or ollama module missing)")

# Import unified job queue
try:
    from server.job_queue import init_queue, get_queue, JobType, JobStatus
    from server.job_handlers import cover_handler, download_handler, pipeline_handler, translate_handler
    UNIFIED_QUEUE_AVAILABLE = True
except ImportError as e:
    UNIFIED_QUEUE_AVAILABLE = False
    print(f"⚠️  Unified job queue not available: {e}")


# Constants
BOOKS_DIR = Path(__file__).parent.parent / "books"
PLAYBACK_DB = Path(__file__).parent / "playback_db.json"
STATIC_DIR = Path(__file__).parent / "static"
JOB_DB_PATH = Path(__file__).parent / "jobs.db"

# Initialize FastAPI app
app = FastAPI(
    title="Audiobook Server",
    description="Local WiFi audiobook server with playback tracking",
    version="1.0.0"
)

# Enable CORS for phone access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins on LAN
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web player
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/jobs")
async def jobs_page():
    """Serve the jobs dashboard page."""
    return FileResponse(STATIC_DIR / "jobs.html")


# ============================================================================
# Utility Functions
# ============================================================================

def get_audio_duration(audio_path: Path) -> Optional[float]:
    """
    Get audio file duration in seconds using ffprobe.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds, or None if cannot be determined
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries',
             'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
             str(audio_path)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, FileNotFoundError):
        pass

    return None


# ============================================================================
# Database Functions
# ============================================================================

def load_playback_db() -> Dict:
    """Load playback database from JSON file."""
    if not PLAYBACK_DB.exists():
        return {}
    try:
        with open(PLAYBACK_DB, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_playback_db(db: Dict) -> None:
    """Save playback database to JSON file (atomic write)."""
    safe_json_write(PLAYBACK_DB, db)


# ============================================================================
# Book Discovery Functions
# ============================================================================

def parse_m3u_playlist(playlist_path: Path) -> List[str]:
    """Parse M3U playlist and return list of audio file paths."""
    audio_files = []
    playlist_dir = playlist_path.parent

    try:
        with open(playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Resolve relative paths
                audio_path = playlist_dir / line
                if audio_path.exists():
                    audio_files.append(str(audio_path.relative_to(BOOKS_DIR)))
    except IOError:
        pass

    return audio_files


def extract_variant_info(filename: str) -> Dict:
    """Extract variant information from playlist filename."""
    info = {
        'type': 'full',  # full, summary, deduped
        'summary_pct': None,
        'is_combined': False,  # audiobook vs chunks
        'timestamp': None,
        'source_lang': None,
        'target_lang': None
    }

    filename_lower = filename.lower()

    # Check if it's a summary
    if 'summarized' in filename_lower or 'summary' in filename_lower:
        info['type'] = 'summary'
        # Extract percentage (e.g., 50pct)
        pct_match = re.search(r'(\d+)pct', filename_lower)
        if pct_match:
            info['summary_pct'] = int(pct_match.group(1))

    # Check if it's deduplicated
    if 'deduped' in filename_lower or 'deduplicated' in filename_lower:
        info['type'] = 'deduped'

    # Check if it's combined (audiobook) or chunks
    if 'audiobook' in filename_lower or 'complete' in filename_lower:
        info['is_combined'] = True

    # Extract timestamp (e.g., 20260105_220208)
    ts_match = re.search(r'(\d{8}_\d{6})', filename)
    if ts_match:
        info['timestamp'] = ts_match.group(1)

    # Extract language translation info (e.g., "German_To_Modern_Modern English")
    lang_match = re.search(r'(\w+)_To_Modern[_ ](\w+(?: \w+)?)', filename, re.IGNORECASE)
    if lang_match:
        info['source_lang'] = lang_match.group(1).capitalize()
        target = lang_match.group(2).replace('_', ' ').strip()
        info['target_lang'] = target.title()

    # Also try to extract from "modern_X" pattern
    if not info['target_lang']:
        modern_match = re.search(r'modern[_ ](\w+(?: \w+)?)', filename_lower)
        if modern_match:
            target = modern_match.group(1).replace('_', ' ').strip()
            info['target_lang'] = target.title()

    return info


def discover_books() -> List[Dict]:
    """
    Auto-discover all books in books/ directory.

    Books are discovered in two stages:
    1. Find all book directories (folders in books/)
    2. Find audio variants (M3U playlists) for each book

    Books without audio are still included (has_audio=False).
    Books with audio have one or more variants:
    - Full translation
    - 50% summary
    - Deduplicated
    - Combined vs chunked files

    Returns list of books with their variants.
    """
    books_by_id = {}

    if not BOOKS_DIR.exists():
        return []

    # STAGE 1: Discover all book directories
    for book_dir in sorted(BOOKS_DIR.iterdir()):
        # Skip non-directories and hidden files
        if not book_dir.is_dir() or book_dir.name.startswith('.'):
            continue

        book_id = book_dir.name

        # Initialize book entry
        title = book_id.replace('_', ' ').title()
        language = None
        author = None
        year = None

        # Get cataloged information first (most authoritative)
        catalog_info = get_book_info(book_id)
        if catalog_info:
            title = catalog_info.get('title', title)
            author = catalog_info.get('author', author)
            year = catalog_info.get('year', year)
            language = catalog_info.get('original_language')

        # Load chapter data from book_manifest.json (single source of truth)
        chapters = None
        manifest_path = book_dir / "book_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                raw_chapters = manifest.get('chapters', [])
                if raw_chapters:
                    chapters = []
                    for i, ch in enumerate(raw_chapters):
                        ch_title = ch.get('title', '')
                        ch_number = ch.get('number', i + 1)
                        section_type = ch.get('section_type', 'chapter')
                        # Build display title based on section type
                        non_numbered_types = ('prologue', 'epilogue', 'preface', 'foreword',
                                             'introduction', 'conclusion', 'interlude', 'appendix', 'dedication')
                        if section_type in non_numbered_types:
                            display_title = ch_title or section_type.title()
                        elif ch_title:
                            # Strip redundant "Chapter N" prefixes from title
                            clean_title = re.sub(r'^Chapter\s+\d+[.:]\s*', '', ch_title, flags=re.IGNORECASE)
                            clean_title = re.sub(r'^CHAPTER\s+[IVXLCDM]+[.:]\s*', '', clean_title)
                            clean_title = clean_title.strip(' .')
                            display_title = f"Chapter {ch_number}: {clean_title}" if clean_title else f"Chapter {ch_number}"
                        else:
                            display_title = f"Chapter {ch_number}"
                        chapters.append({
                            'title': display_title,
                            'number': ch_number,
                            'section_type': section_type,
                            'index': i,
                            'file_index': i,
                            'timestamp': 0.0
                        })
                meta = manifest.get('metadata', {})
                if not catalog_info and meta.get('title'):
                    title = meta['title']
                if not author and meta.get('author'):
                    author = meta['author']
            except (json.JSONDecodeError, IOError):
                pass

        # Check chunk manifest for prologue (chapter 0) and epilogue
        if chapters:
            chunk_manifest_paths = [
                book_dir / "audio_kokoro" / f"{book_id}_chunk_manifest.json",
                book_dir / "audio_kokoro" / "book_chunk_manifest.json",
                book_dir / f"{book_id}_chunk_manifest.json",
            ]
            for cm_path in chunk_manifest_paths:
                if cm_path.exists():
                    try:
                        with open(cm_path, 'r') as cm_f:
                            cm_data = json.load(cm_f)
                        chunk_chapters = set(c.get('chapter') for c in cm_data.get('chunks', []))
                        max_manifest_chapter = max(ch['number'] for ch in chapters)
                        # Prologue: chunk manifest has chapter 0
                        if 0 in chunk_chapters:
                            # Check if sections metadata has a custom prologue title
                            prologue_title = 'Prologue'
                            for sec in cm_data.get('sections', []):
                                if sec.get('chapter') == 0:
                                    prologue_title = sec.get('title', 'Prologue')
                                    break
                            chapters.insert(0, {
                                'title': prologue_title,
                                'number': 0,
                                'section_type': 'prologue',
                                'index': 0,
                                'file_index': 0,
                                'timestamp': 0.0
                            })
                            # Shift existing chapters' indices
                            for ch in chapters[1:]:
                                ch['index'] += 1
                                ch['file_index'] += 1
                        # Epilogue: chunk manifest has chapter > last manifest chapter
                        epilogue_chapters = [c for c in chunk_chapters if c is not None and c > max_manifest_chapter]
                        if epilogue_chapters:
                            epilogue_title = 'Epilogue'
                            for sec in cm_data.get('sections', []):
                                if sec.get('chapter') == min(epilogue_chapters):
                                    epilogue_title = sec.get('title', 'Epilogue')
                                    break
                            next_index = len(chapters)
                            chapters.append({
                                'title': epilogue_title,
                                'number': max_manifest_chapter + 1,
                                'section_type': 'epilogue',
                                'index': next_index,
                                'file_index': next_index,
                                'timestamp': 0.0
                            })
                    except (json.JSONDecodeError, IOError, ValueError):
                        pass
                    break

        # Find cover image
        cover_path = None
        cover_loc = book_dir / "cover.png"
        if cover_loc.exists():
            cover_path = str(cover_loc.relative_to(BOOKS_DIR))

        # Check for source text availability
        source_text_path = find_source_text(book_dir)
        has_source_text = source_text_path is not None

        # Discover available text language tracks
        text_tracks = discover_text_tracks(book_dir, language)

        # Create book entry (with empty variants initially)
        books_by_id[book_id] = {
            'book_id': book_id,
            'title': title,
            'author': author,
            'year': year,
            'language': language or 'Unknown',
            'chapters': chapters,
            'has_chapters': chapters is not None,
            'cover_image': cover_path,
            'has_cover': cover_path is not None,
            'has_audio': False,  # Will be set to True if variants found
            'has_source_text': has_source_text,
            'source_text_path': str(source_text_path.relative_to(book_dir)) if source_text_path else None,
            'text_tracks': text_tracks,
            'variants': []
        }

    # STAGE 2: Find all M3U playlists and add as variants
    for playlist_path in BOOKS_DIR.rglob("*.m3u"):
        # Skip chunks playlists — intermediate build artifacts, not playable variants
        if playlist_path.name.endswith('_chunks.m3u'):
            continue

        # Get book directory (top-level folder in books/)
        try:
            rel_path = playlist_path.relative_to(BOOKS_DIR)
            book_id = rel_path.parts[0]
        except (ValueError, IndexError):
            continue

        # Skip if book not in our list (shouldn't happen, but safety check)
        if book_id not in books_by_id:
            continue

        # Parse playlist
        audio_files = parse_m3u_playlist(playlist_path)
        if not audio_files:
            continue

        # Get playlist info
        playlist_name = playlist_path.stem
        variant_info = extract_variant_info(playlist_name)

        # Calculate size
        total_size = sum(
            (BOOKS_DIR / f).stat().st_size
            for f in audio_files
            if (BOOKS_DIR / f).exists()
        )

        # Get creation time
        created_at = datetime.fromtimestamp(playlist_path.stat().st_mtime).isoformat()

        # Build variant object
        variant = {
            'variant_id': playlist_path.stem,
            'playlist_path': str(playlist_path.relative_to(BOOKS_DIR)),
            'type': variant_info['type'],
            'summary_pct': variant_info['summary_pct'],
            'is_combined': variant_info['is_combined'],
            'source_lang': variant_info['source_lang'],
            'target_lang': variant_info['target_lang'],
            'audio_files': audio_files,
            'file_count': len(audio_files),
            'size_bytes': total_size,
            'size_mb': round(total_size / (1024 * 1024), 2),
            'created_at': created_at,
            'timestamp': variant_info['timestamp'],
            'total_duration': 0
        }

        # Try to get total_duration from chunk manifest
        book_dir = BOOKS_DIR / book_id
        chunk_manifest_candidates = [
            book_dir / "audio_kokoro" / f"{book_id}_chunk_manifest.json",
            book_dir / "audio_kokoro" / "book_chunk_manifest.json",
            book_dir / f"{book_id}_chunk_manifest.json",
        ]
        for cm_path in chunk_manifest_candidates:
            if cm_path.exists():
                try:
                    with open(cm_path, 'r') as cm_f:
                        cm_data = json.load(cm_f)
                        variant['total_duration'] = cm_data.get('total_duration', 0)
                except (json.JSONDecodeError, IOError):
                    pass
                break

        # Add variant to book and mark book as having audio
        books_by_id[book_id]['variants'].append(variant)
        books_by_id[book_id]['has_audio'] = True

        # Try to extract language from audio filenames if not already set
        if books_by_id[book_id]['language'] == 'Unknown' and audio_files:
            first_audio = audio_files[0].lower()
            if 'spanish' in first_audio:
                books_by_id[book_id]['language'] = 'Spanish'
            elif 'english' in first_audio:
                books_by_id[book_id]['language'] = 'English'
            elif 'russian' in first_audio:
                books_by_id[book_id]['language'] = 'Russian'

    # Sort variants by creation date (newest first) and convert to list
    books = []
    for book_data in books_by_id.values():
        if book_data['variants']:
            book_data['variants'].sort(key=lambda v: v['created_at'], reverse=True)
        # Add summary stats
        book_data['variant_count'] = len(book_data['variants'])
        total_audio_size = sum(v['size_bytes'] for v in book_data['variants'])
        book_data['total_size_bytes'] = total_audio_size
        book_data['total_size_mb'] = round(total_audio_size / (1024 * 1024), 2) if total_audio_size else 0
        books.append(book_data)

    return sorted(books, key=lambda x: x['title'])


def get_book_by_id(book_id: str) -> Optional[Dict]:
    """Get book metadata by ID."""
    books = discover_books()
    for book in books:
        if book['book_id'] == book_id:
            return book
    return None


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve web player interface."""
    player_html = STATIC_DIR / "player.html"
    if player_html.exists():
        return FileResponse(player_html)
    return {
        "message": "Audiobook Server API",
        "docs": "/docs",
        "books": "/api/books"
    }


@app.get("/api/books")
async def list_books():
    """
    List all available audiobooks.

    Returns:
        List of books with metadata (title, file count, size, etc.)
    """
    books = discover_books()
    total_library_bytes = sum(b.get('total_size_bytes', 0) for b in books)
    print(f"[API /api/books] Returning {len(books)} books, {round(total_library_bytes / (1024*1024), 1)} MB total")
    for book in books:
        print(f"  - {book['title']} ({book['book_id']}): {book['variant_count']} variants")
    return {
        "books": books,
        "total": len(books),
        "total_library_size_mb": round(total_library_bytes / (1024 * 1024), 2)
    }


@app.get("/api/books/{book_id}")
async def get_book(book_id: str):
    """
    Get detailed information about a specific book.

    Args:
        book_id: Book identifier (folder name)

    Returns:
        Book metadata with chapters and audio file list
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.get("/api/books/{book_id}/variants/{variant_id}/audio/{file_index}")
async def stream_audio(
    book_id: str,
    variant_id: str,
    file_index: int,
    request: Request,
    range: Optional[str] = Header(None)
):
    """
    Stream audio file with range request support (for seeking).

    Args:
        book_id: Book identifier
        variant_id: Variant identifier (playlist name)
        file_index: Index of audio file in variant's audio_files list
        range: HTTP Range header for partial content

    Returns:
        Audio file stream with range support
    """
    print(f"[AUDIO STREAM] book={book_id}, variant={variant_id[:40]}..., file_index={file_index}, range={range}")

    book = get_book_by_id(book_id)
    if not book:
        print(f"[AUDIO STREAM] ERROR: Book not found: {book_id}")
        raise HTTPException(status_code=404, detail="Book not found")

    # Find variant
    variant = None
    for v in book['variants']:
        if v['variant_id'] == variant_id:
            variant = v
            break

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    if file_index >= len(variant['audio_files']):
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_path = BOOKS_DIR / variant['audio_files'][file_index]
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_size = audio_path.stat().st_size

    # Handle range requests (for seeking in audio)
    if range:
        range_match = re.match(r'bytes=(\d+)-(\d*)', range)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

            # Validate range
            if start >= file_size:
                raise HTTPException(status_code=416, detail="Range not satisfiable")

            end = min(end, file_size - 1)
            content_length = end - start + 1

            def iterfile():
                with open(audio_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            headers = {
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(content_length),
                'Content-Type': 'audio/mpeg'
            }

            return StreamingResponse(
                iterfile(),
                status_code=206,
                headers=headers
            )

    # No range request, return full file
    return FileResponse(
        audio_path,
        media_type='audio/mpeg',
        headers={'Accept-Ranges': 'bytes'}
    )


@app.get("/api/books/{book_id}/cover")
async def get_book_cover(book_id: str):
    """
    Get cover image for a book.

    Args:
        book_id: Book identifier

    Returns:
        Cover image file (PNG)
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not book.get('cover_image'):
        raise HTTPException(status_code=404, detail="No cover image found for this book")

    cover_path = BOOKS_DIR / book['cover_image']
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover image file not found")

    return FileResponse(
        cover_path,
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=86400'}  # Cache for 24 hours
    )


@app.get("/api/books/{book_id}/text/{chapter_num}")
async def get_chapter_text(book_id: str, chapter_num: int, track_id: Optional[str] = None):
    """
    Get text content for a specific chapter (for text sync feature).

    Args:
        book_id: Book identifier
        chapter_num: Zero-based chapter index
        track_id: Optional text track ID to select a specific language

    Returns:
        Chapter text with paragraphs for karaoke-style sync
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book_dir = BOOKS_DIR / book_id

    # Resolve text track to a source file path
    explicit_source = None
    if track_id:
        text_tracks = book.get('text_tracks', [])
        track = next((t for t in text_tracks if t['track_id'] == track_id), None)
        if track:
            explicit_source = book_dir / track['file_path']
            if not explicit_source.exists():
                explicit_source = None

    # Load audio chapter timing data if available
    audio_chapter_timing = None
    if book.get('chapters') and chapter_num < len(book['chapters']):
        chapter_info = book['chapters'][chapter_num]

        # Calculate duration from chapter timestamps
        audio_start = chapter_info.get('timestamp', 0)
        audio_duration = None

        # Try to calculate duration from next chapter
        if chapter_num + 1 < len(book['chapters']):
            next_chapter = book['chapters'][chapter_num + 1]
            audio_duration = next_chapter.get('timestamp', 0) - audio_start
        else:
            # For single-chapter books or last chapter, get duration from audio file
            if book.get('variants') and len(book['variants']) > 0:
                # Get the first variant's first audio file
                variant = book['variants'][0]
                if variant.get('audio_files') and len(variant['audio_files']) > 0:
                    audio_file_path = BOOKS_DIR / variant['audio_files'][0]
                    if audio_file_path.exists():
                        total_duration = get_audio_duration(audio_file_path)
                        if total_duration:
                            # Duration is total - start time
                            audio_duration = total_duration - audio_start

        audio_chapter_timing = {
            'timestamp': audio_start,
            'duration': audio_duration
        }

    # Get total audio chapters count to help detect single-file books
    total_audio_chapters = len(book.get('chapters') or [])

    # Get chapter text data
    chapter_data = get_chapter_text_data(book_dir, chapter_num, audio_chapter_timing, total_audio_chapters, source_path=explicit_source)
    if not chapter_data:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter_num} not found or source text not available"
        )

    return chapter_data


@app.get("/api/books/{book_id}/text")
async def get_book_chapters(book_id: str):
    """
    Get list of all chapters for a book.

    Args:
        book_id: Book identifier

    Returns:
        List of chapters with titles and indices
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book_dir = BOOKS_DIR / book_id
    chapters = get_book_chapters_list(book_dir)

    return {
        'book_id': book_id,
        'title': book['title'],
        'chapters': chapters,
        'total_chapters': len(chapters)
    }


@app.get("/api/books/{book_id}/chunk-manifest")
async def get_chunk_manifest(book_id: str):
    """
    Get chunk manifest for audio-text synchronization.

    This endpoint returns the chunk-level metadata that maps audio timestamps
    to text positions, enabling precise synchronization between audio playback
    and text highlighting.

    Args:
        book_id: Book identifier

    Returns:
        Chunk manifest with duration and text position data for each audio chunk
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book_dir = BOOKS_DIR / book_id

    # Look for chunk manifest in audio directories (try multiple locations)
    potential_paths = [
        book_dir / "audio_kokoro" / f"{book_id}_chunk_manifest.json",
        book_dir / "audio_kokoro" / "book_chunk_manifest.json",
        book_dir / f"{book_id}_chunk_manifest.json",
    ]

    chunk_manifest_path = None
    for path in potential_paths:
        if path.exists():
            chunk_manifest_path = path
            break

    if not chunk_manifest_path:
        raise HTTPException(
            status_code=404,
            detail="Chunk manifest not found. This audiobook may need to be regenerated with the latest version."
        )

    try:
        with open(chunk_manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        # Also load text mapping for spoken_text (if available)
        text_mapping_path = chunk_manifest_path.parent / f"{book_id}_text_mapping.json"
        if not text_mapping_path.exists():
            text_mapping_path = chunk_manifest_path.parent / "book_text_mapping.json"

        spoken_text = None
        if text_mapping_path.exists():
            with open(text_mapping_path, 'r', encoding='utf-8') as f:
                text_mapping = json.load(f)
                spoken_text = text_mapping.get('spoken_text')

        # Add spoken_text to response if available
        if spoken_text:
            manifest['spoken_text'] = spoken_text

        return manifest
    except (IOError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load chunk manifest: {str(e)}"
        )


@app.get("/api/books/{book_id}/word-timings")
async def get_book_word_timings(book_id: str):
    """
    Get word-level timing data for karaoke sync (all chapters).

    Args:
        book_id: Book identifier

    Returns:
        Complete word timing data for the book
    """
    book_dir = BOOKS_DIR / book_id

    # Look for word timing JSON file
    word_timings_path = book_dir / f"{book_id}_word_timings.json"

    if not word_timings_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Word timing data not found. Generate with: python generate_word_timings.py"
        )

    try:
        with open(word_timings_path, 'r', encoding='utf-8') as f:
            word_timings = json.load(f)

        return {
            'book_id': book_id,
            'has_word_timings': True,
            'chapters': word_timings
        }
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading word timings: {str(e)}"
        )


@app.get("/api/books/{book_id}/word-timings/{chapter}")
async def get_chapter_word_timings(book_id: str, chapter: int):
    """
    Get word-level timing data for a specific chapter.

    Args:
        book_id: Book identifier
        chapter: Chapter number

    Returns:
        Word timing data for the chapter:
        {
            "chapter_number": 1,
            "file_index": 0,
            "word_count": 2543,
            "duration": 612.5,
            "words": [
                {"word": "Chapter", "start": 0.0, "end": 0.4, "text_pos": 0},
                {"word": "1", "start": 0.5, "end": 0.7, "text_pos": 8},
                ...
            ]
        }
    """
    book_dir = BOOKS_DIR / book_id

    # Look for word timing JSON file
    word_timings_path = book_dir / f"{book_id}_word_timings.json"

    if not word_timings_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Word timing data not found"
        )

    try:
        with open(word_timings_path, 'r', encoding='utf-8') as f:
            all_timings = json.load(f)

        # Look for chapter data
        chapter_key = f"chapter_{chapter}"
        if chapter_key not in all_timings:
            raise HTTPException(
                status_code=404,
                detail=f"Chapter {chapter} not found in word timing data"
            )

        return all_timings[chapter_key]

    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading word timings: {str(e)}"
        )


def _approximate_paragraph_timings(book_dir: Path, all_timings: dict) -> dict:
    """
    Approximate paragraph timings for books that were generated before
    paragraph tracking was added. Uses chapter duration and word counts
    from word timings to estimate paragraph boundaries.

    Args:
        book_dir: Path to book directory
        all_timings: Word timings data

    Returns:
        Dict mapping chapter keys to paragraph timing objects
    """
    from server.text_extractor import _load_manifest_paragraphs

    result = {}
    for chapter_key, chapter_data in all_timings.items():
        if not chapter_key.startswith('chapter_'):
            continue

        # Extract chapter index from key (e.g., "chapter_1" -> 0)
        try:
            chapter_idx = int(chapter_key.split('_')[1]) - 1
        except (IndexError, ValueError):
            continue

        # Get manifest paragraphs (may trigger lazy generation)
        manifest_paras = _load_manifest_paragraphs(book_dir, chapter_idx)
        if not manifest_paras:
            continue

        words = chapter_data.get('words', [])
        if not words:
            continue

        # Get chapter audio duration from word timings
        chapter_duration = max(w.get('end', 0) for w in words) if words else 0
        if chapter_duration <= 0:
            continue

        # Compute total word count and per-paragraph word counts
        total_words = len(words)
        para_word_counts = [p.get('word_count', 1) for p in manifest_paras]
        total_para_words = sum(para_word_counts)

        if total_para_words <= 0:
            continue

        # Approximate: distribute audio time proportionally by word count
        paragraphs = []
        current_time = 0.0
        current_word_idx = 0
        for mp in manifest_paras:
            wc = mp.get('word_count', 1)
            proportion = wc / total_para_words
            duration = proportion * chapter_duration
            word_count_for_para = round(proportion * total_words)

            paragraphs.append({
                'para_id': mp['para_id'],
                'audio_start': round(current_time, 3),
                'audio_end': round(current_time + duration, 3),
                'word_start_idx': current_word_idx,
                'word_end_idx': min(current_word_idx + word_count_for_para - 1, total_words - 1),
            })

            current_time += duration
            current_word_idx += word_count_for_para

        if paragraphs:
            # Ensure last paragraph extends to actual end
            paragraphs[-1]['audio_end'] = round(chapter_duration, 3)
            paragraphs[-1]['word_end_idx'] = total_words - 1
            result[chapter_key] = {'paragraphs': paragraphs}

    return result


@app.get("/api/books/{book_id}/paragraph-timings")
async def get_paragraph_timings(book_id: str):
    """
    Get paragraph-level audio timing data for all chapters.

    Returns paragraph timing summaries extracted from word timings data.
    Each paragraph has audio_start/audio_end timestamps for direct sync.
    This is the primary endpoint the frontend uses for reader text highlighting.

    Args:
        book_id: Book identifier

    Returns:
        Dict mapping chapter keys to lists of paragraph timing objects
    """
    book_dir = BOOKS_DIR / book_id

    # Look for word timing JSON file (paragraph timings are embedded in it)
    word_timings_path = book_dir / f"{book_id}_word_timings.json"

    if not word_timings_path.exists():
        # Try to find word timings in audio subdirectories
        for audio_dir in ['audio_kokoro', 'audio_xtts', 'audio_edge']:
            alt_path = book_dir / audio_dir
            if alt_path.exists():
                timing_files = list(alt_path.glob("*_word_timings.json"))
                if timing_files:
                    word_timings_path = timing_files[0]
                    break

    if not word_timings_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Word timing data not found. Paragraph timings require word timings."
        )

    try:
        with open(word_timings_path, 'r', encoding='utf-8') as f:
            all_timings = json.load(f)

        # Extract paragraph timings from each chapter
        paragraph_data = {}
        for chapter_key, chapter_data in all_timings.items():
            if not chapter_key.startswith('chapter_'):
                continue
            paras = chapter_data.get('paragraphs', [])
            if paras:
                paragraph_data[chapter_key] = {
                    'paragraphs': paras
                }

        # If no paragraph timings in word data, try to approximate from
        # chunk manifest + manifest paragraphs (lazy migration for old books)
        if not paragraph_data:
            paragraph_data = _approximate_paragraph_timings(book_dir, all_timings)

        return {
            'book_id': book_id,
            'has_paragraph_timings': bool(paragraph_data),
            'chapters': paragraph_data
        }

    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading paragraph timings: {str(e)}"
        )


# ============================================================================
# User Profile API
# ============================================================================

@app.get("/api/users")
async def list_users():
    """List all user profiles (public fields only)."""
    return {"users": get_all_users()}


@app.post("/api/users", status_code=201)
async def create_user_endpoint(request: Request):
    """Create a new user profile."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    avatar_emoji = data.get("avatar_emoji", "👤")
    user = create_user(name, avatar_emoji)
    return user


@app.get("/api/users/{user_id}")
async def get_user_endpoint(user_id: str):
    """Get user profile with full settings."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/api/users/{user_id}")
async def update_user_endpoint(user_id: str, request: Request):
    """Update user profile (name, avatar, settings)."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    user = update_user(user_id, data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.delete("/api/users/{user_id}")
async def delete_user_endpoint(user_id: str):
    """Delete user profile and their playback data."""
    db = load_playback_db()
    try:
        result = delete_user(user_id, db)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    save_playback_db(db)
    return {"status": "deleted", **result}


# ============================================================================
# Playback API
# ============================================================================

def _resolve_playback_key(
    user_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> str:
    """Resolve the playback DB key from headers. X-User-ID takes priority."""
    if user_id:
        return user_id
    if device_id:
        return device_id
    return None


@app.get("/api/playback/{book_id}/{variant_id}")
async def get_playback_position(
    book_id: str,
    variant_id: str,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """Get saved playback position. X-User-ID takes priority over X-Device-ID."""
    key = _resolve_playback_key(user_id, device_id)
    if not key:
        raise HTTPException(status_code=400, detail="X-User-ID or X-Device-ID header required")

    db = load_playback_db()
    user_data = db.get(key, {})
    playback_key = f"{book_id}:{variant_id}"
    playback = user_data.get(playback_key, {
        'position': 0.0,
        'speed': 1.0,
        'file_index': 0,
        'word_index': 0,
        'last_updated': None
    })

    print(f"[PLAYBACK GET] key={key[:16]}..., book={book_id}, pos={playback['position']:.1f}s")
    return playback


@app.get("/api/playback/all")
async def get_all_playback_positions(
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """Return all playback positions for a user/device (for library progress bars)."""
    key = _resolve_playback_key(user_id, device_id)
    if not key:
        return {"positions": {}}
    db = load_playback_db()
    return {"positions": db.get(key, {})}


@app.post("/api/playback/{book_id}/{variant_id}")
async def save_playback_position(
    book_id: str,
    variant_id: str,
    request: Request,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """Save playback position. X-User-ID takes priority over X-Device-ID."""
    key = _resolve_playback_key(user_id, device_id)
    if not key:
        raise HTTPException(status_code=400, detail="X-User-ID or X-Device-ID header required")

    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    position = data.get('position', 0.0)
    speed = data.get('speed', 1.0)
    file_index = data.get('file_index', 0)
    word_index = data.get('word_index', 0)

    print(f"[PLAYBACK SAVE] key={key[:16]}..., book={book_id}, pos={position:.1f}s, speed={speed}x")

    db = load_playback_db()
    if key not in db:
        db[key] = {}

    playback_key = f"{book_id}:{variant_id}"
    db[key][playback_key] = {
        'position': position,
        'speed': speed,
        'file_index': file_index,
        'word_index': word_index,
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

    save_playback_db(db)

    return {
        'status': 'saved',
        'book_id': book_id,
        'position': position,
        'speed': speed,
        'file_index': file_index,
        'word_index': word_index
    }


@app.delete("/api/books/{book_id}/variants/{variant_id}")
async def delete_variant(book_id: str, variant_id: str):
    """
    Delete an audiobook variant and all its associated files.

    Args:
        book_id: Book identifier
        variant_id: Variant identifier (playlist filename without .m3u)

    Returns:
        Success status with deletion details
    """
    print(f"[DELETE] Request to delete variant: {book_id}/{variant_id}")

    # Find the book
    book = get_book_by_id(book_id)
    if not book:
        print(f"[DELETE] Book not found: {book_id}")
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    # Find the variant
    variant = None
    for v in book['variants']:
        if v['variant_id'] == variant_id:
            variant = v
            break

    if not variant:
        print(f"[DELETE] Variant not found: {variant_id}")
        raise HTTPException(status_code=404, detail=f"Variant '{variant_id}' not found")

    # Track deleted files
    deleted_files = []
    errors = []

    try:
        # 1. Delete the M3U playlist file
        playlist_path = BOOKS_DIR / variant['playlist_path']
        if playlist_path.exists():
            try:
                playlist_path.unlink()
                deleted_files.append(str(variant['playlist_path']))
                print(f"[DELETE] Deleted playlist: {playlist_path}")
            except Exception as e:
                errors.append(f"Failed to delete playlist: {e}")
                print(f"[DELETE] Error deleting playlist: {e}")

        # 2. Delete all audio files referenced in the playlist
        for audio_file in variant['audio_files']:
            audio_path = BOOKS_DIR / audio_file
            if audio_path.exists():
                try:
                    audio_path.unlink()
                    deleted_files.append(audio_file)
                    print(f"[DELETE] Deleted audio file: {audio_path}")
                except Exception as e:
                    errors.append(f"Failed to delete {audio_file}: {e}")
                    print(f"[DELETE] Error deleting {audio_file}: {e}")

        # 3. Delete cover image if it exists in the variant directory
        # Infer variant directory from playlist path
        variant_dir = playlist_path.parent
        cover_paths = [
            variant_dir / "cover.png",
            variant_dir / f"{variant_id}_cover.png",
            variant_dir / f"{book_id}_cover.png"
        ]

        for cover_path in cover_paths:
            if cover_path.exists():
                # Only delete if this cover is unique to this variant
                # Don't delete if it's the main book cover
                if variant_dir.name != book_id:  # Not in root book directory
                    try:
                        cover_path.unlink()
                        deleted_files.append(str(cover_path.relative_to(BOOKS_DIR)))
                        print(f"[DELETE] Deleted cover: {cover_path}")
                    except Exception as e:
                        errors.append(f"Failed to delete cover: {e}")
                        print(f"[DELETE] Error deleting cover: {e}")

        # 4. Try to remove empty directories
        try:
            # Remove variant directory if empty
            if variant_dir.exists() and variant_dir != BOOKS_DIR / book_id:
                if not any(variant_dir.iterdir()):  # Directory is empty
                    variant_dir.rmdir()
                    print(f"[DELETE] Removed empty directory: {variant_dir}")
        except Exception as e:
            # Not critical if directory removal fails
            print(f"[DELETE] Could not remove directory {variant_dir}: {e}")

        print(f"[DELETE] Successfully deleted variant {variant_id}: {len(deleted_files)} files deleted")

        return {
            'status': 'success',
            'book_id': book_id,
            'variant_id': variant_id,
            'deleted_files': deleted_files,
            'deleted_count': len(deleted_files),
            'errors': errors if errors else None
        }

    except Exception as e:
        print(f"[DELETE] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete variant: {str(e)}"
        )


if AI_ASSISTANT_AVAILABLE:
    @app.post("/api/ask")
    async def ask_ai_assistant(request: Request):
        """
        AI assistant endpoint with tool-calling support.

        Request Body:
        {
            "book_id": "alice_adventures",
            "variant_id": "...",
            "current_chapter": 3,
            "question": "What happens to Alice in chapter 5?"
        }

        Response:
        {
            "answer": "In Chapter 5...",
            "tools_used": ["get_chapter(5)"],
            "iterations": 1,
            "current_chapter": 3,
            "chapters_consulted": [5],
            "error": null
        }
        """
        # Parse request body
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        book_id = data.get('book_id')
        variant_id = data.get('variant_id')
        current_chapter = data.get('current_chapter', 0)
        question = data.get('question')
        user_language = data.get('user_language', 'English')

        if not book_id or not question:
            raise HTTPException(status_code=400, detail="Missing required fields: book_id, question")

        # Get book metadata
        book = get_book_by_id(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Find source text
        book_dir = BOOKS_DIR / book_id
        source_text_path = find_source_text(book_dir)

        if not source_text_path:
            raise HTTPException(
                status_code=404,
                detail="Source text not available for this book. AI assistant requires the original markdown file."
            )

        # Load chapter metadata (if available)
        chapters_metadata = book.get('chapters', [])

        # Initialize BookTools with source text
        tools = BookTools(
            book_md_path=source_text_path,
            chapters_metadata=chapters_metadata
        )

        # Call LLM with tools
        try:
            result = ask_with_tools(
                question=question,
                current_chapter=current_chapter,
                tools=tools,
                model="llama3.2:3b",
                user_language=user_language
            )

            # Extract chapter numbers from tools_used
            chapters_consulted = []
            for tool_call in result.get('tools_used', []):
                # Extract chapter numbers from patterns like "get_chapter(5)" or "get_chapters(3, 5)"
                import re
                numbers = re.findall(r'\d+', tool_call)
                chapters_consulted.extend([int(n) for n in numbers])

            # Remove duplicates and sort
            chapters_consulted = sorted(set(chapters_consulted))

            return {
                'answer': result['answer'],
                'tools_used': result.get('tools_used', []),
                'iterations': result.get('iterations', 0),
                'current_chapter': current_chapter,
                'chapters_consulted': chapters_consulted,
                'model': result.get('model', 'llama3.2:3b'),
                'error': result.get('error')
            }

        except Exception as e:
            print(f"[AI ASSISTANT ERROR] {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"AI assistant error: {str(e)}"
            )


# ============================================================================
# Gutenberg API Endpoints
# ============================================================================

if GUTENBERG_AVAILABLE:
    # Initialize catalog
    gutenberg_catalog = GutenbergCatalog()

    @app.get("/api/gutenberg/catalog")
    async def get_gutenberg_catalog():
        """
        Get full Gutenberg catalog.

        Returns:
            Full catalog with all books (up to 500)
        """
        return {
            'books': gutenberg_catalog.catalog.get('books', []),
            'total': gutenberg_catalog.catalog.get('total', 0),
            'updated_at': gutenberg_catalog.catalog.get('updated_at')
        }

    @app.get("/api/gutenberg/search")
    async def search_gutenberg(
        q: str = "",
        language: str = "all",
        limit: Optional[int] = None
    ):
        """
        Search Gutenberg catalog with filters.

        Args:
            q: Search query (matches title and author)
            language: Language filter ('all', 'en', 'fr', 'de', 'es', 'ru')
            limit: Maximum results to return

        Returns:
            Search results
        """
        results = gutenberg_catalog.search(
            query=q,
            language=language,
            limit=limit
        )

        return {
            'books': results,
            'total': len(results),
            'query': q,
            'language': language
        }

    @app.post("/api/gutenberg/download")
    async def start_gutenberg_download(request: Request):
        """
        Start downloading a book from Gutenberg.

        Request Body:
        {
            "gutenberg_id": 11,
            "book_slug": "alice_adventures"
        }

        Returns:
            Job ID and initial status
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        gutenberg_id = data.get('gutenberg_id')
        book_slug = data.get('book_slug')
        language = data.get('language')  # ISO 639-1 code from catalog

        if not gutenberg_id or not book_slug:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: gutenberg_id, book_slug"
            )

        # Create download job (language passed through for metadata)
        job_id = create_download_job(gutenberg_id, book_slug)

        return {
            'job_id': job_id,
            'status': 'pending',
            'message': f'Download started for book #{gutenberg_id}'
        }

    @app.get("/api/gutenberg/downloads")
    async def list_gutenberg_downloads():
        """
        List all download jobs.

        Returns:
            List of all jobs with their status
        """
        jobs = get_all_gutenberg_jobs()  # Use correct function (not pipeline jobs!)
        print(f"[DEBUG] /api/gutenberg/downloads returning {len(jobs)} jobs: {[j.get('job_id', 'no-id') for j in jobs]}")
        return {
            'jobs': jobs,
            'total': len(jobs)
        }

    @app.get("/api/gutenberg/downloads/{job_id}")
    async def get_gutenberg_download_status(job_id: str):
        """
        Get status of a specific download job.

        Args:
            job_id: Job identifier

        Returns:
            Job status with progress
        """
        job = get_job_status(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job

    @app.get("/api/gutenberg/stats")
    async def get_gutenberg_stats():
        """
        Get catalog statistics.

        Returns:
            Statistics about the catalog
        """
        stats = gutenberg_catalog.get_stats()
        return stats


# ============================================================================
# Audiobook Pipeline API Endpoints
# ============================================================================

# Import language detector for pipeline routes
try:
    from server.language_detector import detect_language as detect_lang_func
    LANGUAGE_DETECTOR_AVAILABLE = True
except ImportError:
    LANGUAGE_DETECTOR_AVAILABLE = False


def _format_pipeline_job(job: Dict) -> Dict:
    """Convert unified queue job to pipeline API response format."""
    state = job.get('state', {}) or {}
    config = job.get('config', {}) or {}
    result = job.get('result', {}) or {}
    return {
        'job_id': job['job_id'],
        'book_id': config.get('book_id'),
        'source_file': config.get('source_file'),
        'config': config,
        'status': job['status'],
        'current_stage': state.get('stage', 'queued'),
        'progress': job.get('progress', 0),
        'stage_progress': state.get('details', {}),
        'created_at': job.get('created_at'),
        'updated_at': job.get('started_at'),
        'started_at': job.get('started_at'),
        'completed_at': job.get('completed_at'),
        'eta_seconds': job.get('eta_seconds'),
        'error': job.get('error'),
        'output_files': result.get('output_files', {})
    }


@app.post("/api/pipeline/generate")
async def start_audiobook_generation(request: Request):
    """Start audiobook generation pipeline via unified job queue."""
    if not UNIFIED_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Job queue not available")

    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    book_id = data.get('book_id')
    source_file = data.get('source_file')

    if not book_id or not source_file:
        raise HTTPException(status_code=400, detail="Missing required fields: book_id, source_file")

    source_path = BOOKS_DIR / book_id / source_file
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Source file not found: {source_file}")

    config = {
        'book_id': book_id,
        'source_file': source_file,
        'translate': data.get('translate', False),
        'source_language': data.get('source_language', 'Russian'),
        'target_language': data.get('target_language', 'Modern English'),
        'translation_model': data.get('translation_model', 'zongwei/gemma3-translator:4b'),
        'summarize': data.get('summarize'),
        'voice': data.get('voice', 'bf_emma'),
        'speed': data.get('speed', 1.0),
        'generate_cover': data.get('generate_cover', True)
    }

    queue = get_queue()
    job_id = queue.create_job(job_type=JobType.AUDIOBOOK, config=config)

    return {
        'job_id': job_id,
        'status': 'pending',
        'estimated_duration': '2-4 hours',
        'message': 'Audiobook generation started'
    }


@app.get("/api/pipeline/jobs/{job_id}")
async def get_pipeline_job_status(job_id: str):
    """Get status of a pipeline job from unified queue."""
    if not UNIFIED_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Job queue not available")

    queue = get_queue()
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _format_pipeline_job(job)


@app.get("/api/pipeline/jobs")
async def list_pipeline_jobs():
    """List all pipeline (audiobook) jobs from unified queue."""
    if not UNIFIED_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Job queue not available")

    queue = get_queue()
    all_jobs = queue.get_all_jobs(job_type=JobType.AUDIOBOOK)
    return {
        'jobs': [_format_pipeline_job(j) for j in all_jobs],
        'total': len(all_jobs)
    }


@app.delete("/api/pipeline/jobs/{job_id}")
async def cancel_pipeline_job(job_id: str):
    """Cancel a running pipeline job."""
    if not UNIFIED_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Job queue not available")

    queue = get_queue()
    success = queue.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")

    return {'status': 'cancelled', 'job_id': job_id}


@app.post("/api/pipeline/cleanup")
async def cleanup_pipeline_jobs(max_age_hours: int = 24):
    """Cleanup old pipeline jobs via unified queue."""
    if not UNIFIED_QUEUE_AVAILABLE:
        return {'cleaned': 0, 'message': 'Job queue not available'}

    queue = get_queue()
    cleaned = queue.db.cleanup_old_jobs(max_age_hours)
    return {
        'cleaned': cleaned,
        'max_age_hours': max_age_hours,
        'message': f'Cleaned up {cleaned} old jobs'
    }


if LANGUAGE_DETECTOR_AVAILABLE:
    @app.get("/api/pipeline/detect-language/{book_id}/{file_name}")
    async def detect_book_language(book_id: str, file_name: str, preferred_language: str = "en"):
        """Auto-detect language of a book file."""
        book_dir = BOOKS_DIR / book_id
        file_path = book_dir / file_name

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        result = detect_lang_func(file_path)
        detected_code = result.get('code', 'en')
        result['needs_translation'] = detected_code != preferred_language
        return result


@app.get("/api/pipeline/source-files/{book_id}")
async def list_source_files(book_id: str):
    """List available source markdown files for a book."""
    book_dir = BOOKS_DIR / book_id

    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Book not found")

    source_files = []
    for md_file in book_dir.glob("*.md"):
        if any(x in md_file.stem.lower() for x in ['_modern_', '_translated', '_summarized', '_cleaned_cleaned', '_original_original']):
            continue
        stat = md_file.stat()
        source_files.append({
            'filename': md_file.name,
            'size_bytes': stat.st_size,
            'size_kb': round(stat.st_size / 1024, 1),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    source_files.sort(key=lambda x: x['modified_at'], reverse=True)
    return {'book_id': book_id, 'files': source_files, 'total': len(source_files)}


# ============================================================================
# Unified Job Queue API Endpoints
# ============================================================================

if UNIFIED_QUEUE_AVAILABLE:
    @app.get("/api/jobs")
    async def list_all_jobs(
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        List all jobs with optional filters.

        Query Parameters:
            job_type: Filter by type ('download', 'translate', 'audiobook')
            status: Filter by status ('pending', 'running', 'completed', 'failed', 'cancelled')
            limit: Maximum results to return

        Returns:
            List of jobs
        """
        queue = get_queue()
        jobs = queue.get_all_jobs(
            job_type=JobType(job_type) if job_type else None,
            status=JobStatus(status) if status else None,
            limit=limit
        )

        return {
            'jobs': jobs,
            'total': len(jobs)
        }

    @app.get("/api/jobs/stats")
    async def get_job_stats():
        """
        Get job queue statistics.

        Returns:
            Statistics about jobs and queue
        """
        queue = get_queue()
        return queue.get_stats()

    @app.post("/api/jobs/cleanup")
    async def cleanup_jobs(max_age_hours: int = 24):
        """
        Cleanup old completed/failed jobs.

        Query Parameters:
            max_age_hours: Maximum age in hours (default: 24)

        Returns:
            Number of jobs cleaned
        """
        queue = get_queue()
        cleaned = queue.cleanup_old_jobs(max_age_hours)

        return {
            'cleaned': cleaned,
            'max_age_hours': max_age_hours
        }

    @app.get("/api/jobs/{job_id}")
    async def get_job_details(job_id: str):
        """
        Get detailed job information.

        Args:
            job_id: Job identifier

        Returns:
            Job details with progress and ETA
        """
        queue = get_queue()
        job = queue.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job

    @app.post("/api/jobs/download")
    async def create_unified_download_job(request: Request):
        """
        Create a Gutenberg download job.

        Request Body:
        {
            "gutenberg_id": 11,
            "book_slug": "alice_adventures"
        }

        Returns:
            Job ID and status
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        gutenberg_id = data.get('gutenberg_id')
        book_slug = data.get('book_slug')
        language = data.get('language')  # ISO 639-1 code from catalog

        if not gutenberg_id or not book_slug:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: gutenberg_id, book_slug"
            )

        queue = get_queue()

        # Prevent duplicate jobs for the same book
        existing = queue.db.has_active_job_for_book(book_slug)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'duplicate_job',
                    'message': f'A {existing["job_type"]} job is already {existing["status"]} for this book',
                    'existing_job_id': existing['job_id']
                }
            )

        job_id = queue.create_job(
            job_type=JobType.DOWNLOAD,
            config={
                'gutenberg_id': gutenberg_id,
                'book_slug': book_slug,
                'language': language
            }
        )

        return {
            'job_id': job_id,
            'status': 'pending',
            'message': f'Download job created for book #{gutenberg_id}'
        }

    @app.post("/api/jobs/translate")
    async def create_translate_job(request: Request):
        """
        Create a standalone translation job.

        Request Body:
        {
            "book_id": "crime_punishment",
            "source_file": "book.md",
            "source_language": "Russian",
            "target_language": "Modern English",
            "translation_model": "zongwei/gemma3-translator:4b"
        }

        Returns:
            Job ID and status
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        book_id = data.get('book_id')
        source_file = data.get('source_file')

        if not book_id or not source_file:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: book_id, source_file"
            )

        queue = get_queue()

        # Prevent duplicate jobs for the same book
        existing = queue.db.has_active_job_for_book(book_id)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'duplicate_job',
                    'message': f'A {existing["job_type"]} job is already {existing["status"]} for this book',
                    'existing_job_id': existing['job_id']
                }
            )

        job_id = queue.create_job(
            job_type=JobType.TRANSLATE,
            config={
                'book_id': book_id,
                'source_file': source_file,
                'source_language': data.get('source_language', 'Russian'),
                'target_language': data.get('target_language', 'Modern English'),
                'translation_model': data.get('translation_model', 'zongwei/gemma3-translator:4b')
            }
        )

        return {
            'job_id': job_id,
            'status': 'pending',
            'message': f'Translation job created for {book_id}/{source_file}'
        }

    @app.post("/api/jobs/audiobook")
    async def create_audiobook_job(request: Request):
        """
        Create a full audiobook pipeline job.

        Request Body:
        {
            "book_id": "crime_punishment",
            "source_file": "translated.md",
            "translate": false,
            "summarize": 50,  // Optional: 10-90
            "voice": "bf_emma",
            "speed": 1.0,
            "generate_cover": true
        }

        Returns:
            Job ID and status
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        book_id = data.get('book_id')
        source_file = data.get('source_file')

        if not book_id or not source_file:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: book_id, source_file"
            )

        queue = get_queue()

        # Prevent duplicate jobs for the same book
        existing = queue.db.has_active_job_for_book(book_id)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'duplicate_job',
                    'message': f'A {existing["job_type"]} job is already {existing["status"]} for this book',
                    'existing_job_id': existing['job_id']
                }
            )

        job_id = queue.create_job(
            job_type=JobType.AUDIOBOOK,
            config={
                'book_id': book_id,
                'source_file': source_file,
                'translate': data.get('translate', False),
                'source_language': data.get('source_language', 'Russian'),
                'target_language': data.get('target_language', 'Modern English'),
                'translation_model': data.get('translation_model', 'zongwei/gemma3-translator:4b'),
                'summarize': data.get('summarize'),
                'voice': data.get('voice', 'bf_emma'),
                'speed': data.get('speed', 1.0),
                'generate_cover': data.get('generate_cover', True)
            }
        )

        return {
            'job_id': job_id,
            'status': 'pending',
            'estimated_duration': '2-4 hours',
            'message': f'Audiobook pipeline job created for {book_id}'
        }

    @app.post("/api/jobs/cover")
    async def create_cover_job(request: Request):
        """
        Create a cover art generation job.

        Request Body:
        {
            "book_id": "the_strange_case_of_dr_jekyll_and_mr_hyde"
        }

        Returns:
            Job ID and status
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        book_id = data.get('book_id')

        if not book_id:
            raise HTTPException(
                status_code=400,
                detail="Missing required field: book_id"
            )

        # Verify book exists
        book_dir = BOOKS_DIR / book_id
        if not book_dir.exists():
            raise HTTPException(status_code=404, detail=f"Book not found: {book_id}")

        queue = get_queue()

        # Prevent duplicate jobs for the same book
        existing = queue.db.has_active_job_for_book(book_id)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'duplicate_job',
                    'message': f'A {existing["job_type"]} job is already {existing["status"]} for this book',
                    'existing_job_id': existing['job_id']
                }
            )

        job_id = queue.create_job(
            job_type=JobType.COVER,
            config={
                'book_id': book_id
            }
        )

        return {
            'job_id': job_id,
            'status': 'pending',
            'message': f'Cover generation job created for {book_id}'
        }

    @app.delete("/api/jobs/{job_id}")
    async def cancel_job_endpoint(job_id: str):
        """
        Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            Success status
        """
        queue = get_queue()
        success = queue.cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or cannot be cancelled"
            )

        return {
            'status': 'cancelled',
            'job_id': job_id
        }

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'ok',
        'books_dir': str(BOOKS_DIR),
        'books_count': len(discover_books()),
        'gutenberg_available': GUTENBERG_AVAILABLE,
        'unified_queue_available': UNIFIED_QUEUE_AVAILABLE,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the audiobook server."""
    parser = argparse.ArgumentParser(description="Audiobook Server")
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0 for LAN access)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to bind to (default: 8000)'
    )
    parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload on code changes (development)'
    )

    args = parser.parse_args()

    # Create necessary directories
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize unified job queue
    global UNIFIED_QUEUE_AVAILABLE  # Need global declaration to modify module-level variable
    if UNIFIED_QUEUE_AVAILABLE:
        try:
            print("\n📋 Initializing unified job queue...")
            queue = init_queue(JOB_DB_PATH, max_workers=4)

            # Register job handlers
            queue.register_handler(JobType.DOWNLOAD, download_handler)
            queue.register_handler(JobType.TRANSLATE, translate_handler)
            queue.register_handler(JobType.AUDIOBOOK, pipeline_handler)
            queue.register_handler(JobType.COVER, cover_handler)

            print(f"✓ Job queue initialized (database: {JOB_DB_PATH})")

            # Show queue stats
            stats = queue.get_stats()
            print(f"✓ Queue stats: {stats['total']} total jobs")
            if stats.get('by_status'):
                for status, count in stats['by_status'].items():
                    print(f"  - {status}: {count}")
        except Exception as e:
            print(f"❌ Failed to initialize job queue: {e}")
            UNIFIED_QUEUE_AVAILABLE = False

    # Initialize user profiles
    playback_db = load_playback_db()
    if ensure_users_initialized(playback_db):
        save_playback_db(playback_db)
        print("✓ User profiles initialized (Guest profile created)")
    else:
        print(f"✓ User profiles: {len(get_all_users())} profiles")

    # Print startup info
    print("\n" + "=" * 60)
    print("Audiobook Server Starting...")
    print("=" * 60)
    print(f"Books directory: {BOOKS_DIR}")
    print(f"Found {len(discover_books())} books")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"API Docs: http://localhost:{args.port}/docs")
    print(f"Jobs UI: http://localhost:{args.port}/static/jobs.html")

    # Check Ollama availability for AI assistant
    if AI_ASSISTANT_AVAILABLE:
        try:
            ollama_status = check_ollama_available()
            if ollama_status['available']:
                models = ollama_status.get('models', [])
                has_llama32 = any('llama3.2' in m for m in models)
                print(f"✓ AI Assistant: Ollama running ({len(models)} models)")
                if not has_llama32:
                    print("  ⚠️  WARNING: llama3.2:3b not found. Run: ollama pull llama3.2:3b")
            else:
                print("✗ AI Assistant: Ollama not available")
                print("  Install: https://ollama.com/download")
                print("  Then run: ollama serve && ollama pull llama3.2:3b")
        except Exception as e:
            print(f"✗ AI Assistant: Ollama check failed ({str(e)})")
    else:
        print("✗ AI Assistant: Not installed (optional feature)")

    print("=" * 60)

    # Run book health check (auto-recovers what it can)
    from server.book_health import run_health_check, start_periodic_health_check
    run_health_check()
    start_periodic_health_check()

    print("Press CTRL+C to stop\n")

    # Run server
    uvicorn.run(
        "audiobook_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
