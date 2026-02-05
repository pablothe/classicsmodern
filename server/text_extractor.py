#!/usr/bin/env python3
"""
Text Extractor - Extract and parse book text for text sync feature

Functions:
- Find source markdown files for books
- Extract chapter text from markdown
- Split text into paragraphs
- Detect chapter boundaries
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def find_source_text(book_dir: Path) -> Optional[Path]:
    """
    Find the best source text file for a book.

    Priority order:
    1. *_cleaned.md (best - no Gutenberg boilerplate)
    2. *_original.md (fallback)
    3. *.md (any markdown file)

    Args:
        book_dir: Path to book directory

    Returns:
        Path to source markdown file, or None if not found
    """
    if not book_dir.exists():
        return None

    # Try cleaned files first
    cleaned_files = list(book_dir.glob("*_cleaned.md"))
    if cleaned_files:
        # Prefer shorter names (more likely to be the main book)
        return min(cleaned_files, key=lambda p: len(p.name))

    # Try original files
    original_files = list(book_dir.glob("*_original.md"))
    if original_files:
        return min(original_files, key=lambda p: len(p.name))

    # Try any markdown file
    md_files = list(book_dir.glob("*.md"))
    if md_files:
        # Exclude chunk files and translation files
        main_files = [
            f for f in md_files
            if 'chunk' not in f.name.lower()
            and not f.name.startswith('_')
        ]
        if main_files:
            return min(main_files, key=lambda p: len(p.name))

    return None


def detect_chapter_markers(text: str) -> List[Dict]:
    """
    Detect chapter markers in markdown text.

    Looks for patterns like:
    - ## CHAPTER I.
    - # Chapter 1
    - CHAPTER I.

    Args:
        text: Full markdown text

    Returns:
        List of chapter dictionaries with start positions and titles
    """
    chapters = []
    lines = text.split('\n')

    # Patterns to match
    patterns = [
        r'^#+\s*CHAPTER\s+([IVXLCDM]+|[\d]+)[.:]\s*(.*?)(?:\s*\{.*?\})?$',  # ## CHAPTER I. Title {#anchor}
        r'^#+\s*Chapter\s+(\d+)[.:]?\s*(.*?)(?:\s*\{.*?\})?$',  # ## Chapter 1: Title {#anchor} or ## Chapter 1 Title
        r'^#+\s+([IVXLCDM]+)\s*$',  # ## I or ## IX (standalone Roman numerals, e.g., Great Gatsby)
        r'^CHAPTER\s+([IVXLCDM]+|[\d]+)[.:]\s*(.*?)$',  # CHAPTER I. Title (no markdown)
    ]

    current_pos = 0
    for line_num, line in enumerate(lines):
        line = line.strip()

        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                chapter_num = match.group(1)
                chapter_title = match.group(2).strip() if len(match.groups()) > 1 else ""

                # Convert Roman numerals to integers if needed
                if chapter_num.isdigit():
                    num = int(chapter_num)
                else:
                    num = roman_to_int(chapter_num)

                # Calculate text position (approximate line start)
                text_before = '\n'.join(lines[:line_num])
                start_pos = len(text_before)

                chapters.append({
                    'number': num,
                    'title': chapter_title or f"Chapter {num}",
                    'full_title': line,
                    'start_line': line_num,
                    'start_pos': start_pos
                })
                break

    return chapters


def roman_to_int(s: str) -> int:
    """Convert Roman numeral to integer."""
    roman_values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev_value = 0

    for char in reversed(s.upper()):
        value = roman_values.get(char, 0)
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value

    return total


def extract_chapter_text(text: str, chapters: List[Dict], chapter_index: int) -> Optional[str]:
    """
    Extract text for a specific chapter.

    Args:
        text: Full markdown text
        chapters: List of chapter markers from detect_chapter_markers()
        chapter_index: Zero-based chapter index

    Returns:
        Chapter text, or None if invalid index
    """
    if chapter_index < 0 or chapter_index >= len(chapters):
        return None

    chapter = chapters[chapter_index]
    start_pos = chapter['start_pos']

    # Find end position (start of next chapter, or end of text)
    if chapter_index < len(chapters) - 1:
        end_pos = chapters[chapter_index + 1]['start_pos']
    else:
        end_pos = len(text)

    return text[start_pos:end_pos]


def split_into_paragraphs(text: str) -> List[Dict]:
    """
    Split text into paragraphs for text sync.

    Args:
        text: Chapter text

    Returns:
        List of paragraph dicts with id and text
    """
    # Split by double newlines (standard paragraph separator)
    raw_paragraphs = re.split(r'\n\s*\n', text)

    paragraphs = []
    for i, para in enumerate(raw_paragraphs):
        para = para.strip()
        if para and len(para) > 10:  # Skip very short fragments
            paragraphs.append({
                'id': i,
                'text': para
            })

    return paragraphs


def get_chapter_text_data(book_dir: Path, chapter_index: int, audio_chapter_timing: Optional[Dict] = None, total_audio_chapters: int = None) -> Optional[Dict]:
    """
    Get chapter text data for text sync API.

    Args:
        book_dir: Path to book directory
        chapter_index: Zero-based chapter index
        audio_chapter_timing: Optional dict with 'timestamp' and 'duration' from audio chapter metadata
        total_audio_chapters: Total number of chapters in audio metadata (helps detect single-file books)

    Returns:
        Dictionary with chapter data, or None if not found
    """
    # Find source text
    source_path = find_source_text(book_dir)
    if not source_path:
        return None

    # Read text
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except IOError:
        return None

    # Detect chapters
    chapters = detect_chapter_markers(text)
    if not chapters:
        # No chapters detected, treat entire text as single chapter
        if chapter_index != 0:
            return None

        paragraphs = split_into_paragraphs(text)
        result = {
            'chapter_num': 0,
            'title': 'Full Text',
            'text': text,
            'paragraphs': paragraphs,
            'word_count': len(text.split()),
            'estimated_duration': len(text.split()) / 200 * 60  # 200 WPM → seconds
        }

        # Add audio timing if available
        if audio_chapter_timing:
            result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
            result['audio_duration'] = audio_chapter_timing.get('duration')

        return result

    # Special case: If text has chapters but audio has only ONE chapter marker (single complete file)
    # This happens when a book has chapter structure in markdown, but the audio was created as one file
    # Example: Call of Cthulhu has 3 chapters in text, but only 1 "Complete Book" chapter in audio
    if (total_audio_chapters == 1 and
        len(chapters) > 1 and
        chapter_index == 0 and
        audio_chapter_timing and
        audio_chapter_timing.get('duration')):

        # This is a complete-book audio file with multi-chapter text
        # Return full book text for linear interpolation across entire audiobook
        paragraphs = split_into_paragraphs(text)
        result = {
            'chapter_num': 0,
            'title': 'Complete Book',
            'text': text,
            'paragraphs': paragraphs,
            'word_count': len(text.split()),
            'estimated_duration': len(text.split()) / 200 * 60,  # 200 WPM → seconds
            'audio_start': audio_chapter_timing.get('timestamp', 0),
            'audio_duration': audio_chapter_timing.get('duration')
        }
        return result

    # Extract chapter text (normal multi-chapter behavior)
    chapter_text = extract_chapter_text(text, chapters, chapter_index)
    if not chapter_text:
        return None

    chapter = chapters[chapter_index]
    paragraphs = split_into_paragraphs(chapter_text)

    result = {
        'chapter_num': chapter['number'],
        'title': chapter['title'],
        'text': chapter_text,
        'paragraphs': paragraphs,
        'word_count': len(chapter_text.split()),
        'estimated_duration': len(chapter_text.split()) / 200 * 60  # 200 WPM → seconds
    }

    # Add audio timing if available
    if audio_chapter_timing:
        result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
        result['audio_duration'] = audio_chapter_timing.get('duration')

    return result


def get_book_chapters_list(book_dir: Path) -> List[Dict]:
    """
    Get list of all chapters in a book.

    Args:
        book_dir: Path to book directory

    Returns:
        List of chapter info dicts
    """
    source_path = find_source_text(book_dir)
    if not source_path:
        return []

    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except IOError:
        return []

    chapters = detect_chapter_markers(text)
    return [
        {
            'number': ch['number'],
            'title': ch['title'],
            'index': i
        }
        for i, ch in enumerate(chapters)
    ]
