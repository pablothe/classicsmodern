#!/usr/bin/env python3
"""
Smart Book Splitter for Local Reader

Splits books by chapters (if they have headers) or by size-based chunks.
Handles books with no clear chapter structure.
"""

import re
from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class BookChunk:
    """Represents a chunk of a book"""
    number: int
    title: str
    content: str
    word_count: int


def split_by_headers(text: str, header_level: int = 2) -> List[BookChunk]:
    """Split book text into chunks at Markdown header boundaries.

    Finds all headers at the given level and splits the text so each chunk
    starts with its header and ends just before the next one.

    Args:
        text: Full book text in Markdown format.
        header_level: Markdown header level to split on (default: 2 = ##).

    Returns:
        List of BookChunk objects. Empty list if no headers found.
    """
    pattern = f'^{"#" * header_level}\\s+(.+)$'
    chunks = []
    chunk_positions = []

    for match in re.finditer(pattern, text, re.MULTILINE):
        title = match.group(1).strip()
        position = match.start()
        chunk_positions.append((title, position))

    if not chunk_positions:
        return []

    for i, (title, start_pos) in enumerate(chunk_positions):
        end_pos = chunk_positions[i + 1][1] if i < len(chunk_positions) - 1 else len(text)
        content = text[start_pos:end_pos].strip()
        word_count = len(content.split())

        chunks.append(BookChunk(
            number=i + 1,
            title=title,
            content=content,
            word_count=word_count
        ))

    return chunks


def split_by_word_count(
    text: str,
    target_words_per_chunk: int = 10000,
    book_title: str = "Book"
) -> List[BookChunk]:
    """
    Split book into chunks of approximately equal word count.
    Tries to break at paragraph boundaries.

    Args:
        text: The book text
        target_words_per_chunk: Target words per chunk
        book_title: Title for naming chunks

    Returns:
        List of BookChunk objects
    """
    # Split into paragraphs (double newline)
    paragraphs = re.split(r'\n\n+', text)

    chunks = []
    current_chunk = []
    current_word_count = 0
    chunk_number = 1

    for para in paragraphs:
        para_words = len(para.split())

        # If adding this paragraph exceeds target, save current chunk
        if current_word_count > 0 and current_word_count + para_words > target_words_per_chunk:
            # Save current chunk
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append(BookChunk(
                number=chunk_number,
                title=f"{book_title} - Part {chunk_number}",
                content=chunk_content,
                word_count=current_word_count
            ))

            # Start new chunk
            chunk_number += 1
            current_chunk = []
            current_word_count = 0

        current_chunk.append(para)
        current_word_count += para_words

    # Add final chunk
    if current_chunk:
        chunk_content = '\n\n'.join(current_chunk)
        chunks.append(BookChunk(
            number=chunk_number,
            title=f"{book_title} - Part {chunk_number}",
            content=chunk_content,
            word_count=current_word_count
        ))

    return chunks


def analyze_and_split(
    input_file: str,
    output_dir: str = None,
    words_per_chunk: int = 10000
) -> List[BookChunk]:
    """
    Analyze book and split using best strategy.

    Args:
        input_file: Path to book file
        output_dir: Output directory (creates 'chunks/' if None)
        words_per_chunk: Target words per chunk if splitting by size

    Returns:
        List of BookChunk objects
    """
    # Read file
    print(f"Reading: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    input_path = Path(input_file)
    book_title = input_path.stem

    total_words = len(text.split())
    total_chars = len(text)

    print(f"Book: {book_title}")
    print(f"Size: {total_chars:,} characters, {total_words:,} words\n")

    # Try to split by headers first
    print("Analyzing structure...")
    chunks = None

    for level in [1, 2, 3]:
        test_chunks = split_by_headers(text, level)
        if test_chunks and len(test_chunks) >= 3:  # At least 3 chapters
            print(f"Found {len(test_chunks)} chapters at H{level} level")
            chunks = test_chunks
            break

    # If no good header structure, split by word count
    if not chunks:
        print(f"No chapter structure found. Splitting by word count ({words_per_chunk} words/chunk)")
        chunks = split_by_word_count(text, words_per_chunk, book_title)

    # Create output directory
    if output_dir is None:
        output_dir = input_path.parent / "chunks"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save chunks
    print(f"\nSaving {len(chunks)} chunks to: {output_dir}/\n")

    # Save manifest
    manifest_path = output_dir / "chunks_manifest.txt"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(f"Book: {book_title}\n")
        f.write(f"Total chunks: {len(chunks)}\n")
        f.write(f"Total words: {total_words:,}\n")
        f.write(f"Total characters: {total_chars:,}\n")
        f.write("\n" + "="*60 + "\n\n")

        for chunk in chunks:
            f.write(f"Chunk {chunk.number}: {chunk.title}\n")
            f.write(f"  Words: {chunk.word_count:,}\n")
            f.write(f"  File: chunk_{chunk.number:03d}.md\n")
            f.write("\n")

    print(f"Saved manifest: {manifest_path}\n")

    # Save each chunk
    for chunk in chunks:
        filename = f"chunk_{chunk.number:03d}.md"
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            # Add title header
            f.write(f"# {chunk.title}\n\n")
            f.write(chunk.content)

        print(f"  [{chunk.number:3d}] {filename:20s} - {chunk.word_count:6,} words - {chunk.title[:40]}")

    print(f"\n{'='*60}")
    print(f"SPLITTING COMPLETE")
    print(f"{'='*60}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Output directory: {output_dir}")
    print(f"Average words/chunk: {total_words // len(chunks):,}")

    return chunks


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python local_reader_smart_splitter.py <input_file> [words_per_chunk]")
        print("\nExample:")
        print("  python local_reader_smart_splitter.py books/crime_punishment/book.md")
        print("  python local_reader_smart_splitter.py books/crime_punishment/book.md 5000")
        print("\nThis will:")
        print("  1. Analyze the book structure")
        print("  2. Split by chapters (if found) or by word count")
        print("  3. Create a 'chunks/' directory with individual files")
        print("  4. Generate a manifest file")
        sys.exit(1)

    input_file = sys.argv[1]
    words_per_chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 10000

    analyze_and_split(input_file, words_per_chunk=words_per_chunk)


if __name__ == "__main__":
    main()
