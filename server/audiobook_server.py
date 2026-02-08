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
import sys
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
sys.path.insert(0, str(Path(__file__).parent.parent))
from book_catalog import get_book_info
from server.text_extractor import find_source_text, get_chapter_text_data, get_book_chapters_list

# Import Gutenberg modules
try:
    from server.gutenberg_catalog import GutenbergCatalog
    from server.gutenberg_downloader import create_download_job, get_job_status, get_all_jobs
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


# Constants
BOOKS_DIR = Path(__file__).parent.parent / "books"
PLAYBACK_DB = Path(__file__).parent / "playback_db.json"
STATIC_DIR = Path(__file__).parent / "static"

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
    """Save playback database to JSON file."""
    with open(PLAYBACK_DB, 'w') as f:
        json.dump(db, f, indent=2)


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

        # Extract metadata from translated files
        translated_files = list(book_dir.glob("*_modern_*.md")) + list(book_dir.glob("*translated*.md"))
        if translated_files and not language:
            filename = translated_files[0].stem
            if 'spanish' in filename.lower():
                language = 'Spanish'
            elif 'english' in filename.lower():
                language = 'English'
            elif 'french' in filename.lower():
                language = 'French'
            elif 'german' in filename.lower():
                language = 'German'
            elif 'russian' in filename.lower():
                language = 'Russian'
            elif 'italian' in filename.lower():
                language = 'Italian'

        # Load chapter data and metadata
        # NEW STANDARD: Check metadata.json first
        chapters = None
        has_chapters = False
        metadata_file = book_dir / "metadata.json"

        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if 'chapters' in metadata:
                        chapters = metadata['chapters']
                        has_chapters = True
                    if 'title' in metadata:
                        title = metadata['title']
                    if 'author' in metadata and not author:
                        author = metadata['author']
            except (json.JSONDecodeError, IOError):
                pass

        # LEGACY: Fall back to old chapter_data.json files
        if not has_chapters:
            chapter_json = list(book_dir.glob("*_chapter_data.json"))
            if chapter_json:
                try:
                    with open(chapter_json[0], 'r') as f:
                        chapter_data = json.load(f)
                        chapters = chapter_data.get('chapters', [])
                        if 'title' in chapter_data:
                            title = chapter_data['title']
                        if 'author' in chapter_data and not author:
                            author = chapter_data['author']
                except (json.JSONDecodeError, IOError):
                    pass

        # Find cover image (check multiple locations)
        cover_path = None
        cover_locations = [
            book_dir / "cover.png",                           # Root level
            book_dir / "audio" / "kokoro" / "cover.png",      # New structure
            book_dir / "audio" / "original" / "cover.png",    # New structure
            book_dir / "audio_kokoro" / "cover.png",          # Legacy
            book_dir / "audio_xtts" / "cover.png",            # Legacy
            book_dir / "audio_xtts" / f"{book_id}_cover.png"  # Legacy
        ]
        for loc in cover_locations:
            if loc.exists():
                cover_path = str(loc.relative_to(BOOKS_DIR))
                break

        # Check for source text availability
        source_text_path = find_source_text(book_dir)
        has_source_text = source_text_path is not None

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
            'variants': []
        }

    # STAGE 2: Find all M3U playlists and add as variants
    for playlist_path in BOOKS_DIR.rglob("*.m3u"):
        # Skip backup directories (migration artifacts)
        path_str = str(playlist_path)
        if '.old_structure_backup' in path_str or '.old_duplicates' in path_str:
            continue

        # Skip timestamped backup playlists (e.g., *_20260208_115152.m3u)
        # These are created for history but shouldn't appear as separate variants
        if re.search(r'_\d{8}_\d{6}\.m3u$', playlist_path.name):
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
            'timestamp': variant_info['timestamp']
        }

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
    print(f"[API /api/books] Returning {len(books)} books")
    for book in books:
        print(f"  - {book['title']} ({book['book_id']}): {book['variant_count']} variants")
    return {
        "books": books,
        "total": len(books)
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
async def get_chapter_text(book_id: str, chapter_num: int):
    """
    Get text content for a specific chapter (for text sync feature).

    Args:
        book_id: Book identifier
        chapter_num: Zero-based chapter index

    Returns:
        Chapter text with paragraphs for karaoke-style sync
    """
    book = get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book_dir = BOOKS_DIR / book_id

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
    total_audio_chapters = len(book.get('chapters', []))

    # Get chapter text data
    chapter_data = get_chapter_text_data(book_dir, chapter_num, audio_chapter_timing, total_audio_chapters)
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


@app.get("/api/playback/{book_id}/{variant_id}")
async def get_playback_position(
    book_id: str,
    variant_id: str,
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """
    Get saved playback position for a book variant.

    Args:
        book_id: Book identifier
        variant_id: Variant identifier
        device_id: Device identifier (from header)

    Returns:
        Playback state (position, speed, timestamp)
    """
    if not device_id:
        print(f"[PLAYBACK] Missing device ID for {book_id}/{variant_id}")
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    db = load_playback_db()
    device_data = db.get(device_id, {})
    playback_key = f"{book_id}:{variant_id}"
    playback = device_data.get(playback_key, {
        'position': 0.0,
        'speed': 1.0,
        'file_index': 0,
        'word_index': 0,
        'last_updated': None
    })

    print(f"[PLAYBACK GET] device={device_id[:12]}..., book={book_id}, variant={variant_id[:40]}..., pos={playback['position']:.1f}s, file={playback['file_index']}, word={playback.get('word_index', 0)}")

    return playback


@app.post("/api/playback/{book_id}/{variant_id}")
async def save_playback_position(
    book_id: str,
    variant_id: str,
    request: Request,
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """
    Save playback position for a book variant.

    Args:
        book_id: Book identifier
        variant_id: Variant identifier
        device_id: Device identifier (from header)
        Body: JSON with position, speed, file_index

    Returns:
        Success status
    """
    if not device_id:
        print(f"[PLAYBACK] Missing device ID for SAVE {book_id}/{variant_id}")
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    # Parse request body
    try:
        data = await request.json()
    except json.JSONDecodeError:
        print(f"[PLAYBACK] Invalid JSON in request body")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    position = data.get('position', 0.0)
    speed = data.get('speed', 1.0)
    file_index = data.get('file_index', 0)
    word_index = data.get('word_index', 0)

    print(f"[PLAYBACK SAVE] device={device_id[:12]}..., book={book_id}, variant={variant_id[:40]}..., pos={position:.1f}s, speed={speed}x, file={file_index}, word={word_index}")

    # Load database
    db = load_playback_db()

    # Create device entry if needed
    if device_id not in db:
        db[device_id] = {}

    # Save playback state (using combined key for book:variant)
    playback_key = f"{book_id}:{variant_id}"
    db[device_id][playback_key] = {
        'position': position,
        'speed': speed,
        'file_index': file_index,
        'word_index': word_index,
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

    # Save to disk
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
                model="llama3.2:3b"
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

        if not gutenberg_id or not book_slug:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: gutenberg_id, book_slug"
            )

        # Create download job
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
        jobs = get_all_jobs()
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

# Import pipeline module
try:
    from server.audiobook_pipeline import create_job, get_job, get_all_jobs, cancel_job
    from server.language_detector import detect_language as detect_lang_func
    PIPELINE_AVAILABLE = True
except ImportError as e:
    PIPELINE_AVAILABLE = False
    print(f"⚠️  Audiobook pipeline not available: {e}")


if PIPELINE_AVAILABLE:
    @app.post("/api/pipeline/generate")
    async def start_audiobook_generation(request: Request):
        """
        Start audiobook generation pipeline.

        Request Body:
        {
            "book_id": "crime_punishment",
            "source_file": "Преступление_и_наказание.md",
            "translate": true,
            "source_language": "Russian",
            "target_language": "Modern English",
            "translation_model": "o3-mini-high",
            "summarize": 50,  // Optional: 10-90 or null
            "voice": "bf_emma",
            "speed": 1.0,
            "generate_cover": true
        }

        Returns:
            {
                "job_id": "...",
                "status": "pending",
                "estimated_duration": "2-4 hours"
            }
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Validate required fields
        book_id = data.get('book_id')
        source_file = data.get('source_file')

        if not book_id or not source_file:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: book_id, source_file"
            )

        # Validate book exists
        book_dir = BOOKS_DIR / book_id
        source_path = book_dir / source_file

        if not source_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Source file not found: {source_file}"
            )

        # Build config
        config = {
            'translate': data.get('translate', False),
            'source_language': data.get('source_language', 'Russian'),
            'target_language': data.get('target_language', 'Modern English'),
            'translation_model': data.get('translation_model', 'o3-mini-high'),
            'summarize': data.get('summarize'),  # Can be None
            'voice': data.get('voice', 'bf_emma'),
            'speed': data.get('speed', 1.0),
            'generate_cover': data.get('generate_cover', True)
        }

        # Create job
        job_id = create_job(book_id, source_file, config)

        return {
            'job_id': job_id,
            'status': 'pending',
            'estimated_duration': '2-4 hours',
            'message': 'Audiobook generation started'
        }


    @app.get("/api/pipeline/jobs/{job_id}")
    async def get_pipeline_job_status(job_id: str):
        """
        Get status of a pipeline job.

        Args:
            job_id: Job identifier

        Returns:
            Job status with progress
        """
        job = get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job


    @app.get("/api/pipeline/jobs")
    async def list_pipeline_jobs():
        """
        List all pipeline jobs.

        Returns:
            List of jobs with their status
        """
        jobs = get_all_jobs()
        return {
            'jobs': jobs,
            'total': len(jobs)
        }


    @app.delete("/api/pipeline/jobs/{job_id}")
    async def cancel_pipeline_job(job_id: str):
        """
        Cancel a running pipeline job.

        Args:
            job_id: Job identifier

        Returns:
            Success status
        """
        success = cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or cannot be cancelled"
            )

        return {
            'status': 'cancelled',
            'job_id': job_id
        }


    @app.get("/api/pipeline/detect-language/{book_id}/{file_name}")
    async def detect_book_language(book_id: str, file_name: str):
        """
        Auto-detect language of a book file.

        Args:
            book_id: Book directory name
            file_name: Filename to analyze

        Returns:
            Language detection results
        """
        book_dir = BOOKS_DIR / book_id
        file_path = book_dir / file_name

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        result = detect_lang_func(file_path)

        return result


    @app.get("/api/pipeline/source-files/{book_id}")
    async def list_source_files(book_id: str):
        """
        List available source markdown files for a book.

        Args:
            book_id: Book directory name

        Returns:
            List of available source files
        """
        book_dir = BOOKS_DIR / book_id

        if not book_dir.exists():
            raise HTTPException(status_code=404, detail="Book not found")

        # Find all markdown files (exclude generated files)
        source_files = []
        for md_file in book_dir.glob("*.md"):
            # Skip generated files
            if any(x in md_file.stem.lower() for x in ['_modern_', '_translated', '_summarized', '_cleaned_cleaned', '_original_original']):
                continue

            # Get file info
            stat = md_file.stat()
            source_files.append({
                'filename': md_file.name,
                'size_bytes': stat.st_size,
                'size_kb': round(stat.st_size / 1024, 1),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        # Sort by modification date (newest first)
        source_files.sort(key=lambda x: x['modified_at'], reverse=True)

        return {
            'book_id': book_id,
            'files': source_files,
            'total': len(source_files)
        }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'ok',
        'books_dir': str(BOOKS_DIR),
        'books_count': len(discover_books()),
        'gutenberg_available': GUTENBERG_AVAILABLE,
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

    # Print startup info
    print("=" * 60)
    print("Audiobook Server Starting...")
    print("=" * 60)
    print(f"Books directory: {BOOKS_DIR}")
    print(f"Found {len(discover_books())} books")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"API Docs: http://localhost:{args.port}/docs")

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
    print("\nPress CTRL+C to stop\n")

    # Run server
    uvicorn.run(
        "audiobook_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
