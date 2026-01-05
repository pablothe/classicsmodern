#!/usr/bin/env python3
"""
Audiobook Player for Classic Literature
Serves a web interface to play audiobooks organized by book and chapter.
"""

import os
import json
import re
from pathlib import Path
from flask import Flask, render_template, jsonify, send_from_directory, request
from datetime import datetime

app = Flask(__name__)

# Directory structure
BOOKS_DIR = Path("books")
PROGRESS_FILE = Path(".audiobook_progress.json")


class AudiobookLibrary:
    """Scans and organizes audiobook files by book and chapter"""

    def __init__(self, books_dir: Path):
        self.books_dir = books_dir

    def scan_library(self):
        """
        Scan books directory for audiobooks organized by chapters.

        Returns:
            dict: {
                "book_name": {
                    "title": "Book Title",
                    "chapters": [
                        {
                            "name": "Chapter 1",
                            "tracks": ["track1.mp3", "track2.mp3"],
                            "playlist": "path/to/playlist.m3u"
                        }
                    ]
                }
            }
        """
        library = {}

        for book_path in self.books_dir.iterdir():
            if not book_path.is_dir():
                continue

            book_name = book_path.name
            audiobooks = self._scan_book_audiobooks(book_path)

            if audiobooks:
                library[book_name] = {
                    "title": self._format_title(book_name),
                    "chapters": audiobooks
                }

        return library

    def _scan_book_audiobooks(self, book_path: Path):
        """Scan a single book directory for audiobook files"""
        chapters = []

        # Look for audio in chunks/translated/deduplicated/audio_xtts/
        audio_xtts_dir = book_path / "chunks" / "translated" / "deduplicated" / "audio_xtts"
        if audio_xtts_dir.exists():
            chapters.extend(self._scan_xtts_audio(audio_xtts_dir, book_path))

        # Look for legacy OpenAI audio in chunks/translated/deduplicated/audio/
        audio_legacy_dir = book_path / "chunks" / "translated" / "deduplicated" / "audio"
        if audio_legacy_dir.exists():
            chapters.extend(self._scan_legacy_audio(audio_legacy_dir, book_path))

        # Look for audio in book root directory
        chapters.extend(self._scan_root_audio(book_path))

        # Sort chapters by name
        chapters.sort(key=lambda x: x['name'])

        return chapters

    def _scan_xtts_audio(self, audio_dir: Path, book_path: Path):
        """Scan XTTS audio directory for chapters"""
        chapters = []

        # First, check for stitched chapters (single files)
        stitched_dir = audio_dir / "stitched"
        if stitched_dir.exists():
            for mp3 in sorted(stitched_dir.glob("chapter_*.mp3")):
                # Extract chapter number from filename like "chapter_001.mp3"
                match = re.match(r'chapter_(\d+)\.mp3', mp3.name)
                if match:
                    chapter_num = match.group(1)
                    chapters.append({
                        "name": f"Chapter {int(chapter_num)}",
                        "tracks": [str(mp3.relative_to(book_path))],
                        "playlist": None,
                        "type": "xtts-stitched"
                    })

        # If no stitched chapters found, fall back to individual chunks
        if not chapters:
            # Group MP3 files by chunk prefix
            mp3_files = sorted(audio_dir.glob("*.mp3"))
            chunk_groups = {}

            for mp3 in mp3_files:
                # Extract chunk name from filename like "chunk_001_modern_english_4b_DEDUPED_chunk001.mp3"
                match = re.match(r'(chunk_\d+)_.*?_(chunk\d+)\.mp3', mp3.name)
                if match:
                    chunk_prefix = match.group(1)
                    if chunk_prefix not in chunk_groups:
                        chunk_groups[chunk_prefix] = []
                    chunk_groups[chunk_prefix].append(mp3)

            # Create chapter entry for each chunk group
            for chunk_name, mp3_list in chunk_groups.items():
                # Find associated playlist
                playlist = None
                for m3u in audio_dir.glob(f"{chunk_name}*.m3u"):
                    playlist = m3u.relative_to(book_path)
                    break

                chapters.append({
                    "name": self._format_chapter_name(chunk_name),
                    "tracks": [str(mp3.relative_to(book_path)) for mp3 in sorted(mp3_list)],
                    "playlist": str(playlist) if playlist else None,
                    "type": "xtts"
                })

        return chapters

    def _scan_legacy_audio(self, audio_dir: Path, book_path: Path):
        """Scan legacy OpenAI audio directory for chapters"""
        chapters = []

        # Group by playlist files
        for m3u in audio_dir.glob("*.m3u"):
            playlist_path = m3u.relative_to(book_path)

            # Parse playlist to get tracks
            tracks = self._parse_m3u(m3u, book_path)

            if tracks:
                chapters.append({
                    "name": self._format_chapter_name(m3u.stem),
                    "tracks": tracks,
                    "playlist": str(playlist_path),
                    "type": "openai"
                })

        return chapters

    def _scan_root_audio(self, book_path: Path):
        """Scan book root for standalone audio files"""
        chapters = []

        # Look for playlists in root
        for m3u in book_path.glob("*.m3u"):
            tracks = self._parse_m3u(m3u, book_path)

            if tracks:
                chapters.append({
                    "name": self._format_chapter_name(m3u.stem),
                    "tracks": tracks,
                    "playlist": str(m3u.relative_to(book_path)),
                    "type": "standalone"
                })

        return chapters

    def _parse_m3u(self, m3u_path: Path, book_path: Path):
        """Parse M3U playlist and return list of track paths relative to book"""
        tracks = []
        m3u_dir = m3u_path.parent

        try:
            with open(m3u_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Resolve track path (M3U paths are relative to playlist location)
                        track_path = m3u_dir / line
                        if track_path.exists():
                            tracks.append(str(track_path.relative_to(book_path)))
        except Exception as e:
            print(f"Error parsing playlist {m3u_path}: {e}")

        return tracks

    def _format_title(self, book_name: str) -> str:
        """Format book directory name into readable title"""
        return book_name.replace('_', ' ').title()

    def _format_chapter_name(self, chunk_name: str) -> str:
        """Format chunk/chapter name into readable text"""
        # Extract chunk number if present
        match = re.search(r'chunk[_\s]?(\d+)', chunk_name, re.IGNORECASE)
        if match:
            return f"Chapter {int(match.group(1))}"

        # Otherwise clean up the name
        name = chunk_name.replace('_', ' ')
        name = re.sub(r'audiobook.*', '', name, flags=re.IGNORECASE)
        return name.strip().title()


class ProgressTracker:
    """Track listening progress across books and chapters"""

    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self.progress = self._load_progress()

    def _load_progress(self):
        """Load progress from JSON file"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading progress: {e}")
        return {}

    def _save_progress(self):
        """Save progress to JSON file"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
        except Exception as e:
            print(f"Error saving progress: {e}")

    def get_progress(self, book_name: str, chapter_name: str):
        """Get progress for a specific book chapter"""
        key = f"{book_name}:{chapter_name}"
        return self.progress.get(key, {"position": 0, "track_index": 0})

    def set_progress(self, book_name: str, chapter_name: str, position: float, track_index: int):
        """Save progress for a specific book chapter"""
        key = f"{book_name}:{chapter_name}"
        self.progress[key] = {
            "position": position,
            "track_index": track_index,
            "last_played": datetime.now().isoformat()
        }
        self._save_progress()


# Initialize library and progress tracker
library = AudiobookLibrary(BOOKS_DIR)
progress_tracker = ProgressTracker(PROGRESS_FILE)


@app.route('/')
def index():
    """Serve the audiobook player interface"""
    return render_template('player.html')


@app.route('/api/library')
def get_library():
    """API endpoint to get the complete audiobook library"""
    return jsonify(library.scan_library())


@app.route('/api/progress/<book_name>/<chapter_name>')
def get_progress(book_name, chapter_name):
    """API endpoint to get progress for a book chapter"""
    return jsonify(progress_tracker.get_progress(book_name, chapter_name))


@app.route('/api/progress/<book_name>/<chapter_name>', methods=['POST'])
def save_progress(book_name, chapter_name):
    """API endpoint to save progress for a book chapter"""
    data = request.json
    position = data.get('position', 0)
    track_index = data.get('track_index', 0)

    progress_tracker.set_progress(book_name, chapter_name, position, track_index)
    return jsonify({"status": "success"})


@app.route('/audio/<path:filepath>')
def serve_audio(filepath):
    """Serve audio files from books directory"""
    # Security: ensure path is within books directory
    try:
        full_path = (BOOKS_DIR / filepath).resolve()
        if not str(full_path).startswith(str(BOOKS_DIR.resolve())):
            return "Access denied", 403

        return send_from_directory(full_path.parent, full_path.name)
    except Exception as e:
        return f"File not found: {e}", 404


if __name__ == '__main__':
    print("\n📚 Starting Audiobook Player...")
    print(f"📂 Scanning library: {BOOKS_DIR.absolute()}")

    lib = library.scan_library()
    print(f"\n✓ Found {len(lib)} books:")
    for book_name, book_data in lib.items():
        print(f"  - {book_data['title']} ({len(book_data['chapters'])} chapters)")

    print("\n🎵 Player available at: http://localhost:5001")
    print("Press Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
