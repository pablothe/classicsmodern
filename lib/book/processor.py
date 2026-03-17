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

import hashlib
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
    section_type: str = "chapter"  # 'chapter', 'prologue', 'epilogue', 'preface', 'introduction', 'part', etc.
    checkpoints: Dict = field(default_factory=lambda: {
        'translation': None,
        'audio': None
    })
    paragraphs: List[Dict] = field(default_factory=list)  # Paragraph registry for position tracking


@dataclass
class BookManifest:
    """Complete book structure and metadata."""
    version: str = "3.0"
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

    # Minimal fallback patterns for unstructured text (Priority 3)
    # Used only when no gutenberg_chapters.json or ## headers are found
    FALLBACK_PATTERNS = [
        # Italic chapter titles from Gutenberg (e.g., *1. The Horror in Clay.* or *I. Title.*)
        (r'^\*(?:(?:CHAPTER|Chapter|CHAPITRE|Chapitre)\s+)?([IVXLCDM]+|\d+)\.\s+(.+?)\*$', 'italic_chapter'),

        # Chapter keyword + number (multilingual)
        (r'^(CHAPTER|Chapter|CHAPITRE|Chapitre|KAPITEL|Kapitel|CAPÍTULO|Capítulo|CAPITOLO|Capitolo|Глава)\s+([IVXLCDM]+|\d+)\.?\s*(.*)', 'chapter_keyword'),

        # Act/Scene for plays (multilingual)
        (r'^(Act|ACT|Scene|SCENE|Acte|ACTE|Scène|SCÈNE|Akt|AKT|Szene|Acto|ACTO|Escena|Atto|ATTO|Scena)\s+([IVXLCDM]+|\d+)', 'act_scene'),

        # Epistolary formats (Letter I, Entry 1, Day 1, etc.)
        (r'^(Letter|Entry|Day|Night|Journal|Diary|Lettre|Brief|Carta|Lettera)\s+(\d+|[IVXLCDM]+)\b', 'epistolary'),

        # Special sections (multilingual)
        (r'^(Prologue|Epilogue|Introduction|Preface|Foreword|Interlude|Conclusion|Appendix|Préface|Épilogue|Avant-propos|Einleitung|Nachwort|Vorwort|Prólogo|Epílogo|Introducción|Conclusión|Prefazione|Epilogo|Introduzione)', 'special_section'),
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

        # Step 3: Detect chapters (Gutenberg TOC → ## headers → regex fallback)
        chapters = self.detect_chapters(cleaned_text, book_file=book_file)
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

        # Step 6: Extract paragraphs for each chapter
        for chapter in chapters:
            chapter.paragraphs = self._extract_paragraphs(chapter.content, chapter.number)

        # Step 7: Create manifest
        manifest = BookManifest(
            version="3.0",
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

    def detect_chapters(self, text: str, book_file: Path = None) -> List[Chapter]:
        """
        Detect all chapters using a 3-step priority chain.

        Priority 0: Gutenberg HTML TOC (gutenberg_chapters.json) — most reliable
        Priority 1: Markdown ## headers
        Priority 2: Minimal regex fallback

        Args:
            text: Book text content
            book_file: Path to the book file (used to find gutenberg_chapters.json)

        Returns:
            List of Chapter objects
        """
        lines = text.split('\n')
        chapter_dicts = []

        # PRIORITY 0: Gutenberg HTML TOC — authoritative chapter list from HTML
        if book_file is not None:
            gutenberg_data = self._load_gutenberg_chapters(Path(book_file))
            if gutenberg_data:
                version = gutenberg_data.get('version', '1.0')
                if version == '2.0':
                    # v2.0: Direct line-number lookup (no fuzzy matching needed)
                    chapter_dicts = self._locate_chapters_v2(lines, gutenberg_data)
                    if chapter_dicts:
                        self.log_message(f"Priority 0: Found {len(chapter_dicts)} chapters from gutenberg_chapters.json v2.0 (direct lookup)")
                else:
                    # v1.0 (legacy): Fuzzy title matching
                    chapter_dicts = self._locate_chapters_by_titles(lines, gutenberg_data['chapters'])
                    if chapter_dicts:
                        self.log_message(f"Priority 0: Found {len(chapter_dicts)} chapters from gutenberg_chapters.json v1.0")

        # PRIORITY 1: Markdown ## headers (Gutenberg downloads + any structured markdown)
        if not chapter_dicts:
            chapter_dicts = self._detect_header_chapters(lines)
            if chapter_dicts:
                self.log_message(f"Priority 1: Found {len(chapter_dicts)} chapters from ## headers")

        # PRIORITY 2: Minimal regex fallback (bare "Chapter I" lines, acts, prologues)
        if not chapter_dicts:
            chapter_dicts = self._detect_fallback_regex(lines)
            if chapter_dicts:
                self.log_message(f"Priority 2: Found {len(chapter_dicts)} chapters via regex fallback")

        # LAST RESORT: Single chapter for whole text
        if not chapter_dicts:
            word_count = len(text.split())
            if word_count >= 100:
                self.log_message(f"No chapter markers found — treating entire text as single chapter ({word_count:,} words)")
                chapter_dicts = [{
                    'line_num': 0,
                    'char_pos': 0,
                    'marker': '',
                    'title': 'Full Text',
                    'detection_type': 'single_chapter_fallback'
                }]

        return self._dicts_to_chapters(chapter_dicts, lines, text)

    def _load_gutenberg_chapters(self, book_file: Path) -> Optional[dict]:
        """Load chapter metadata from gutenberg_chapters.json if available.

        Returns:
            For v2.0: dict with 'version', 'chapters', 'front_matter', 'hierarchy', etc.
            For v1.0 (legacy): dict with 'version': '1.0', 'chapters': [...]
            None if file doesn't exist or is invalid.
        """
        gutenberg_json = book_file.parent / "gutenberg_chapters.json"
        if not gutenberg_json.exists():
            return None
        try:
            with open(gutenberg_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            chapters = data.get('chapters', [])
            if len(chapters) < 1:
                return None
            version = data.get('version', '1.0')
            self.log_message(f"Loaded {len(chapters)} chapters from gutenberg_chapters.json (v{version})")
            if version == '2.0':
                return data  # Return full v2.0 structure
            else:
                # Legacy v1.0: wrap in standardized format
                return {'version': '1.0', 'chapters': chapters}
        except (json.JSONDecodeError, IOError) as e:
            self.log_message(f"Failed to load gutenberg_chapters.json: {e}")
        return None

    # Ordinal words → numbers for matching "FIRST ACT" style labels
    ORDINAL_MAP = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
    }

    # Structural keywords used in prefix stripping
    _STRUCT_KEYWORDS = (
        r'Chapter|CHAPTER|Chapitre|CHAPITRE|Kapitel|KAPITEL|Part|PART|Partie|'
        r'Act|ACT|Acte|ACTE|Scene|SCENE|Scène|SCÈNE|Book|BOOK|Volume|VOLUME'
    )

    @staticmethod
    def _normalize_title_for_matching(title: str) -> str:
        """Normalize a chapter title for fuzzy matching.

        Strips structural prefixes (Chapter/Part/Act/Scene + number),
        handles ordinal words (FIRST ACT → strip), normalizes whitespace/case/punctuation.
        """
        kw = BookProcessor._STRUCT_KEYWORDS
        # Strip "Chapter N:", "Part N.", "Act N", "Scene N", etc.
        title = re.sub(
            rf'^({kw})\s+([IVXLCDM]+|\d+)[.:,]?\s*',
            '', title, flags=re.IGNORECASE
        )
        # Strip ordinal word + structural keyword (e.g., "FIRST ACT", "SECOND PART")
        ordinals = '|'.join(BookProcessor.ORDINAL_MAP.keys())
        title = re.sub(
            rf'^({ordinals})\s+({kw})\.?\s*',
            '', title, flags=re.IGNORECASE
        )
        # Strip leading number with dot (e.g., "1. Title")
        title = re.sub(r'^\d+\.\s*', '', title)
        # Normalize whitespace and case
        title = re.sub(r'\s+', ' ', title).strip().lower()
        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title)
        return title

    @staticmethod
    def _extract_chapter_number(title: str) -> int:
        """Extract chapter/part/act number from a structural label.

        Handles: 'CHAPTER I', 'Chapter 3:', 'Part II', 'Act V', 'Scene 2',
                 'FIRST ACT', 'SECOND PART', etc.
        Returns 0 if no number found.
        """
        kw = BookProcessor._STRUCT_KEYWORDS
        # Standard format: keyword + number
        m = re.match(rf'^(?:{kw})\s+([IVXLCDM]+|\d+)', title, re.IGNORECASE)
        if m:
            num_str = m.group(1)
            if num_str.isdigit():
                return int(num_str)
            try:
                return BookProcessor.roman_to_int(num_str)
            except (ValueError, KeyError):
                return 0

        # Ordinal format: "FIRST ACT", "SECOND PART", etc.
        ordinals = '|'.join(BookProcessor.ORDINAL_MAP.keys())
        m = re.match(rf'^({ordinals})\s+(?:{kw})', title, re.IGNORECASE)
        if m:
            return BookProcessor.ORDINAL_MAP.get(m.group(1).lower(), 0)

        return 0

    @staticmethod
    def _is_bare_chapter_label(title: str) -> bool:
        """Check if a title is just a structural label with no subtitle.

        Matches: 'CHAPTER I', 'Part 2', 'ACT V', 'Scene III', 'FIRST ACT', etc.
        """
        kw = BookProcessor._STRUCT_KEYWORDS
        if re.match(rf'^(?:{kw})\s+([IVXLCDM]+|\d+)\.?\s*$', title.strip(), re.IGNORECASE):
            return True
        ordinals = '|'.join(BookProcessor.ORDINAL_MAP.keys())
        if re.match(rf'^({ordinals})\s+(?:{kw})\.?\s*$', title.strip(), re.IGNORECASE):
            return True
        return False

    # Headers to skip when matching (metadata, not content)
    _SKIP_HEADERS = {
        'contents', 'table of contents', 'copyright',
        'acknowledgements', 'acknowledgments', 'about the author',
        'colophon', 'note', 'notes', 'bibliography', 'index',
        'footnotes', 'endnotes', 'glossary',
    }

    def _locate_chapters_v2(self, lines: list, gutenberg_data: dict) -> list:
        """Locate chapters using v2.0 gutenberg_chapters.json with direct line-number lookup.

        v2.0 files contain header_line_number and markdown_header recorded during
        download. This eliminates the need for fuzzy title matching entirely.

        Falls back to header text matching if line numbers are not populated.
        """
        chapters = gutenberg_data.get('chapters', [])
        chapter_dicts = []

        for gc in chapters:
            line_num = gc.get('header_line_number')
            markdown_header = gc.get('markdown_header')

            # Strategy 1: Direct line-number lookup (most reliable)
            if line_num is not None and 0 <= line_num < len(lines):
                actual_line = lines[line_num].strip()
                # Verify the header is still there (file may have been edited)
                if actual_line.startswith('##'):
                    chapter_dicts.append({
                        'line_num': line_num,
                        'char_pos': sum(len(l) + 1 for l in lines[:line_num]),
                        'marker': actual_line,
                        'title': re.sub(r'^##\s+', '', actual_line).strip(),
                        'detection_type': 'gutenberg_toc_v2',
                        'section_type': gc.get('section_type', 'chapter')
                    })
                    continue

            # Strategy 2: Match by markdown_header text (if line shifted)
            if markdown_header:
                for i, line in enumerate(lines):
                    if line.strip() == markdown_header:
                        chapter_dicts.append({
                            'line_num': i,
                            'char_pos': sum(len(l) + 1 for l in lines[:i]),
                            'marker': line.strip(),
                            'title': re.sub(r'^##\s+', '', line.strip()).strip(),
                            'detection_type': 'gutenberg_toc_v2',
                            'section_type': gc.get('section_type', 'chapter')
                        })
                        break

        # Sort by line number and deduplicate
        chapter_dicts.sort(key=lambda x: x['line_num'])
        seen_lines = set()
        deduped = []
        for cd in chapter_dicts:
            if cd['line_num'] not in seen_lines:
                seen_lines.add(cd['line_num'])
                deduped.append(cd)

        return deduped

    def _locate_chapters_by_titles(self, lines: list, gutenberg_chapters: list) -> list:
        """Locate chapters in markdown by matching against known Gutenberg titles.

        Uses the structured data from gutenberg_chapters.json to find where each
        chapter starts in the markdown text. Matching strategies:
        1. Title-based: normalized title comparison against ## headers
        2. Number-based: for bare "CHAPTER N" labels, match by chapter number
        3. Structural fallback: if strategies 1-2 matched very few, accept any
           structural ## headers (Act/Part/Chapter) since we know it's a Gutenberg book
        """
        # Build lookups from Gutenberg data
        title_lookup = {}  # normalized_title -> gc
        number_lookup = {}  # chapter_number -> gc (only for bare labels)

        for gc in gutenberg_chapters:
            norm = self._normalize_title_for_matching(gc['title'])
            if norm:
                title_lookup[norm] = gc
            # Also try original_title if present
            if 'original_title' in gc:
                norm_orig = self._normalize_title_for_matching(gc['original_title'])
                if norm_orig and norm_orig not in title_lookup:
                    title_lookup[norm_orig] = gc

            # For bare chapter labels like "CHAPTER I", build a number-based lookup
            if self._is_bare_chapter_label(gc['title']):
                ch_num = self._extract_chapter_number(gc['title'])
                if ch_num > 0:
                    number_lookup[ch_num] = gc

        # Collect all ## headers with their positions
        all_headers = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            match = re.match(r'^##\s+(.+)', stripped)
            if not match:
                continue
            header_text = match.group(1).strip()
            # Skip metadata headers
            if header_text.lower() in self._SKIP_HEADERS:
                continue
            if header_text.lower().startswith('by '):
                continue
            if re.match(r'^\[.*\]\(#', header_text):
                continue
            all_headers.append((i, stripped, header_text))

        # Pass 1: Title and number matching
        chapter_dicts = []
        matched_gc = set()
        matched_header_indices = set()

        for i, stripped, header_text in all_headers:
            norm_header = self._normalize_title_for_matching(header_text)
            gc = None

            # Strategy 1: Exact normalized title match
            if norm_header:
                gc = title_lookup.get(norm_header)

            # Strategy 2: Substring match (handles reformatted titles)
            if not gc and norm_header:
                for norm_title, gc_candidate in title_lookup.items():
                    if id(gc_candidate) in matched_gc:
                        continue
                    if norm_title in norm_header or norm_header in norm_title:
                        gc = gc_candidate
                        break

            # Strategy 3: Number-based match for bare "CHAPTER N" labels
            if not gc and number_lookup:
                ch_num = self._extract_chapter_number(header_text)
                if ch_num > 0 and ch_num in number_lookup:
                    gc_candidate = number_lookup[ch_num]
                    if id(gc_candidate) not in matched_gc:
                        gc = gc_candidate

            if gc:
                matched_gc.add(id(gc))
                matched_header_indices.add(i)
                chapter_dicts.append({
                    'line_num': i,
                    'char_pos': len('\n'.join(lines[:i])),
                    'marker': stripped,
                    'title': header_text,
                    'detection_type': 'gutenberg_toc',
                    'section_type': gc.get('section_type', 'chapter')
                })

        # Pass 2: Structural fallback for granularity mismatches
        # (e.g., JSON has Scenes but MD only has Acts)
        # If we matched very few entries, accept unmatched structural headers
        if len(chapter_dicts) < len(gutenberg_chapters) * 0.5:
            for i, stripped, header_text in all_headers:
                if i in matched_header_indices:
                    continue
                # Accept if this header has a structural keyword with a number
                ch_num = self._extract_chapter_number(header_text)
                if ch_num > 0:
                    # Detect section_type from the header
                    section_type = 'chapter'
                    header_lower = header_text.lower()
                    for kw, stype in [('act', 'act'), ('part', 'part'), ('book', 'book'),
                                      ('volume', 'volume'), ('scene', 'scene')]:
                        if kw in header_lower:
                            section_type = stype
                            break
                    chapter_dicts.append({
                        'line_num': i,
                        'char_pos': len('\n'.join(lines[:i])),
                        'marker': stripped,
                        'title': header_text,
                        'detection_type': 'gutenberg_toc',
                        'section_type': section_type
                    })

            # Re-sort by line number after adding fallback entries
            chapter_dicts.sort(key=lambda x: x['line_num'])

        return chapter_dicts

    def _detect_header_chapters(self, lines: list) -> list:
        """
        Priority 2: Detect chapters from ## markdown headers.

        Filters out metadata headers (Contents, Copyright, etc.).
        Returns chapter dicts if 2+ real content headers found.
        """
        SKIP_HEADERS = {
            'contents', 'table of contents', 'copyright',
            'acknowledgements', 'acknowledgments', 'about the author',
            'colophon', 'note', 'notes', 'bibliography', 'index',
            'footnotes', 'endnotes', 'glossary',
        }

        candidates = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Strip "end chapter" artifacts from Gutenberg HTML conversion
            stripped = re.sub(r'^end chapter', '', stripped, flags=re.IGNORECASE).strip()
            match = re.match(r'^##\s+(.+)', stripped)
            if not match:
                # Handle mid-line ## headers (e.g., TOC text followed by ## Chapter I.)
                mid_match = re.search(r'(?<![#\[])##\s+([A-Z])', stripped)
                if mid_match:
                    # Extract from the ## onwards
                    rest = stripped[mid_match.start():]
                    match = re.match(r'^##\s+(.+)', rest)
                    if match:
                        stripped = rest
                if not match:
                    continue
            title = match.group(1).strip()
            if title.lower() in SKIP_HEADERS:
                continue
            if title.lower().startswith('by '):
                continue
            # Filter TOC link artifacts like "[Chapter 1](#chapter-1)"
            if re.match(r'^\[.*\]\(#', title):
                continue
            # Detect section type from header title
            section_type = 'chapter'
            title_lower = title.lower().split('.')[0].split(':')[0].strip()
            section_keywords = {
                'prologue': 'prologue', 'epilogue': 'epilogue', 'preface': 'preface',
                'foreword': 'foreword', 'introduction': 'introduction', 'interlude': 'interlude',
                'conclusion': 'conclusion', 'appendix': 'appendix', 'afterword': 'epilogue',
                'dedication': 'dedication',
                'part': 'part', 'book': 'book', 'act': 'act', 'scene': 'scene',
                'letter': 'letter',
            }
            for kw, stype in section_keywords.items():
                if kw in title_lower:
                    section_type = stype
                    break
            candidates.append({
                'line_num': i,
                'char_pos': len('\n'.join(lines[:i])),
                'marker': stripped,
                'title': title,
                'detection_type': 'markdown_header',
                'section_type': section_type
            })

        if candidates:
            return candidates
        return []

    def _detect_fallback_regex(self, lines: list) -> list:
        """
        Priority 3: Minimal regex fallback for unstructured text.

        Uses a small set of patterns for books without ## headers.
        """
        chapters = []
        chapter_lines = set()

        for pattern_regex, pattern_type in self.FALLBACK_PATTERNS:
            pattern = re.compile(pattern_regex, re.IGNORECASE)
            for i, line in enumerate(lines):
                if i in chapter_lines:
                    continue
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                match = pattern.match(line_stripped)
                if match:
                    chapter_lines.add(i)
                    title = self.extract_chapter_title(line_stripped, match, pattern_type)
                    # Determine section_type from pattern and matched text
                    section_type = 'chapter'
                    if pattern_type == 'special_section':
                        keyword = match.group(1).lower()
                        section_type_map = {
                            'prologue': 'prologue', 'préface': 'preface', 'preface': 'preface',
                            'foreword': 'foreword', 'avant-propos': 'foreword', 'vorwort': 'foreword',
                            'introduction': 'introduction', 'einleitung': 'introduction',
                            'introducción': 'introduction', 'introduzione': 'introduction',
                            'epilogue': 'epilogue', 'épilogue': 'epilogue', 'nachwort': 'epilogue',
                            'epílogo': 'epilogue', 'epilogo': 'epilogue',
                            'interlude': 'interlude', 'conclusion': 'conclusion',
                            'conclusión': 'conclusion', 'appendix': 'appendix',
                            'prólogo': 'prologue', 'prefazione': 'preface',
                        }
                        section_type = section_type_map.get(keyword, keyword)
                    elif pattern_type == 'act_scene':
                        section_type = 'act' if match.group(1).lower() in ('act', 'acte', 'akt', 'acto', 'atto') else 'scene'
                    elif pattern_type == 'epistolary':
                        section_type = match.group(1).lower()
                    chapters.append({
                        'line_num': i,
                        'char_pos': len('\n'.join(lines[:i])),
                        'marker': line_stripped,
                        'title': title,
                        'detection_type': pattern_type,
                        'section_type': section_type
                    })

        # Sort and deduplicate (remove detections within 3 lines of each other)
        chapters.sort(key=lambda x: x['line_num'])
        if len(chapters) > 1:
            deduped = [chapters[0]]
            for ch in chapters[1:]:
                if ch['line_num'] - deduped[-1]['line_num'] > 3:
                    deduped.append(ch)
            chapters = deduped

        return chapters

    @staticmethod
    def _extract_paragraphs(chapter_content: str, chapter_number: int) -> List[Dict]:
        """
        Extract paragraphs from chapter content and assign stable IDs.

        Each paragraph gets a deterministic ID (e.g., ch01_p001) and character
        offsets within the chapter content. These IDs flow through the entire
        pipeline: translation, TTS, word timings, and frontend sync.

        Args:
            chapter_content: The raw text content of the chapter
            chapter_number: The chapter number (for ID generation)

        Returns:
            List of paragraph dicts with para_id, index, char_start, char_end,
            word_count, and content_hash
        """
        if not chapter_content or not chapter_content.strip():
            return []

        # Split on double newlines (standard paragraph boundary in markdown)
        raw_parts = re.split(r'\n\s*\n', chapter_content)

        paragraphs = []
        search_start = 0

        for raw in raw_parts:
            stripped = raw.strip()
            if not stripped or len(stripped) <= 1:
                continue

            # Find the actual position of this paragraph text in the chapter content
            actual_start = chapter_content.find(stripped, search_start)
            if actual_start == -1:
                # Fallback: search from beginning (shouldn't happen with ordered iteration)
                actual_start = chapter_content.find(stripped)
            if actual_start == -1:
                continue

            actual_end = actual_start + len(stripped)
            para_index = len(paragraphs)
            para_id = f"ch{chapter_number:02d}_p{para_index + 1:03d}"

            # Content hash for fuzzy matching after translation
            content_hash = hashlib.sha256(stripped[:200].encode('utf-8')).hexdigest()[:16]

            paragraphs.append({
                'para_id': para_id,
                'index': para_index,
                'char_start': actual_start,
                'char_end': actual_end,
                'word_count': len(stripped.split()),
                'content_hash': content_hash,
            })

            # Advance search position to avoid matching the same text twice
            search_start = actual_end

        return paragraphs

    def _dicts_to_chapters(self, chapter_dicts: list, lines: list, text: str) -> List[Chapter]:
        """
        Convert a list of chapter dicts to Chapter objects with content.

        Each dict must have: line_num, char_pos, marker, title, detection_type.
        """
        chapter_objects = []
        for i, ch_info in enumerate(chapter_dicts):
            start_line = ch_info['line_num']
            if i + 1 < len(chapter_dicts):
                end_line = chapter_dicts[i + 1]['line_num']
            else:
                end_line = len(lines)

            content_lines = lines[start_line + 1:end_line]
            content = '\n'.join(content_lines).strip()

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
                detection_type=ch_info['detection_type'],
                section_type=ch_info.get('section_type', 'chapter')
            ))

        # Filter out near-empty chapters (decorative title headers, separators, etc.)
        filtered = []
        for ch in chapter_objects:
            real_content = re.sub(r'^-{3,}\s*$', '', ch.content, flags=re.MULTILINE).strip()
            real_words = len(real_content.split()) if real_content else 0
            if real_words < 5:
                self.log_message(f"Dropping near-empty chapter '{ch.title}' ({real_words} real words)")
                continue
            filtered.append(ch)

        # Renumber if any chapters were filtered out
        if len(filtered) < len(chapter_objects):
            for i, ch in enumerate(filtered):
                ch.number = i + 1

        return filtered

    def extract_chapter_title(self, line: str, match: re.Match, pattern_type: str) -> str:
        """Extract a clean chapter title from the matched line."""
        # For italic chapters: extract the title after the number
        if pattern_type == 'italic_chapter':
            title = match.group(2).strip().rstrip('.*')
            return title if title else match.group(0)

        # For act_scene, epistolary, special_section: use the full line
        if pattern_type in ('act_scene', 'epistolary', 'special_section'):
            return line.strip()

        # For chapter_keyword: strip the keyword + number prefix to get the title
        cleaned = re.sub(
            r'^(CHAPTER|Chapter|CHAPITRE|Chapitre|KAPITEL|Kapitel|CAPÍTULO|Capítulo|CAPITOLO|Capitolo|Глава)\s+([IVXLCDM]+|\d+)\.?\s*',
            '', line, flags=re.IGNORECASE
        )
        title = cleaned.strip()
        return title if title else match.group(0)

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
        # Always print this warning regardless of verbose setting
        print(f"  ⚠ WARNING: Chapter numbers are non-sequential, renumbering...")
        print(f"    Original: {sorted(actual_numbers)}")
        print(f"    Expected: 1 through {len(chapters)}")
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

    def detect_toc(self, text: str) -> List[Dict]:
        """
        Detect table of contents entries in text.

        Absorbed from book_preprocessor.ChapterDetector.detect_toc().

        Returns:
            List of TOC entries with chapter numbers and titles
        """
        toc_entries = []
        lines = text.split('\n')

        # Pattern 1: Markdown TOC links like "1. [Chapter 1: Title](#anchor)"
        pattern1 = re.compile(r'^\s*(\d+)\.\s*\[([^\]]+)\]\([^)]+\)', re.IGNORECASE)

        # Pattern 2: Simple numbered list "1. Chapter 1: Title"
        pattern2 = re.compile(r'^\s*(\d+)\.\s*(Chapter|CHAPTER|Part|PART)\s+(\d+|[IVXLCDM]+):?\s*(.+)', re.IGNORECASE)

        # Pattern 3: Roman numerals in TOC
        pattern3 = re.compile(r'^\s*(\d+)\.\s*\[?([IVXLCDM]+)\.?\s*([^\]]*)\]?', re.IGNORECASE)

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            match = pattern1.match(line_stripped)
            if match:
                toc_entries.append({
                    'number': int(match.group(1)),
                    'title': match.group(2),
                    'line': i + 1,
                    'type': 'markdown_toc'
                })
                continue

            match = pattern2.match(line_stripped)
            if match:
                chapter_type = match.group(2)
                chapter_num = match.group(3)
                title = match.group(4).strip()
                toc_entries.append({
                    'number': int(match.group(1)),
                    'title': f"{chapter_type} {chapter_num}: {title}",
                    'line': i + 1,
                    'type': 'simple_list'
                })
                continue

            match = pattern3.match(line_stripped)
            if match:
                roman = match.group(2)
                title = match.group(3).strip()
                toc_entries.append({
                    'number': int(match.group(1)),
                    'title': f"{roman}. {title}" if title else f"{roman}.",
                    'line': i + 1,
                    'type': 'roman_toc'
                })
                continue

        return toc_entries

    @staticmethod
    def roman_to_int(roman: str) -> int:
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

    def validate_chapter_sequence(self, chapters: List[Dict]) -> Dict:
        """
        Validate that chapters are sequential and complete.

        Absorbed from book_preprocessor.ChapterDetector.validate_chapter_sequence().

        Args:
            chapters: List of chapter dicts with 'marker' keys

        Returns:
            Dict with validation results
        """
        if not chapters:
            return {
                'valid': False,
                'error': 'No chapters detected',
                'missing': [],
                'duplicates': []
            }

        chapter_numbers = []
        for ch in chapters:
            marker = ch.marker if hasattr(ch, 'marker') else ch.get('marker', '')

            # Try Roman numeral
            roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', marker)
            if roman_match:
                num = self.roman_to_int(marker)
                chapter_numbers.append(num)
                continue

            # Try digit
            num_match = re.search(r'(\d+)', marker)
            if num_match:
                chapter_numbers.append(int(num_match.group(1)))
                continue

            # Try Roman in other formats
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

        expected = list(range(1, max(chapter_numbers) + 1))
        missing = [n for n in expected if n not in chapter_numbers]
        duplicates = [n for n in set(chapter_numbers) if chapter_numbers.count(n) > 1]

        return {
            'valid': len(missing) == 0 and len(duplicates) == 0,
            'total_found': len(chapters),
            'expected_total': max(chapter_numbers) if chapter_numbers else 0,
            'missing': missing,
            'duplicates': duplicates,
            'chapter_numbers': chapter_numbers
        }

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