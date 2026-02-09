#!/usr/bin/env python3
"""
Book Processor - Unified preprocessing for all book formats.

This is the single source of truth for book structure. It:
1. Strips Gutenberg boilerplate
2. Detects chapters with multiple patterns
3. Validates and fixes chapter sequences
4. Generates table of contents
5. Creates a manifest for downstream processes
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import argparse


@dataclass
class Chapter:
    """Represents a single chapter with all metadata."""
    number: int
    title: str
    marker: str  # Original marker from text (e.g., "Chapter 1:", "I.")
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    content: str
    word_count: int
    detection_type: str  # Which pattern detected this
    checkpoints: Dict = field(default_factory=lambda: {
        'translation': None,
        'audio': None
    })


@dataclass
class BookManifest:
    """Complete book structure and metadata."""
    version: str = "2.0"
    metadata: Dict = field(default_factory=dict)
    processing: Dict = field(default_factory=dict)
    chapters: List[Chapter] = field(default_factory=list)
    toc_markdown: str = ""
    original_file: str = ""
    processed_at: str = ""
    processing_log: List[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert chapter objects to dicts
        data['chapters'] = [asdict(ch) for ch in self.chapters]
        return data

    def save(self, output_path: Path):
        """Save manifest to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, manifest_path: Path):
        """Load manifest from JSON file."""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct Chapter objects
        chapters = []
        for ch_data in data.get('chapters', []):
            chapters.append(Chapter(**ch_data))

        data['chapters'] = chapters
        return cls(**data)


