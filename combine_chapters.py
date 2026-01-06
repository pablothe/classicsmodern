#!/usr/bin/env python3
"""
Combine existing audio chunks into chapter-based files.
Detects chapters in the source markdown and combines corresponding audio files.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime


def detect_chapters(text: str) -> list:
    """
    Detect chapter boundaries in text.
    Looks for Roman numerals (I., II., III.) or Markdown headers.

    Returns:
        List of tuples: (chapter_number, start_position, title)
    """
    chapters = []
    lines = text.split('\n')

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Roman numeral pattern (I., II., III., etc.)
        roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', line_stripped)
        if roman_match:
            # Convert position in lines to character position
            char_pos = len('\n'.join(lines[:i]))
            chapter_num = len(chapters) + 1
            chapters.append((chapter_num, char_pos, line_stripped))
            continue

        # Markdown header patterns
        header_match = re.match(r'^#+\s+(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+)', line_stripped)
        if header_match:
            char_pos = len('\n'.join(lines[:i]))
            chapter_num = len(chapters) + 1
            chapters.append((chapter_num, char_pos, line_stripped))

    return chapters


def combine_audio_files(audio_files: list, output_file: Path) -> Path:
    """
    Combine multiple audio files into one using FFmpeg.

    Args:
        audio_files: List of audio file paths to combine
        output_file: Output file path

    Returns:
        Path to combined audio file
    """
    if not audio_files:
        return None

    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Warning: ffmpeg not found, cannot combine files")
        return None

    # Create concat file for ffmpeg
    concat_file = output_file.parent / f"concat_{output_file.stem}.txt"
    with open(concat_file, 'w', encoding='utf-8') as f:
        for audio_file in audio_files:
            # Use absolute paths for ffmpeg concat
            abs_path = Path(audio_file).resolve()
            f.write(f"file '{abs_path}'\n")

    # Combine files
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(output_file)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        concat_file.unlink()  # Clean up concat file
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Failed to combine files: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python combine_chapters.py <markdown_file> [audio_directory]")
        print("\nExample:")
        print("  python combine_chapters.py books/mybook/translated.md books/mybook/audio_xtts/")
        sys.exit(1)

    markdown_file = Path(sys.argv[1])

    if len(sys.argv) > 2:
        audio_dir = Path(sys.argv[2])
    else:
        # Auto-detect audio directory
        audio_dir = markdown_file.parent / "audio_xtts"
        if not audio_dir.exists():
            print(f"❌ Audio directory not found: {audio_dir}")
            print("Please specify audio directory as second argument")
            sys.exit(1)

    if not markdown_file.exists():
        print(f"❌ Markdown file not found: {markdown_file}")
        sys.exit(1)

    if not audio_dir.exists():
        print(f"❌ Audio directory not found: {audio_dir}")
        sys.exit(1)

    print("="*70)
    print("CHAPTER-BASED AUDIO COMBINING")
    print("="*70)
    print(f"Source text: {markdown_file}")
    print(f"Audio directory: {audio_dir}")
    print()

    # Read markdown file
    print("Reading source text...")
    with open(markdown_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # Detect chapters
    print("Detecting chapters...")
    chapters = detect_chapters(text)

    if not chapters:
        print("❌ No chapters detected in source text")
        print("Looking for patterns like 'I.', 'II.', 'III.' or '# Chapter 1'")
        sys.exit(1)

    print(f"✓ Found {len(chapters)} chapters:")
    for ch_num, ch_pos, ch_title in chapters[:10]:  # Show first 10
        print(f"  {ch_num:2d}. {ch_title}")
    if len(chapters) > 10:
        print(f"  ... and {len(chapters) - 10} more")
    print()

    # Find all audio files
    audio_files = sorted(audio_dir.glob("*.mp3"))
    if not audio_files:
        audio_files = sorted(audio_dir.glob("*.wav"))

    if not audio_files:
        print(f"❌ No audio files (.mp3 or .wav) found in: {audio_dir}")
        sys.exit(1)

    print(f"Found {len(audio_files)} audio chunks")
    ext = audio_files[0].suffix

    # Map audio chunks to chapters
    # Assume chunks are generated sequentially and correspond to text order
    chunks_per_chapter = len(audio_files) // len(chapters)
    remainder = len(audio_files) % len(chapters)

    print(f"Mapping {len(audio_files)} chunks to {len(chapters)} chapters...")
    print(f"  (~{chunks_per_chapter} chunks per chapter)")
    print()

    # Create chapter mapping based on character positions
    text_length = len(text)
    chunk_to_chapter = []

    for i, audio_file in enumerate(audio_files):
        # Estimate position of this chunk in the text
        chunk_ratio = i / len(audio_files)
        estimated_pos = int(chunk_ratio * text_length)

        # Find which chapter this position falls into
        chapter_num = 1
        for j, (ch_num, ch_pos, ch_title) in enumerate(chapters):
            if estimated_pos >= ch_pos:
                chapter_num = ch_num
            else:
                break

        chunk_to_chapter.append(chapter_num)

    # Combine chunks into chapter files
    base_name = markdown_file.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chapter_files = []

    print(f"📚 Combining chunks into chapter files...")
    print()

    for chapter_num in range(1, max(chunk_to_chapter) + 1):
        # Find all audio files for this chapter
        chapter_audio_files = [
            audio_files[i] for i in range(len(audio_files))
            if chunk_to_chapter[i] == chapter_num
        ]

        if chapter_audio_files:
            chapter_filename = f"{base_name}_chapter_{chapter_num:02d}{ext}"
            chapter_path = audio_dir / chapter_filename

            print(f"  Chapter {chapter_num:2d}: Combining {len(chapter_audio_files):3d} chunks...", end=" ", flush=True)

            result = combine_audio_files(chapter_audio_files, chapter_path)
            if result:
                chapter_files.append(result)
                # Get file size
                size_mb = result.stat().st_size / (1024 * 1024)
                print(f"✓ {chapter_path.name} ({size_mb:.1f} MB)")
            else:
                print("✗ Failed")

    # Generate master audiobook playlist
    if chapter_files:
        playlist_path = audio_dir / f"{base_name}_audiobook_{timestamp}.m3u"
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for i, chapter_file in enumerate(chapter_files, 1):
                f.write(f"#EXTINF:-1,Chapter {i}\n")
                f.write(f"{chapter_file.name}\n")

        print()
        print(f"✓ Master audiobook playlist: {playlist_path.name}")
        print(f"  ({len(chapter_files)} chapters)")

    print()
    print("="*70)
    print("COMBINING COMPLETE")
    print("="*70)
    print(f"Chapters created: {len(chapter_files)}")
    print(f"Output directory: {audio_dir}")
    print(f"Playlist: {playlist_path}")
    print("="*70)
    print()
    print("💡 To play: afplay", str(playlist_path))


if __name__ == "__main__":
    main()
