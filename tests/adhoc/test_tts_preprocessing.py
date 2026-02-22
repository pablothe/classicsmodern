#!/usr/bin/env python3
"""
Test TTS Preprocessing - Validate that markdown is properly cleaned before TTS

This script tests that the preprocessing pipeline correctly removes anchor tags
and other problematic markdown before text reaches the TTS engine.

It simulates the full pipeline:
1. Read markdown from file
2. Run through audio_text_preprocessor (if available)
3. Clean text for speech
4. Verify no anchor tags or hash symbols remain

Usage:
    python3 test_tts_preprocessing.py books/call_cthulhu/book.md
"""

import sys
import re
from pathlib import Path


def test_preprocessing(input_file: Path) -> dict:
    """
    Test the TTS preprocessing pipeline.

    Args:
        input_file: Path to markdown file

    Returns:
        Dictionary with test results
    """
    results = {
        'file': str(input_file),
        'passed': True,
        'issues': [],
        'warnings': []
    }

    # Read file
    print(f"📖 Reading: {input_file.name}")
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # Step 1: Check if source file has anchor tags (should be cleaned now)
    anchor_pattern = r'\{#[^}]+\}'
    source_anchors = re.findall(anchor_pattern, raw_text)

    if source_anchors:
        results['issues'].append(f"Source file contains {len(source_anchors)} anchor tags (should be cleaned)")
        results['passed'] = False
        print(f"  ❌ Found {len(source_anchors)} anchor tags in source")
        for anchor in source_anchors[:3]:
            print(f"     Example: {anchor}")
    else:
        print(f"  ✓ Source file is clean (no anchor tags)")

    # Step 2: Try audio_text_preprocessor if available
    preprocessed_text = raw_text
    try:
        from lib.audio.preprocessor import AudioTextPreprocessor
        print(f"\n🔧 Running audio_text_preprocessor...")

        preprocessor = AudioTextPreprocessor()
        result = preprocessor.preprocess_for_speech(raw_text)
        preprocessed_text = result.spoken_text

        print(f"  ✓ Preprocessor applied {len(result.transformations)} transformations")

        # Check for problematic patterns in preprocessed text
        if '{#' in preprocessed_text:
            anchor_count = len(re.findall(anchor_pattern, preprocessed_text))
            results['issues'].append(f"Preprocessed text contains {anchor_count} anchor tags")
            results['passed'] = False
            print(f"  ❌ Preprocessed text still has anchor tags!")
    except ImportError:
        results['warnings'].append("audio_text_preprocessor not available")
        print(f"  ⚠️  audio_text_preprocessor not available")

    # Step 3: Simulate clean_text_for_speech from local_tts_kokoro
    print(f"\n🧹 Simulating clean_text_for_speech...")

    # This simulates the cleaning that happens in local_tts_kokoro.py
    cleaned_text = preprocessed_text

    # Remove markdown headers but keep text
    cleaned_text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', cleaned_text, flags=re.MULTILINE)

    # Remove markdown links but keep text
    cleaned_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned_text)

    # Remove emphasis symbols
    cleaned_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_text)  # Bold
    cleaned_text = re.sub(r'\*([^*]+)\*', r'\1', cleaned_text)      # Italic

    print(f"  ✓ Text cleaning applied")

    # Step 4: Final checks on cleaned text
    print(f"\n✅ Final validation...")

    # Check for anchor tags
    final_anchors = re.findall(anchor_pattern, cleaned_text)
    if final_anchors:
        results['issues'].append(f"Final text contains {len(final_anchors)} anchor tags")
        results['passed'] = False
        print(f"  ❌ Found {len(final_anchors)} anchor tags in final text!")
        for anchor in final_anchors[:3]:
            print(f"     {anchor}")
    else:
        print(f"  ✓ No anchor tags in final text")

    # Check for markdown hash symbols (should be removed by header cleaning)
    # Look for lines that start with ## (potential unremoved headers)
    header_pattern = r'^#{1,6}\s+'
    remaining_headers = re.findall(header_pattern, cleaned_text, re.MULTILINE)
    if remaining_headers:
        results['warnings'].append(f"Found {len(remaining_headers)} markdown headers in final text")
        print(f"  ⚠️  Found {len(remaining_headers)} markdown headers (may be intentional)")

    # Check for problematic patterns that could cause TTS issues
    problematic_chars = ['{', '}', '#']
    for char in problematic_chars:
        if char in cleaned_text[:5000]:  # Check first 5000 chars
            count = cleaned_text[:5000].count(char)
            # Some characters are OK in content (like # in dates)
            # Only warn if there are many occurrences
            if count > 10:
                results['warnings'].append(f"Found {count} '{char}' characters in text")
                print(f"  ⚠️  Found {count} '{char}' characters")

    # Extract sample chapter titles for verification
    print(f"\n📋 Sample chapter titles (as they would be spoken):")
    chapter_pattern = r'^(Chapter \d+:?.+)$'
    chapter_titles = re.findall(chapter_pattern, cleaned_text, re.MULTILINE)[:5]
    for i, title in enumerate(chapter_titles, 1):
        print(f"  {i}. {title}")

        # Check if this title has problematic characters
        if '{#' in title or '#}' in title:
            results['issues'].append(f"Chapter title contains anchor: {title}")
            results['passed'] = False
            print(f"     ❌ Contains anchor tag!")

    return results


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("TTS Preprocessing Test - Validate markdown cleaning before TTS")
        print("\nUsage:")
        print("  python3 test_tts_preprocessing.py <markdown_file>")
        print("\nExample:")
        print("  python3 test_tts_preprocessing.py books/call_cthulhu/book.md")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)

    print("\n" + "="*60)
    print("TTS PREPROCESSING TEST")
    print("="*60)
    print()

    results = test_preprocessing(input_file)

    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)

    if results['passed']:
        print("✅ PASSED - Text is properly cleaned for TTS")
    else:
        print("❌ FAILED - Issues found:")
        for issue in results['issues']:
            print(f"  • {issue}")

    if results['warnings']:
        print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
        for warning in results['warnings']:
            print(f"  • {warning}")

    print("="*60 + "\n")

    sys.exit(0 if results['passed'] else 1)


if __name__ == "__main__":
    main()
