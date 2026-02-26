#!/usr/bin/env python3
"""
Text Extractor - Extract and parse book text for text sync feature

Functions:
- Find source markdown files for books
- Extract chapter text from markdown
- Split text into paragraphs
- Detect chapter boundaries
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def find_source_text(book_dir: Path) -> Optional[Path]:
    """
    Find the source text file for a book.

    Args:
        book_dir: Path to book directory

    Returns:
        Path to source markdown file, or None if not found
    """
    if not book_dir.exists():
        return None

    book_md = book_dir / 'book.md'
    if book_md.exists():
        return book_md

    return None


def _normalize_language_name(raw: str) -> str:
    """Normalize language key/filename fragment to display name.

    Examples: 'modern_english' -> 'Modern English', 'Spanish' -> 'Spanish'
    """
    return raw.replace('_', ' ').strip().title()


def discover_text_tracks(book_dir: Path, book_language: Optional[str] = None) -> List[Dict]:
    """
    Discover all available text language tracks for a book.

    Sources:
    1. Original source file (book.md)
    2. Filename pattern scan for *_{Language}_{timestamp}.md and translations/*.md

    Args:
        book_dir: Path to book directory
        book_language: Original language of the book (e.g., 'French', 'Latin')

    Returns:
        List of track dicts with track_id, language, label, file_path, is_original
    """
    if not book_dir.exists():
        return []

    tracks = []
    seen_paths = set()
    original_language = book_language

    # --- Source 1: Original source text ---
    source_path = find_source_text(book_dir)
    if source_path and source_path.exists():
        lang = original_language or 'Original'
        tracks.append({
            'track_id': 'original',
            'language': lang,
            'label': f'{lang} (Original)' if original_language else 'Original',
            'file_path': str(source_path.relative_to(book_dir)),
            'is_original': True,
        })
        seen_paths.add(source_path.resolve())

    # --- Source 2: Filename pattern scan ---
    lang_timestamp_pattern = re.compile(
        r'^.+?_([A-Z][a-z]+(?:_[A-Z][a-z]+)*)_(\d{8}_\d{6})\.md$'
    )

    skip_substrings = ('manifest', 'checkpoint', 'chapter_data', 'state')

    for md_file in sorted(book_dir.glob('*.md')):
        if md_file.resolve() in seen_paths:
            continue
        name = md_file.name
        if any(s in name.lower() for s in skip_substrings):
            continue

        match = lang_timestamp_pattern.match(name)
        if match:
            language = _normalize_language_name(match.group(1))
            timestamp = match.group(2)
            track_id = f"{language.lower().replace(' ', '_')}_{timestamp}"
            tracks.append({
                'track_id': track_id,
                'language': language,
                'label': language,
                'file_path': name,
                'is_original': False,
            })
            seen_paths.add(md_file.resolve())

    # Scan translations/ subdirectory
    translations_dir = book_dir / 'translations'
    if translations_dir.is_dir():
        for md_file in sorted(translations_dir.glob('*.md')):
            if md_file.resolve() in seen_paths:
                continue
            lang_key = md_file.stem
            language = _normalize_language_name(lang_key)
            rel_path = f'translations/{md_file.name}'
            tracks.append({
                'track_id': lang_key,
                'language': language,
                'label': language,
                'file_path': rel_path,
                'is_original': False,
            })
            seen_paths.add(md_file.resolve())

    # Deduplicate non-original tracks by language (keep latest per language)
    original_tracks = [t for t in tracks if t.get('is_original')]
    non_original_tracks = [t for t in tracks if not t.get('is_original')]

    language_groups: Dict[str, List[Dict]] = {}
    for track in non_original_tracks:
        lang = track['language'].lower()
        language_groups.setdefault(lang, []).append(track)

    deduped = list(original_tracks)
    for lang, group in language_groups.items():
        deduped.append(group[-1])

    return deduped


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
        r'^\*([IVXLCDM]+|\d+)\.\s+(.*?)\*$',  # *1. Title.* or *I. Title.* (Gutenberg italic chapters)
    ]

    current_pos = 0
    for line_num, line in enumerate(lines):
        line = line.strip()
        # Strip "end chapter" artifacts from Gutenberg HTML conversion
        line = re.sub(r'^end chapter', '', line, flags=re.IGNORECASE).strip()

        matched = False
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
                matched = True
                break

        # Handle mid-line ## headers (e.g., TOC text followed by ## Chapter I.)
        if not matched:
            mid_match = re.search(r'(?<![#\[])##\s+(?:CHAPTER|Chapter)', line)
            if mid_match:
                rest = line[mid_match.start():]
                for pattern in patterns:
                    match = re.match(pattern, rest, re.IGNORECASE)
                    if match:
                        chapter_num = match.group(1)
                        chapter_title = match.group(2).strip() if len(match.groups()) > 1 else ""

                        if chapter_num.isdigit():
                            num = int(chapter_num)
                        else:
                            num = roman_to_int(chapter_num)

                        text_before = '\n'.join(lines[:line_num])
                        start_pos = len(text_before) + mid_match.start()

                        chapters.append({
                            'number': num,
                            'title': chapter_title or f"Chapter {num}",
                            'full_title': rest,
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


def _load_manifest_paragraphs(book_dir: Path, chapter_index: int) -> Optional[List[Dict]]:
    """
    Load paragraph registry from book manifest for a specific chapter.
    If the manifest exists but has no paragraphs, lazily generates them
    from chapter content and saves back to the manifest.

    Args:
        book_dir: Path to book directory
        chapter_index: Zero-based chapter index

    Returns:
        List of paragraph dicts from manifest, or None if not available
    """
    manifest_path = book_dir / 'book_manifest.json'
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        chapters = manifest.get('chapters', [])
        if chapter_index < len(chapters):
            paras = chapters[chapter_index].get('paragraphs', [])
            if paras:
                return paras

            # Lazy migration: generate paragraphs from chapter content
            chapter = chapters[chapter_index]
            content = chapter.get('content', '')
            if not content:
                return None

            from lib.book.processor import BookProcessor
            chapter_num = chapter.get('number', chapter_index + 1)
            generated = BookProcessor._extract_paragraphs(content, chapter_num)
            if generated:
                chapters[chapter_index]['paragraphs'] = generated
                manifest['version'] = '3.0'
                try:
                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest, f, indent=2, ensure_ascii=False)
                except IOError:
                    pass  # Non-critical: continue with generated data even if save fails
                return generated

    except (json.JSONDecodeError, IOError, KeyError):
        pass

    return None


def split_into_paragraphs(text: str, manifest_paragraphs: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Split text into paragraphs for text sync.

    When manifest_paragraphs is provided (from BookProcessor), uses stable
    para_id values that flow through the entire pipeline (translation, TTS,
    word timings, playback position). Falls back to sequential IDs otherwise.

    Args:
        text: Chapter text
        manifest_paragraphs: Optional paragraph registry from book manifest
                             (list of dicts with para_id, char_start, char_end)

    Returns:
        List of paragraph dicts with id, para_id, and text
    """
    if manifest_paragraphs:
        # Use manifest paragraph data for stable IDs
        paragraphs = []
        for mp in manifest_paragraphs:
            para_text = text[mp['char_start']:mp['char_end']].strip()
            if para_text and len(para_text) > 1:
                paragraphs.append({
                    'id': mp['index'],
                    'para_id': mp['para_id'],
                    'text': para_text
                })
        return paragraphs

    # Fallback: split by double newlines with sequential IDs
    raw_paragraphs = re.split(r'\n\s*\n', text)

    paragraphs = []
    for i, para in enumerate(raw_paragraphs):
        para = para.strip()
        if para and len(para) > 1:  # Skip empty fragments but keep short dialogue
            paragraphs.append({
                'id': i,
                'text': para
            })

    return paragraphs


def _load_manifest(book_dir: Path) -> Optional[Dict]:
    """Load book_manifest.json if it exists."""
    manifest_path = book_dir / 'book_manifest.json'
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _get_audio_extras(book_dir: Path, max_manifest_chapter: int = 0) -> tuple:
    """Check chunk manifest for prologue (chapter 0) and epilogue.

    discover_books() injects a prologue at index 0 and/or appends an
    epilogue when the chunk manifest has chapters outside the manifest
    range.  The text API must account for these extra entries.

    Returns:
        (has_prologue, has_epilogue)
    """
    for name in ('book_chunk_manifest.json',
                 f'{book_dir.name}_chunk_manifest.json'):
        cm_path = book_dir / 'audio_kokoro' / name
        if cm_path.exists():
            try:
                with open(cm_path, 'r') as f:
                    cm = json.load(f)
                chunk_chapters = {c.get('chapter') for c in cm.get('chunks', [])}
                has_prologue = 0 in chunk_chapters
                has_epilogue = any(
                    c is not None and c > max_manifest_chapter
                    for c in chunk_chapters
                ) if max_manifest_chapter > 0 else False
                return has_prologue, has_epilogue
            except (json.JSONDecodeError, IOError):
                pass
    return False, False


def _has_audio_prologue(book_dir: Path) -> bool:
    """Convenience wrapper — True when chunk manifest has chapter 0."""
    has_prologue, _ = _get_audio_extras(book_dir)
    return has_prologue


def get_chapter_text_data(book_dir: Path, chapter_index: int, audio_chapter_timing: Optional[Dict] = None, total_audio_chapters: int = None, source_path: Optional[Path] = None) -> Optional[Dict]:
    """
    Get chapter text data for text sync API.

    Uses book_manifest.json as the primary source of truth for chapter
    boundaries and paragraph data. Falls back to detect_chapter_markers()
    when no manifest exists or when an explicit non-default source_path
    is provided (e.g., a translation file).

    Args:
        book_dir: Path to book directory
        chapter_index: Zero-based chapter index
        audio_chapter_timing: Optional dict with 'timestamp' and 'duration' from audio chapter metadata
        total_audio_chapters: Total number of chapters in audio metadata (helps detect single-file books)
        source_path: Optional explicit source file path (overrides manifest)

    Returns:
        Dictionary with chapter data, or None if not found
    """
    # --- Manifest-first path (for original text) ---
    use_manifest = source_path is None
    if use_manifest:
        manifest = _load_manifest(book_dir)
        if manifest and manifest.get('chapters'):
            manifest_chapters = manifest['chapters']

            # Special case: single-file audio with multi-chapter text
            if (total_audio_chapters == 1 and
                len(manifest_chapters) > 1 and
                chapter_index == 0 and
                audio_chapter_timing and
                audio_chapter_timing.get('duration')):

                # Concatenate all chapter content for linear interpolation
                full_text = '\n\n'.join(ch.get('content', '') for ch in manifest_chapters)
                paragraphs = split_into_paragraphs(full_text)
                return {
                    'chapter_num': 0,
                    'title': 'Complete Book',
                    'text': full_text,
                    'paragraphs': paragraphs,
                    'word_count': len(full_text.split()),
                    'estimated_duration': len(full_text.split()) / 200 * 60,
                    'audio_start': audio_chapter_timing.get('timestamp', 0),
                    'audio_duration': audio_chapter_timing.get('duration')
                }

            # Audio extras: discover_books() injects a prologue at index 0
            # and/or appends an epilogue.  Detect both to adjust indices.
            max_ch = max((ch.get('number', 0) for ch in manifest_chapters), default=0)
            has_prologue, has_epilogue = _get_audio_extras(book_dir, max_ch)
            prologue_offset = 1 if has_prologue else 0
            epilogue_index = len(manifest_chapters) + prologue_offset if has_epilogue else -1

            # --- Prologue: front matter before first chapter ---
            if has_prologue and chapter_index == 0:
                src = find_source_text(book_dir)
                if src:
                    try:
                        with open(src, 'r', encoding='utf-8') as f:
                            full_text = f.read()
                        first_start = manifest_chapters[0].get('start_char', 0)
                        front_matter = full_text[:first_start].strip() if first_start > 0 else ''
                        if front_matter:
                            paragraphs = split_into_paragraphs(front_matter)
                            result = {
                                'chapter_num': 0,
                                'title': 'Prologue',
                                'text': front_matter,
                                'paragraphs': paragraphs,
                                'word_count': len(front_matter.split()),
                                'estimated_duration': len(front_matter.split()) / 200 * 60
                            }
                            if audio_chapter_timing:
                                result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
                                result['audio_duration'] = audio_chapter_timing.get('duration')
                            return result
                    except IOError:
                        pass
                return None

            # --- Epilogue: text after last chapter ---
            if has_epilogue and chapter_index == epilogue_index:
                src = find_source_text(book_dir)
                if src:
                    try:
                        with open(src, 'r', encoding='utf-8') as f:
                            full_text = f.read()
                        last_end = manifest_chapters[-1].get('end_char', len(full_text))
                        back_matter = full_text[last_end:].strip() if last_end < len(full_text) else ''
                        if back_matter:
                            paragraphs = split_into_paragraphs(back_matter)
                            result = {
                                'chapter_num': max_ch + 1,
                                'title': 'Epilogue',
                                'text': back_matter,
                                'paragraphs': paragraphs,
                                'word_count': len(back_matter.split()),
                                'estimated_duration': len(back_matter.split()) / 200 * 60
                            }
                            if audio_chapter_timing:
                                result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
                                result['audio_duration'] = audio_chapter_timing.get('duration')
                            return result
                    except IOError:
                        pass
                return None

            # Adjust index to account for injected prologue
            manifest_index = chapter_index - prologue_offset

            if manifest_index < 0 or manifest_index >= len(manifest_chapters):
                return None

            chapter = manifest_chapters[manifest_index]
            chapter_text = chapter.get('content', '')
            if not chapter_text:
                # Manifest chapter has no content, fall through to detection
                pass
            else:
                # Use manifest paragraphs (offsets match manifest content)
                manifest_paras = chapter.get('paragraphs', [])
                paragraphs = split_into_paragraphs(chapter_text, manifest_paras if manifest_paras else None)

                result = {
                    'chapter_num': chapter.get('number', chapter_index + 1),
                    'title': chapter.get('title', f'Chapter {chapter_index + 1}'),
                    'text': chapter_text,
                    'paragraphs': paragraphs,
                    'word_count': len(chapter_text.split()),
                    'estimated_duration': len(chapter_text.split()) / 200 * 60
                }

                if audio_chapter_timing:
                    result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
                    result['audio_duration'] = audio_chapter_timing.get('duration')

                return result

    # --- Fallback: detect chapters from source text ---
    if not source_path:
        source_path = find_source_text(book_dir)
    if not source_path:
        return None

    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except IOError:
        return None

    chapters = detect_chapter_markers(text)
    if not chapters:
        if chapter_index != 0:
            return None

        paragraphs = split_into_paragraphs(text)
        result = {
            'chapter_num': 0,
            'title': 'Full Text',
            'text': text,
            'paragraphs': paragraphs,
            'word_count': len(text.split()),
            'estimated_duration': len(text.split()) / 200 * 60
        }

        if audio_chapter_timing:
            result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
            result['audio_duration'] = audio_chapter_timing.get('duration')

        return result

    # Special case: single-file audio with multi-chapter text (fallback path)
    if (total_audio_chapters == 1 and
        len(chapters) > 1 and
        chapter_index == 0 and
        audio_chapter_timing and
        audio_chapter_timing.get('duration')):

        paragraphs = split_into_paragraphs(text)
        return {
            'chapter_num': 0,
            'title': 'Complete Book',
            'text': text,
            'paragraphs': paragraphs,
            'word_count': len(text.split()),
            'estimated_duration': len(text.split()) / 200 * 60,
            'audio_start': audio_chapter_timing.get('timestamp', 0),
            'audio_duration': audio_chapter_timing.get('duration')
        }

    # Apply prologue/epilogue offset for translation tracks (fallback path).
    # The UI chapter indices include injected prologue/epilogue from audio,
    # but detected chapters in the translation file don't have those.
    detected_max = max((ch.get('number', 0) for ch in chapters), default=0)
    fb_prologue, fb_epilogue = _get_audio_extras(book_dir, detected_max)
    fb_offset = 1 if fb_prologue else 0

    if fb_prologue and chapter_index == 0:
        # Prologue: serve front matter from the original source text
        orig_src = find_source_text(book_dir)
        if orig_src:
            manifest = _load_manifest(book_dir)
            if manifest and manifest.get('chapters'):
                try:
                    with open(orig_src, 'r', encoding='utf-8') as f:
                        orig_text = f.read()
                    first_start = manifest['chapters'][0].get('start_char', 0)
                    front_matter = orig_text[:first_start].strip() if first_start > 0 else ''
                    if front_matter:
                        paragraphs = split_into_paragraphs(front_matter)
                        result = {
                            'chapter_num': 0,
                            'title': 'Prologue',
                            'text': front_matter,
                            'paragraphs': paragraphs,
                            'word_count': len(front_matter.split()),
                            'estimated_duration': len(front_matter.split()) / 200 * 60
                        }
                        if audio_chapter_timing:
                            result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
                            result['audio_duration'] = audio_chapter_timing.get('duration')
                        return result
                except IOError:
                    pass
        return None

    fb_epilogue_index = len(chapters) + fb_offset if fb_epilogue else -1
    if fb_epilogue and chapter_index == fb_epilogue_index:
        return None  # Epilogue text not available in translation

    adjusted_index = chapter_index - fb_offset

    chapter_text = extract_chapter_text(text, chapters, adjusted_index)
    if not chapter_text:
        return None

    chapter = chapters[adjusted_index]
    paragraphs = split_into_paragraphs(chapter_text)

    result = {
        'chapter_num': chapter['number'],
        'title': chapter['title'],
        'text': chapter_text,
        'paragraphs': paragraphs,
        'word_count': len(chapter_text.split()),
        'estimated_duration': len(chapter_text.split()) / 200 * 60
    }

    if audio_chapter_timing:
        result['audio_start'] = audio_chapter_timing.get('timestamp', 0)
        result['audio_duration'] = audio_chapter_timing.get('duration')

    return result


def get_book_chapters_list(book_dir: Path) -> List[Dict]:
    """
    Get list of all chapters in a book.

    Uses book_manifest.json as primary source of truth.
    Falls back to detect_chapter_markers() when no manifest exists.

    Args:
        book_dir: Path to book directory

    Returns:
        List of chapter info dicts
    """
    # Manifest-first path
    manifest = _load_manifest(book_dir)
    if manifest and manifest.get('chapters'):
        manifest_chapters = manifest['chapters']
        max_ch = max((ch.get('number', 0) for ch in manifest_chapters), default=0)
        has_prologue, has_epilogue = _get_audio_extras(book_dir, max_ch)

        chapters = []
        offset = 0

        if has_prologue:
            chapters.append({'number': 0, 'title': 'Prologue', 'index': 0})
            offset = 1

        chapters.extend(
            {
                'number': ch.get('number', i + 1),
                'title': ch.get('title', f'Chapter {i + 1}'),
                'index': i + offset
            }
            for i, ch in enumerate(manifest_chapters)
        )

        if has_epilogue:
            chapters.append({
                'number': max_ch + 1,
                'title': 'Epilogue',
                'index': len(manifest_chapters) + offset
            })

        return chapters

    # Fallback: detect from source text
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
