#!/usr/bin/env python3
"""
Book Manifest - Data structure for book metadata and chapters

Simple data class to represent a book's structure.
Used by the orchestrator to understand chapters without
the TTS needing to know about book structure.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class BookManifest:
    """
    Represents a book's structure and metadata.

    This is the single source of truth for book structure,
    shared between all components of the pipeline.
    """

    # Basic metadata
    metadata: Dict[str, str] = field(default_factory=dict)

    # Chapter information
    chapters: List[Dict] = field(default_factory=list)

    # Processing information
    processing: Dict[str, any] = field(default_factory=dict)

    # Optional fields
    version: str = "2.0"
    original_file: Optional[str] = None
    processed_at: Optional[str] = None
    toc_markdown: Optional[str] = None
    processing_log: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert manifest to dictionary for JSON serialization."""
        return asdict(self)

    def get_chapter_count(self) -> int:
        """Get the number of chapters."""
        return len(self.chapters)

    def get_chapter_by_number(self, number: int) -> Optional[Dict]:
        """Get a chapter by its number (1-indexed)."""
        for chapter in self.chapters:
            if chapter.get('number') == number:
                return chapter
        return None

    def add_chapter(self,
                   title: str,
                   content: str = "",
                   marker: str = "",
                   detection_type: str = "manual") -> None:
        """
        Add a new chapter to the manifest.

        Args:
            title: Chapter title
            content: Chapter text content
            marker: Original chapter marker from source
            detection_type: How the chapter was detected
        """
        chapter_num = len(self.chapters) + 1

        self.chapters.append({
            'number': chapter_num,
            'title': title,
            'content': content,
            'marker': marker,
            'detection_type': detection_type,
            'word_count': len(content.split()) if content else 0,
            'char_count': len(content) if content else 0,
            'checkpoints': {
                'translation': None,
                'audio': None
            }
        })

    def update_checkpoint(self,
                         chapter_num: int,
                         checkpoint_type: str,
                         status: str) -> None:
        """
        Update processing checkpoint for a chapter.

        Args:
            chapter_num: Chapter number (1-indexed)
            checkpoint_type: Type of checkpoint ('translation' or 'audio')
            status: Status value (e.g., 'completed', 'in_progress')
        """
        chapter = self.get_chapter_by_number(chapter_num)
        if chapter and 'checkpoints' in chapter:
            chapter['checkpoints'][checkpoint_type] = {
                'status': status,
                'timestamp': datetime.now().isoformat()
            }

    @classmethod
    def create_minimal(cls,
                      title: str,
                      author: str,
                      chapters: List[str]) -> 'BookManifest':
        """
        Create a minimal manifest for testing.

        Args:
            title: Book title
            author: Book author
            chapters: List of chapter titles

        Returns:
            New BookManifest instance
        """
        manifest = cls(
            metadata={
                'title': title,
                'author': author,
                'language': 'Unknown'
            },
            processed_at=datetime.now().isoformat()
        )

        for chapter_title in chapters:
            manifest.add_chapter(title=chapter_title)

        return manifest