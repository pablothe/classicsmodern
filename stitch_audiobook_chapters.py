#!/usr/bin/env python3
"""
Stitch MP3 Chunks into Complete Chapter Files

Combines the hundreds of small MP3 chunks created by TTS into single,
continuous chapter files for easier playback.
"""

import os
import subprocess
from pathlib import Path
import re
from typing import List, Dict
import tempfile


def find_audio_directories() -> List[Path]:
    """Find all audio_xtts directories in the books folder"""
    books_dir = Path("books")
    audio_dirs = []

    for path in books_dir.rglob("audio_xtts"):
        if path.is_dir():
            audio_dirs.append(path)

    return audio_dirs


def group_mp3_files(audio_dir: Path) -> Dict[str, List[Path]]:
    """
    Group MP3 files by chapter/chunk prefix.

    Returns:
        dict: {"chunk_001": [chunk001.mp3, chunk002.mp3, ...], ...}
    """
    mp3_files = sorted(audio_dir.glob("*.mp3"))
    chapters = {}

    for mp3 in mp3_files:
        # Extract chapter/chunk prefix from filenames like:
        # "chunk_001_modern_english_4b_DEDUPED_chunk001.mp3"
        match = re.match(r'(chunk_\d+)_.*?_chunk\d+\.mp3', mp3.name)
        if match:
            chapter_prefix = match.group(1)
            if chapter_prefix not in chapters:
                chapters[chapter_prefix] = []
            chapters[chapter_prefix].append(mp3)

    # Sort files within each chapter
    for chapter_prefix in chapters:
        chapters[chapter_prefix].sort()

    return chapters


def stitch_mp3_files(mp3_files: List[Path], output_file: Path) -> bool:
    """
    Stitch multiple MP3 files into a single file using ffmpeg.

    Args:
        mp3_files: List of MP3 files to concatenate
        output_file: Output file path

    Returns:
        bool: True if successful
    """
    if not mp3_files:
        print("  ⚠️  No MP3 files to stitch")
        return False

    # Create temporary file list for ffmpeg concat
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for mp3 in mp3_files:
            # ffmpeg concat demuxer requires absolute paths
            f.write(f"file '{mp3.absolute()}'\n")
        concat_file = f.name

    try:
        # Use ffmpeg concat demuxer for lossless concatenation
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            '-y',  # Overwrite output file
            str(output_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ❌ ffmpeg error: {result.stderr}")
            return False

        return True

    finally:
        # Clean up temp file
        os.unlink(concat_file)


def get_audio_duration(file_path: Path) -> float:
    """Get duration of audio file in seconds using ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0.0


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def stitch_all_chapters():
    """Main function to stitch all audiobook chapters"""
    print("\n📚 Audiobook Chapter Stitcher")
    print("=" * 60)

    # Find all audio directories
    audio_dirs = find_audio_directories()

    if not audio_dirs:
        print("\n❌ No audio_xtts directories found in books/")
        return

    print(f"\n✓ Found {len(audio_dirs)} audio directories\n")

    total_chapters = 0
    total_size_saved = 0

    for audio_dir in audio_dirs:
        # Get book name from path
        book_name = audio_dir.parts[-5] if len(audio_dir.parts) >= 5 else "unknown"
        print(f"\n📖 Processing: {book_name}")
        print(f"   Directory: {audio_dir.relative_to('.')}")

        # Group MP3 files by chapter
        chapters = group_mp3_files(audio_dir)

        if not chapters:
            print("   ⚠️  No MP3 files found")
            continue

        print(f"   Found {len(chapters)} chapters")

        # Create stitched directory
        stitched_dir = audio_dir / "stitched"
        stitched_dir.mkdir(exist_ok=True)

        # Stitch each chapter
        for chapter_prefix, mp3_files in chapters.items():
            chapter_num = re.search(r'\d+', chapter_prefix).group()
            output_file = stitched_dir / f"chapter_{chapter_num}.mp3"

            # Skip if already exists and is newer than source files
            if output_file.exists():
                output_mtime = output_file.stat().st_mtime
                source_mtime = max(f.stat().st_mtime for f in mp3_files)

                if output_mtime > source_mtime:
                    duration = get_audio_duration(output_file)
                    print(f"   ✓ Chapter {chapter_num}: Already stitched ({len(mp3_files)} tracks → {format_duration(duration)})")
                    total_chapters += 1
                    continue

            print(f"   🔨 Chapter {chapter_num}: Stitching {len(mp3_files)} tracks...", end=" ", flush=True)

            if stitch_mp3_files(mp3_files, output_file):
                duration = get_audio_duration(output_file)
                size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"✓ ({format_duration(duration)}, {size_mb:.1f} MB)")
                total_chapters += 1
            else:
                print("❌ Failed")

    print("\n" + "=" * 60)
    print(f"✅ Complete! Stitched {total_chapters} chapters")
    print(f"\n💡 Stitched files saved to: books/.../audio_xtts/stitched/")
    print(f"   Refresh your audiobook player to see single-file chapters")


if __name__ == '__main__':
    try:
        stitch_all_chapters()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
