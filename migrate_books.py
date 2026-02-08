#!/usr/bin/env python3
"""
Book Directory Migration Script

Migrates from messy structure to clean structure:

OLD (messy):
  books/alice/
    - alices_adventures.md
    - alices_adventures_cleaned.md
    - alices_adventures_original.md
    - alices_adventures_spanish.md
    - audio_kokoro/*.mp3

NEW (clean):
  books/alice/
    - book.md                    # Single source of truth
    - metadata.json              # All metadata
    - translations/
      - spanish.md
    - audio/
      - original/*.mp3
      - spanish/*.mp3
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import re


class BookMigrator:
    """Migrates book directories to clean structure"""

    def __init__(self, books_dir: Path):
        self.books_dir = Path(books_dir)
        self.stats = {
            'books_processed': 0,
            'files_moved': 0,
            'files_deleted': 0,
            'duplicates_removed': 0
        }

    def identify_source_file(self, book_dir: Path) -> Optional[Path]:
        """
        Identify the best source markdown file.

        Priority:
        1. Shortest filename without _cleaned, _original, _translated, etc.
        2. Most common base name
        3. Largest file
        """
        md_files = list(book_dir.glob('*.md'))

        if not md_files:
            return None

        # Filter out obvious derivatives
        main_candidates = [
            f for f in md_files
            if '_cleaned' not in f.name
            and '_original' not in f.name
            and '_modern' not in f.name
            and '_spanish' not in f.name
            and '_english' not in f.name
            and 'chunk' not in f.name.lower()
            and not f.name.startswith('_')
        ]

        if main_candidates:
            # Return shortest name (likely the original)
            return min(main_candidates, key=lambda f: len(f.name))

        # Fallback: return largest file
        return max(md_files, key=lambda f: f.stat().st_size)

    def identify_translations(self, book_dir: Path, source: Path) -> List[tuple]:
        """
        Identify translation files.

        Returns: List of (lang, filepath) tuples
        """
        translations = []
        md_files = list(book_dir.glob('*.md'))

        for f in md_files:
            if f == source:
                continue

            # Skip obvious duplicates
            if '_cleaned' in f.name or '_original' in f.name:
                continue

            # Detect language from filename
            name_lower = f.name.lower()

            if 'spanish' in name_lower or 'español' in name_lower:
                translations.append(('spanish', f))
            elif 'modern_english' in name_lower:
                translations.append(('modern_english', f))
            elif 'german' in name_lower or 'deutsch' in name_lower:
                translations.append(('german', f))
            elif 'russian' in name_lower:
                translations.append(('russian', f))
            elif 'latin' in name_lower:
                translations.append(('latin', f))

        return translations

    def identify_summaries(self, book_dir: Path, source: Path) -> List[tuple]:
        """
        Identify summary files.

        Returns: List of (percentage, filepath) tuples
        """
        summaries = []
        md_files = list(book_dir.glob('*.md'))

        for f in md_files:
            if f == source:
                continue

            # Look for percentage patterns
            match = re.search(r'(\d+)pct|(\d+)%', f.name)
            if match:
                pct = match.group(1) or match.group(2)
                summaries.append((f'{pct}pct', f))

        return summaries

    def extract_metadata(self, source_file: Path, book_id: str) -> Dict:
        """Extract metadata from source file"""

        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return {}

        # Extract title (first # header)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else book_id.replace('_', ' ').title()

        # Extract author (look for "by Author" or "**by Author**")
        author_match = re.search(r'\*?\*?by\s+([^\n*]+)\*?\*?', content, re.IGNORECASE)
        author = author_match.group(1).strip() if author_match else None

        return {
            'title': title,
            'author': author,
            'language': 'English',  # Default
            'source_file': 'book.md'
        }

    def migrate_book(self, book_dir: Path, dry_run: bool = False):
        """Migrate a single book directory"""

        book_id = book_dir.name
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating: {book_id}")
        print("=" * 60)

        # Identify source file
        source = self.identify_source_file(book_dir)
        if not source:
            print("  ⚠️  No markdown source found - SKIPPING")
            return

        print(f"  📖 Source: {source.name}")

        # Identify translations
        translations = self.identify_translations(book_dir, source)
        if translations:
            print(f"  🌍 Translations: {len(translations)}")
            for lang, _ in translations:
                print(f"      - {lang}")

        # Identify summaries
        summaries = self.identify_summaries(book_dir, source)
        if summaries:
            print(f"  📝 Summaries: {len(summaries)}")
            for pct, _ in summaries:
                print(f"      - {pct}")

        # Count duplicates that will be removed
        all_md = list(book_dir.glob('*.md'))
        keep_files = {source} | {f for _, f in translations} | {f for _, f in summaries}
        duplicates = [f for f in all_md if f not in keep_files]

        if duplicates:
            print(f"  🗑️  Duplicates to remove: {len(duplicates)}")
            for dup in duplicates[:3]:
                print(f"      - {dup.name}")
            if len(duplicates) > 3:
                print(f"      ... and {len(duplicates) - 3} more")

        if dry_run:
            print("  ✓ Analysis complete (dry run)")
            return

        # === ACTUAL MIGRATION ===

        # 1. Create new directory structure
        new_dir = book_dir / '.new_structure'
        new_dir.mkdir(exist_ok=True)

        # 2. Copy source as book.md
        shutil.copy2(source, new_dir / 'book.md')
        self.stats['files_moved'] += 1

        # 3. Create translations directory
        if translations:
            trans_dir = new_dir / 'translations'
            trans_dir.mkdir(exist_ok=True)
            for lang, filepath in translations:
                shutil.copy2(filepath, trans_dir / f'{lang}.md')
                self.stats['files_moved'] += 1

        # 4. Create summaries directory
        if summaries:
            summ_dir = new_dir / 'summaries'
            summ_dir.mkdir(exist_ok=True)
            for pct, filepath in summaries:
                shutil.copy2(filepath, summ_dir / f'{pct}.md')
                self.stats['files_moved'] += 1

        # 5. Move audio directories
        audio_dirs = ['audio_kokoro', 'audio_xtts', 'audio_edge', 'audio']
        new_audio = new_dir / 'audio'

        for audio_type in audio_dirs:
            old_audio = book_dir / audio_type
            if old_audio.exists():
                # Rename to just variant name (e.g., kokoro, xtts)
                variant_name = audio_type.replace('audio_', '').replace('audio', 'original')
                dest = new_audio / variant_name
                shutil.copytree(old_audio, dest, dirs_exist_ok=True)
                print(f"  ✓ Moved {audio_type}/ → audio/{variant_name}/")

        # 6. Create metadata.json
        metadata = self.extract_metadata(source, book_id)
        metadata['translations'] = {lang: f'translations/{lang}.md' for lang, _ in translations}
        metadata['summaries'] = {pct: f'summaries/{pct}.md' for pct, _ in summaries}

        # Look for chapter data
        chapter_json = book_dir / f'{book_id}_chapter_data.json'
        if chapter_json.exists():
            with open(chapter_json) as f:
                chapter_data = json.load(f)
                metadata['chapters'] = chapter_data.get('chapters', [])

        with open(new_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 7. Remove duplicates
        for dup in duplicates:
            print(f"  🗑️  Deleting: {dup.name}")
            # Don't actually delete yet - move to .old_duplicates
            old_dir = book_dir / '.old_duplicates'
            old_dir.mkdir(exist_ok=True)
            shutil.move(str(dup), str(old_dir / dup.name))
            self.stats['duplicates_removed'] += 1

        print(f"  ✅ Migration complete! Review .new_structure/ before finalizing")
        self.stats['books_processed'] += 1

    def migrate_all(self, dry_run: bool = True):
        """Migrate all books"""

        print("=" * 60)
        print("BOOK MIGRATION SCRIPT")
        print("=" * 60)
        print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify files)'}")
        print()

        book_dirs = [d for d in self.books_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

        print(f"Found {len(book_dirs)} books to process")

        for book_dir in sorted(book_dirs):
            self.migrate_book(book_dir, dry_run)

        # Print summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Books processed: {self.stats['books_processed']}")
        print(f"Files moved: {self.stats['files_moved']}")
        print(f"Duplicates removed: {self.stats['duplicates_removed']}")

        if dry_run:
            print("\n⚠️  This was a DRY RUN - no changes were made")
            print("Run with --execute to perform actual migration")
        else:
            print("\n✅ Migration complete!")
            print("\nNext steps:")
            print("1. Review each book's .new_structure/ directory")
            print("2. Run finalize_migration.py to replace old structure")


def main():
    import sys

    dry_run = '--execute' not in sys.argv

    migrator = BookMigrator(Path('books'))
    migrator.migrate_all(dry_run=dry_run)


if __name__ == '__main__':
    main()
