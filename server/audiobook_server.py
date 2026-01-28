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
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import argparse

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import book catalog
sys.path.insert(0, str(Path(__file__).parent.parent))
from book_catalog import get_book_info


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
    Auto-discover books by finding M3U playlists.

    Each playlist represents a version/variant of a book:
    - Full translation
    - 50% summary
    - Deduplicated
    - Combined vs chunked files

    Returns list of books with their variants.
    """
    books_by_id = {}

    if not BOOKS_DIR.exists():
        return []

    # Find all M3U playlists
    for playlist_path in BOOKS_DIR.rglob("*.m3u"):
        # Get book directory (top-level folder in books/)
        try:
            rel_path = playlist_path.relative_to(BOOKS_DIR)
            book_id = rel_path.parts[0]
        except (ValueError, IndexError):
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

        # Create or update book entry
        if book_id not in books_by_id:
            book_dir = BOOKS_DIR / book_id
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

            # Extract metadata from translated files
            translated_files = list(book_dir.glob("*_modern_*.md")) + list(book_dir.glob("*translated*.md"))
            if translated_files:
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

            # Try to extract from audio filenames as well
            if not language and audio_files:
                first_audio = audio_files[0].lower()
                if 'spanish' in first_audio:
                    language = 'Spanish'
                elif 'english' in first_audio:
                    language = 'English'
                elif 'russian' in first_audio:
                    language = 'Russian'

            # Load chapter data (can override catalog info)
            chapters = None
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
                book_dir / "cover.png",
                book_dir / "audio_xtts" / "cover.png",
                book_dir / "audio_xtts" / f"{book_id}_cover.png"
            ]
            for loc in cover_locations:
                if loc.exists():
                    cover_path = str(loc.relative_to(BOOKS_DIR))
                    break

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
                'variants': []
            }

        # Add variant to book
        books_by_id[book_id]['variants'].append(variant)

    # Sort variants by creation date (newest first) and convert to list
    books = []
    for book_data in books_by_id.values():
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
        'last_updated': None
    })

    print(f"[PLAYBACK GET] device={device_id[:12]}..., book={book_id}, variant={variant_id[:40]}..., pos={playback['position']:.1f}s, file={playback['file_index']}")

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

    print(f"[PLAYBACK SAVE] device={device_id[:12]}..., book={book_id}, variant={variant_id[:40]}..., pos={position:.1f}s, speed={speed}x, file={file_index}")

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
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

    # Save to disk
    save_playback_db(db)

    return {
        'status': 'saved',
        'book_id': book_id,
        'position': position,
        'speed': speed,
        'file_index': file_index
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'ok',
        'books_dir': str(BOOKS_DIR),
        'books_count': len(discover_books()),
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
