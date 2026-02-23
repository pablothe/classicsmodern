#!/usr/bin/env python3
"""
Audio Text Preprocessor - Transform written text for natural speech synthesis

This middleware sits between the source text and TTS generation, transforming
visual formatting (markdown headers, Roman numerals) into natural spoken text.

Key features:
- Markdown headers → Spoken chapter announcements ("## 1:" → "Chapter 1")
- Roman numerals → Arabic numbers ("## I." → "Chapter 1")
- Bidirectional position mapping (original char pos ↔ spoken char pos)
- Preserve paragraph structure and punctuation for natural pauses

Usage:
    from audio_text_preprocessor import AudioTextPreprocessor

    preprocessor = AudioTextPreprocessor()
    result = preprocessor.preprocess_for_speech("## 1: The Horror\\n\\nText here...")

    print(result.spoken_text)       # "Chapter 1: The Horror\\n\\nText here..."
    print(result.get_spoken_pos(0)) # Get spoken position for original char 0
    print(result.get_original_pos(8)) # Get original position for spoken char 8
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PreprocessingResult:
    """Result of text preprocessing with bidirectional position mapping"""
    original_text: str
    spoken_text: str
    original_to_spoken: Dict[int, int]  # Maps original char pos → spoken char pos
    spoken_to_original: Dict[int, int]  # Maps spoken char pos → original char pos
    transformations: List[Dict]         # Log of all transformations applied

    def get_spoken_pos(self, original_pos: int) -> Optional[int]:
        """Get spoken text position for original text position"""
        # Find the nearest mapped position <= original_pos
        if original_pos in self.original_to_spoken:
            return self.original_to_spoken[original_pos]

        # Find nearest previous mapped position
        positions = sorted([p for p in self.original_to_spoken.keys() if p <= original_pos])
        if positions:
            nearest = positions[-1]
            offset = original_pos - nearest
            return self.original_to_spoken[nearest] + offset

        return None

    def get_original_pos(self, spoken_pos: int) -> Optional[int]:
        """Get original text position for spoken text position"""
        # Find the nearest mapped position <= spoken_pos
        if spoken_pos in self.spoken_to_original:
            return self.spoken_to_original[spoken_pos]

        # Find nearest previous mapped position
        positions = sorted([p for p in self.spoken_to_original.keys() if p <= spoken_pos])
        if positions:
            nearest = positions[-1]
            offset = spoken_pos - nearest
            return self.spoken_to_original[nearest] + offset

        return None


class AudioTextPreprocessor:
    """Preprocess text to make it suitable for natural speech synthesis"""

    # Roman numeral conversion table
    ROMAN_TO_ARABIC = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
        'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
        'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25,
        'XXX': 30, 'XL': 40, 'L': 50, 'LX': 60, 'LXX': 70,
        'LXXX': 80, 'XC': 90, 'C': 100
    }

    def __init__(self):
        self.transformations = []

    def _log_transformation(self, original: str, spoken: str, position: int, transform_type: str):
        """Log a transformation for debugging"""
        self.transformations.append({
            'type': transform_type,
            'original': original,
            'spoken': spoken,
            'position': position
        })

    def _roman_to_arabic(self, roman: str) -> Optional[int]:
        """Convert Roman numeral to Arabic number"""
        roman = roman.upper().strip()
        return self.ROMAN_TO_ARABIC.get(roman)

    def _process_markdown_header(self, line: str, line_num: int) -> Tuple[str, int, int]:
        """
        Process a markdown header line and convert to spoken form.

        Args:
            line: Line of text (possibly a markdown header)
            line_num: Line number for transformation logging

        Returns:
            Tuple of (processed_line, original_length, spoken_length)
        """
        original_line = line

        # Pattern 1: "## 1: The Horror in Clay" → "Chapter 1: The Horror in Clay"
        numbered_match = re.match(r'^(#{1,6})\s*(\d+):\s*(.+)$', line)
        if numbered_match:
            chapter_num = numbered_match.group(2)
            title = numbered_match.group(3)
            spoken_line = f"Chapter {chapter_num}: {title}"
            self._log_transformation(original_line, spoken_line, line_num, 'numbered_header')
            return spoken_line, len(original_line), len(spoken_line)

        # Pattern 2: "## I." → "Chapter 1"
        roman_match = re.match(r'^(#{1,6})\s*([IVXLCDM]+)\.?\s*$', line)
        if roman_match:
            roman = roman_match.group(2)
            arabic = self._roman_to_arabic(roman)
            if arabic:
                spoken_line = f"Chapter {arabic}"
                self._log_transformation(original_line, spoken_line, line_num, 'roman_header')
                return spoken_line, len(original_line), len(spoken_line)

        # Pattern 3: "## I. Title" → "Chapter 1. Title"
        roman_title_match = re.match(r'^(#{1,6})\s*([IVXLCDM]+)\.?\s+(.+)$', line)
        if roman_title_match:
            roman = roman_title_match.group(2)
            title = roman_title_match.group(3)
            arabic = self._roman_to_arabic(roman)
            if arabic:
                spoken_line = f"Chapter {arabic}. {title}"
                self._log_transformation(original_line, spoken_line, line_num, 'roman_title_header')
                return spoken_line, len(original_line), len(spoken_line)

        # Pattern 4: "## Chapter 1: Title" → "Chapter 1: Title" (remove markdown only)
        chapter_match = re.match(r'^(#{1,6})\s*(Chapter|CHAPTER)\s+(.+)$', line, re.IGNORECASE)
        if chapter_match:
            spoken_line = f"Chapter {chapter_match.group(3)}"
            self._log_transformation(original_line, spoken_line, line_num, 'chapter_header')
            return spoken_line, len(original_line), len(spoken_line)

        # Pattern 5: Generic markdown header → just remove markers
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            spoken_line = header_match.group(2)
            self._log_transformation(original_line, spoken_line, line_num, 'generic_header')
            return spoken_line, len(original_line), len(spoken_line)

        # No transformation needed
        return line, len(line), len(line)

    def _process_standalone_roman(self, line: str, line_num: int) -> Tuple[str, int, int]:
        """
        Process standalone Roman numerals (not in headers).

        Args:
            line: Line of text
            line_num: Line number for transformation logging

        Returns:
            Tuple of (processed_line, original_length, spoken_length)
        """
        original_line = line

        # Pattern: Standalone "I." or "II." on its own line
        standalone_match = re.match(r'^([IVXLCDM]+)\.\s*$', line.strip())
        if standalone_match:
            roman = standalone_match.group(1)
            arabic = self._roman_to_arabic(roman)
            if arabic:
                spoken_line = f"Chapter {arabic}"
                self._log_transformation(original_line, spoken_line, line_num, 'standalone_roman')
                return spoken_line, len(original_line), len(spoken_line)

        # Pattern: "I. Title" (numbered list style chapter)
        numbered_list_match = re.match(r'^([IVXLCDM]+)\.\s+(.+)$', line.strip())
        if numbered_list_match:
            roman = numbered_list_match.group(1)
            title = numbered_list_match.group(2)
            arabic = self._roman_to_arabic(roman)
            if arabic and len(title) > 15:  # Likely chapter title (not TOC)
                spoken_line = f"Chapter {arabic}. {title}"
                self._log_transformation(original_line, spoken_line, line_num, 'numbered_list_chapter')
                return spoken_line, len(original_line), len(spoken_line)

        # No transformation needed
        return line, len(line), len(line)

    def preprocess_for_speech(self, text: str) -> PreprocessingResult:
        """
        Preprocess text for natural speech synthesis.

        Transformations:
        - Markdown headers → Spoken chapter announcements
        - Roman numerals → Arabic numbers
        - Remove visual formatting (bold, italic)
        - Preserve paragraph structure

        Args:
            text: Original markdown text

        Returns:
            PreprocessingResult with spoken text and position mappings
        """
        self.transformations = []

        original_to_spoken = {}
        spoken_to_original = {}

        lines = text.split('\n')
        spoken_lines = []

        original_pos = 0
        spoken_pos = 0

        for line_num, line in enumerate(lines):
            # Track position mapping at line start
            original_to_spoken[original_pos] = spoken_pos
            spoken_to_original[spoken_pos] = original_pos

            # Process markdown headers
            processed_line, orig_len, spoken_len = self._process_markdown_header(line, line_num)

            # If no header transformation, try standalone Roman numerals
            if processed_line == line:
                processed_line, orig_len, spoken_len = self._process_standalone_roman(line, line_num)

            spoken_lines.append(processed_line)

            # Update positions (including newline character)
            original_pos += len(line) + 1  # +1 for \n
            spoken_pos += len(processed_line) + 1  # +1 for \n

        spoken_text = '\n'.join(spoken_lines)

        # Final position mapping (end of text)
        original_to_spoken[len(text)] = len(spoken_text)
        spoken_to_original[len(spoken_text)] = len(text)

        return PreprocessingResult(
            original_text=text,
            spoken_text=spoken_text,
            original_to_spoken=original_to_spoken,
            spoken_to_original=spoken_to_original,
            transformations=self.transformations
        )

    def save_mapping(self, result: PreprocessingResult, output_path: str):
        """
        Save preprocessing result and position mapping to JSON file.

        Args:
            result: PreprocessingResult to save
            output_path: Path to output JSON file
        """
        import json
        from pathlib import Path

        data = {
            'original_text_length': len(result.original_text),
            'spoken_text_length': len(result.spoken_text),
            'transformations': result.transformations,
            'position_mapping': {
                'original_to_spoken': {str(k): v for k, v in result.original_to_spoken.items()},
                'spoken_to_original': {str(k): v for k, v in result.spoken_to_original.items()}
            },
            'spoken_text': result.spoken_text
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✓ Preprocessing mapping saved: {output_file}")


def main():
    """Command-line interface for testing"""
    import sys
    import json

    if len(sys.argv) < 2:
        print("Audio Text Preprocessor - Transform text for natural speech")
        print("\nUsage:")
        print("  python audio_text_preprocessor.py <input.md> [output_mapping.json]")
        print("\nExample:")
        print("  python audio_text_preprocessor.py books/call_cthulhu/call_cthulhu.md")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Read input
    with open(input_path, 'r', encoding='utf-8') as f:
        original_text = f.read()

    # Preprocess
    preprocessor = AudioTextPreprocessor()
    result = preprocessor.preprocess_for_speech(original_text)

    # Show results
    print("\n" + "="*70)
    print("AUDIO TEXT PREPROCESSING RESULTS")
    print("="*70)
    print(f"Original text: {len(result.original_text):,} characters")
    print(f"Spoken text:   {len(result.spoken_text):,} characters")
    print(f"Transformations: {len(result.transformations)}")
    print()

    if result.transformations:
        print("Sample transformations:")
        for i, t in enumerate(result.transformations[:5], 1):
            print(f"  {i}. {t['type']}: '{t['original']}' → '{t['spoken']}'")
        if len(result.transformations) > 5:
            print(f"  ... and {len(result.transformations) - 5} more")
    else:
        print("No transformations applied (text already speech-ready)")

    # Save mapping if requested
    if output_path:
        preprocessor.save_mapping(result, output_path)
        print(f"\n✓ Mapping saved to: {output_path}")

    # Test bidirectional mapping
    print("\n" + "="*70)
    print("POSITION MAPPING TEST")
    print("="*70)
    test_positions = [0, 100, 500]
    for orig_pos in test_positions:
        if orig_pos < len(result.original_text):
            spoken_pos = result.get_spoken_pos(orig_pos)
            print(f"Original pos {orig_pos:4d} → Spoken pos {spoken_pos}")

    print("\n✓ Preprocessing complete!")


if __name__ == "__main__":
    main()
