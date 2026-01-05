#!/usr/bin/env python3
"""
Check translation progress and show what needs to be done
"""

import json
from pathlib import Path

def main():
    # Paths
    chunks_dir = Path("books/crime_punishment/chunks")
    translated_dir = chunks_dir / "translated"
    checkpoint_file = translated_dir / ".translation_progress.json"

    print("="*70)
    print("CRIME AND PUNISHMENT TRANSLATION STATUS")
    print("="*70)
    print()

    # Check checkpoint
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
            completed = data.get('completed_files', [])
            last_updated = data.get('last_updated', 'unknown')

        print(f"Progress checkpoint found:")
        print(f"  Last updated: {last_updated}")
        print(f"  Completed files: {len(completed)}")
        print()
    else:
        print("No progress checkpoint found")
        completed = []

    # List all chunks
    all_chunks = sorted(chunks_dir.glob("chunk_*.md"))
    print(f"Total chunks: {len(all_chunks)}")
    print()

    # Check which are translated
    translated_files = list(translated_dir.glob("chunk_*_modern_english_4b.md"))
    corrupted_files = list(translated_dir.glob("chunk_*_modern_english_4b.md.CORRUPTED"))

    print(f"Translated: {len(translated_files)}")
    print(f"Corrupted: {len(corrupted_files)}")
    print()

    # Find missing
    translated_names = {f.name for f in translated_files}
    missing = []

    for chunk in all_chunks:
        expected_name = f"{chunk.stem}_modern_english_4b.md"
        if expected_name not in translated_names:
            missing.append(chunk.name)

    if missing:
        print(f"❌ Missing translations ({len(missing)}):")
        for name in missing:
            print(f"   - {name}")
        print()
        print("To fix, run:")
        print("  python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian 'Modern English'")
        print()
        print("This will automatically:")
        print("  1. Skip already-completed chunks")
        print("  2. Translate missing chunks only")
        print("  3. Run deduplication")
        print("  4. Create clean files in translated/deduplicated/")
    else:
        print("✅ All chunks translated!")
        print()

        # Check deduplication
        dedup_dir = translated_dir / "deduplicated"
        if dedup_dir.exists():
            dedup_files = list(dedup_dir.glob("*_DEDUPED.md"))
            print(f"Deduplicated files: {len(dedup_files)}")

            if len(dedup_files) < len(all_chunks):
                print("⚠️  Some deduplicated files missing - run deduplication:")
                print("  python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian 'Modern English'")
            else:
                print("✅ Deduplication complete!")
                print()
                print("Ready for audio generation:")
                print("  python3 local_tts_xtts.py books/crime_punishment/chunks/translated/deduplicated/chunk_001_modern_english_4b_DEDUPED.md voice.wav en")
        else:
            print("⚠️  No deduplicated directory found - run deduplication:")
            print("  python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian 'Modern English'")

    print()
    print("="*70)

if __name__ == "__main__":
    main()
