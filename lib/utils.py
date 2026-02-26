"""
Local Reader Utilities Module

Shared utility functions for text processing, file management, and helpers.
"""

import re
import os
import json
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
import hashlib


def safe_json_write(path: Path, data: dict, indent: int = 2) -> None:
    """Atomically write JSON data to a file using write-then-rename.

    Writes to a temporary file first, flushes to disk, then atomically
    replaces the target file. This prevents corruption if the process
    crashes mid-write.
    """
    path = Path(path)
    tmp_path = path.with_suffix('.json.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp_path), str(path))


class TextProcessor:
    """Utilities for processing and analyzing text"""

    @staticmethod
    def count_words(text: str) -> int:
        """
        Count words in text.

        Args:
            text: The text to analyze

        Returns:
            Word count
        """
        # Remove Markdown formatting for accurate count
        clean_text = TextProcessor.strip_markdown(text)
        words = clean_text.split()
        return len(words)

    @staticmethod
    def strip_markdown(text: str) -> str:
        """
        Remove Markdown formatting from text.

        Args:
            text: Text with Markdown formatting

        Returns:
            Plain text
        """
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # Remove bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # Remove links but keep text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        # Remove images
        text = re.sub(r'!\[.+?\]\(.+?\)', '', text)

        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`(.+?)`', r'\1', text)

        # Remove tables (keep content)
        text = re.sub(r'\|', ' ', text)

        # Remove list markers
        text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)

        # Remove blockquotes
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        return text.strip()

    @staticmethod
    def estimate_reading_time(
        text: str,
        words_per_minute: int = 160
    ) -> Tuple[int, int]:
        """
        Estimate reading/listening time for text.

        Args:
            text: The text to analyze
            words_per_minute: Average reading speed

        Returns:
            Tuple of (hours, minutes)
        """
        word_count = TextProcessor.count_words(text)
        total_minutes = word_count / words_per_minute

        hours = int(total_minutes // 60)
        minutes = int(total_minutes % 60)

        return hours, minutes

    @staticmethod
    def calculate_compression_ratio(
        target_hours: int,
        target_minutes: int,
        total_words: int,
        words_per_minute: int = 160
    ) -> float:
        """
        Calculate required compression ratio based on time budget.

        Args:
            target_hours: Desired hours
            target_minutes: Desired minutes
            total_words: Total words in original text
            words_per_minute: Reading speed

        Returns:
            Compression ratio (0.0 to 1.0)
        """
        total_target_minutes = (target_hours * 60) + target_minutes
        target_words = total_target_minutes * words_per_minute

        if total_words == 0:
            return 1.0

        ratio = target_words / total_words

        # Clamp between 0.1 and 0.9
        return max(0.1, min(0.9, ratio))

    @staticmethod
    def clean_gutenberg_text(text: str) -> str:
        """
        Remove Project Gutenberg headers and footers.

        Args:
            text: Raw Gutenberg text

        Returns:
            Cleaned text
        """
        # Find the start of the actual book content
        start_markers = [
            r'\*\*\* START OF THIS PROJECT GUTENBERG',
            r'\*\*\* START OF THE PROJECT GUTENBERG',
            r'START OF THIS PROJECT GUTENBERG'
        ]

        for marker in start_markers:
            match = re.search(marker, text, re.IGNORECASE)
            if match:
                # Find the end of the header line
                next_newline = text.find('\n', match.end())
                if next_newline != -1:
                    text = text[next_newline:].lstrip()
                break

        # Find the end of the actual book content
        end_markers = [
            r'\*\*\* END OF THIS PROJECT GUTENBERG',
            r'\*\*\* END OF THE PROJECT GUTENBERG',
            r'END OF THIS PROJECT GUTENBERG'
        ]

        for marker in end_markers:
            match = re.search(marker, text, re.IGNORECASE)
            if match:
                text = text[:match.start()].rstrip()
                break

        return text


class FileManager:
    """Utilities for file and path management"""

    @staticmethod
    def generate_filename(
        book_title: str,
        target_language: str,
        model_name: str,
        extension: str = "md",
        include_timestamp: bool = True
    ) -> str:
        """
        Generate standardized filename for processed books.

        Args:
            book_title: Title of the book
            target_language: Target language
            model_name: Model used for processing
            extension: File extension (default: md)
            include_timestamp: Include date in filename

        Returns:
            Formatted filename
        """
        # Sanitize book title
        safe_title = FileManager.sanitize_filename(book_title)

        # Sanitize language
        safe_language = target_language.lower().replace(' ', '_')

        # Extract model version (e.g., "4b" from "zongwei/gemma3-translator:4b")
        model_version = model_name.split(':')[-1] if ':' in model_name else model_name

        # Build filename
        parts = [safe_title, safe_language]

        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d")
            parts.append(timestamp)

        parts.append(model_version)

        filename = '_'.join(parts) + f'.{extension}'
        return filename

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a string for use as a filename.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Convert to lowercase
        filename = filename.lower()

        # Replace spaces and special chars with underscores
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '_', filename)

        # Remove leading/trailing underscores
        filename = filename.strip('_')

        return filename

    @staticmethod
    def get_file_hash(filepath: str, algorithm: str = "md5") -> str:
        """
        Calculate hash of a file.

        Args:
            filepath: Path to file
            algorithm: Hash algorithm (md5, sha256)

        Returns:
            Hex digest of file hash
        """
        hash_func = hashlib.new(algorithm)

        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_func.update(chunk)

        return hash_func.hexdigest()

    @staticmethod
    def ensure_directory(path: str) -> Path:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path

        Returns:
            Path object
        """
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj


class ProgressTracker:
    """Track and display progress for long-running operations"""

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the operation
        """
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = datetime.now()

    def update(self, increment: int = 1):
        """
        Update progress.

        Args:
            increment: Number of items completed
        """
        self.current += increment
        self._display_progress()

    def _display_progress(self):
        """Display current progress"""
        percentage = (self.current / self.total) * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()

        # Estimate remaining time
        if self.current > 0:
            rate = self.current / elapsed
            remaining_items = self.total - self.current
            eta_seconds = remaining_items / rate if rate > 0 else 0
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "calculating..."

        print(f"\r{self.description}: {self.current}/{self.total} "
              f"({percentage:.1f}%) - ETA: {eta_str}", end='', flush=True)

        if self.current >= self.total:
            print()  # New line when complete

    @staticmethod
    def _format_time(seconds: float) -> str:
        """
        Format seconds into human-readable time.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


class MarkdownHelper:
    """Utilities for working with Markdown documents"""

    @staticmethod
    def extract_title(text: str) -> Optional[str]:
        """
        Extract the title from Markdown (first H1 header).

        Args:
            text: Markdown text

        Returns:
            Title string or None
        """
        match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def extract_headers(text: str) -> List[Tuple[int, str]]:
        """
        Extract all headers from Markdown.

        Args:
            text: Markdown text

        Returns:
            List of (level, title) tuples
        """
        headers = []
        pattern = r'^(#{1,6})\s+(.+)$'

        for match in re.finditer(pattern, text, re.MULTILINE):
            level = len(match.group(1))
            title = match.group(2).strip()
            headers.append((level, title))

        return headers

    @staticmethod
    def create_table_of_contents(text: str) -> str:
        """
        Generate a table of contents from headers.

        Args:
            text: Markdown text

        Returns:
            Markdown table of contents
        """
        headers = MarkdownHelper.extract_headers(text)

        if not headers:
            return ""

        toc_lines = ["# Table of Contents\n"]

        for level, title in headers:
            # Skip the main title (H1)
            if level == 1:
                continue

            # Create anchor link
            anchor = title.lower()
            anchor = re.sub(r'[^\w\s-]', '', anchor)
            anchor = re.sub(r'[-\s]+', '-', anchor)

            # Indent based on header level
            indent = "  " * (level - 2)
            toc_lines.append(f"{indent}- [{title}](#{anchor})")

        return '\n'.join(toc_lines)


if __name__ == "__main__":
    # Test utilities
    sample_text = """# Test Book

This is a test paragraph with **bold** and *italic* text.

## Chapter 1

Some content here with [a link](https://example.com).

- List item 1
- List item 2
"""

    print("Text Processing Tests:")
    print(f"Word count: {TextProcessor.count_words(sample_text)}")
    print(f"Reading time: {TextProcessor.estimate_reading_time(sample_text)}")
    print(f"Stripped text: {TextProcessor.strip_markdown(sample_text)[:50]}...")

    print("\nMarkdown Tests:")
    print(f"Title: {MarkdownHelper.extract_title(sample_text)}")
    print(f"Headers: {MarkdownHelper.extract_headers(sample_text)}")

    print("\nFilename Generation:")
    filename = FileManager.generate_filename(
        "Thus Spoke Zarathustra",
        "Modern English",
        "zongwei/gemma3-translator:4b"
    )
    print(f"Generated filename: {filename}")