class BookProcessor:
    """Main processor for book structure extraction and cleaning."""

    # Comprehensive chapter detection patterns (order matters - most specific first)
    CHAPTER_PATTERNS = [
        # Roman numerals standalone (I., II., III., etc.)
        (r'^(X{0,3})(IX|IV|V?I{0,3})\.\s*$', 'roman_standalone'),

        # Markdown headers with chapter keywords
        (r'^#{1,6}\s+(Chapter|CHAPTER|Part|PART|Book|BOOK|Section|SECTION)\s+(\d+|[IVXLCDM]+):?\s*(.*)', 'markdown_chapter'),

        # Alice in Wonderland style - chapters without line breaks (## CHAPTER I.Title)
        (r'(#{1,6}\s*)?(CHAPTER|Chapter)\s+([IVXLCDM]+|[0-9]+)\.([^#\n]+)', 'alice_style'),

        # Numbered lists (1. Title or 1. Chapter 1)
        (r'^(\d+)\.\s+(.+)', 'numbered_list'),

        # Chapter with word numbers (Chapter One, Part Two, etc.)
        (r'^(Chapter|Part|Book|Section)\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)', 'word_number'),

        # Ordinal chapters (First Chapter, Second Part, etc.)
        (r'^(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\s+(Chapter|Part|Book)', 'ordinal'),

        # Act/Scene for plays (Act I, Scene 1)
        (r'^(Act|ACT|Scene|SCENE)\s+([IVXLCDM]+|\d+)', 'act_scene'),

        # Epistolary formats (Letter I, Entry 1, Day 1)
        (r'^(Letter|Entry|Day|Night|Journal|Diary)\s+(\d+|[IVXLCDM]+)', 'epistolary'),

        # Special sections
        (r'^(Prologue|Epilogue|Introduction|Preface|Foreword|Interlude|Conclusion|Appendix)', 'special_section'),

        # Academic sections (Section 1.2.3)
        (r'^Section\s+\d+(\.\d+)*', 'academic_section'),

        # Story/Tale format (Story I: Title, Tale 1)
        (r'^(Story|Tale|Adventure|Case)\s+([IVXLCDM]+|\d+):?\s*(.*)', 'story_format'),

        # Winnie the Pooh style ("In Which...")
        (r'^In\s+Which\s+[A-Z]', 'winnie_pooh_style'),

        # Volume + Chapter (Vol. I, Chapter 1)
        (r'^(Vol\.|Volume)\s+([IVXLCDM]+|\d+),?\s+(Chapter|Part)\s+(\d+|[IVXLCDM]+)', 'volume_chapter'),
    ]

    # Gutenberg markers to detect and remove
    GUTENBERG_MARKERS = [
        r'\*\*\* START OF (THIS|THE) PROJECT GUTENBERG',
        r'\*\*\* END OF (THIS|THE) PROJECT GUTENBERG',
        r'End of (the )?Project Gutenberg',
        r'This eBook is for the use of anyone',
        r'Project Gutenberg-tm',
        r'PROJECT GUTENBERG',
        r'http://www\.gutenberg\.(org|net)',
        r'Produced by .+',
        r'Transcriber\'s Note:',
        r'\[Transcriber\'s Note:',
        r'Updated editions will replace',
    ]

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.log = []

    def process(self, book_file: Path, auto_fix: bool = True) -> BookManifest:
        """
        Process a book file into a structured manifest.

        Args:
            book_file: Path to the book markdown/text file
            auto_fix: Whether to automatically fix issues

        Returns:
            BookManifest with complete book structure
        """
        book_file = Path(book_file)

        if not book_file.exists():
            raise FileNotFoundError(f"Book file not found: {book_file}")

        self.log_message(f"Processing: {book_file.name}")

        # Read the file
        with open(book_file, 'r', encoding='utf-8') as f:
            original_text = f.read()

        self.log_message(f"Original size: {len(original_text):,} chars")

        # Step 1: Strip Gutenberg boilerplate
        cleaned_text, gutenberg_stripped = self.strip_gutenberg(original_text)
        if gutenberg_stripped:
            chars_removed = len(original_text) - len(cleaned_text)
            self.log_message(f"Stripped {chars_removed:,} chars of Gutenberg boilerplate")

        # Step 2: Extract metadata
        metadata = self.extract_metadata(cleaned_text)
        self.log_message(f"Metadata: {metadata.get('title', 'Unknown')} by {metadata.get('author', 'Unknown')}")

        # Step 3: Detect chapters
        chapters = self.detect_chapters(cleaned_text)
        self.log_message(f"Detected {len(chapters)} chapters")

        if chapters:
            # Show chapter types distribution
            type_counts = {}
            for ch in chapters:
                type_counts[ch.detection_type] = type_counts.get(ch.detection_type, 0) + 1
            for dtype, count in type_counts.items():
                self.log_message(f"  {dtype}: {count} chapters")

        # Step 4: Validate and fix chapter sequence
        if auto_fix and chapters:
            chapters = self.fix_chapter_sequence(chapters)

        # Step 5: Generate or extract TOC
        toc_markdown = self.generate_toc(chapters)
        if toc_markdown:
            self.log_message("Generated table of contents")

        # Step 6: Create manifest
        manifest = BookManifest(
            version="2.0",
            metadata=metadata,
            processing={
                'gutenberg_stripped': gutenberg_stripped,
                'toc_generated': bool(toc_markdown),
                'chapters_fixed': auto_fix,
                'total_words': len(cleaned_text.split()),
                'total_chars': len(cleaned_text)
            },
            chapters=chapters,
            toc_markdown=toc_markdown,
            original_file=str(book_file),
            processed_at=datetime.now().isoformat(),
            processing_log=self.log.copy()
        )

        return manifest

    def strip_gutenberg(self, text: str) -> Tuple[str, bool]:
        """
        Remove Project Gutenberg headers and footers.

        Returns:
            (cleaned_text, was_stripped)
        """
        original_length = len(text)

        # Find start marker
        start_pos = 0
        for pattern in self.GUTENBERG_MARKERS[:2]:  # START markers
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Find the end of the line after the marker
                newline_pos = text.find('\n', match.end())
                if newline_pos != -1:
                    start_pos = newline_pos + 1
                else:
                    start_pos = match.end()
                break

        # Find end marker
        end_pos = len(text)
        for pattern in self.GUTENBERG_MARKERS[2:4]:  # END markers
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Find the beginning of the line before the marker
                line_start = text.rfind('\n', 0, match.start())
                if line_start != -1:
                    end_pos = line_start
                else:
                    end_pos = match.start()
                break

        # Extract the clean content
        if start_pos > 0 or end_pos < len(text):
            cleaned = text[start_pos:end_pos].strip()

            # Remove any remaining Gutenberg references
            for pattern in self.GUTENBERG_MARKERS:
                cleaned = re.sub(pattern + r'.*?\n', '', cleaned, flags=re.IGNORECASE)

            return cleaned, True

        return text, False

    def extract_metadata(self, text: str) -> Dict:
        """Extract title, author, and other metadata from text."""
        metadata = {}
        lines = text.split('\n')[:50]  # Check first 50 lines

        # Look for title (# Title or Title: format)
        for line in lines:
            # Markdown header title
            if line.startswith('# ') and not metadata.get('title'):
                metadata['title'] = line[2:].strip()
                continue

            # Title: format
            if line.lower().startswith('title:'):
                metadata['title'] = line.split(':', 1)[1].strip()
                continue

        # Look for author
        for line in lines:
            # Author: format
            if line.lower().startswith('author:'):
                metadata['author'] = line.split(':', 1)[1].strip()
                continue

            # by Author format
            if line.lower().startswith('by '):
                metadata['author'] = line[3:].strip()
                continue

            # **by Author** format (markdown bold)
            match = re.match(r'\*\*by (.+)\*\*', line, re.IGNORECASE)
            if match:
                metadata['author'] = match.group(1).strip()
                continue

        # Try to detect language from content
        metadata['language'] = self.detect_language(text)

        return metadata

    def detect_language(self, text: str) -> str:
        """Simple language detection based on common words."""
        # Sample of text for language detection
        sample = text[:5000].lower()

        # Language indicators
        languages = {
            'English': ['the', 'and', 'of', 'to', 'in', 'that', 'is', 'was'],
            'Spanish': ['el', 'la', 'de', 'que', 'en', 'los', 'las', 'por'],
            'German': ['der', 'die', 'und', 'das', 'ist', 'ein', 'eine', 'ich'],
            'French': ['le', 'de', 'la', 'et', 'les', 'des', 'que', 'dans'],
            'Latin': ['et', 'in', 'est', 'non', 'cum', 'sed', 'qui', 'quod'],
            'Italian': ['il', 'di', 'che', 'la', 'e', 'un', 'per', 'con'],
            'Russian': ['и', 'в', 'не', 'на', 'я', 'что', 'с', 'он']
        }

        scores = {}
        for lang, words in languages.items():
            score = sum(1 for word in words if f' {word} ' in sample)
            scores[lang] = score

        # Return the language with highest score
        if scores:
            best_lang = max(scores, key=scores.get)
            if scores[best_lang] > 5:  # Threshold for confidence
                return best_lang

        return 'Unknown'

    def detect_chapters(self, text: str) -> List[Chapter]:
        """
        Detect all chapters using multiple patterns.

        Returns:
            List of Chapter objects
        """
        chapters = []
        lines = text.split('\n')

        # Track which lines have been identified as chapters
        chapter_lines = set()

        # Try each pattern
        for pattern_regex, pattern_type in self.CHAPTER_PATTERNS:
            pattern = re.compile(pattern_regex, re.IGNORECASE)

            for i, line in enumerate(lines):
                if i in chapter_lines and pattern_type != 'alice_style':
                    continue  # Already identified as chapter (except alice_style can have multiple per line)

                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Special handling for alice_style - can have multiple matches on one line
                if pattern_type == 'alice_style':
                    # Use finditer to find all matches on the line
                    for match in pattern.finditer(line_stripped):
                        # Calculate character position for this specific match
                        char_pos = len('\n'.join(lines[:i])) + match.start()

                        # Extract components
                        chapter_num = match.group(3)  # Roman numeral or number
                        chapter_title = match.group(4).strip() if match.group(4) else ""

                        chapters.append({
                            'line_num': i,
                            'char_pos': char_pos,
                            'marker': match.group(0),
                            'title': chapter_title,
                            'detection_type': pattern_type
                        })
                else:
                    # Normal pattern matching
                    match = pattern.match(line_stripped)
                    if match:
                        chapter_lines.add(i)

                        # Calculate character position
                        char_pos = len('\n'.join(lines[:i]))

                        # Extract title from the match
                        title = self.extract_chapter_title(line_stripped, match, pattern_type)

                        chapters.append({
                            'line_num': i,
                            'char_pos': char_pos,
                            'marker': line_stripped,
                            'title': title,
                            'detection_type': pattern_type
                        })

        # Sort chapters by position
        chapters.sort(key=lambda x: x['line_num'])

        # Convert to Chapter objects with content
        chapter_objects = []
        for i, ch_info in enumerate(chapters):
            # Determine content boundaries
            start_line = ch_info['line_num']
            if i + 1 < len(chapters):
                end_line = chapters[i + 1]['line_num']
            else:
                end_line = len(lines)

            # Extract content (excluding the marker line itself)
            content_lines = lines[start_line + 1:end_line]
            content = '\n'.join(content_lines).strip()

            # Calculate positions
            start_char = ch_info['char_pos']
            end_char = start_char + len('\n'.join(lines[start_line:end_line]))

            chapter_objects.append(Chapter(
                number=i + 1,
                title=ch_info['title'],
                marker=ch_info['marker'],
                start_line=start_line,
                end_line=end_line,
                start_char=start_char,
                end_char=end_char,
                content=content,
                word_count=len(content.split()),
                detection_type=ch_info['detection_type']
            ))

        return chapter_objects

    def extract_chapter_title(self, line: str, match: re.Match, pattern_type: str) -> str:
        """Extract a clean chapter title from the matched line."""
        # Special handling for alice_style which already extracted the title
        if pattern_type == 'alice_style':
            # Title was already extracted in detect_chapters
            return line

        # Remove markdown headers
        line = re.sub(r'^#{1,6}\s*', '', line)

        # Remove leading numbers and dots
        line = re.sub(r'^\d+\.\s*', '', line)

        # For some patterns, use the full line as title
        if pattern_type in ['winnie_pooh_style', 'special_section']:
            return line.strip()

        # For chapter patterns, try to extract just the title part
        if 'Chapter' in line or 'Part' in line:
            # Remove "Chapter X:" or "Part X:" prefix
            line = re.sub(r'^(Chapter|Part|Book|Section)\s+([IVXLCDM]+|\d+):?\s*', '', line, flags=re.IGNORECASE)

        # Clean up any remaining formatting
        title = line.strip()

        # If we end up with empty title, use the marker
        if not title:
            title = match.group(0)

        return title

    def fix_chapter_sequence(self, chapters: List[Chapter]) -> List[Chapter]:
        """
        Fix chapter numbering issues (gaps, duplicates, etc.).

        Args:
            chapters: List of detected chapters

        Returns:
            Fixed list of chapters
        """
        if not chapters:
            return chapters

        # Check for gaps in numbering
        expected_numbers = set(range(1, len(chapters) + 1))
        actual_numbers = {ch.number for ch in chapters}

        if expected_numbers == actual_numbers:
            return chapters  # No fixing needed

        # Renumber sequentially based on position
        self.log_message("Fixing chapter numbering...")
        for i, chapter in enumerate(chapters):
            if chapter.number != i + 1:
                old_num = chapter.number
                chapter.number = i + 1
                self.log_message(f"  Renumbered chapter {old_num} -> {chapter.number}")

        return chapters

    def generate_toc(self, chapters: List[Chapter]) -> str:
        """
        Generate a markdown table of contents from chapters.

        Args:
            chapters: List of Chapter objects

        Returns:
            Markdown-formatted TOC
        """
        if not chapters:
            return ""

        toc_lines = ["## Table of Contents\n"]

        for chapter in chapters:
            # Create anchor from chapter title (simplified)
            anchor = re.sub(r'[^\w\s-]', '', chapter.title.lower())
            anchor = re.sub(r'\s+', '-', anchor)

            # Add TOC entry
            if chapter.title:
                toc_lines.append(f"{chapter.number}. [{chapter.title}](#{anchor})")
            else:
                toc_lines.append(f"{chapter.number}. [Chapter {chapter.number}](#chapter-{chapter.number})")

        return '\n'.join(toc_lines)

    def log_message(self, message: str):
        """Add message to processing log."""
        self.log.append(message)
        if self.verbose:
            print(f"  {message}")


