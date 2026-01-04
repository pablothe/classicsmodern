#!/usr/bin/env python3
"""
Audio Compression for Local Reader

Compresses MP3 files to reduce size while maintaining quality.
Useful for mobile devices and sharing.
"""

import sys
import subprocess
from pathlib import Path


def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def compress_mp3(input_file: str, output_file: str = None, bitrate: str = "96k"):
    """
    Compress MP3 file to reduce size.

    Args:
        input_file: Input MP3 file path
        output_file: Output file path (auto-generated if None)
        bitrate: Target bitrate (64k, 96k, 128k, 192k)
                 Lower = smaller file, lower quality
                 For audiobooks, 64k-96k is usually fine

    Common bitrates:
        64k  = Very small, acceptable for speech
        96k  = Good balance for audiobooks (RECOMMENDED)
        128k = Higher quality, larger file
        192k = High quality (probably unnecessary for audiobooks)
    """
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Generate output filename
    if output_file is None:
        output_file = input_path.parent / f"{input_path.stem}_compressed.mp3"
    else:
        output_file = Path(output_file)

    print(f"Compressing: {input_path.name}")
    print(f"Target bitrate: {bitrate}")

    # ffmpeg command for compression
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-codec:a', 'libmp3lame',  # MP3 encoder
        '-b:a', bitrate,            # Bitrate
        '-ar', '44100',             # Sample rate (CD quality)
        '-ac', '1',                 # Mono (audiobooks don't need stereo)
        '-y',                       # Overwrite output
        str(output_file)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            raise RuntimeError("ffmpeg compression failed")

        # Show results
        original_size = input_path.stat().st_size / (1024 * 1024)
        compressed_size = output_file.stat().st_size / (1024 * 1024)
        reduction = ((original_size - compressed_size) / original_size) * 100

        print(f"\n✓ Compression complete!")
        print(f"Original:   {original_size:.1f} MB")
        print(f"Compressed: {compressed_size:.1f} MB")
        print(f"Reduction:  {reduction:.1f}%")
        print(f"Output:     {output_file}")

        return output_file

    except Exception as e:
        if output_file.exists():
            output_file.unlink()  # Clean up partial file
        raise


def compress_directory(audio_dir: str, bitrate: str = "96k"):
    """
    Compress all MP3 files in a directory.

    Args:
        audio_dir: Directory containing MP3 files
        bitrate: Target bitrate
    """
    audio_path = Path(audio_dir)

    if not audio_path.exists():
        raise FileNotFoundError(f"Directory not found: {audio_dir}")

    # Find all MP3 files (excluding already compressed ones)
    mp3_files = [
        f for f in audio_path.glob("*.mp3")
        if "_compressed" not in f.stem and f.is_file()
    ]

    if not mp3_files:
        print("No MP3 files found to compress")
        return

    print(f"Found {len(mp3_files)} files to compress\n")

    compressed_files = []
    total_original = 0
    total_compressed = 0

    for i, mp3_file in enumerate(mp3_files, 1):
        print(f"[{i}/{len(mp3_files)}]")
        try:
            output = compress_mp3(str(mp3_file), bitrate=bitrate)
            compressed_files.append(output)

            total_original += mp3_file.stat().st_size
            total_compressed += output.stat().st_size

        except Exception as e:
            print(f"✗ Failed: {e}")

        print()  # Blank line between files

    # Summary
    total_original_mb = total_original / (1024 * 1024)
    total_compressed_mb = total_compressed / (1024 * 1024)
    total_reduction = ((total_original - total_compressed) / total_original) * 100

    print("="*60)
    print("COMPRESSION SUMMARY")
    print("="*60)
    print(f"Files compressed: {len(compressed_files)}")
    print(f"Original total:   {total_original_mb:.1f} MB")
    print(f"Compressed total: {total_compressed_mb:.1f} MB")
    print(f"Space saved:      {total_original_mb - total_compressed_mb:.1f} MB ({total_reduction:.1f}%)")
    print("="*60)


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Usage: python local_reader_audio_compress.py <input_file_or_dir> [bitrate]")
        print("\nExamples:")
        print("  # Compress single file (default 96k)")
        print("  python local_reader_audio_compress.py audiobook.mp3")
        print()
        print("  # Compress with specific bitrate")
        print("  python local_reader_audio_compress.py audiobook.mp3 64k")
        print()
        print("  # Compress all files in directory")
        print("  python local_reader_audio_compress.py audio/")
        print()
        print("Bitrate options:")
        print("  64k  - Very compressed (smallest, adequate for speech)")
        print("  96k  - Good balance (RECOMMENDED for audiobooks)")
        print("  128k - Higher quality")
        print("  192k - High quality (probably unnecessary)")
        print()
        print("Note: This converts to MONO (audiobooks don't need stereo)")
        print("      Typical reduction: 40-60% smaller file size")
        sys.exit(1)

    # Check for ffmpeg
    if not check_ffmpeg():
        print("❌ ERROR: ffmpeg not found")
        print("\nPlease install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        sys.exit(1)

    input_path = sys.argv[1]
    bitrate = sys.argv[2] if len(sys.argv) > 2 else "96k"

    try:
        path = Path(input_path)

        if path.is_file():
            # Compress single file
            compress_mp3(input_path, bitrate=bitrate)
        elif path.is_dir():
            # Compress directory
            compress_directory(input_path, bitrate=bitrate)
        else:
            print(f"Error: {input_path} is not a file or directory")
            sys.exit(1)

        print("\n✅ Done!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
