#!/usr/bin/env python3
"""
Text Deduplication for Overlapping Translation Chunks

Removes exact text duplicates at chunk boundaries caused by translation overlap.
Only removes text if there's an EXACT match - no fuzzy logic.
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
import sys


def find_exact_overlap(text1_end: str, text2_start: str, max_words: int = 30) -> Optional[str]:
    """
    Find exact overlapping text between end of text1 and start of text2.

    Args:
        text1_end: Last portion of first text
        text2_start: First portion of second text
        max_words: Maximum words to search for overlap

    Returns:
        The exact overlapping text, or None if no overlap found
    """
    # Clean up whitespace for comparison
    words1 = text1_end.split()[-max_words:]
    words2 = text2_start.split()[:max_words * 2]  # Search window

    # Try progressively smaller overlaps (start with max_words, go down)
    for overlap_size in range(max_words, 0, -1):
        if overlap_size > len(words1) or overlap_size > len(words2):
            continue

        # Get candidate overlap from end of text1
        candidate = ' '.join(words1[-overlap_size:])

        # Check if it matches start of text2
        text2_candidate = ' '.join(words2[:overlap_size])

        if candidate == text2_candidate:
            return candidate

    return None


def deduplicate_chunks(chunk_files: List[Path], output_dir: Path, max_overlap_words: int = 30) -> List[Path]:
    """
    Remove exact duplicate text from consecutive chunks.

    Args:
        chunk_files: List of chunk file paths in order
        output_dir: Output directory for deduplicated chunks
        max_overlap_words: Maximum expected overlap in words

    Returns:
        List of output file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_files = []

    print(f"Deduplicating {len(chunk_files)} chunks...")
    print(f"Maximum overlap to check: {max_overlap_words} words\n")

    total_removed_chars = 0

    for i, chunk_file in enumerate(chunk_files):
        print(f"Processing chunk {i+1}/{len(chunk_files)}: {chunk_file.name}")

        with open(chunk_file, 'r', encoding='utf-8') as f:
            content = f.read()

        original_length = len(content)

        # For chunks after the first, check for overlap with previous chunk
        if i > 0:
            # Read previous chunk
            prev_file = chunk_files[i-1]
            with open(prev_file, 'r', encoding='utf-8') as f:
                prev_content = f.read()

            # Find exact overlap
            overlap = find_exact_overlap(prev_content, content, max_overlap_words)

            if overlap:
                # Remove the overlap from the start of current chunk
                content = content[len(overlap):].lstrip()
                removed = original_length - len(content)
                total_removed_chars += removed

                overlap_words = len(overlap.split())
                print(f"  ✓ Removed {overlap_words} words ({removed:,} chars)")
                print(f"    Preview: '{overlap[:60]}...'")
            else:
                print(f"  ○ No exact overlap found")
        else:
            print(f"  ○ First chunk - no deduplication needed")

        # Save deduplicated content
        output_file = output_dir / f"{chunk_file.stem}_DEDUPED.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        output_files.append(output_file)
        print()

    print("="*60)
    print(f"DEDUPLICATION COMPLETE")
    print("="*60)
    print(f"Total characters removed: {total_removed_chars:,}")
    print(f"Output directory: {output_dir}")
    print(f"Files created: {len(output_files)}")

    return output_files


def find_translated_chunks(directory: Path, pattern: str = "*_spanish.md") -> List[Path]:
    """
    Find all translated chunk files in a directory.

    Args:
        directory: Directory to search
        pattern: Glob pattern for chunk files

    Returns:
        Sorted list of chunk files
    """
    chunks = sorted(directory.glob(pattern))

    # Filter out already deduplicated files
    chunks = [c for c in chunks if '_DEDUPED' not in c.name]

    return chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python local_reader_deduplicate.py <directory> [pattern]")
        print("\nExamples:")
        print("  # Deduplicate all Spanish translations in a directory")
        print("  python local_reader_deduplicate.py books/crime_punishment/chunks/test_chunk/translated/")
        print()
        print("  # Custom pattern")
        print("  python local_reader_deduplicate.py translated/ 'chunk_*_english.md'")
        print()
        print("This will:")
        print("  1. Find all matching chunk files (sorted by name)")
        print("  2. Detect exact text overlap between consecutive chunks")
        print("  3. Remove duplicates from start of each chunk (except first)")
        print("  4. Save deduplicated files with _DEDUPED suffix")
        sys.exit(1)

    directory = Path(sys.argv[1])
    pattern = sys.argv[2] if len(sys.argv) > 2 else "*_spanish.md"

    if not directory.exists():
        print(f"❌ ERROR: Directory not found: {directory}")
        sys.exit(1)

    # Find chunks
    chunk_files = find_translated_chunks(directory, pattern)

    if not chunk_files:
        print(f"❌ ERROR: No files found matching pattern '{pattern}' in {directory}")
        sys.exit(1)

    print(f"Found {len(chunk_files)} chunk files:\n")
    for chunk in chunk_files:
        print(f"  - {chunk.name}")
    print()

    # Create output directory
    output_dir = directory / "deduplicated"

    try:
        output_files = deduplicate_chunks(chunk_files, output_dir)
        print("\n✅ SUCCESS!")
        print(f"\nNext step: Generate audio from deduplicated files:")
        print(f"  python local_reader_audio.py {output_dir}/chunk_001_DEDUPED.md")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
