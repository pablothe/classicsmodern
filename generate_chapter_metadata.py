#!/usr/bin/env python3
"""
Generate Chapter Metadata for Audiobook Player

This script creates chapter_data.json files that map chapters to audio file positions.
It reads chapter information from the TTS generation process and creates the metadata
needed for the web player's chapter navigation feature.

Usage:
    python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_20260107_123456.m3u
"""

import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import sys


def get_audio_duration(audio_file: Path) -> float:
    """
    Get duration of an audio file using ffprobe.

    Args:
        audio_file: Path to audio file

    Returns:
        Duration in seconds
    """
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_file)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        print(f"⚠️  Warning: Could not get duration for {audio_file.name}: {e}")
        return 0.0


def parse_m3u_playlist(playlist_path: Path) -> List[Path]:
    """
    Parse M3U playlist and return audio file paths.

    Args:
        playlist_path: Path to .m3u file

    Returns:
        List of audio file paths
    """
    audio_files = []
    playlist_dir = playlist_path.parent

    with open(playlist_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Resolve relative path
            audio_path = playlist_dir / line
            if audio_path.exists():
                audio_files.append(audio_path)
            else:
                print(f"⚠️  Warning: Audio file not found: {line}")

    return audio_files


def detect_chapter_pattern(filename: str) -> Optional[int]:
    """
    Detect chapter number from filename.

    Patterns:
        - name_chapter_01.mp3
        - name_chapter01.mp3
        - name_ch01.mp3

    Args:
        filename: Audio filename

    Returns:
        Chapter number or None
    """
    # Pattern: chapter_XX or chapterXX or chXX
    patterns = [
        r'chapter[_-]?(\d+)',
        r'ch[_-]?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_chapter_titles_from_source(book_dir: Path) -> Dict[int, str]:
    """
    Extract chapter titles from source markdown file.

    Args:
        book_dir: Book directory (e.g., books/call_cthulhu/)

    Returns:
        Dictionary mapping chapter number to title (e.g., {1: "The Horror in Clay"})
    """
    # Find source markdown file
    source_candidates = list(book_dir.glob("*.md"))
    if not source_candidates:
        return {}

    # Use the first .md file found
    source_file = source_candidates[0]

    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"⚠️  Could not read source file {source_file.name}: {e}")
        return {}

    chapter_titles = {}
    lines = text.split('\n')

    # Find Gutenberg boundaries to exclude boilerplate
    gutenberg_start = -1
    gutenberg_end = -1
    for i, line in enumerate(lines):
        if '*** START OF THE PROJECT GUTENBERG EBOOK' in line.upper():
            gutenberg_start = i
        if '*** END OF THE PROJECT GUTENBERG EBOOK' in line.upper():
            gutenberg_end = i
            break

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Skip Gutenberg boilerplate
        if gutenberg_start >= 0 and i < gutenberg_start:
            continue
        if gutenberg_end >= 0 and i >= gutenberg_end:
            continue

        # Skip empty lines and horizontal rules
        if not line_stripped or re.match(r'^[-*_]{3,}$', line_stripped):
            continue

        # Detect numbered chapters (e.g., "1. The Horror in Clay.")
        numbered_match = re.match(r'^(\d+)\.\s+(.+)$', line_stripped)
        if numbered_match:
            chapter_num = int(numbered_match.group(1))
            chapter_text = numbered_match.group(2).strip()

            # Exclude TOC entries (markdown links)
            if re.search(r'\[.*?\]\(#', chapter_text):
                continue
            # Exclude short entries (likely list items)
            if len(chapter_text) < 15:
                continue

            # Remove trailing period if present
            if chapter_text.endswith('.'):
                chapter_text = chapter_text[:-1]

            chapter_titles[chapter_num] = chapter_text

    return chapter_titles


def generate_chapter_metadata(
    playlist_path: Path,
    title: str = None,
    author: str = None
) -> Dict:
    """
    Generate chapter metadata from audiobook playlist.

    Args:
        playlist_path: Path to M3U playlist
        title: Book title (optional)
        author: Book author (optional)

    Returns:
        Chapter metadata dictionary
    """
    print(f"📖 Analyzing playlist: {playlist_path.name}")

    # Parse playlist
    audio_files = parse_m3u_playlist(playlist_path)
    print(f"✓ Found {len(audio_files)} audio files")

    # Detect if files are chapter-based
    chapters_data = []

    # Check if filenames indicate chapters
    chapter_files = {}
    for audio_file in audio_files:
        chapter_num = detect_chapter_pattern(audio_file.name)
        if chapter_num:
            if chapter_num not in chapter_files:
                chapter_files[chapter_num] = []
            chapter_files[chapter_num].append(audio_file)

    if chapter_files:
        # Files are organized by chapter
        print(f"✓ Detected chapter-based organization ({len(chapter_files)} chapters)")

        # Try to extract chapter titles from source markdown
        book_dir = playlist_path.parent
        while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio', 'deduplicated', 'translated', 'chunks']:
            book_dir = book_dir.parent

        chapter_titles = extract_chapter_titles_from_source(book_dir)
        if chapter_titles:
            print(f"✓ Extracted {len(chapter_titles)} chapter titles from source")

        for chapter_num in sorted(chapter_files.keys()):
            files = chapter_files[chapter_num]

            # Chapter starts at file_index 0 (first file for this chapter)
            # Timestamp is always 0.0 because each chapter is its own file(s)
            file_index = audio_files.index(files[0])

            # Use extracted title if available, otherwise generic
            chapter_title = chapter_titles.get(chapter_num, f"Chapter {chapter_num}")

            chapters_data.append({
                "number": chapter_num,
                "title": chapter_title,
                "file_index": file_index,
                "timestamp": 0.0
            })

            print(f"  Chapter {chapter_num:2d}: {chapter_title} (file_index={file_index}, files={len(files)})")

    else:
        # No chapter markers in filenames
        # Try to detect chapters from text or create single chapter
        print("ℹ  No chapter markers in filenames")
        print("  Creating single-chapter metadata")

        chapters_data.append({
            "number": 1,
            "title": "Complete Book",
            "file_index": 0,
            "timestamp": 0.0
        })

    # Auto-detect title from playlist name if not provided
    if not title:
        # Remove timestamp and extension
        title = re.sub(r'_audiobook_\d{8}_\d{6}$', '', playlist_path.stem)
        title = re.sub(r'_', ' ', title).title()

    metadata = {
        "title": title,
        "author": author,
        "chapters": chapters_data
    }

    return metadata


def save_chapter_metadata(metadata: Dict, output_path: Path):
    """
    Save chapter metadata to JSON file.

    Args:
        metadata: Chapter metadata dictionary
        output_path: Where to save the JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Chapter metadata saved: {output_path}")
    print(f"  Title: {metadata['title']}")
    print(f"  Chapters: {len(metadata['chapters'])}")


def main():
    """Main function for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python3 generate_chapter_metadata.py <playlist.m3u> [title] [author]")
        print("\nExample:")
        print("  python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_20260107_123456.m3u")
        print("  python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_20260107_123456.m3u \"Alice's Adventures\" \"Lewis Carroll\"")
        print("\nThis will create:")
        print("  books/alice_adventures/alices_adventures_chapter_data.json")
        sys.exit(1)

    playlist_path = Path(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else None
    author = sys.argv[3] if len(sys.argv) > 3 else None

    if not playlist_path.exists():
        print(f"❌ Error: Playlist not found: {playlist_path}")
        sys.exit(1)

    if playlist_path.suffix.lower() != '.m3u':
        print(f"❌ Error: Not an M3U file: {playlist_path}")
        sys.exit(1)

    # Generate metadata
    metadata = generate_chapter_metadata(playlist_path, title, author)

    # Determine output path (book root directory)
    # Playlist is in: books/alice_adventures/audio_xtts/playlist.m3u
    # Output should be: books/alice_adventures/alices_adventures_chapter_data.json

    # Find the book directory (may be nested in chunks/translated/etc)
    book_dir = playlist_path.parent
    while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio', 'deduplicated', 'translated', 'chunks']:
        book_dir = book_dir.parent

    # Ensure we're in the actual book directory (under books/)
    if book_dir.parent.name == 'books':
        book_name = book_dir.name
        output_path = book_dir / f"{book_name}_chapter_data.json"
    else:
        # Fallback: use the immediate parent
        book_name = playlist_path.parent.name
        output_path = playlist_path.parent / f"{book_name}_chapter_data.json"

    # Save
    save_chapter_metadata(metadata, output_path)

    print("\n" + "="*60)
    print("✓ CHAPTER METADATA GENERATED SUCCESSFULLY")
    print("="*60)
    print(f"\nNext steps:")
    print(f"1. Restart the audiobook server:")
    print(f"   cd server && python3 audiobook_server.py")
    print(f"2. Open the book in the web player")
    print(f"3. You should see the 'Chapters' button!")


if __name__ == "__main__":
    main()
