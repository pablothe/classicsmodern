#!/usr/bin/env python3
"""
Audio Combiner for Local Reader

Combines multiple MP3 files into a single audiobook file.
Requires: pydub and ffmpeg
"""

import sys
from pathlib import Path
from typing import List
import subprocess


def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def combine_mp3_files_simple(input_files: List[Path], output_file: Path):
    """
    Combine MP3 files using ffmpeg concat (fast, no re-encoding).

    Args:
        input_files: List of input MP3 file paths
        output_file: Output file path
    """
    # Create a temporary file list for ffmpeg
    concat_file = output_file.parent / "concat_list.txt"

    with open(concat_file, 'w', encoding='utf-8') as f:
        for mp3_file in input_files:
            # ffmpeg requires absolute paths
            abs_path = mp3_file.absolute()
            f.write(f"file '{abs_path}'\n")

    try:
        # Use ffmpeg concat demuxer (fast, no re-encoding)
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',  # Copy codec (no re-encoding)
            str(output_file)
        ]

        print(f"Combining {len(input_files)} files...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            raise RuntimeError("ffmpeg failed")

        print(f"✓ Combined audiobook created: {output_file}")

    finally:
        # Clean up temporary file
        if concat_file.exists():
            concat_file.unlink()


def combine_from_playlist(playlist_file: str, output_file: str = None):
    """
    Combine MP3 files from an M3U playlist.

    Args:
        playlist_file: Path to M3U playlist
        output_file: Output MP3 file (auto-generated if None)
    """
    playlist_path = Path(playlist_file)

    if not playlist_path.exists():
        raise FileNotFoundError(f"Playlist not found: {playlist_file}")

    # Read playlist
    print(f"Reading playlist: {playlist_path}")
    mp3_files = []

    with open(playlist_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Playlist entries are relative to playlist location
                mp3_path = playlist_path.parent / line
                if mp3_path.exists():
                    mp3_files.append(mp3_path)
                else:
                    print(f"Warning: File not found: {mp3_path}")

    if not mp3_files:
        raise ValueError("No valid MP3 files found in playlist")

    print(f"Found {len(mp3_files)} MP3 files")

    # Generate output filename if not provided
    if output_file is None:
        base_name = playlist_path.stem.replace('_audiobook_playlist', '_COMBINED')
        output_file = playlist_path.parent / f"{base_name}.mp3"
    else:
        output_file = Path(output_file)

    # Combine files
    combine_mp3_files_simple(mp3_files, output_file)

    # Show file info
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\nFile size: {size_mb:.1f} MB")
    print(f"Location: {output_file}")

    return output_file


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Usage: python local_reader_audio_combiner.py <playlist.m3u> [output.mp3]")
        print("\nExample:")
        print("  python local_reader_audio_combiner.py audiobook_playlist.m3u combined.mp3")
        print("\nThis will combine all MP3 files from the playlist into a single file.")
        print("\nRequires: ffmpeg (install with: brew install ffmpeg)")
        sys.exit(1)

    # Check for ffmpeg
    if not check_ffmpeg():
        print("❌ ERROR: ffmpeg not found")
        print("\nPlease install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/")
        sys.exit(1)

    playlist_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = combine_from_playlist(playlist_file, output_file)
        print("\n✅ Success!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
