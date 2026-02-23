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


class GutenbergDownloader:
    """Download and process Gutenberg books"""

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
            markdown = self._html_to_markdown(html_content)

            if job_id:
                download_jobs[job_id]['progress'] = 60

            # Strip boilerplate
            print("✂️  Stripping Gutenberg boilerplate...")
            cleaned = self._strip_boilerplate(markdown)

            # Normalize markdown formatting
            print("🔧 Normalizing markdown formatting...")
            normalized = self._normalize_markdown(cleaned)

            # Save to file
            output_file = book_dir / "source.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(normalized)

            print(f"✓ Saved: {output_file}")

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
        Extract table of contents from Gutenberg HTML.

        Gutenberg books often have a TOC section with internal anchor links like:
            <a href="#chap01">CHAPITRE I. Comment Candide...</a>
            <a href="#link2H_4_0002">Chapter I</a>

        Returns:
            List of dicts with 'anchor', 'title', 'number' keys
        """
        toc_entries = []

        # Find internal links that point to anchors within the document
        internal_links = soup.find_all('a', href=re.compile(r'^#'))

        # Multilingual chapter keyword pattern
        chapter_kw = re.compile(
            r'(chapter|chapitre|kapitel|capítulo|capitolo|глава|'
            r'part|partie|teil|parte|часть|'
            r'book|livre|buch|libro|книга|'
            r'act|scene|acte|akt|'
            r'prologue|epilogue|préface|introduction|conclusion)',
            re.IGNORECASE
        )

        chapter_links = []
        for link in internal_links:
            href = link.get('href', '')[1:]  # Remove leading #
            text = link.get_text(strip=True)
            if not text or not href:
                continue

            is_chapter = bool(chapter_kw.search(text))
            # Also accept standalone Roman numerals (e.g., "I.", "XIV.")
            if not is_chapter:
                is_chapter = bool(re.match(r'^[IVXLCDM]+\.?\s', text))

            if is_chapter:
                chapter_links.append({'anchor': href, 'title': text})

        # Need at least 3 chapter links to consider it a real TOC
        if len(chapter_links) < 3:
            return []

        for i, entry in enumerate(chapter_links):
            title = entry['title']
            # Try to extract chapter number (Roman or Arabic)
            num_match = re.search(r'\b([IVXLCDM]+)\b', title)
            number = i + 1
            if num_match:
                try:
                    number = self._roman_to_int(num_match.group(1))
                except Exception:
                    pass
            else:
                digit_match = re.search(r'\b(\d+)\b', title)
                if digit_match:
                    try:
                        number = int(digit_match.group(1))
                    except Exception:
                        pass

            toc_entries.append({
                'anchor': entry['anchor'],
                'title': title,
                'number': number
            })

        return toc_entries

    def _normalize_chapter_title(self, original_title: str, chapter_number: int) -> str:
        """
        Convert a multilingual chapter title to standardized markdown format.

        Examples:
            "CHAPITRE I. Comment Candide fut élevé" → "Chapter 1. Comment Candide fut élevé"
            "Chapter XIV" → "Chapter 14"
        """
        title = original_title
        # Remove chapter keyword in any language
        title = re.sub(
            r'^(CHAPITRE|Chapitre|CHAPTER|Chapter|KAPITEL|Kapitel|'
            r'CAPÍTULO|Capítulo|CAPITOLO|Capitolo|Глава)\s+',
            '', title, flags=re.IGNORECASE
        )
        # Remove leading Roman numeral or number with optional dot
        title = re.sub(r'^([IVXLCDM]+|\d+)\.?\s*', '', title)
        # Clean up extra punctuation
        title = title.strip().strip('.').strip()

        if title:
            return f"Chapter {chapter_number}. {title}"
        else:
            return f"Chapter {chapter_number}"

    def _inject_chapter_headers(self, soup, toc_entries: list):
        """
        Inject <h2> chapter headers into HTML at anchor target positions.

        For each TOC entry, find the matching anchor target (by name or id attribute)
        and insert a standardized chapter header element after it.
        """
        anchor_map = {entry['anchor']: entry for entry in toc_entries}

        for anchor_id, entry in anchor_map.items():
            # Find elements with matching name or id attribute
            targets = soup.find_all(attrs={'name': anchor_id})
            targets += soup.find_all(attrs={'id': anchor_id})

            for target in targets:
                title = self._normalize_chapter_title(entry['title'], entry['number'])
                h2 = soup.new_tag('h2')
                h2.string = title
                target.insert_after(h2)

    def _html_to_markdown(self, html: str) -> str:
        """
        Convert HTML to Markdown.

        Args:
            html: HTML content

        Returns:
            Markdown content
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        # Extract TOC and inject chapter headers before conversion
        toc_entries = self._extract_toc_from_html(soup)
        if toc_entries:
            print(f"  Found {len(toc_entries)} chapters in HTML TOC")
            self._inject_chapter_headers(soup, toc_entries)

        # Get body content
        body = soup.body if soup.body else soup

        # Convert to markdown
        markdown = self._convert_element_to_markdown(body)

        # Strip "end chapter" artifacts from HTML chapter div markers
        markdown = re.sub(r'end chapter', '', markdown, flags=re.IGNORECASE)

        # Clean up excessive whitespace
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        return markdown.strip()

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
