#!/usr/bin/env python3
"""
Manifest Utilities - Shared functions for working with book manifests.

This module provides utilities for:
- Loading/creating manifests
- Updating checkpoints
- Converting between manifest and legacy formats
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

from lib.book.processor import BookManifest, Chapter, BookProcessor


class ManifestManager:
    """Utilities for working with book manifests."""

    @staticmethod
    def get_or_create_manifest(input_path: Path, auto_fix: bool = True, verbose: bool = True) -> Tuple[BookManifest, Path]:
        """
        Get existing manifest or create new one from book file.

        Args:
            input_path: Path to .md book file or .json manifest
            auto_fix: Whether to auto-fix issues when creating manifest
            verbose: Whether to print progress messages

        Returns:
            Tuple of (manifest, manifest_path)
        """
        input_path = Path(input_path)

        # If already a manifest, load it
        if input_path.suffix == '.json':
            if verbose:
                print(f"📖 Loading existing manifest: {input_path.name}")
            manifest = BookManifest.load(input_path)
            return manifest, input_path

        # Generate manifest from book file
        if verbose:
            print(f"📖 Generating manifest from: {input_path.name}")

        processor = BookProcessor(verbose=verbose)
        manifest = processor.process(input_path, auto_fix=auto_fix)

        # Save manifest next to book file
        manifest_path = input_path.parent / f"{input_path.stem}_manifest.json"
        manifest.save(manifest_path)

        if verbose:
            print(f"✅ Manifest saved to: {manifest_path.name}")
            print(f"   Chapters: {len(manifest.chapters)}")
            print(f"   Language: {manifest.metadata.get('language', 'Unknown')}")

        return manifest, manifest_path

    @staticmethod
    def update_translation_checkpoint(
        manifest: BookManifest,
        manifest_path: Path,
        chapter_num: int,
        complete: bool,
        target_lang: str,
        translated_file: Optional[str] = None,
        partial_content: Optional[str] = None,
        chunk_progress: Optional[Dict] = None
    ):
        """
        Update translation checkpoint for a chapter.

        Args:
            manifest: The book manifest
            manifest_path: Path to save updated manifest
            chapter_num: Chapter number (1-based)
            complete: Whether translation is complete
            target_lang: Target language for translation
            translated_file: Path to translated file (if complete)
            partial_content: Partial translated content (if incomplete)
            chunk_progress: Progress within chapter (current/total chunks)
        """
        if chapter_num < 1 or chapter_num > len(manifest.chapters):
            raise ValueError(f"Invalid chapter number: {chapter_num}")

        chapter = manifest.chapters[chapter_num - 1]

        # Update checkpoint
        checkpoint = {
            'complete': complete,
            'target_lang': target_lang,
            'timestamp': datetime.now().isoformat()
        }

        if complete and translated_file:
            checkpoint['translated_file'] = str(translated_file)
        elif partial_content:
            checkpoint['partial_content'] = partial_content

        if chunk_progress:
            checkpoint['chunk_progress'] = chunk_progress

        chapter.checkpoints['translation'] = checkpoint

        # Save updated manifest
        manifest.save(manifest_path)

    @staticmethod
    def update_audio_checkpoint(
        manifest: BookManifest,
        manifest_path: Path,
        chapter_num: int,
        complete: bool,
        voice: str,
        speed: float = 1.0,
        chunk_files: Optional[List[str]] = None,
        chapter_file: Optional[str] = None,
        chunks_complete: int = 0,
        total_chunks: int = 0
    ):
        """
        Update audio generation checkpoint for a chapter.

        Args:
            manifest: The book manifest
            manifest_path: Path to save updated manifest
            chapter_num: Chapter number (1-based)
            complete: Whether audio generation is complete
            voice: Voice used for generation
            speed: Playback speed
            chunk_files: List of generated chunk files
            chapter_file: Final chapter audio file (if complete)
            chunks_complete: Number of chunks completed
            total_chunks: Total chunks in chapter
        """
        if chapter_num < 1 or chapter_num > len(manifest.chapters):
            raise ValueError(f"Invalid chapter number: {chapter_num}")

        chapter = manifest.chapters[chapter_num - 1]

        # Update checkpoint
        checkpoint = {
            'complete': complete,
            'voice': voice,
            'speed': speed,
            'timestamp': datetime.now().isoformat()
        }

        if complete and chapter_file:
            checkpoint['chapter_file'] = str(chapter_file)
        elif chunk_files:
            checkpoint['chunk_files'] = chunk_files

        if total_chunks > 0:
            checkpoint['progress'] = {
                'chunks_complete': chunks_complete,
                'total_chunks': total_chunks,
                'percentage': round(100 * chunks_complete / total_chunks, 1)
            }

        chapter.checkpoints['audio'] = checkpoint

        # Save updated manifest
        manifest.save(manifest_path)

    @staticmethod
    def get_incomplete_chapters(manifest: BookManifest, process_type: str) -> List[int]:
        """
        Get list of chapter numbers that are incomplete for a process.

        Args:
            manifest: The book manifest
            process_type: 'translation' or 'audio'

        Returns:
            List of chapter numbers (1-based) that are incomplete
        """
        incomplete = []

        for i, chapter in enumerate(manifest.chapters, 1):
            checkpoint = chapter.checkpoints.get(process_type)
            if not checkpoint or not checkpoint.get('complete', False):
                incomplete.append(i)

        return incomplete

    @staticmethod
    def get_resume_point(manifest: BookManifest, process_type: str) -> Optional[int]:
        """
        Get the chapter number to resume from.

        Args:
            manifest: The book manifest
            process_type: 'translation' or 'audio'

        Returns:
            Chapter number to resume from (1-based) or None if all complete
        """
        incomplete = ManifestManager.get_incomplete_chapters(manifest, process_type)
        return incomplete[0] if incomplete else None

    @staticmethod
    def manifest_to_legacy_structure(manifest: BookManifest) -> Dict:
        """
        Convert manifest to legacy BookStructure format for backwards compatibility.

        Args:
            manifest: The book manifest

        Returns:
            Dictionary compatible with legacy BookStructure
        """
        # This is used for backwards compatibility with existing code
        from dataclasses import dataclass

        @dataclass
        class LegacyChapter:
            number: int
            marker: str
            content: str
            start_line: int
            end_line: int
            metadata: Dict

        legacy_chapters = []
        for ch in manifest.chapters:
            legacy_chapters.append(LegacyChapter(
                number=ch.number,
                marker=ch.marker,
                content=ch.content,
                start_line=ch.start_line,
                end_line=ch.end_line,
                metadata={'type': ch.detection_type}
            ))

        return {
            'metadata': manifest.metadata,
            'chapters': legacy_chapters,
            'original_file': Path(manifest.original_file)
        }

    @staticmethod
    def print_progress_report(manifest: BookManifest):
        """
        Print a progress report for all processes.

        Args:
            manifest: The book manifest
        """
        print("\n" + "=" * 60)
        print("PROCESSING PROGRESS REPORT")
        print("=" * 60)
        print(f"Book: {manifest.metadata.get('title', 'Unknown')}")
        print(f"Chapters: {len(manifest.chapters)}")
        print()

        # Translation progress
        translation_complete = sum(
            1 for ch in manifest.chapters
            if ch.checkpoints.get('translation', {}).get('complete', False)
        )
        print(f"📚 Translation: {translation_complete}/{len(manifest.chapters)} chapters")

        if translation_complete < len(manifest.chapters):
            incomplete = ManifestManager.get_incomplete_chapters(manifest, 'translation')
            print(f"   Incomplete: {', '.join(map(str, incomplete[:5]))}")
            if len(incomplete) > 5:
                print(f"   ... and {len(incomplete) - 5} more")

        # Audio progress
        audio_complete = sum(
            1 for ch in manifest.chapters
            if ch.checkpoints.get('audio', {}).get('complete', False)
        )
        print(f"🎵 Audio: {audio_complete}/{len(manifest.chapters)} chapters")

        if audio_complete < len(manifest.chapters):
            incomplete = ManifestManager.get_incomplete_chapters(manifest, 'audio')
            print(f"   Incomplete: {', '.join(map(str, incomplete[:5]))}")
            if len(incomplete) > 5:
                print(f"   ... and {len(incomplete) - 5} more")

        print("=" * 60)
        print()


def main():
    """Test/demo the manifest utilities."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python manifest_utils.py <book.md or manifest.json>")
        print("\nThis will load or create a manifest and show progress.")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    # Get or create manifest
    manifest, manifest_path = ManifestManager.get_or_create_manifest(input_path)

    # Print progress report
    ManifestManager.print_progress_report(manifest)

    # Show resume points
    trans_resume = ManifestManager.get_resume_point(manifest, 'translation')
    audio_resume = ManifestManager.get_resume_point(manifest, 'audio')

    if trans_resume:
        print(f"📖 Translation would resume from chapter {trans_resume}")
    else:
        print("✅ Translation complete (or not started)")

    if audio_resume:
        print(f"🎵 Audio would resume from chapter {audio_resume}")
    else:
        print("✅ Audio complete (or not started)")


if __name__ == "__main__":
    main()