def main():
    """Command-line interface for book processor."""
    parser = argparse.ArgumentParser(
        description="Process books into structured manifests with chapter detection and TOC generation"
    )
    parser.add_argument('input', help='Path to book file (markdown or text)')
    parser.add_argument(
        '--output', '-o',
        help='Output path for manifest JSON (default: same dir as input)',
        default=None
    )
    parser.add_argument(
        '--auto-fix',
        action='store_true',
        default=True,
        help='Automatically fix chapter numbering issues'
    )
    parser.add_argument(
        '--no-fix',
        action='store_false',
        dest='auto_fix',
        help='Disable automatic fixes'
    )
    parser.add_argument(
        '--save-cleaned',
        action='store_true',
        help='Save cleaned text (without Gutenberg boilerplate) to separate file'
    )
    parser.add_argument(
        '--save-toc',
        action='store_true',
        help='Save generated TOC to separate markdown file'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress verbose output'
    )

    args = parser.parse_args()

    # Process the book
    processor = BookProcessor(verbose=not args.quiet)

    try:
        input_path = Path(args.input)
        manifest = processor.process(input_path, auto_fix=args.auto_fix)

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = input_path.parent / f"{input_path.stem}_manifest.json"

        # Save manifest
        manifest.save(output_path)
        print(f"\n✅ Manifest saved to: {output_path}")

        # Save optional outputs
        if args.save_cleaned:
            cleaned_path = input_path.parent / f"{input_path.stem}_cleaned.md"
            # Reconstruct cleaned text from chapters
            cleaned_text = '\n\n'.join([
                f"{ch.marker}\n{ch.content}" for ch in manifest.chapters
            ])
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
            print(f"✅ Cleaned text saved to: {cleaned_path}")

        if args.save_toc and manifest.toc_markdown:
            toc_path = input_path.parent / f"{input_path.stem}_toc.md"
            with open(toc_path, 'w', encoding='utf-8') as f:
                f.write(manifest.toc_markdown)
            print(f"✅ Table of contents saved to: {toc_path}")

        # Print summary
        print(f"\n📚 Book: {manifest.metadata.get('title', 'Unknown')}")
        print(f"👤 Author: {manifest.metadata.get('author', 'Unknown')}")
        print(f"🌐 Language: {manifest.metadata.get('language', 'Unknown')}")
        print(f"📖 Chapters: {len(manifest.chapters)}")
        print(f"📝 Words: {manifest.processing['total_words']:,}")

        if manifest.processing.get('gutenberg_stripped'):
            print("✓ Gutenberg boilerplate removed")
        if manifest.processing.get('toc_generated'):
            print("✓ Table of contents generated")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())