#!/usr/bin/env python3
"""
Text Deduplication for Overlapping Translation Chunks

Removes exact text duplicates at chunk boundaries caused by translation overlap.
Only removes text if there's an EXACT match - no fuzzy logic.
"""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Tuple, Optional
import sys


def find_exact_overlap(text1_end: str, text2_start: str, max_words: int = 50) -> Optional[str]:
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


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using punctuation boundaries."""
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in parts if s.strip()]


def find_fuzzy_overlap(
    text1_end: str,
    text2_start: str,
    similarity_threshold: float = 0.8,
    max_sentences: int = 5,
) -> List[Tuple[str, str, float]]:
    """
    Find near-duplicate sentences between end of text1 and start of text2.

    Uses difflib.SequenceMatcher for similarity scoring (stdlib, no deps).
    Returns pairs of similar sentences that likely represent echoed context.

    Args:
        text1_end: Last portion of first text
        text2_start: First portion of second text
        similarity_threshold: Minimum similarity ratio (0.0-1.0) to count as overlap
        max_sentences: Maximum sentences to compare from each side

    Returns:
        List of (sentence_from_text1, sentence_from_text2, similarity_score)
        for pairs exceeding the threshold
    """
    sentences1 = _split_sentences(text1_end)[-max_sentences:]
    sentences2 = _split_sentences(text2_start)[:max_sentences]

    if not sentences1 or not sentences2:
        return []

    matches = []
    # Compare sentences from end of text1 against start of text2
    # Only check sequential alignment (sentence i in text1 ~ sentence j in text2)
    # to avoid false positives from coincidental similarity
    matched_j = set()
    for s1 in sentences1:
        for j, s2 in enumerate(sentences2):
            if j in matched_j:
                continue
            ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
            if ratio >= similarity_threshold:
                matches.append((s1, s2, ratio))
                matched_j.add(j)
                break  # Each s1 matches at most one s2

    return matches


def remove_fuzzy_overlap(text: str, fuzzy_matches: List[Tuple[str, str, float]]) -> str:
    """
    Remove fuzzy-matched sentences from the start of text.

    Only removes sentences that appear at the beginning of the text and match
    a sentence from the previous chunk. Preserves the rest of the text.

    Args:
        text: The text to clean (start of a chunk/paragraph)
        fuzzy_matches: Output from find_fuzzy_overlap()

    Returns:
        Text with overlapping sentences removed from the start
    """
    if not fuzzy_matches:
        return text

    # Get the sentences that were found in text2 (the current text)
    sentences_to_remove = [match[1] for match in fuzzy_matches]

    result = text
    for sentence in sentences_to_remove:
        # Only remove if it appears at or near the start of the text
        # Use a loose match: find the sentence in the first portion of text
        idx = result.find(sentence)
        if idx != -1 and idx < 100:  # Within first 100 chars = at the start
            result = result[idx + len(sentence):].lstrip()

    return result


def deduplicate_chunks(chunk_files: List[Path], output_dir: Path, max_overlap_words: int = 50) -> List[Path]:
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
                print(f"  ✓ Removed {overlap_words} words ({removed:,} chars) [exact]")
                print(f"    Preview: '{overlap[:60]}...'")
            else:
                # Fallback: try fuzzy overlap detection
                fuzzy_matches = find_fuzzy_overlap(
                    prev_content, content, similarity_threshold=0.85
                )
                if fuzzy_matches:
                    content = remove_fuzzy_overlap(content, fuzzy_matches)
                    removed = original_length - len(content)
                    total_removed_chars += removed
                    print(f"  ✓ Removed {len(fuzzy_matches)} fuzzy match(es) ({removed:,} chars)")
                    for s1, s2, score in fuzzy_matches:
                        print(f"    [{score:.0%}] '{s2[:50]}...'")
                else:
                    print(f"  ○ No overlap found")
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
