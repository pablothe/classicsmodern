#!/usr/bin/env python3
"""
TTS Comparison Tool

Generates the same sample text with different TTS engines to compare quality.
Helps users choose the best TTS engine for their audiobook project.

Usage:
    python compare_tts.py                    # Uses test sample
    python compare_tts.py custom_text.md     # Uses custom file
"""

import sys
import subprocess
from pathlib import Path


def print_header(title):
    """Print formatted section header"""
    width = 70
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width + "\n")


def run_command(cmd, description):
    """Run command and handle errors"""
    print(f"▶ {description}")
    print(f"  Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  ✓ Success\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Error: {e}")
        print(f"  {e.stderr}\n")
        return False
    except FileNotFoundError:
        print(f"  ✗ Error: Command not found")
        print(f"  Make sure the TTS script exists\n")
        return False


def main():
    """Main comparison workflow"""

    print_header("TTS Engine Comparison Tool")

    # Determine input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "test_orpheus_sample.md"

    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        print("\nPlease provide a valid markdown file:")
        print(f"  python {sys.argv[0]} path/to/file.md")
        sys.exit(1)

    print(f"Input file: {input_file}")
    print(f"Comparing TTS engines on: {input_path.stem}\n")

    results = {}

    # 1. Orpheus-TTS (recommended)
    print_header("1. Orpheus-TTS (Recommended)")
    print("Quality: ⭐⭐⭐⭐⭐ (Most human-like)")
    print("Speed: 1-2x realtime (GPU)")
    print("Cost: Free\n")

    orpheus_cmd = ["python", "local_tts_orpheus.py", input_file, "--voice", "tara"]
    results['Orpheus'] = run_command(orpheus_cmd, "Generating with Orpheus-TTS (voice: tara)")

    # 2. XTTS-v2 (requires voice reference)
    print_header("2. XTTS-v2 (Voice Cloning)")
    print("Quality: ⭐⭐⭐⭐ (Very good, slightly robotic)")
    print("Speed: 2-4x slower than realtime")
    print("Cost: Free\n")

    print("▶ Generating with XTTS-v2")
    print("  ⚠️  Skipped - Requires voice reference file")
    print("  To test XTTS-v2, run:")
    print(f"    python local_tts_xtts.py {input_file} voice_ref.wav en\n")
    results['XTTS'] = None

    # 3. OpenAI Cloud (requires API key)
    print_header("3. OpenAI Cloud TTS")
    print("Quality: ⭐⭐⭐⭐ (Professional)")
    print("Speed: 3-5x realtime")
    print("Cost: ~$15/book\n")

    print("▶ Generating with OpenAI Cloud TTS")
    print("  ⚠️  Skipped - Requires API key and different input format")
    print("  To test Cloud TTS, see CLAUDE.md for instructions\n")
    results['Cloud'] = None

    # Summary
    print_header("Comparison Summary")

    if results['Orpheus']:
        print("✓ Orpheus-TTS audio generated successfully")
        orpheus_dir = Path(f"audio_orpheus")
        if orpheus_dir.exists():
            playlist = list(orpheus_dir.glob(f"{input_path.stem}_audiobook_*.m3u"))
            if playlist:
                print(f"  Listen: afplay {playlist[0]}")
                print(f"  Output: {orpheus_dir}/\n")

    print("\nRecommendation:")
    print("─" * 70)
    print("For BEST QUALITY: Use Orpheus-TTS (default)")
    print("  • Most human-like speech")
    print("  • Natural intonation and emotion")
    print("  • Free and fast (with GPU)")
    print()
    print("For VOICE MATCHING: Use XTTS-v2")
    print("  • Clone specific voices")
    print("  • Good quality (slightly robotic)")
    print("  • Free but slower")
    print()
    print("For SPEED: Use OpenAI Cloud")
    print("  • Professional quality")
    print("  • Fastest generation")
    print("  • Costs ~$15/book")
    print("─" * 70)

    print("\nNext Steps:")
    print("1. Listen to the generated audio")
    print("2. Choose your preferred TTS engine")
    print("3. Run on your full audiobook:")
    print(f"   python local_tts_orpheus.py books/mybook/translated.md --voice tara\n")


if __name__ == "__main__":
    main()
