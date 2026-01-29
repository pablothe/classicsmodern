#!/usr/bin/env python3
"""
Simple TTS Comparison - Generate 1 sample from each model, pick the best

Usage: python3 tts_simple_test.py
"""

import os
import time
import tempfile
from pathlib import Path

# Test passage - simple narrative
TEST_TEXT = """It was a bright cold day in April, and the clocks were striking thirteen.
Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind,
slipped quickly through the glass doors of Victory Mansions."""

OUTPUT_DIR = Path("tts_simple_comparison")


def test_bark():
    """Test Suno AI Bark (MIT license)"""
    print("\n[1/2] Testing Bark (MIT license, expressive)...")
    try:
        # Fix PyTorch 2.6+ weights_only issue - MUST BE BEFORE bark imports
        import torch
        import torch.serialization
        import numpy.core.multiarray
        torch.serialization.add_safe_globals([numpy.core.multiarray.scalar])

        # Now safe to import bark
        from bark import SAMPLE_RATE, generate_audio, preload_models
        from scipy.io.wavfile import write as write_wav

        print("  Loading models (first time only, downloads ~1GB)...")
        preload_models()

        print("  Generating audio...")
        start = time.time()
        audio_array = generate_audio(TEST_TEXT)
        elapsed = time.time() - start

        output = OUTPUT_DIR / "sample_bark.wav"
        write_wav(output, SAMPLE_RATE, audio_array)

        print(f"  ✓ Complete in {elapsed:.1f}s: {output}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_kokoro():
    """Test Kokoro TTS (Apache 2.0, new model)"""
    print("\n[2/2] Testing Kokoro (Apache 2.0, new)...")
    try:
        from kokoro_tts import convert_text_to_audio
        import tempfile

        print("  Generating audio...")
        start = time.time()
        output = OUTPUT_DIR / "sample_kokoro.wav"

        # Write text to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(TEST_TEXT)
            temp_path = temp_file.name

        # Model paths (downloaded in OUTPUT_DIR)
        model_path = str(OUTPUT_DIR / "kokoro-v1.0.onnx")
        voices_path = str(OUTPUT_DIR / "voices-v1.0.bin")

        # Generate audio
        try:
            convert_text_to_audio(
                input_file=temp_path,
                output_file=str(output),
                voice='af_sky',  # Female voice
                speed=1.0,
                lang='en-us',
                format='wav',
                model_path=model_path,
                voices_path=voices_path
            )
        finally:
            os.unlink(temp_path)

        elapsed = time.time() - start
        print(f"  ✓ Complete in {elapsed:.1f}s: {output}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*60)
    print("Simple TTS Comparison Test - Local Models Only")
    print("="*60)
    print(f"\nTest text ({len(TEST_TEXT.split())} words):")
    print(f'  "{TEST_TEXT[:80]}..."')
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nTesting 2 local, commercial-friendly TTS models...")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Test all models
    results = []

    if test_bark():
        results.append("✓ Bark (Suno AI, MIT)")

    if test_kokoro():
        results.append("✓ Kokoro (Apache 2.0)")

    # Summary
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)
    print(f"\nGenerated samples: {len(results)}")
    for result in results:
        print(f"  {result}")

    print(f"\n📁 All samples saved to: {OUTPUT_DIR}/")
    print("\n🎧 Next steps:")
    print("  1. Listen to each sample:")
    print(f"     afplay {OUTPUT_DIR}/sample_bark.wav")
    print(f"     afplay {OUTPUT_DIR}/sample_kokoro.wav")
    print("  2. Pick your favorite")
    print("  3. Tell me which one sounds best!")
    print()


if __name__ == "__main__":
    main()
