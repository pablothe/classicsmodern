#!/usr/bin/env python3
"""
Gutenberg Book Downloader

Downloads books from Project Gutenberg and converts to clean Markdown.

Features:
- Download HTML/TXT from Gutenberg
- Convert to Markdown
- Strip Gutenberg boilerplate
- Validate structure
- Simple job queue (max 3 concurrent)

Usage:
    python3 server/gutenberg_downloader.py 11 alice_adventures
"""

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install requests beautifulsoup4")
    sys.exit(1)


# Constants
BOOKS_DIR = Path(__file__).parent.parent / "books"
MAX_CONCURRENT_DOWNLOADS = 3


# Global download jobs
download_jobs = {}  # {job_id: {status, progress, error, book_slug, ...}}
download_semaphore = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)


def _check_siblings_for_heading(element, heading_tags, max_siblings=5):
    """Check next siblings for heading elements (h1-h4)."""
    count = 0
    sibling = element.next_sibling
    while sibling and count < max_siblings:
        if hasattr(sibling, 'name'):
            if sibling.name in heading_tags:
                return True
            # Check children of container elements (div wrapping an h2)
            if sibling.name in ('div', 'section', 'header', 'p'):
                if sibling.find(list(heading_tags)):
                    return True
            count += 1
        sibling = sibling.next_sibling
    return False


