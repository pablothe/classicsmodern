#!/usr/bin/env python3
"""
Test chapter detection and preservation logic.
"""

import re

def clean_text_for_speech(text: str, preserve_chapter_markers: bool = False) -> str:
    """
    Clean markdown text for natural speech synthesis.
    """
    # Preserve standalone Roman numeral chapter markers FIRST (before other cleaning)
    if preserve_chapter_markers:
        # Replace standalone Roman numerals on their own line with markers
        text = re.sub(
            r'^(X{0,3})(IX|IV|V?I{0,3})\.$',
            lambda m: f"CHAPTER_MARKER_{m.group(0)}",
            text,
            flags=re.MULTILINE
        )

    # Remove markdown headers but keep text (unless it's a chapter marker)
    if preserve_chapter_markers:
        # Keep Roman numerals in headers as chapter markers
        def replace_header(match):
            header_text = match.group(2)
            # Check if it's a Roman numeral chapter marker
            if re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', header_text.strip()):
                return f"CHAPTER_MARKER_{header_text.strip()}"
            return header_text
        text = re.sub(r'^(#{1,6})\s+(.+)$', replace_header, text, flags=re.MULTILINE)
    else:
        text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)

    return text

def detect_chapters(text: str, is_cleaned: bool = False) -> list:
    """
    Detect chapter boundaries in text.
    """
    chapters = []
    lines = text.split('\n')

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Check for preserved chapter markers (in cleaned text)
        if is_cleaned and line_stripped.startswith('CHAPTER_MARKER_'):
            marker = line_stripped.replace('CHAPTER_MARKER_', '')
            char_pos = len('\n'.join(lines[:i]))
            chapter_num = len(chapters) + 1
            chapters.append((chapter_num, char_pos, marker))
            continue

        # Roman numeral pattern (I., II., III., etc.)
        roman_match = re.match(r'^(X{0,3})(IX|IV|V?I{0,3})\.$', line_stripped)
        if roman_match:
            char_pos = len('\n'.join(lines[:i]))
            chapter_num = len(chapters) + 1
            chapters.append((chapter_num, char_pos, line_stripped))
            continue

    return chapters


# Test data
test_text = """Some intro text here.

I.
This is chapter one content.
It has multiple lines.

II.
This is chapter two content.

III.
This is chapter three content.

More content here.
"""

print("="*70)
print("CHAPTER DETECTION TEST")
print("="*70)
print()

# Step 1: Detect chapters in raw text
print("Step 1: Detect chapters in RAW text")
chapters_raw = detect_chapters(test_text, is_cleaned=False)
print(f"Found {len(chapters_raw)} chapters:")
for ch_num, ch_pos, ch_title in chapters_raw:
    print(f"  {ch_num}. {ch_title} at position {ch_pos}")
print()

# Step 2: Clean text with chapter preservation
print("Step 2: Clean text WITH chapter marker preservation")
clean_with_markers = clean_text_for_speech(test_text, preserve_chapter_markers=True)
print("Cleaned text preview:")
print(clean_with_markers[:200] + "...")
print()

# Step 3: Detect chapters in cleaned text
print("Step 3: Detect chapters in CLEANED text")
chapters_clean = detect_chapters(clean_with_markers, is_cleaned=True)
print(f"Found {len(chapters_clean)} chapters:")
for ch_num, ch_pos, ch_title in chapters_clean:
    print(f"  {ch_num}. {ch_title} at position {ch_pos}")
print()

# Step 4: Verify both methods find same number of chapters
print("Step 4: Verification")
if len(chapters_raw) == len(chapters_clean):
    print(f"✅ SUCCESS: Both methods found {len(chapters_raw)} chapters")
else:
    print(f"❌ FAILURE: Raw found {len(chapters_raw)}, cleaned found {len(chapters_clean)}")
print()

# Step 5: Test removal of markers for TTS
print("Step 5: Remove markers for TTS (so they don't get spoken)")
tts_text = re.sub(r'CHAPTER_MARKER_[^\s]*', '', clean_with_markers).strip()
print("Text ready for TTS (no markers):")
print(tts_text[:200] + "...")
print()

if "CHAPTER_MARKER_" in tts_text:
    print("❌ FAILURE: Markers still present in TTS text")
else:
    print("✅ SUCCESS: Markers removed from TTS text")
print()

print("="*70)
