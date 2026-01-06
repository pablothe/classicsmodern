#!/usr/bin/env python3
"""
Summarize and Generate Audiobook

Simple pipeline: translated text → summarize → audiobook
Perfect for when you already have a translated file.
"""

import sys
import subprocess
from pathlib import Path
from book_summarizer import BookSummarizer


def main():
    if len(sys.argv) < 4:
        print("Usage: python summarize_and_audio.py <input_file> <target_percentage> <voice_ref> [language]")
        print("\nExample:")
        print("  python summarize_and_audio.py translated.md 50 voice_ref.wav en")
        print("  python summarize_and_audio.py translated.md 10 voice_ref.wav es")
        print("\nThis will:")
        print("  1. Summarize the file to target percentage")
        print("  2. Generate audiobook from the summary")
        print("  3. Output audio files ready to play")
        sys.exit(1)

    input_file = sys.argv[1]
    target_percentage = int(sys.argv[2])
    voice_ref = sys.argv[3]
    language = sys.argv[4] if len(sys.argv) > 4 else "en"

    # Validate inputs
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"❌ ERROR: File not found: {input_file}")
        sys.exit(1)

    voice_path = Path(voice_ref)
    if not voice_path.exists():
        print(f"❌ ERROR: Voice reference not found: {voice_ref}")
        sys.exit(1)

    if target_percentage < 10 or target_percentage > 90:
        print(f"❌ ERROR: Target percentage must be between 10-90 (got {target_percentage})")
        sys.exit(1)

    print("\n" + "="*70)
    print("SUMMARIZE & AUDIOBOOK PIPELINE")
    print("="*70)
    print(f"Input: {input_path.name}")
    print(f"Target: {target_percentage}% summary")
    print(f"Voice: {voice_ref}")
    print(f"Language: {language}")
    print("="*70)
    print()

    # STAGE 1: Summarization
    print("\n" + "="*70)
    print("STAGE 1: SUMMARIZATION")
    print("="*70)

    # Read input
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    original_words = len(text.split())
    print(f"Original length: {original_words:,} words\n")

    # Summarize
    summarizer = BookSummarizer(target_percentage=target_percentage)
    print(f"Chunk size: {summarizer.chunk_size_words} words (~{summarizer.chunk_size_words/500:.1f} pages)\n")

    try:
        result = summarizer.summarize_document(text, target_percentage)
    except Exception as e:
        print(f"\n❌ Summarization failed: {e}")
        sys.exit(1)

    # Save summary
    output_filename = f"{input_path.stem}_summarized_{target_percentage}pct.md"
    output_path = input_path.parent / output_filename

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result.translated_text)

    print(f"\n✅ Summary saved: {output_path.name}")

    # STAGE 2: Audio Generation
    print("\n" + "="*70)
    print("STAGE 2: AUDIO GENERATION")
    print("="*70)
    print(f"Generating audiobook from summary...")
    print()

    # Run local_tts_xtts.py
    cmd = [
        sys.executable,
        "local_tts_xtts.py",
        str(output_path),
        str(voice_ref),
        language
    ]

    try:
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Audio generation failed with exit code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Audio generation error: {e}")
        sys.exit(1)

    print("\n" + "="*70)
    print("🎉 PIPELINE COMPLETE!")
    print("="*70)
    print(f"Summary: {output_path}")
    print(f"Audio files: Check the audio_xtts/ directory")
    print("="*70)


if __name__ == "__main__":
    main()