class GutenbergDownloader:
    """Download and process Gutenberg books"""

    # Multilingual chapter keywords → section types
    _SECTION_TYPE_MAP = {
        # Chapters
        'chapter': 'chapter', 'chapitre': 'chapter', 'kapitel': 'chapter',
        'capítulo': 'chapter', 'capitolo': 'chapter', 'глава': 'chapter',
        # Parts
        'part': 'part', 'partie': 'part', 'teil': 'part', 'часть': 'part',
        # Books/Volumes
        'book': 'book', 'livre': 'book', 'buch': 'book', 'libro': 'book', 'книга': 'book',
        'volume': 'volume',
        # Drama
        'act': 'act', 'acte': 'act', 'akt': 'act', 'acto': 'act', 'atto': 'act',
        'scene': 'scene', 'scène': 'scene',
        # Front matter
        'prologue': 'prologue', 'prólogo': 'prologue',
        'preface': 'preface', 'préface': 'preface', 'prefazione': 'preface', 'vorwort': 'preface',
        'foreword': 'foreword', 'avant-propos': 'foreword',
        'introduction': 'introduction', 'einleitung': 'introduction',
        'introducción': 'introduction', 'introduzione': 'introduction',
        'dedication': 'dedication',
        "author's note": 'preface', "editor's note": 'preface', "translator's note": 'preface',
        # Back matter
        'epilogue': 'epilogue', 'épilogue': 'epilogue', 'nachwort': 'epilogue',
        'epílogo': 'epilogue', 'epilogo': 'epilogue',
        'afterword': 'epilogue',
        'conclusion': 'conclusion', 'conclusión': 'conclusion',
        'appendix': 'appendix',
        # Other
        'interlude': 'interlude',
        'letter': 'letter', 'lettre': 'letter', 'brief': 'letter', 'carta': 'letter',
    }

    # Section types that are front matter
    _FRONT_MATTER_TYPES = {'prologue', 'preface', 'foreword', 'introduction', 'dedication'}

    # Section types that are back matter
    _BACK_MATTER_TYPES = {'epilogue', 'afterword', 'conclusion', 'appendix'}

    # Structural parent types (contain children)
    _PARENT_TYPES = {'part', 'book', 'volume'}

    @staticmethod
    def _classify_section_type(title: str) -> str:
        """Classify a section title into a structural type.

        Checks front/back matter keywords first, then structural (part/act/scene),
        then chapter keywords. Returns 'chapter' as default.
        """
        title_lower = title.lower().strip()

        # Check all known keywords, longest match first
        for keyword, stype in sorted(
            GutenbergDownloader._SECTION_TYPE_MAP.items(),
            key=lambda x: -len(x[0])
        ):
            # Match at word boundary: keyword at start or after non-alpha
            if re.search(rf'(?:^|\s){re.escape(keyword)}(?:\s|$|[.:,])', title_lower):
                return stype

        return 'chapter'

    @staticmethod
    def _extract_number_from_title(title: str) -> tuple:
        """Extract ordinal number from title. Returns (number, method).

        Requires Roman numerals to follow a chapter keyword directly,
        preventing false matches like 'C' in 'P.C.' being parsed as 100.

        Handles: 'CHAPTER I', 'Chapter 3:', 'Part II', 'FIRST ACT',
                 standalone 'XIV.', 'CHAPTER ONE' (English ordinal words).
        Returns (0, 'none') if no number found.
        """
        # English ordinal words
        ordinals = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
            'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
            'nineteen': 19, 'twenty': 20, 'twenty-one': 21, 'twenty-two': 22,
            'twenty-three': 23, 'twenty-four': 24, 'twenty-five': 25,
            'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
            'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31,
            'thirty-two': 32, 'thirty-three': 33, 'thirty-four': 34,
            'thirty-five': 35, 'thirty-six': 36, 'thirty-seven': 37,
            'thirty-eight': 38, 'thirty-nine': 39, 'forty': 40,
            'forty-one': 41, 'forty-two': 42, 'forty-three': 43,
            'forty-four': 44, 'forty-five': 45, 'forty-six': 46,
            'forty-seven': 47, 'forty-eight': 48,
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
        }

        # Keyword pattern for structural labels
        kw = (r'(?:CHAPTER|CHAPITRE|KAPITEL|CAPÍTULO|CAPITOLO|ГЛАВА|'
              r'PART|PARTIE|TEIL|ЧАСТЬ|'
              r'BOOK|LIVRE|BUCH|LIBRO|КНИГА|VOLUME|'
              r'ACT|ACTE|AKT|ACTO|ATTO|'
              r'SCENE|SCÈNE|'
              r'LETTER|LETTRE|BRIEF|CARTA|LETTERA|'
              r'ENTRY|DAY|NIGHT|JOURNAL|DIARY)')

        # 1. Keyword + Roman numeral (strict: must follow keyword directly)
        m = re.match(rf'({kw})\s+([IVXLCDM]+)\b', title, re.IGNORECASE)
        if m:
            roman_str = m.group(2).upper()
            # Validate it's actually a plausible Roman numeral (not just 'I' from a word)
            if len(roman_str) > 0:
                try:
                    val = GutenbergDownloader._roman_to_int(roman_str)
                    if val > 0:
                        return (val, 'roman')
                except Exception:
                    pass

        # 2. Keyword + Arabic numeral
        m = re.match(rf'({kw})\s+(\d+)', title, re.IGNORECASE)
        if m:
            return (int(m.group(2)), 'arabic')

        # 3. Keyword + English ordinal word (e.g., "CHAPTER ONE", "CHAPTER TWENTY-THREE")
        m = re.match(rf'({kw})\s+(\w+(?:-\w+)?)', title, re.IGNORECASE)
        if m:
            word = m.group(2).lower()
            if word in ordinals:
                return (ordinals[word], 'word')

        # 4. Ordinal word + keyword (e.g., "FIRST ACT", "SECOND PART")
        ordinal_pattern = '|'.join(sorted(
            [k for k in ordinals if not k.replace('-', '').isalpha() or len(k) > 2],
            key=len, reverse=True
        ))
        m = re.match(rf'({ordinal_pattern})\s+({kw})', title, re.IGNORECASE)
        if m:
            word = m.group(1).lower()
            if word in ordinals:
                return (ordinals[word], 'ordinal_word')

        # 5. Standalone Roman numeral (e.g., "XIV.", "II")
        m = re.match(r'^([IVXLCDM]+)\.?\s*$', title.strip())
        if m:
            try:
                val = GutenbergDownloader._roman_to_int(m.group(1))
                if val > 0:
                    return (val, 'roman_standalone')
            except Exception:
                pass

        return (0, 'none')

    def __init__(self, books_dir: Path = BOOKS_DIR):
        self.books_dir = books_dir
        self.books_dir.mkdir(parents=True, exist_ok=True)

    def download_book(
        self,
        gutenberg_id: int,
        book_slug: str,
        job_id: Optional[str] = None
    ) -> Dict:
        """
        Download and process a Gutenberg book.

        Args:
            gutenberg_id: Gutenberg book ID
            book_slug: Directory name (e.g., 'alice_adventures')
            job_id: Optional job ID for tracking

        Returns:
            Dictionary with status and paths
        """
        # Update job status
        if job_id:
            download_jobs[job_id]['status'] = 'downloading'
            download_jobs[job_id]['progress'] = 10

        try:
            # Create book directory
            book_dir = self.books_dir / book_slug
            book_dir.mkdir(parents=True, exist_ok=True)

            # Download HTML
            print(f"\n📥 Downloading Gutenberg #{gutenberg_id}...")
            html_content = self._fetch_html(gutenberg_id)

            if job_id:
                download_jobs[job_id]['progress'] = 40

            # Convert to Markdown
            print("🔄 Converting to Markdown...")
            markdown, toc_entries, metadata = self._html_to_markdown(html_content)

            if job_id:
                download_jobs[job_id]['progress'] = 60

            # Strip boilerplate
            print("✂️  Stripping Gutenberg boilerplate...")
            cleaned = self._strip_boilerplate(markdown)

            # Normalize markdown formatting
            print("🔧 Normalizing markdown formatting...")
            normalized = self._normalize_markdown(cleaned)

            # Save to file
            output_file = book_dir / "book.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(normalized)

            print(f"✓ Saved: {output_file}")

            # Save Gutenberg chapter metadata (v2.0 format)
            if toc_entries:
                chapters_data = self._build_v2_chapters_json(
                    toc_entries, gutenberg_id, normalized
                )
                gutenberg_json = book_dir / "gutenberg_chapters.json"
                with open(gutenberg_json, 'w', encoding='utf-8') as f:
                    json.dump(chapters_data, f, indent=2, ensure_ascii=False)
                ch_count = len(chapters_data.get('chapters', []))
                print(f"✓ Saved {ch_count} chapters to gutenberg_chapters.json (v2.0)")

            # Save Gutenberg metadata (title, author from HTML)
            gutenberg_meta = {
                'gutenberg_id': gutenberg_id,
                'title': metadata.get('title'),
                'author': metadata.get('author'),
                'downloaded_at': datetime.now().isoformat()
            }
            meta_path = book_dir / "gutenberg_metadata.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(gutenberg_meta, f, indent=2, ensure_ascii=False)
            if metadata.get('author'):
                print(f"✓ Metadata: {metadata['title']} by {metadata['author']}")

            if job_id:
                download_jobs[job_id]['progress'] = 80

            # Validate
            print("✅ Validating structure...")
            validation = self._validate_book(output_file)

            if job_id:
                download_jobs[job_id]['status'] = 'complete'
                download_jobs[job_id]['progress'] = 100
                download_jobs[job_id]['output_file'] = str(output_file)
                download_jobs[job_id]['validation'] = validation

            print(f"\n🎉 Download complete!")
            print(f"   File: {output_file}")
            print(f"   Chapters: {validation.get('chapter_count', 'Unknown')}")
            print(f"   Word count: {validation.get('word_count', 'Unknown')}")

            return {
                'success': True,
                'book_slug': book_slug,
                'output_file': str(output_file),
                'validation': validation
            }

        except Exception as e:
            print(f"❌ Error: {e}")
            if job_id:
                download_jobs[job_id]['status'] = 'error'
                download_jobs[job_id]['error'] = str(e)

            return {
                'success': False,
                'error': str(e)
            }

    def _decode_response(self, response) -> str:
        """
        Properly decode HTTP response content, handling Gutenberg's encoding quirks.

        Gutenberg pages often have incorrect encoding headers, causing mojibake
        (e.g., Ã© instead of é). This method tries multiple strategies.
        """
        # Strategy 1: Try UTF-8 on raw bytes (most reliable for Gutenberg)
        try:
            text = response.content.decode('utf-8')
            # Quick sanity check: mojibake typically has Ã followed by another char
            if 'Ã©' not in text and 'Ã¨' not in text and 'Ã¢' not in text:
                return text
        except UnicodeDecodeError:
            pass

        # Strategy 2: Check HTML meta charset
        try:
            # Peek at raw bytes for charset declaration
            raw_head = response.content[:2000].decode('ascii', errors='ignore')
            charset_match = re.search(r'charset[="\s]+([^\s";>]+)', raw_head, re.IGNORECASE)
            if charset_match:
                charset = charset_match.group(1).strip('"\'')
                return response.content.decode(charset)
        except (UnicodeDecodeError, LookupError):
            pass

        # Strategy 3: Try latin-1 (never fails, but may not be correct)
        try:
            text = response.content.decode('latin-1')
            return text
        except UnicodeDecodeError:
            pass

        # Strategy 4: Fall back to requests' auto-detection
        return response.text

    def _fetch_html(self, gutenberg_id: int) -> str:
        """
        Fetch book HTML from Gutenberg.

        Args:
            gutenberg_id: Gutenberg book ID

        Returns:
            HTML content as string
        """
        # Try HTML format first (better formatting, has TOC for chapter extraction)
        html_urls = [
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/{gutenberg_id}-h.htm",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.html",
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h.htm"
        ]

        for url in html_urls:
            try:
                print(f"  Trying: {url}")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    content = self._decode_response(response)
                    print(f"  ✓ Success (HTML)!")
                    return content
            except requests.RequestException:
                continue

        # Fallback to plain text
        txt_urls = [
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        ]
        for txt_url in txt_urls:
            try:
                print(f"  Trying TXT: {txt_url}")
                response = requests.get(txt_url, timeout=30)
                if response.status_code == 200:
                    text = self._decode_response(response)
                    html = f"<html><body><pre>{text}</pre></body></html>"
                    print(f"  ✓ Success (TXT format)!")
                    return html
            except requests.RequestException:
                continue

        raise ValueError(f"Could not download book #{gutenberg_id} from any URL")

    @staticmethod
    def _roman_to_int(roman: str) -> int:
        """Convert Roman numeral string to integer."""
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

    def _extract_toc_from_html(self, soup) -> list:
        """
        Extract table of contents from Gutenberg HTML (v2.0 format).

        Gutenberg books often have a TOC section with internal anchor links like:
            <a href="#chap01">CHAPITRE I. Comment Candide...</a>
            <a href="#link2H_4_0002">Chapter I</a>

        Returns:
            List of dicts with 'anchor', 'title', 'ordinal', 'section_type' keys.
            Uses sequential ordinal (1, 2, 3...) instead of parsed number to avoid
            Roman numeral parsing errors (e.g., 'C' in 'P.C.' = 100).
        """
        # Multilingual chapter keyword pattern
        chapter_kw = re.compile(
            r'(chapter|chapitre|kapitel|capítulo|capitolo|глава|'
            r'part|partie|teil|parte|часть|'
            r'book|livre|buch|libro|книга|volume|'
            r'act|scene|acte|akt|acto|atto|scène|'
            r'prologue|epilogue|préface|preface|foreword|introduction|'
            r'conclusion|dedication|appendix|interlude|'
            r'prólogo|epílogo|epilogo|prefazione|vorwort|nachwort|'
            r'avant-propos|einleitung|introducción|introduzione|conclusión|'
            r'letter|lettre|brief|carta|lettera|'
            r'entry|day|night|journal|diary)',
            re.IGNORECASE
        )

        # Find internal links that point to anchors within the document
        internal_links = soup.find_all('a', href=re.compile(r'^#'))

        chapter_links = []
        for link in internal_links:
            href = link.get('href', '')[1:]  # Remove leading #
            text = link.get_text(strip=True)
            if not text or not href:
                continue

            is_chapter = bool(chapter_kw.search(text))

            # Also accept standalone Roman numerals (e.g., "I.", "XIV.")
            if not is_chapter:
                is_chapter = bool(re.match(r'^[IVXLCDM]+\.?[\s,;]?$|^[IVXLCDM]+\.?\s', text.strip()))

            if is_chapter:
                section_type = self._classify_section_type(text)
                chapter_links.append({'anchor': href, 'title': text, 'section_type': section_type})

        # Need at least 3 chapter links to consider it a real TOC
        if len(chapter_links) < 3:
            return []

        toc_entries = []
        for i, entry in enumerate(chapter_links):
            title = entry['title']
            number, _ = self._extract_number_from_title(title)

            toc_entries.append({
                'anchor': entry['anchor'],
                'title': title,
                'ordinal': i + 1,
                'number': number if number > 0 else i + 1,
                'section_type': entry['section_type']
            })

        return toc_entries

    def _extract_chapters_from_headings(self, soup) -> list:
        """
        Fallback: extract chapter entries from HTML heading tags (h2, h3, h4).

        Used when no anchor-based TOC is found. Scans heading tags for content
        that looks like chapter titles (has chapter keywords or Roman/Arabic numerals).

        Returns:
            List of dicts with 'anchor', 'title', 'ordinal', 'number', 'section_type' keys
        """
        chapter_kw = re.compile(
            r'(chapter|chapitre|kapitel|capítulo|capitolo|глава|'
            r'part|partie|teil|parte|часть|'
            r'book|livre|buch|libro|книга|volume|'
            r'act|scene|acte|akt|acto|atto|scène|'
            r'prologue|epilogue|préface|preface|foreword|introduction|'
            r'conclusion|dedication|appendix|'
            r'prólogo|epílogo|epilogo|prefazione|vorwort|nachwort|'
            r'avant-propos|einleitung|introducción|introduzione)',
            re.IGNORECASE
        )

        # Skip headers that are clearly metadata, not content
        skip_patterns = re.compile(
            r'(table of contents|contents|copyright|gutenberg|'
            r'transcriber|produced by|about the author|license|'
            r'^\s*by\s)',
            re.IGNORECASE
        )

        # Try heading levels in order of preference
        for tag_name in ['h2', 'h3', 'h4']:
            headings = soup.find_all(tag_name)
            if len(headings) < 2:
                continue

            chapter_headings = []
            for heading in headings:
                text = heading.get_text(strip=True)
                if not text or len(text) > 200:
                    continue
                if skip_patterns.search(text):
                    continue

                is_chapter = bool(chapter_kw.search(text))

                # Accept Roman numerals (e.g., "I.", "XIV. Title")
                if not is_chapter:
                    is_chapter = bool(re.match(r'^[IVXLCDM]+\.?\s', text))

                if is_chapter:
                    chapter_headings.append({
                        'text': text,
                        'section_type': self._classify_section_type(text),
                        'element': heading
                    })

            # If we found 3+ chapter headings at this level, use them
            if len(chapter_headings) >= 3:
                toc_entries = []
                for i, ch in enumerate(chapter_headings):
                    title = ch['text']
                    number, _ = self._extract_number_from_title(title)
                    anchor = re.sub(r'[^\w]', '_', title[:30]).strip('_')

                    toc_entries.append({
                        'anchor': anchor,
                        'title': title,
                        'ordinal': i + 1,
                        'number': number if number > 0 else i + 1,
                        'section_type': ch['section_type']
                    })

                print(f"  Found {len(toc_entries)} chapters from <{tag_name}> heading tags")
                return toc_entries

        # Fallback: if many headings exist at one level without chapter keywords,
        # check if they're all descriptive titles (short, no Gutenberg boilerplate)
        for tag_name in ['h2', 'h3', 'h4']:
            headings = soup.find_all(tag_name)
            content_headings = []
            for heading in headings:
                text = heading.get_text(strip=True)
                if not text or len(text) > 200 or len(text) < 2:
                    continue
                if skip_patterns.search(text):
                    continue
                content_headings.append(text)

            if len(content_headings) >= 5:
                toc_entries = []
                for i, title in enumerate(content_headings):
                    anchor = re.sub(r'[^\w]', '_', title[:30]).strip('_')
                    toc_entries.append({
                        'anchor': anchor,
                        'title': title,
                        'ordinal': i + 1,
                        'number': i + 1,
                        'section_type': self._classify_section_type(title)
                    })
                print(f"  Found {len(toc_entries)} chapters from <{tag_name}> descriptive headings")
                return toc_entries

        return []

    @staticmethod
    def _clean_toc_title(original_title: str) -> str:
        """
        Minimal cleanup of TOC title text for header injection.

        Only cleans whitespace artifacts and trailing periods.
        Does NOT restructure, renumber, or strip keywords — the markdown
        normalizer and display layer handle formatting downstream.
        """
        title = original_title.strip()
        # Collapse internal whitespace (TOC often has \r\n from HTML formatting)
        title = re.sub(r'\s+', ' ', title)
        # Strip trailing periods
        title = title.rstrip('.')
        return title

    def _build_v2_chapters_json(self, toc_entries: list, gutenberg_id: int,
                                markdown_text: str) -> dict:
        """
        Build v2.0 gutenberg_chapters.json with front matter, hierarchy,
        and line positions from the final markdown text.

        Args:
            toc_entries: Raw TOC entries from HTML extraction
            gutenberg_id: Gutenberg book ID
            markdown_text: Final normalized markdown content (book.md)

        Returns:
            Complete v2.0 chapters dict
        """
        md_lines = markdown_text.split('\n')

        # Build a map of ## header text → line number in the final markdown
        header_line_map = {}  # normalized header text → (line_number, raw_line)
        for line_idx, line in enumerate(md_lines):
            stripped = line.strip()
            m = re.match(r'^##\s+(.+)', stripped)
            if m:
                header_text = m.group(1).strip()
                # Store with multiple normalizations for flexible matching
                norm = re.sub(r'\s+', ' ', header_text).strip()
                if norm not in header_line_map:
                    header_line_map[norm] = (line_idx, stripped)
                # Also store lowercased version
                norm_lower = norm.lower()
                if norm_lower not in header_line_map:
                    header_line_map[norm_lower] = (line_idx, stripped)

        # Build chapter entries with line positions
        chapters = []
        for entry in toc_entries:
            clean_title = self._clean_toc_title(entry['title'])
            section_type = entry.get('section_type', 'chapter')

            # Try to find this chapter's ## header in the markdown
            header_line_number = None
            markdown_header = None

            # Strategy 1: Exact match on clean title
            norm_title = re.sub(r'\s+', ' ', clean_title).strip()
            if norm_title in header_line_map:
                header_line_number, markdown_header = header_line_map[norm_title]
            elif norm_title.lower() in header_line_map:
                header_line_number, markdown_header = header_line_map[norm_title.lower()]

            # Strategy 2: Substring match (title may have been truncated or reformatted)
            if header_line_number is None:
                for norm_key, (ln, raw) in header_line_map.items():
                    if norm_title.lower() in norm_key or norm_key in norm_title.lower():
                        header_line_number = ln
                        markdown_header = raw
                        break

            # Strategy 3: Match by sequential position (fallback for order-preserving conversion)
            # (handled in the position-filling pass below)

            ch_entry = {
                'ordinal': entry.get('ordinal', entry.get('number', 0)),
                'title': clean_title,
                'section_type': section_type,
            }
            if header_line_number is not None:
                ch_entry['header_line_number'] = header_line_number
                ch_entry['markdown_header'] = markdown_header

            chapters.append(ch_entry)

        # Position-filling pass: for chapters without line numbers, match remaining
        # ## headers by document order (since HTML→MD preserves order)
        unmatched_chapters = [i for i, ch in enumerate(chapters) if 'header_line_number' not in ch]
        if unmatched_chapters:
            matched_lines = {ch.get('header_line_number') for ch in chapters if 'header_line_number' in ch}
            unmatched_headers = sorted([
                (ln, raw) for norm, (ln, raw) in header_line_map.items()
                if ln not in matched_lines
            ], key=lambda x: x[0])

            # Deduplicate headers (same line may appear under multiple normalizations)
            seen_lines = set()
            unique_unmatched = []
            for ln, raw in unmatched_headers:
                if ln not in seen_lines:
                    seen_lines.add(ln)
                    unique_unmatched.append((ln, raw))

            # Assign by order: first unmatched chapter gets first unmatched header
            for ch_idx, (ln, raw) in zip(unmatched_chapters, unique_unmatched):
                chapters[ch_idx]['header_line_number'] = ln
                chapters[ch_idx]['markdown_header'] = raw

        # Build front_matter block
        front_matter_sections = []
        for ch in chapters:
            if ch['section_type'] in self._FRONT_MATTER_TYPES:
                front_matter_sections.append({
                    'title': ch['title'],
                    'section_type': ch['section_type']
                })

        front_matter = {
            'has_prologue': any(s['section_type'] == 'prologue' for s in front_matter_sections),
            'has_preface': any(s['section_type'] in ('preface', 'foreword') for s in front_matter_sections),
            'has_dedication': any(s['section_type'] == 'dedication' for s in front_matter_sections),
            'has_introduction': any(s['section_type'] == 'introduction' for s in front_matter_sections),
            'sections': front_matter_sections
        }

        # Build hierarchy for parent types (parts, books, volumes)
        hierarchy = []
        parent_indices = [i for i, ch in enumerate(chapters) if ch['section_type'] in self._PARENT_TYPES]
        for pi, parent_idx in enumerate(parent_indices):
            parent = chapters[parent_idx]
            # Children range: from next entry to either next parent or end
            child_start = parent_idx + 1
            if pi + 1 < len(parent_indices):
                child_end = parent_indices[pi + 1] - 1
            else:
                child_end = len(chapters) - 1

            hierarchy.append({
                'type': parent['section_type'],
                'title': parent['title'],
                'ordinal': parent['ordinal'],
                'children_range': [child_start, child_end]
            })

        # Determine review_status based on heuristics
        review_status = 'auto'
        ordinals_by_type = {}
        for ch in chapters:
            st = ch['section_type']
            ordinals_by_type.setdefault(st, []).append(ch['ordinal'])
        # Flag if >50 chapters, or missing line numbers
        if len(chapters) > 50:
            review_status = 'needs_review'
        missing_lines = sum(1 for ch in chapters if 'header_line_number' not in ch)
        if missing_lines > len(chapters) * 0.3:
            review_status = 'needs_review'

        return {
            'version': '2.0',
            'source': 'gutenberg_html',
            'gutenberg_id': gutenberg_id,
            'review_status': review_status,
            'chapter_count': len(chapters),
            'front_matter': front_matter,
            'hierarchy': hierarchy,
            'chapters': chapters
        }

    @staticmethod
    def _has_nearby_heading(element) -> bool:
        """Check if there's an h1-h4 heading near this element.

        Gutenberg uses varied structures:
        - <h2><a id="chap01"></a>CHAPTER I.</h2>  (Alice: anchor inside heading)
        - <p><a id="link2HCH0001"></a></p><div>...</div><h2>CHAPTER 1.</h2>  (Moby Dick: heading is parent's sibling)
        """
        heading_tags = {'h1', 'h2', 'h3', 'h4'}

        # Check the element itself
        if hasattr(element, 'name') and element.name in heading_tags:
            return True

        # Check parent (anchor might be inside a heading)
        parent = getattr(element, 'parent', None)
        if parent and hasattr(parent, 'name') and parent.name in heading_tags:
            return True

        # Check element's own siblings
        if _check_siblings_for_heading(element, heading_tags):
            return True

        # Check parent's siblings (anchor is often inside a <p> or <span>,
        # and the heading is a sibling of that container)
        if parent and hasattr(parent, 'name') and parent.name not in ('body', 'html', '[document]'):
            if _check_siblings_for_heading(parent, heading_tags):
                return True

        return False

    def _inject_chapter_headers(self, soup, toc_entries: list):
        """
        Inject <h2> chapter headers at anchor positions only when no heading exists nearby.

        Many Gutenberg books already have headings in the body. This method
        only injects when the anchor target has no heading nearby, preventing
        duplicate headers.
        """
        anchor_map = {entry['anchor']: entry for entry in toc_entries}
        injected = 0

        for anchor_id, entry in anchor_map.items():
            targets = soup.find_all(attrs={'name': anchor_id})
            targets += soup.find_all(attrs={'id': anchor_id})

            for target in targets:
                if self._has_nearby_heading(target):
                    continue  # Heading already exists — don't duplicate

                title = self._clean_toc_title(entry['title'])
                h2 = soup.new_tag('h2')
                h2.string = title
                target.insert_after(h2)
                injected += 1

        if injected:
            print(f"  Injected {injected} chapter headers (skipped {len(anchor_map) - injected} with existing headings)")

    @staticmethod
    def _extract_metadata(soup) -> dict:
        """
        Extract title and author from Gutenberg HTML.

        Parses the <title> tag which has the format:
        "The Project Gutenberg eBook of {Title}, by {Author}"

        Returns:
            Dict with 'title' and 'author' keys (values may be None)
        """
        metadata = {'title': None, 'author': None}
        title_tag = soup.find('title')
        if not title_tag:
            return metadata

        text = title_tag.get_text(strip=True)

        # Strip common Gutenberg prefixes
        for prefix in [
            'The Project Gutenberg eBook of ',
            'The Project Gutenberg EBook of ',
            'Project Gutenberg eBook of ',
        ]:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break

        # Strip "| Project Gutenberg" suffix
        text = re.sub(r'\s*\|\s*Project Gutenberg\s*$', '', text)

        # Split on ", by " to separate title and author
        # Handle variations: ", by ", " by ", ", par " (French)
        for sep in [', by ', ' by ', ', par ']:
            if sep in text:
                title_part, author_part = text.rsplit(sep, 1)
                # Clean trailing periods from author
                author_part = author_part.rstrip('.')
                metadata['title'] = title_part.strip()
                metadata['author'] = author_part.strip()
                return metadata

        # No author separator found — treat whole thing as title
        metadata['title'] = text.strip()
        return metadata

    def _html_to_markdown(self, html: str) -> tuple:
        """
        Convert HTML to Markdown.

        Args:
            html: HTML content

        Returns:
            Tuple of (markdown_content, toc_entries, metadata)
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract metadata BEFORE decomposing any tags
        metadata = self._extract_metadata(soup)

        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        # Extract TOC from anchor links, or fall back to heading tags
        toc_entries = self._extract_toc_from_html(soup)
        if not toc_entries:
            toc_entries = self._extract_chapters_from_headings(soup)
        if toc_entries:
            if not any(soup.find_all('a', attrs={'name': e.get('anchor', '')}) or
                       soup.find_all(attrs={'id': e.get('anchor', '')})
                       for e in toc_entries[:1]):
                # Heading-based entries don't have anchors to inject at
                pass
            else:
                print(f"  Found {len(toc_entries)} chapters in HTML TOC")
                self._inject_chapter_headers(soup, toc_entries)

        # Get body content
        body = soup.body if soup.body else soup

        # Convert to markdown
        markdown = self._convert_element_to_markdown(body)

        # Strip "end chapter" artifacts from HTML chapter div markers
        markdown = re.sub(r'end chapter', '', markdown, flags=re.IGNORECASE)

        # Promote italic chapter lines to ## headers (when no TOC was found)
        if not toc_entries:
            markdown = self._promote_italic_chapter_lines(markdown)

        # Clean up excessive whitespace
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        return markdown.strip(), toc_entries, metadata

    def _promote_italic_chapter_lines(self, markdown: str) -> str:
        """
        Convert standalone italic chapter lines to ## markdown headers.

        When Gutenberg HTML has no TOC, chapter titles in <em> tags become
        italic lines like *1. The Horror in Clay.* — promote these to ##
        headers for proper chapter detection.

        Only promotes when 2+ matching lines are found to avoid false positives.
        """
        pattern = re.compile(
            r'^\*(?:(?:CHAPTER|Chapter|CHAPITRE|Chapitre)\s+)?'
            r'([IVXLCDM]+|\d+)\.\s+'
            r'(.+?)\*$',
            re.MULTILINE | re.IGNORECASE
        )

        matches = list(pattern.finditer(markdown))
        if len(matches) < 2:
            return markdown

        def replacer(match):
            number_str = match.group(1)
            title = match.group(2).rstrip('.')
            return f'## {number_str}. {title}'

        result = pattern.sub(replacer, markdown)
        print(f"  Promoted {len(matches)} italic chapter lines to ## headers")
        return result

    def _convert_element_to_markdown(self, element, depth=0) -> str:
        """
        Recursively convert HTML element to Markdown.

        Args:
            element: BeautifulSoup element
            depth: Current recursion depth (safety limit: 100)

        Returns:
            Markdown string
        """
        if isinstance(element, NavigableString):
            text = str(element).strip()
            return text if text else ""

        # Safety net: prevent stack overflow on deeply nested HTML
        if depth > 100:
            return element.get_text(strip=True) if hasattr(element, 'get_text') else str(element).strip()

        md = ""

        # Headers (leading \n ensures they always start on their own line)
        if element.name == 'h1':
            md += f"\n# {element.get_text(strip=True)}\n\n"
        elif element.name == 'h2':
            md += f"\n## {element.get_text(strip=True)}\n\n"
        elif element.name == 'h3':
            md += f"\n### {element.get_text(strip=True)}\n\n"
        elif element.name == 'h4':
            md += f"\n#### {element.get_text(strip=True)}\n\n"

        # Paragraphs
        elif element.name == 'p':
            text = ''.join(self._convert_element_to_markdown(child, depth + 1) for child in element.children)
            if text:
                md += text + "\n\n"

        # Line breaks
        elif element.name == 'br':
            md += "  \n"

        # Horizontal rules
        elif element.name == 'hr':
            md += "\n---\n\n"

        # Lists
        elif element.name in ['ul', 'ol']:
            is_ordered = (element.name == 'ol')
            for i, li in enumerate(element.find_all('li', recursive=False), start=1):
                if is_ordered:
                    md += f"{i}. {self._convert_element_to_markdown(li, depth + 1).strip()}\n"
                else:
                    md += f"- {self._convert_element_to_markdown(li, depth + 1).strip()}\n"
            md += "\n"

        # Links
        elif element.name == 'a':
            href = element.get('href', '#')
            text = ''.join(self._convert_element_to_markdown(child, depth + 1) for child in element.children).strip()
            md += f"[{text}]({href})"

        # Emphasis
        elif element.name in ['em', 'i']:
            text = element.get_text(strip=True)
            md += f"*{text}*"
        elif element.name in ['strong', 'b']:
            text = element.get_text(strip=True)
            md += f"**{text}**"

        # Blockquotes
        elif element.name == 'blockquote':
            text = ''.join(self._convert_element_to_markdown(child, depth + 1) for child in element.children).strip()
            lines = text.split('\n')
            md += '\n'.join(f"> {line}" for line in lines) + "\n\n"

        # Pre-formatted text
        elif element.name == 'pre':
            text = element.get_text()
            md += f"```\n{text}\n```\n\n"

        # Default: process children
        else:
            for child in element.children:
                md += self._convert_element_to_markdown(child, depth + 1)

        return md

    def _strip_boilerplate(self, markdown: str) -> str:
        """
        Strip Project Gutenberg boilerplate (header and footer).

        Args:
            markdown: Markdown content

        Returns:
            Cleaned markdown
        """
        lines = markdown.split('\n')

        # Find start of content (after Gutenberg header)
        start_markers = [
            '*** START OF',
            'START OF THIS PROJECT GUTENBERG',
            'START OF THE PROJECT GUTENBERG'
        ]

        start_idx = 0
        for i, line in enumerate(lines):
            for marker in start_markers:
                if marker in line.upper():
                    start_idx = i + 1
                    break

        # Find end of content (before Gutenberg footer)
        end_markers = [
            '*** END OF',
            'END OF THIS PROJECT GUTENBERG',
            'END OF THE PROJECT GUTENBERG'
        ]

        end_idx = len(lines)
        for i in range(len(lines) - 1, start_idx, -1):
            for marker in end_markers:
                if marker in lines[i].upper():
                    end_idx = i
                    break
            if end_idx != len(lines):
                break

        # Extract content
        content = '\n'.join(lines[start_idx:end_idx])

        # Clean up
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    def _normalize_markdown(self, markdown: str) -> str:
        """
        Normalize markdown formatting.

        Removes anchor tags, standardizes chapter headers.

        Args:
            markdown: Markdown content

        Returns:
            Normalized markdown
        """
        try:
            # Import normalizer (lazy import to avoid circular dependencies)
            from lib.book.normalizer import normalize_markdown
            return normalize_markdown(markdown, verbose=False)
        except ImportError as e:
            print(f"⚠️  Warning: Could not import markdown_normalizer: {e}")
            print("   Skipping normalization step")
            return markdown

    def _validate_book(self, file_path: Path) -> Dict:
        """
        Validate book structure using validate.py.

        Args:
            file_path: Path to markdown file

        Returns:
            Validation results dictionary
        """
        validator_script = file_path.parent.parent.parent / "validate.py"

        if not validator_script.exists():
            # Basic validation without external script
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            word_count = len(content.split())
            chapter_matches = re.findall(r'^#+\s+(Chapter|CHAPTER)', content, re.MULTILINE)

            return {
                'valid': word_count > 100,
                'word_count': word_count,
                'chapter_count': len(chapter_matches),
                'validator_available': False
            }

        # Run validator
        try:
            result = subprocess.run(
                [sys.executable, str(validator_script), str(file_path), '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse JSON output
                output = result.stdout.strip()
                # Extract JSON from output (may have other text)
                match = re.search(r'\{.*\}', output, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    return data

        except Exception as e:
            print(f"⚠️  Validator error: {e}")

        return {'valid': True, 'validator_available': False}


def download_worker(job_id: str, gutenberg_id: int, book_slug: str):
    """
    Background worker for downloading books.

    Args:
        job_id: Job identifier
        gutenberg_id: Gutenberg book ID
        book_slug: Book directory slug
    """
    # Acquire semaphore (limit concurrent downloads)
    with download_semaphore:
        downloader = GutenbergDownloader()
        downloader.download_book(gutenberg_id, book_slug, job_id)


def create_download_job(gutenberg_id: int, book_slug: str) -> str:
    """
    Create a new download job.

    Args:
        gutenberg_id: Gutenberg book ID
        book_slug: Book directory slug

    Returns:
        Job ID
    """
    job_id = uuid.uuid4().hex[:8]

    download_jobs[job_id] = {
        'job_id': job_id,
        'status': 'pending',
        'progress': 0,
        'gutenberg_id': gutenberg_id,
        'book_slug': book_slug,
        'created_at': datetime.now().isoformat(),
        'error': None,
        'output_file': None
    }

    # Start download in background
    thread = threading.Thread(
        target=download_worker,
        args=(job_id, gutenberg_id, book_slug),
        daemon=True
    )
    thread.start()

    return job_id


def get_job_status(job_id: str) -> Optional[Dict]:
    """
    Get job status by ID.

    Args:
        job_id: Job identifier

    Returns:
        Job status dictionary, or None if not found
    """
    return download_jobs.get(job_id)


def get_all_jobs() -> list:
    """
    Get all download jobs.

    Returns:
        List of job dictionaries
    """
    return list(download_jobs.values())


def main():
    """CLI entry point"""
    if len(sys.argv) < 3:
        print("Usage: python3 server/gutenberg_downloader.py <gutenberg_id> <book_slug>")
        print("\nExample:")
        print("  python3 server/gutenberg_downloader.py 11 alice_adventures")
        sys.exit(1)

    gutenberg_id = int(sys.argv[1])
    book_slug = sys.argv[2]

    downloader = GutenbergDownloader()
    result = downloader.download_book(gutenberg_id, book_slug)

    if result['success']:
        print(f"\n✅ Success!")
        print(f"\nNext steps:")
        print(f"  1. Review the downloaded file:")
        print(f"     cat {result['output_file']}")
        print(f"\n  2. Generate audiobook:")
        print(f"     python3 make_audiobook.py {result['output_file']} --voice bf_emma --generate-cover")
        sys.exit(0)
    else:
        print(f"\n❌ Failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
