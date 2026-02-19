#!/usr/bin/env python3
"""
Book Preprocessor - Analyze and prepare books for translation and audio production.

This script:
1. Detects table of contents and chapter structure
2. Validates chapter completeness
3. Normalizes chapter markers
4. Generates preprocessing report
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import json


class ChapterDetector:
    """Detect and analyze chapter structure in books.

    DEPRECATED: For chapter detection, use BookProcessor from book_processor.py instead.
    BookProcessor has 14+ patterns and is the canonical source of truth for chapter detection.
    ChapterDetector is retained only for its TOC detection (detect_toc) and sequence
    validation (validate_chapter_sequence) methods.
    """

    def __init__(self, text: str, filename: str = ""):
        self.text = text
        self.filename = filename
        self.chapters = []
        self.toc_chapters = []

    def detect_toc(self) -> List[Dict]:
        """
        Detect table of contents entries.

        Returns:
            List of TOC entries with chapter numbers and titles
        """
        toc_entries = []
        lines = self.text.split('\n')

        # Pattern 1: Markdown TOC links like "1. [Chapter 1: Title](#anchor)"
        pattern1 = re.compile(r'^\s*(\d+)\.\s*\[([^\]]+)\]\([^)]+\)', re.IGNORECASE)

        # Pattern 2: Simple numbered list "1. Chapter 1: Title"
        pattern2 = re.compile(r'^\s*(\d+)\.\s*(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+):?\s*(.+)', re.IGNORECASE)

        # Pattern 3: Roman numerals in TOC
        pattern3 = re.compile(r'^\s*(\d+)\.\s*\[?([IVXLCDM]+)\.?\s*([^\]]*)\]?', re.IGNORECASE)

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Try pattern 1 (markdown TOC)
            match = pattern1.match(line_stripped)
            if match:
                num = int(match.group(1))
                title = match.group(2)
                toc_entries.append({
                    'number': num,
                    'title': title,
                    'line': i + 1,
                    'type': 'markdown_toc'
                })
                continue

            # Try pattern 2 (simple list)
            match = pattern2.match(line_stripped)
            if match:
                num = int(match.group(1))
                chapter_type = match.group(2)
                chapter_num = match.group(3)
                title = match.group(4).strip()
                toc_entries.append({
                    'number': num,
                    'title': f"{chapter_type} {chapter_num}: {title}",
                    'line': i + 1,
                    'type': 'simple_list'
                })
                continue

            # Try pattern 3 (Roman numerals)
            match = pattern3.match(line_stripped)
            if match:
                num = int(match.group(1))
                roman = match.group(2)
                title = match.group(3).strip()
                toc_entries.append({
                    'number': num,
                    'title': f"{roman}. {title}" if title else f"{roman}.",
                    'line': i + 1,
                    'type': 'roman_toc'
                })
                continue

        self.toc_chapters = toc_entries
        return toc_entries

    def detect_chapters_in_content(self) -> List[Dict]:
        """
        Detect actual chapter markers in the content (not TOC).

        Returns:
            List of chapter markers with positions
        """
        chapters = []
        lines = self.text.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Strip "end chapter" artifacts from Gutenberg HTML conversion
            line_stripped = re.sub(r'^end chapter', '', line_stripped, flags=re.IGNORECASE).strip()
            char_pos = len('\n'.join(lines[:i]))

            # Roman numeral pattern (I., II., III., etc.) - standalone
            roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', line_stripped)
            if roman_match:
                chapters.append({
                    'number': len(chapters) + 1,
                    'marker': line_stripped,
                    'line': i + 1,
                    'char_pos': char_pos,
                    'type': 'roman_standalone'
                })
                continue

            # Markdown header with Roman numeral and title (## I. THE EVE OF THE WAR.)
            # Common in Gutenberg books that don't use the word "Chapter"
            roman_title_match = re.match(r'^#{1,6}\s+([IVXLCDM]+)\.\s+(.+)', line_stripped)
            if roman_title_match:
                chapters.append({
                    'number': len(chapters) + 1,
                    'marker': line_stripped,
                    'line': i + 1,
                    'char_pos': char_pos,
                    'type': 'markdown_roman_title'
                })
                continue

            # Alice in Wonderland style - chapters without line breaks (## CHAPTER I.Title)
            # This pattern catches multiple chapters on a single line
            # Skip TOC entries that have markdown links [CHAPTER I.](#anchor)
            alice_pattern = re.compile(r'(#{1,6}\s*)?(CHAPTER|Chapter)\s+([IVXLCDM]+|[0-9]+)\.([^#\[\n]+)', re.IGNORECASE)
            alice_matches = list(alice_pattern.finditer(line_stripped))
            if alice_matches:
                for match in alice_matches:
                    # Skip if this is a TOC link (preceded by '[' or followed by ']')
                    match_start = match.start()
                    match_end = match.end()

                    # Check if preceded by '[' (TOC link)
                    if match_start > 0 and line_stripped[match_start - 1] == '[':
                        continue

                    # Check if this looks like a markdown link (has ](#) pattern nearby)
                    surrounding = line_stripped[max(0, match_start - 10):min(len(line_stripped), match_end + 20)]
                    if '](#' in surrounding and '[CHAPTER' in surrounding:
                        continue

                    chapter_num = match.group(3)  # Roman numeral or number
                    chapter_title = match.group(4).strip() if match.group(4) else ""
                    full_marker = f"CHAPTER {chapter_num}. {chapter_title}"

                    chapters.append({
                        'number': len(chapters) + 1,
                        'marker': full_marker,
                        'line': i + 1,
                        'char_pos': char_pos + match.start(),
                        'type': 'alice_style'
                    })
                continue

            # Markdown header patterns: # Chapter 1, ## Part 2, etc.
            header_match = re.match(r'^(#{1,6})\s+(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+):?\s*(.*)', line_stripped, re.IGNORECASE)
            if header_match:
                level = len(header_match.group(1))
                chapter_type = header_match.group(2)
                chapter_num = header_match.group(3)
                title = header_match.group(4).strip()
                full_marker = f"{chapter_type} {chapter_num}" + (f": {title}" if title else "")

                chapters.append({
                    'number': len(chapters) + 1,
                    'marker': full_marker,
                    'line': i + 1,
                    'char_pos': char_pos,
                    'type': f'markdown_h{level}'
                })
                continue

        self.chapters = chapters
        return chapters

    def roman_to_int(self, roman: str) -> int:
        """Convert Roman numeral to integer."""
        roman = roman.upper().rstrip('.')
        values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        total = 0
        prev = 0

        for char in reversed(roman):
            value = values.get(char, 0)
            if value < prev:
                total -= value
            else:
                total += value
            prev = value

        return total

    def validate_chapter_sequence(self) -> Dict:
        """
        Validate that chapters are sequential and complete.

        Returns:
            Dict with validation results
        """
        if not self.chapters:
            return {
                'valid': False,
                'error': 'No chapters detected',
                'missing': [],
                'duplicates': []
            }

        # Extract chapter numbers from markers
        chapter_numbers = []
        for ch in self.chapters:
            marker = ch['marker']

            # Try to extract number from Roman numeral
            roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', marker)
            if roman_match:
                num = self.roman_to_int(marker)
                chapter_numbers.append(num)
                continue

            # Try to extract from "Chapter N" format
            num_match = re.search(r'(\d+)', marker)
            if num_match:
                chapter_numbers.append(int(num_match.group(1)))
                continue

            # Try Roman numeral in other formats
            roman_match2 = re.search(r'\b([IVXLCDM]+)\b', marker, re.IGNORECASE)
            if roman_match2:
                num = self.roman_to_int(roman_match2.group(1))
                chapter_numbers.append(num)

        if not chapter_numbers:
            return {
                'valid': False,
                'error': 'Could not extract chapter numbers',
                'missing': [],
                'duplicates': []
            }

        # Check for sequential chapters
        expected = list(range(1, max(chapter_numbers) + 1))
        missing = [n for n in expected if n not in chapter_numbers]
        duplicates = [n for n in set(chapter_numbers) if chapter_numbers.count(n) > 1]

        return {
            'valid': len(missing) == 0 and len(duplicates) == 0,
            'total_found': len(self.chapters),
            'expected_total': max(chapter_numbers) if chapter_numbers else 0,
            'missing': missing,
            'duplicates': duplicates,
            'chapter_numbers': chapter_numbers
        }

    def generate_report(self) -> str:
        """Generate a human-readable preprocessing report."""

        report = []
        report.append("="*70)
        report.append("BOOK PREPROCESSING REPORT")
        report.append("="*70)
        report.append(f"File: {self.filename}")
        report.append(f"Size: {len(self.text):,} characters, {len(self.text.split()):,} words")
        report.append("")

        # Table of Contents
        toc = self.detect_toc()
        report.append(f"TABLE OF CONTENTS: {len(toc)} entries found")
        if toc:
            for entry in toc[:10]:  # Show first 10
                report.append(f"  {entry['number']:2d}. {entry['title']} (line {entry['line']})")
            if len(toc) > 10:
                report.append(f"  ... and {len(toc) - 10} more")
        else:
            report.append("  ⚠️  No table of contents detected")
        report.append("")

        # Actual Chapters
        chapters = self.detect_chapters_in_content()
        report.append(f"CHAPTERS IN CONTENT: {len(chapters)} found")
        if chapters:
            for ch in chapters[:10]:  # Show first 10
                report.append(f"  {ch['number']:2d}. {ch['marker']} (line {ch['line']}, type: {ch['type']})")
            if len(chapters) > 10:
                report.append(f"  ... and {len(chapters) - 10} more")
        else:
            report.append("  ⚠️  No chapter markers detected in content")
        report.append("")

        # Validation
        validation = self.validate_chapter_sequence()
        report.append("VALIDATION:")

        if validation['valid']:
            report.append(f"  ✅ All {validation['total_found']} chapters present and sequential")
        else:
            if 'error' in validation:
                report.append(f"  ❌ {validation['error']}")
            else:
                report.append(f"  ❌ Chapter sequence incomplete")
                report.append(f"     Found: {validation['total_found']} chapters")
                report.append(f"     Expected: {validation['expected_total']} chapters")

                if validation['missing']:
                    report.append(f"     Missing: {validation['missing']}")

                if validation['duplicates']:
                    report.append(f"     Duplicates: {validation['duplicates']}")

        # Compare TOC vs Content
        if toc and chapters:
            report.append("")
            report.append("TOC vs CONTENT:")
            if len(toc) == len(chapters):
                report.append(f"  ✅ TOC and content match ({len(toc)} chapters)")
            else:
                report.append(f"  ⚠️  Mismatch: TOC has {len(toc)} entries, content has {len(chapters)} chapters")

        report.append("")
        report.append("="*70)

        return "\n".join(report)


def preprocess_book(file_path: str, output_report: bool = True):
    """
    Preprocess a book file and generate analysis report.

    Args:
        file_path: Path to the markdown file
        output_report: If True, save report to file
    """
    path = Path(file_path)

    if not path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    # Read file
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Analyze
    detector = ChapterDetector(text, path.name)
    report = detector.generate_report()

    # Print report
    print(report)

    # Save report
    if output_report:
        report_path = path.parent / f"{path.stem}_preprocessing_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_path}")

    # Save JSON data
    json_path = path.parent / f"{path.stem}_chapter_data.json"
    data = {
        'filename': path.name,
        'toc_entries': detector.toc_chapters,
        'chapters': detector.chapters,
        'validation': detector.validate_chapter_sequence()
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"📊 Chapter data saved to: {json_path}")

    return detector


def main():
    if len(sys.argv) < 2:
        print("Usage: python book_preprocessor.py <markdown_file>")
        print("\nExample:")
        print("  python book_preprocessor.py books/mybook/book.md")
        sys.exit(1)

    file_path = sys.argv[1]
    preprocess_book(file_path)


if __name__ == "__main__":
    main()
