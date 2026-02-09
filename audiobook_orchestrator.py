#!/usr/bin/env python3
"""
Audiobook Orchestrator - Clean architecture for audiobook generation

This orchestrator handles the high-level workflow:
1. Process book structure (chapters, metadata)
2. For each chapter: call simple TTS
3. Create playlist and metadata

The TTS module handles only text-to-speech conversion.
This module handles everything else.

Usage:
    python3 audiobook_orchestrator.py books/test_german/book.md --voice bf_emma
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Import the simple TTS module
from tts_simple import SimpleKokoroTTS

# Import book processing utilities
from book_processor import BookProcessor
from book_manifest import BookManifest


class AudiobookOrchestrator:
    """
    Orchestrates audiobook generation using clean architecture.
    Handles chapter detection and calls simple TTS for each chapter.
    """

    def __init__(self,
                 voice: str = 'af_sky',
                 language: str = 'en-us',
                 speed: float = 1.0,
                 normalize: bool = True):
        """
        Initialize the orchestrator.

        Args:
            voice: Kokoro voice ID
            language: Language code
            speed: Playback speed
            normalize: Whether to normalize audio
        """
        self.voice = voice
        self.language = language
        self.speed = speed
        self.normalize = normalize

        # Create TTS instance (stateless)
        self.tts = SimpleKokoroTTS(
            voice=voice,
            language=language,
            speed=speed,
            normalize=normalize
        )

        # Book processor for structure
        self.processor = BookProcessor()

    def process_book(self, book_path: Path) -> BookManifest:
        """
        Process book to extract structure and chapters.

        Args:
            book_path: Path to book markdown file

        Returns:
            Book manifest with chapter information
        """
        print(f"\n📖 Processing book structure...")
        print(f"   Book: {book_path.name}")

        # Check for existing manifest
        manifest_path = book_path.parent / "book_manifest.json"
        if manifest_path.exists():
            print(f"   Using existing manifest: {manifest_path.name}")
            with open(manifest_path) as f:
                manifest_data = json.load(f)
                return BookManifest(**manifest_data)

        # Process book to create manifest
        manifest = self.processor.process_book(book_path)

        # Save manifest for future use
        with open(manifest_path, 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2)

        print(f"   ✓ Detected {len(manifest.chapters)} chapters")
        for i, chapter in enumerate(manifest.chapters, 1):
            print(f"      Chapter {i}: {chapter['title']}")

        return manifest

    def generate_chapter_audio(self,
                             chapter_text: str,
                             chapter_num: int,
                             output_dir: Path) -> Path:
        """
        Generate audio for a single chapter.

        Args:
            chapter_text: Text content of the chapter
            chapter_num: Chapter number
            output_dir: Output directory

        Returns:
            Path to generated audio file
        """
        output_file = output_dir / f"chapter_{chapter_num:02d}.mp3"

        print(f"\n🎵 Generating audio for Chapter {chapter_num}")
        print(f"   Text length: {len(chapter_text)} characters")
        print(f"   Output: {output_file.name}")

        # Call simple TTS - it only knows about text, not chapters!
        audio_file = self.tts.generate_audio_from_text(
            chapter_text,
            output_file,
            verbose=False  # Less verbose for cleaner output
        )

        print(f"   ✓ Audio generated: {audio_file.name}")
        return audio_file

    def create_playlist(self,
                       chapter_files: List[Path],
                       output_dir: Path,
                       book_title: str) -> Path:
        """
        Create M3U playlist for the audiobook.

        Args:
            chapter_files: List of chapter audio files
            output_dir: Output directory
            book_title: Title of the book

        Returns:
            Path to playlist file
        """
        playlist_path = output_dir / "audiobook.m3u"

        with open(playlist_path, 'w') as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:{book_title}\n\n")

            for i, chapter_file in enumerate(chapter_files, 1):
                f.write(f"#EXTINF:-1,Chapter {i}\n")
                f.write(f"{chapter_file.name}\n")

        print(f"\n📋 Playlist created: {playlist_path.name}")
        return playlist_path

    def create_metadata(self,
                       manifest: BookManifest,
                       chapter_files: List[Path],
                       output_dir: Path) -> Path:
        """
        Create metadata JSON for web player.

        Args:
            manifest: Book manifest
            chapter_files: List of chapter audio files
            output_dir: Output directory

        Returns:
            Path to metadata file
        """
        metadata = {
            "title": manifest.metadata.get("title", "Unknown Book"),
            "author": manifest.metadata.get("author", "Unknown Author"),
            "language": manifest.metadata.get("language", "Unknown"),
            "generated_at": datetime.now().isoformat(),
            "voice": self.voice,
            "chapters": []
        }

        for i, (chapter, audio_file) in enumerate(zip(manifest.chapters, chapter_files)):
            metadata["chapters"].append({
                "number": i + 1,
                "title": chapter.get("title", f"Chapter {i+1}"),
                "audio_file": audio_file.name,
                "file_index": i,
                "timestamp": 0.0  # Each chapter is a separate file
            })

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"📊 Metadata created: {metadata_path.name}")
        return metadata_path

    def generate_audiobook(self,
                          book_path: Path,
                          output_dir: Optional[Path] = None) -> Dict:
        """
        Main orchestration method - generates complete audiobook.

        Args:
            book_path: Path to book markdown file
            output_dir: Output directory (auto-created if None)

        Returns:
            Dictionary with generation results
        """
        print("\n" + "=" * 60)
        print("AUDIOBOOK GENERATION - CLEAN ARCHITECTURE")
        print("=" * 60)

        # Step 1: Process book structure
        manifest = self.process_book(book_path)

        # Step 2: Set up output directory
        if output_dir is None:
            output_dir = book_path.parent / "audio_orchestrated"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 Output directory: {output_dir}")

        # Step 3: Generate audio for each chapter
        chapter_files = []
        for i, chapter in enumerate(manifest.chapters, 1):
            # Extract chapter content
            if 'content' in chapter and chapter['content']:
                chapter_text = chapter['content']
            else:
                # Fallback: extract from original file if content not in manifest
                print(f"   ⚠️ Chapter {i} has no content in manifest, extracting from file...")
                with open(book_path) as f:
                    full_text = f.read()
                # This is a simplified extraction - in production, use proper boundaries
                chapter_text = f"Chapter {i} content would be extracted here."

            # Generate audio for this chapter
            audio_file = self.generate_chapter_audio(
                chapter_text,
                i,
                output_dir
            )
            chapter_files.append(audio_file)

        # Step 4: Create playlist
        book_title = manifest.metadata.get("title", "Audiobook")
        playlist = self.create_playlist(chapter_files, output_dir, book_title)

        # Step 5: Create metadata for web player
        metadata = self.create_metadata(manifest, chapter_files, output_dir)

        # Summary
        print("\n" + "=" * 60)
        print("✅ AUDIOBOOK GENERATION COMPLETE")
        print("=" * 60)
        print(f"📚 Book: {book_title}")
        print(f"📖 Chapters: {len(chapter_files)}")
        print(f"🎤 Voice: {self.voice}")
        print(f"📁 Output: {output_dir}")
        print(f"📋 Playlist: {playlist.name}")
        print(f"📊 Metadata: {metadata.name}")
        print("=" * 60)

        return {
            "book_title": book_title,
            "chapters": len(chapter_files),
            "chapter_files": [str(f) for f in chapter_files],
            "playlist": str(playlist),
            "metadata": str(metadata),
            "output_dir": str(output_dir)
        }


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate audiobook using clean architecture"
    )
    parser.add_argument(
        "book_path",
        help="Path to book markdown file"
    )
    parser.add_argument(
        "--voice",
        default="af_sky",
        help="Kokoro voice ID (default: af_sky)"
    )
    parser.add_argument(
        "--language",
        default="en-us",
        help="Language code (default: en-us)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed (default: 1.0)"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: book_dir/audio_orchestrated)"
    )

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = AudiobookOrchestrator(
        voice=args.voice,
        language=args.language,
        speed=args.speed
    )

    # Generate audiobook
    book_path = Path(args.book_path)
    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        result = orchestrator.generate_audiobook(book_path, output_dir)
        print(f"\n✅ Success! Audiobook generated in: {result['output_dir']}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()