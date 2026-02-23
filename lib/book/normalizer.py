#!/usr/bin/env python3
"""
Markdown Normalizer - Clean and standardize markdown formatting

This module provides the single source of truth for markdown cleanup.
All books should be normalized immediately after download/import to ensure
consistent formatting across the entire project.

Key normalizations:
1. Remove markdown anchor tags {#...}
2. Remove HTML id attributes
3. Standardize chapter headers
4. Normalize whitespace
5. Convert Roman numerals to Arabic in chapter titles

Usage:
    from markdown_normalizer import normalize_markdown

    clean_text = normalize_markdown(dirty_text)
"""

import re
from typing import Dict, List, Tuple


class MarkdownNormalizer:
    """Normalize markdown files to consistent format."""

    # Roman numeral conversion table
    ROMAN_TO_ARABIC = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
        'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
        'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25,
        'XXVI': 26, 'XXVII': 27, 'XXVIII': 28, 'XXIX': 29, 'XXX': 30,
        'XXXI': 31, 'XXXII': 32, 'XXXIII': 33, 'XXXIV': 34, 'XXXV': 35,
        'XL': 40, 'L': 50, 'LX': 60, 'LXX': 70, 'LXXX': 80, 'XC': 90, 'C': 100
    }

    def __init__(self, verbose: bool = False):
        """
        Initialize normalizer.

        Args:
            verbose: Print transformation details
        """
        self.verbose = verbose
        self.transformations = []

    def _log_transform(self, transform_type: str, before: str, after: str):
        """Log a transformation for debugging."""
        if before != after:
            self.transformations.append({
                'type': transform_type,
                'before': before[:100],  # First 100 chars
                'after': after[:100]
            })
            if self.verbose:
                print(f"  [{transform_type}] '{before[:50]}' → '{after[:50]}'")

    def _roman_to_arabic(self, roman: str) -> int:
        """
        Convert Roman numeral to Arabic number.

        Args:
            roman: Roman numeral string

        Returns:
            Arabic number, or None if not a valid Roman numeral
        """
        roman = roman.upper().strip()
        return self.ROMAN_TO_ARABIC.get(roman)

    def _strip_anchor_tags(self, text: str) -> str:
        """
        Remove markdown anchor tags like {#chapter-1}.

        Args:
            text: Text containing anchor tags

        Returns:
            Text with anchor tags removed
        """
        # Pattern: {#anything} at end of line
        cleaned = re.sub(r'\s*\{#[^}]+\}\s*', ' ', text)

        # Pattern: <a id="..."></a> or <a name="..."></a>
        cleaned = re.sub(r'<a\s+(id|name)="[^"]*"></a>', '', cleaned)

        # Pattern: <span id="..."></span>
        cleaned = re.sub(r'<span\s+id="[^"]*"></span>', '', cleaned)

        self._log_transform('strip_anchors', text, cleaned)
        return cleaned

    def _normalize_chapter_header(self, line: str) -> str:
        """
        Normalize chapter headers to consistent format.

        Transforms:
        - "## 1. Title" → "## Chapter 1: Title"
        - "## I. Title" → "## Chapter 1: Title"
        - "## Chapter 1: Title {#anchor}" → "## Chapter 1: Title"

        Args:
            line: Single line of text

        Returns:
            Normalized line
        """
        original = line
        line = line.strip()

        # First, remove any anchor tags
        line = self._strip_anchor_tags(line)

        # Pattern 1: "## 1. Title" or "## 1: Title" → "## Chapter 1: Title"
        match = re.match(r'^(#{1,6})\s*(\d+)[.:]?\s*(.+)$', line)
        if match:
            hashes = match.group(1)
            chapter_num = match.group(2)
            title = match.group(3).strip()

            # Don't transform if it already says "Chapter"
            if not re.match(r'^(Chapter|CHAPTER|Part|PART)', title, re.IGNORECASE):
                normalized = f"{hashes} Chapter {chapter_num}: {title}"
                self._log_transform('normalize_numbered_header', original, normalized)
                return normalized

        # Pattern 2: "## I. Title" or "## I: Title" → "## Chapter 1: Title"
        match = re.match(r'^(#{1,6})\s*([IVXLCDM]+)[.:]?\s+(.+)$', line)
        if match:
            hashes = match.group(1)
            roman = match.group(2)
            title = match.group(3).strip()

            # Check if it's a valid Roman numeral
            arabic = self._roman_to_arabic(roman)
            if arabic and not re.match(r'^(Chapter|CHAPTER|Part|PART)', title, re.IGNORECASE):
                normalized = f"{hashes} Chapter {arabic}: {title}"
                self._log_transform('normalize_roman_header', original, normalized)
                return normalized

        # Pattern 3: Already has "Chapter" but needs cleanup
        # "## Chapter 1 : Title" → "## Chapter 1: Title" (fix spacing)
        match = re.match(r'^(#{1,6})\s*(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+)\s*:?\s*(.*)$', line, re.IGNORECASE)
        if match:
            hashes = match.group(1)
            keyword = match.group(2).capitalize()  # Normalize to "Chapter"
            num = match.group(3)
            title = match.group(4).strip()

            # Convert Roman to Arabic if needed
            if re.match(r'^[IVXLCDM]+$', num):
                arabic = self._roman_to_arabic(num)
                if arabic:
                    num = str(arabic)

            if title:
                normalized = f"{hashes} {keyword} {num}: {title}"
            else:
                normalized = f"{hashes} {keyword} {num}"

            if normalized != line:
                self._log_transform('cleanup_chapter_header', original, normalized)
                return normalized

        # If no transformations matched, just remove anchors
        if line != original.strip():
            self._log_transform('strip_anchors_only', original, line)

        return line

    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text.

        - Remove trailing whitespace from lines
        - Convert 3+ newlines to 2 newlines
        - Ensure single space after punctuation

        Args:
            text: Text to normalize

        Returns:
            Text with normalized whitespace
        """
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Convert 3+ consecutive newlines to exactly 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Ensure exactly one space after sentence-ending punctuation (. ! ?)
        # But not for abbreviations (e.g., "Mr. Smith")
        # This is a heuristic - only fix obvious cases
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)

        return text

    def normalize(self, markdown: str) -> str:
        """
        Normalize markdown text.

        Performs all normalization steps:
        1. Strip anchor tags throughout document
        2. Normalize chapter headers
        3. Normalize whitespace

        Args:
            markdown: Original markdown text

        Returns:
            Normalized markdown text
        """
        self.transformations = []

        if self.verbose:
            print("📝 Normalizing markdown...")

        # Step 1: Process line by line
        lines = markdown.split('\n')
        normalized_lines = []

        for line in lines:
            # Check if this looks like a header that needs normalization
            if re.match(r'^#{1,6}\s+', line):
                normalized_line = self._normalize_chapter_header(line)
            else:
                # Just strip anchor tags from non-headers
                normalized_line = self._strip_anchor_tags(line)

            normalized_lines.append(normalized_line)

        result = '\n'.join(normalized_lines)

        # Step 2: Normalize whitespace
        result = self._normalize_whitespace(result)

        if self.verbose:
            print(f"✓ Applied {len(self.transformations)} transformations")

        return result.strip()


def normalize_markdown(markdown: str, verbose: bool = False) -> str:
    """
    Normalize markdown text (convenience function).

    Args:
        markdown: Original markdown text
        verbose: Print transformation details

    Returns:
        Normalized markdown text
    """
    normalizer = MarkdownNormalizer(verbose=verbose)
    return normalizer.normalize(markdown)


def main():
    """Command-line interface for testing."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Markdown Normalizer - Clean and standardize markdown formatting")
        print("\nUsage:")
        print("  python markdown_normalizer.py <input.md> [output.md]")
        print("\nIf output.md is not specified, overwrites input.md")
        print("\nExample:")
        print("  python markdown_normalizer.py books/call_cthulhu/book.md")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else input_file

    if not input_file.exists():
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)

    # Read input
    print(f"📖 Reading: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        original = f.read()

    # Normalize
    print("🔧 Normalizing...")
    normalized = normalize_markdown(original, verbose=True)

    # Check if changes were made
    if normalized == original:
        print("✓ No changes needed - file is already normalized")
        sys.exit(0)

    # Backup original if overwriting
    if output_file == input_file:
        backup = input_file.with_suffix('.md.backup')
        print(f"💾 Creating backup: {backup}")
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(original)

    # Save normalized version
    print(f"💾 Saving: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(normalized)

    # Show stats
    print("\n" + "="*60)
    print("✓ NORMALIZATION COMPLETE")
    print("="*60)
    print(f"Original size:   {len(original):,} chars")
    print(f"Normalized size: {len(normalized):,} chars")
    print(f"Difference:      {len(normalized) - len(original):+,} chars")
    print()


if __name__ == "__main__":
    main()
