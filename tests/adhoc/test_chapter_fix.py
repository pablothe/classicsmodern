#!/usr/bin/env python3
"""
Test script to verify chapter detection fix for Call of Cthulhu
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from local_tts_kokoro import KokoroAudioGenerator

def test_chapter_detection():
    """Test chapter detection with markdown headers containing anchors"""

    # Sample text from Call of Cthulhu with anchors
    test_text = """# The CALL of CTHULHU
**by H.P. LOVECRAFT**

## Chapter 1: The Horror in Clay. {#chapter-1}

The most merciful thing in the world, I think, is the inability of the
human mind to correlate all its contents.

## Chapter 2: The Tale of Inspector Legrasse. {#chapter-2}

The matter which I am about to relate is of the most extraordinary
and incredible character.

## Chapter 3: The Madness from the Sea. {#chapter-3}

If heaven ever wishes to grant me a boon, it will be a total effacing
of the results of a mere chance which fixed my eye on a certain piece
of shelf-paper.
"""

    generator = KokoroAudioGenerator()

    # Test chapter detection on raw text
    print("Testing chapter detection on raw text...")
    chapters = generator.detect_chapters(test_text, is_cleaned=False)

    print(f"\nFound {len(chapters)} chapters:")
    for ch_num, ch_pos, ch_title in chapters:
        print(f"  Chapter {ch_num}: {ch_title}")

    # Verify we found all 3 chapters
    if len(chapters) == 3:
        print("\n✅ SUCCESS: All 3 chapters detected correctly!")
        print("Chapter titles are clean (no anchors):")
        for ch_num, ch_pos, ch_title in chapters:
            if "{#" not in ch_title:
                print(f"  ✓ Chapter {ch_num} title is clean")
            else:
                print(f"  ✗ Chapter {ch_num} title still has anchor: {ch_title}")
    else:
        print(f"\n❌ FAILED: Expected 3 chapters, found {len(chapters)}")

    return len(chapters) == 3

if __name__ == "__main__":
    success = test_chapter_detection()
    sys.exit(0 if success else 1)