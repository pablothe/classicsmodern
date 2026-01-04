#!/usr/bin/env python3
"""
Chapter Splitter for Local Reader

Splits large book files into individual chapters based on Markdown headers.
Creates a directory structure for organized translation.
"""

import re
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Chapter:
    """Represents a book chapter"""
    number: int
    title: str
    content: str
    header_level: int  # Number of # symbols
    start_pos: int
    end_pos: int


class BookChapterSplitter:
    """Splits books into chapters based on Markdown structure"""

    def __init__(self, min_header_level: int = 1, max_header_level: int = 2):
        """
        Initialize the chapter splitter.

        Args:
            min_header_level: Minimum header level to consider as chapter (1 = #)
            max_header_level: Maximum header level to consider as chapter (2 = ##)
        """
        self.min_header_level = min_header_level
        self.max_header_level = max_header_level

    def analyze_structure(self, text: str) -> dict:
        """
        Analyze the book structure to determine best chapter splitting strategy.

        Args:
            text: The book text

        Returns:
            Dictionary with analysis results
        """
        # Count headers at each level
        header_counts = {}
        for level in range(1, 7):
            pattern = f'^{"#" * level}\\s+(.+)$'
            headers = re.findall(pattern, text, re.MULTILINE)
            header_counts[level] = len(headers)

        # Find all headers with positions
        all_headers = []
        pattern = r'^(#{1,6})\s+(.+)$'
        for match in re.finditer(pattern, text, re.MULTILINE):
            level = len(match.group(1))
            title = match.group(2).strip()
            position = match.start()
            all_headers.append((level, title, position))

        return {
            'header_counts': header_counts,
            'total_headers': sum(header_counts.values()),
            'all_headers': all_headers,
            'total_chars': len(text),
            'recommended_level': self._recommend_chapter_level(header_counts)
        }

    def _recommend_chapter_level(self, header_counts: dict) -> int:
        """
        Recommend the best header level to use for chapter splitting.

        Args:
            header_counts: Dictionary of header counts by level

        Returns:
            Recommended header level
        """
        # Prefer level with 10-100 headers (good chapter size)
        for level in [1, 2, 3]:
            count = header_counts.get(level, 0)
            if 10 <= count <= 100:
                return level

        # Otherwise, use the level with most headers (but not too many)
        for level in [1, 2, 3]:
            count = header_counts.get(level, 0)
            if count > 0:
                return level

        return 1  # Default to H1

    def split_into_chapters(
        self,
        text: str,
        chapter_header_level: int = None
    ) -> List[Chapter]:
        """
        Split text into chapters based on headers.

        Args:
            text: The book text
            chapter_header_level: Header level to use for chapters (auto-detect if None)

        Returns:
            List of Chapter objects
        """
        if chapter_header_level is None:
            analysis = self.analyze_structure(text)
            chapter_header_level = analysis['recommended_level']
            print(f"Auto-detected chapter level: H{chapter_header_level}")

        # Find all chapter headers
        pattern = f'^{"#" * chapter_header_level}\\s+(.+)$'
        chapters = []
        chapter_positions = []

        for match in re.finditer(pattern, text, re.MULTILINE):
            title = match.group(1).strip()
            position = match.start()
            chapter_positions.append((title, position))

        # Extract content for each chapter
        for i, (title, start_pos) in enumerate(chapter_positions):
            # Determine end position
            if i < len(chapter_positions) - 1:
                end_pos = chapter_positions[i + 1][1]
            else:
                end_pos = len(text)

            # Extract content
            content = text[start_pos:end_pos].strip()

            chapters.append(Chapter(
                number=i + 1,
                title=title,
                content=content,
                header_level=chapter_header_level,
                start_pos=start_pos,
                end_pos=end_pos
            ))

        return chapters

    def save_chapters_to_directory(
        self,
        chapters: List[Chapter],
        output_dir: Path,
        book_title: str = "book"
    ):
        """
        Save each chapter to a separate file in a directory.

        Args:
            chapters: List of Chapter objects
            output_dir: Directory to save chapters
            book_title: Base name for the book
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save a manifest file
        manifest_path = output_dir / "chapters_manifest.txt"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(f"Book: {book_title}\n")
            f.write(f"Total chapters: {len(chapters)}\n")
            f.write(f"Chapter header level: H{chapters[0].header_level if chapters else 'N/A'}\n")
            f.write("\n" + "="*60 + "\n\n")

            for chapter in chapters:
                word_count = len(chapter.content.split())
                char_count = len(chapter.content)
                f.write(f"Chapter {chapter.number}: {chapter.title}\n")
                f.write(f"  Words: {word_count:,}\n")
                f.write(f"  Characters: {char_count:,}\n")
                f.write(f"  File: chapter_{chapter.number:03d}.md\n")
                f.write("\n")

        print(f"Saved manifest to: {manifest_path}")

        # Save each chapter
        for chapter in chapters:
            filename = f"chapter_{chapter.number:03d}.md"
            filepath = output_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(chapter.content)

            word_count = len(chapter.content.split())
            print(f"  Saved: {filename} ({word_count:,} words) - {chapter.title[:50]}")

        print(f"\nAll {len(chapters)} chapters saved to: {output_dir}")


def main():
    """Main function for command-line usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python local_reader_chapter_splitter.py <input_file> [chapter_level]")
        print("\nExample:")
        print("  python local_reader_chapter_splitter.py books/crime_punishment/book.md")
        print("  python local_reader_chapter_splitter.py books/crime_punishment/book.md 2")
        print("\nThis will:")
        print("  1. Analyze the book structure")
        print("  2. Split into chapters (auto-detect or use specified level)")
        print("  3. Create a 'chapters/' directory with individual chapter files")
        print("  4. Generate a manifest file with chapter info")
        sys.exit(1)

    input_file = sys.argv[1]
    chapter_level = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # Read the book
    print(f"Reading: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"File size: {len(text):,} characters\n")

    # Initialize splitter
    splitter = BookChapterSplitter()

    # Analyze structure
    print("Analyzing book structure...")
    analysis = splitter.analyze_structure(text)

    print("\nHeader Analysis:")
    for level in range(1, 4):
        count = analysis['header_counts'].get(level, 0)
        if count > 0:
            print(f"  H{level} (#{'#' * (level-1)}): {count} headers")

    print(f"\nRecommended chapter level: H{analysis['recommended_level']}")

    if chapter_level:
        print(f"Using user-specified level: H{chapter_level}")
    else:
        chapter_level = analysis['recommended_level']

    # Show first few headers at the selected level
    print(f"\nFirst chapters (H{chapter_level}):")
    headers_at_level = [h for h in analysis['all_headers'] if h[0] == chapter_level]
    for i, (level, title, pos) in enumerate(headers_at_level[:10], 1):
        print(f"  {i}. {title}")

    if len(headers_at_level) > 10:
        print(f"  ... and {len(headers_at_level) - 10} more")

    # Ask for confirmation
    print(f"\nThis will split the book into {len(headers_at_level)} chapters.")
    response = input("Proceed? (y/n): ").strip().lower()

    if response != 'y':
        print("Aborted.")
        sys.exit(0)

    # Split into chapters
    print("\nSplitting into chapters...")
    chapters = splitter.split_into_chapters(text, chapter_level)

    # Determine output directory
    input_path = Path(input_file)
    output_dir = input_path.parent / "chapters"

    # Save chapters
    print(f"\nSaving chapters to: {output_dir}/")
    book_title = input_path.stem
    splitter.save_chapters_to_directory(chapters, output_dir, book_title)

    print("\n" + "="*60)
    print("CHAPTER SPLITTING COMPLETE")
    print("="*60)
    print(f"Chapters saved: {len(chapters)}")
    print(f"Output directory: {output_dir}")
    print(f"Manifest file: {output_dir}/chapters_manifest.txt")


if __name__ == "__main__":
    main()
