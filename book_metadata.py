#!/usr/bin/env python3
"""
Book Metadata Management

Centralized metadata tracking for all book processing operations:
- Translations (source/target language, model, timestamp)
- Summarizations (compression ratio, model, passes)
- Audio generation (voice, language, duration)

Metadata is stored as JSON sidecar files alongside processed files.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class TranslationMetadata:
    """Metadata for translation operations"""
    source_language: str
    target_language: str
    model: str
    timestamp: str
    original_file: str
    word_count_original: int
    word_count_translated: int
    chunks_processed: int
    duration_seconds: float


@dataclass
class SummarizationMetadata:
    """Metadata for summarization operations"""
    target_percentage: int
    actual_percentage: float
    model: str
    timestamp: str
    original_file: str
    word_count_original: int
    word_count_summarized: int
    chunks_processed: int
    duration_seconds: float
    recursive_passes: int = 1  # 1 = single pass, 2+ = multi-pass


@dataclass
class AudioMetadata:
    """Metadata for audio generation"""
    voice_reference: str
    language: str
    model: str  # e.g., "xtts-v2", "openai-tts"
    timestamp: str
    source_file: str
    audio_chunks: int
    duration_seconds: Optional[float] = None
    processing_time_seconds: Optional[float] = None
    speed_multiplier: float = 1.0
    normalized: bool = False


@dataclass
class BookMetadata:
    """Complete metadata for a processed book"""
    book_title: str
    original_file: str
    created_at: str
    updated_at: str

    # Processing chain history
    translations: List[TranslationMetadata] = None
    summarizations: List[SummarizationMetadata] = None
    audio_generations: List[AudioMetadata] = None

    # Current state
    current_language: Optional[str] = None
    current_word_count: Optional[int] = None
    is_summarized: bool = False
    has_audio: bool = False

    def __post_init__(self):
        if self.translations is None:
            self.translations = []
        if self.summarizations is None:
            self.summarizations = []
        if self.audio_generations is None:
            self.audio_generations = []


class MetadataManager:
    """Manages book metadata storage and retrieval"""

    METADATA_SUFFIX = ".meta.json"

    @staticmethod
    def get_metadata_path(file_path: Path) -> Path:
        """Get the metadata file path for a given book file"""
        return file_path.parent / f"{file_path.stem}{MetadataManager.METADATA_SUFFIX}"

    @staticmethod
    def load(file_path: Path) -> Optional[BookMetadata]:
        """Load metadata for a book file"""
        metadata_path = MetadataManager.get_metadata_path(file_path)

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct dataclasses
            if 'translations' in data and data['translations']:
                data['translations'] = [
                    TranslationMetadata(**t) for t in data['translations']
                ]
            if 'summarizations' in data and data['summarizations']:
                data['summarizations'] = [
                    SummarizationMetadata(**s) for s in data['summarizations']
                ]
            if 'audio_generations' in data and data['audio_generations']:
                data['audio_generations'] = [
                    AudioMetadata(**a) for a in data['audio_generations']
                ]

            return BookMetadata(**data)
        except Exception as e:
            print(f"⚠️  Warning: Failed to load metadata from {metadata_path}: {e}")
            return None

    @staticmethod
    def save(file_path: Path, metadata: BookMetadata):
        """Save metadata for a book file"""
        metadata_path = MetadataManager.get_metadata_path(file_path)

        # Update timestamp
        metadata.updated_at = datetime.now().isoformat()

        # Convert to dict (handle nested dataclasses)
        data = asdict(metadata)

        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Warning: Failed to save metadata to {metadata_path}: {e}")

    @staticmethod
    def create_or_update(
        file_path: Path,
        book_title: Optional[str] = None,
        original_file: Optional[str] = None
    ) -> BookMetadata:
        """Create new metadata or load existing"""
        existing = MetadataManager.load(file_path)

        if existing:
            return existing

        # Create new
        return BookMetadata(
            book_title=book_title or file_path.stem,
            original_file=original_file or str(file_path),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

    @staticmethod
    def add_translation(
        file_path: Path,
        translation: TranslationMetadata,
        book_title: Optional[str] = None
    ):
        """Add translation metadata to a file"""
        metadata = MetadataManager.create_or_update(file_path, book_title)
        metadata.translations.append(translation)
        metadata.current_language = translation.target_language
        metadata.current_word_count = translation.word_count_translated
        MetadataManager.save(file_path, metadata)

    @staticmethod
    def add_summarization(
        file_path: Path,
        summarization: SummarizationMetadata,
        book_title: Optional[str] = None
    ):
        """Add summarization metadata to a file"""
        metadata = MetadataManager.create_or_update(file_path, book_title)
        metadata.summarizations.append(summarization)
        metadata.current_word_count = summarization.word_count_summarized
        metadata.is_summarized = True
        MetadataManager.save(file_path, metadata)

    @staticmethod
    def add_audio(
        file_path: Path,
        audio: AudioMetadata,
        book_title: Optional[str] = None
    ):
        """Add audio generation metadata to a file"""
        metadata = MetadataManager.create_or_update(file_path, book_title)
        metadata.audio_generations.append(audio)
        metadata.has_audio = True
        MetadataManager.save(file_path, metadata)

    @staticmethod
    def print_metadata(file_path: Path):
        """Print human-readable metadata summary"""
        metadata = MetadataManager.load(file_path)

        if not metadata:
            print(f"No metadata found for: {file_path}")
            return

        print("\n" + "="*70)
        print(f"METADATA: {metadata.book_title}")
        print("="*70)
        print(f"Original file: {metadata.original_file}")
        print(f"Created: {metadata.created_at}")
        print(f"Updated: {metadata.updated_at}")
        print()

        if metadata.current_language:
            print(f"Current language: {metadata.current_language}")
        if metadata.current_word_count:
            print(f"Current word count: {metadata.current_word_count:,}")
        if metadata.is_summarized:
            print(f"Summarized: Yes")
        if metadata.has_audio:
            print(f"Has audio: Yes")

        # Translation history
        if metadata.translations:
            print("\n" + "-"*70)
            print("TRANSLATION HISTORY")
            print("-"*70)
            for i, trans in enumerate(metadata.translations, 1):
                print(f"\n{i}. {trans.source_language} → {trans.target_language}")
                print(f"   Model: {trans.model}")
                print(f"   Words: {trans.word_count_original:,} → {trans.word_count_translated:,}")
                print(f"   Chunks: {trans.chunks_processed}")
                print(f"   Duration: {trans.duration_seconds:.1f}s ({trans.duration_seconds/60:.1f}min)")
                print(f"   Date: {trans.timestamp}")

        # Summarization history
        if metadata.summarizations:
            print("\n" + "-"*70)
            print("SUMMARIZATION HISTORY")
            print("-"*70)
            for i, summ in enumerate(metadata.summarizations, 1):
                print(f"\n{i}. {summ.target_percentage}% compression")
                print(f"   Model: {summ.model}")
                print(f"   Words: {summ.word_count_original:,} → {summ.word_count_summarized:,}")
                print(f"   Actual: {summ.actual_percentage:.1f}%")
                print(f"   Passes: {summ.recursive_passes}")
                print(f"   Duration: {summ.duration_seconds:.1f}s ({summ.duration_seconds/60:.1f}min)")
                print(f"   Date: {summ.timestamp}")

        # Audio history
        if metadata.audio_generations:
            print("\n" + "-"*70)
            print("AUDIO GENERATION HISTORY")
            print("-"*70)
            for i, audio in enumerate(metadata.audio_generations, 1):
                print(f"\n{i}. {audio.model}")
                print(f"   Language: {audio.language}")
                print(f"   Voice: {audio.voice_reference}")
                print(f"   Chunks: {audio.audio_chunks}")
                if audio.speed_multiplier != 1.0:
                    print(f"   Speed: {audio.speed_multiplier}x")
                if audio.normalized:
                    print(f"   Normalized: Yes")
                if audio.processing_time_seconds:
                    print(f"   Processing time: {audio.processing_time_seconds:.1f}s ({audio.processing_time_seconds/60:.1f}min)")
                print(f"   Date: {audio.timestamp}")

        print("\n" + "="*70)


def main():
    """CLI for viewing metadata"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python book_metadata.py <file_path>")
        print("\nDisplays metadata for a processed book file")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"❌ ERROR: File not found: {file_path}")
        sys.exit(1)

    MetadataManager.print_metadata(file_path)


if __name__ == "__main__":
    main()
