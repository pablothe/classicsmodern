#!/usr/bin/env python3
"""
TTS Model Comparison Test Harness

Generates audio samples from multiple TTS models for side-by-side comparison.
Organizes output for easy blind testing and grading.
"""

import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
import psutil

# Test passages
PASSAGES = {
    "passage1_short": "The old clock on the mantelpiece struck twelve. Margaret closed her book and looked out the window at the falling snow.",

    "passage2_narrative": "It was a bright cold day in April, and the clocks were striking thirteen. Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind, slipped quickly through the glass doors of Victory Mansions, though not quickly enough to prevent a swirl of gritty dust from entering along with him. The hallway smelt of boiled cabbage and old rag mats.",

    "passage3_dialogue": '"Where are you going?" asked the old man.\n\n"To the market," she replied, adjusting her basket. "Mother needs flour for tomorrow\'s bread."\n\nHe nodded slowly. "Be careful out there. The roads are icy this time of year."\n\n"I always am," she said with a gentle smile.',

    "passage4_emotional": "Her heart pounded as she reached for the door handle. Behind it, she could hear muffled voices—angry, desperate voices. She had come too far to turn back now. Taking a deep breath, she pushed the door open. The room fell silent. Every eye turned toward her.",

    "passage5_long": """The morning sun filtered through the dusty windows of the old library, casting long shadows across rows of forgotten books. Dr. Harrison had spent the last three months searching for a single reference—a footnote in an obscure journal from 1847 that might confirm his theory. His colleagues thought him mad, wasting his sabbatical on such a trivial pursuit. But he knew better.

As he climbed the rickety ladder to reach the top shelf, his fingers traced the spines of leather-bound volumes, each one a portal to another time. The air smelled of aged paper and leather, a scent he had grown to love over his forty years in academia. Finally, his hand stopped on a thin green volume, barely visible between two larger texts.

"This is it," he whispered to himself, carefully extracting the book. His hands trembled slightly as he opened to the index. There—page 247—exactly where the catalog said it would be. He descended the ladder slowly, clutching his prize, already composing the opening paragraph of the paper that would vindicate his research.""",

    "passage6_technical": "On December 15th, 1791, the Bill of Rights was ratified. James Madison, often called the \"Father of the Constitution,\" drafted the first ten amendments to address concerns about centralized governmental power. The First Amendment alone encompasses five fundamental freedoms: speech, religion, press, assembly, and petition."
}


class TTSModel:
    """Base class for TTS model adapters"""

    def __init__(self, name):
        self.name = name

    def generate(self, text, output_path, voice_ref=None):
        """Generate audio from text. Returns (success, metrics_dict)"""
        raise NotImplementedError

    def is_available(self):
        """Check if this model can be loaded"""
        raise NotImplementedError


class XTTSv2Model(TTSModel):
    """Current XTTS-v2 baseline"""

    def __init__(self):
        super().__init__("xtts-v2")
        self.tts = None

    def is_available(self):
        try:
            from TTS.api import TTS
            return True
        except ImportError:
            return False

    def generate(self, text, output_path, voice_ref=None):
        if self.tts is None:
            from TTS.api import TTS
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

        start_time = time.time()
        start_mem = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        try:
            self.tts.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=voice_ref if voice_ref else "voice_ref.wav",
                language="en"
            )

            elapsed = time.time() - start_time
            end_mem = psutil.Process().memory_info().rss / 1024 / 1024

            return True, {
                "generation_time": elapsed,
                "memory_peak_mb": end_mem - start_mem,
                "text_length": len(text.split()),
                "words_per_second": len(text.split()) / elapsed if elapsed > 0 else 0
            }
        except Exception as e:
            print(f"Error generating with XTTS-v2: {e}")
            return False, {}


class ChatterboxTurboModel(TTSModel):
    """Resemble AI Chatterbox Turbo"""

    def __init__(self):
        super().__init__("chatterbox-turbo")
        self.model = None

    def is_available(self):
        try:
            # Check if chatterbox is installed
            import torch
            # TODO: Update this when we know the actual import path
            return False  # Not installed yet
        except ImportError:
            return False

    def generate(self, text, output_path, voice_ref=None):
        # TODO: Implement when Chatterbox Turbo is installed
        print("Chatterbox Turbo not yet implemented")
        return False, {}


class BarkModel(TTSModel):
    """Suno AI Bark"""

    def __init__(self):
        super().__init__("bark")
        self.model = None

    def is_available(self):
        try:
            from bark import SAMPLE_RATE, generate_audio, preload_models
            return True
        except ImportError:
            return False

    def generate(self, text, output_path, voice_ref=None):
        if self.model is None:
            # Fix PyTorch 2.6+ weights_only issue for Bark
            import torch.serialization
            import numpy.core.multiarray
            torch.serialization.add_safe_globals([numpy.core.multiarray.scalar])

            from bark import SAMPLE_RATE, generate_audio, preload_models
            preload_models()

        start_time = time.time()
        start_mem = psutil.Process().memory_info().rss / 1024 / 1024

        try:
            from bark import generate_audio, SAMPLE_RATE
            from scipy.io.wavfile import write as write_wav

            audio_array = generate_audio(text)
            write_wav(output_path, SAMPLE_RATE, audio_array)

            elapsed = time.time() - start_time
            end_mem = psutil.Process().memory_info().rss / 1024 / 1024

            return True, {
                "generation_time": elapsed,
                "memory_peak_mb": end_mem - start_mem,
                "text_length": len(text.split()),
                "words_per_second": len(text.split()) / elapsed if elapsed > 0 else 0
            }
        except Exception as e:
            print(f"Error generating with Bark: {e}")
            return False, {}


class TortoiseModel(TTSModel):
    """Tortoise TTS"""

    def __init__(self):
        super().__init__("tortoise")
        self.model = None

    def is_available(self):
        try:
            from tortoise.api import TextToSpeech
            return True
        except ImportError:
            return False

    def generate(self, text, output_path, voice_ref=None):
        # TODO: Implement when Tortoise is installed
        print("Tortoise TTS not yet implemented")
        return False, {}


class MeloTTSModel(TTSModel):
    """MeloTTS"""

    def __init__(self):
        super().__init__("melotts")
        self.model = None

    def is_available(self):
        try:
            from melo.api import TTS
            return True
        except ImportError:
            return False

    def generate(self, text, output_path, voice_ref=None):
        # TODO: Implement when MeloTTS is installed
        print("MeloTTS not yet implemented")
        return False, {}


def run_comparison_test(output_dir="tts_comparison_test", voice_ref=None, models_to_test=None):
    """
    Run comparison test across all available TTS models.

    Args:
        output_dir: Directory to save results
        voice_ref: Path to reference voice file (if applicable)
        models_to_test: List of model names to test (None = test all available)
    """

    # Create output directory structure
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_run_dir = output_path / f"test_run_{timestamp}"
    test_run_dir.mkdir(exist_ok=True)

    # Initialize models
    all_models = [
        XTTSv2Model(),
        ChatterboxTurboModel(),
        BarkModel(),
        TortoiseModel(),
        MeloTTSModel()
    ]

    # Filter available models
    available_models = [m for m in all_models if m.is_available()]

    if models_to_test:
        available_models = [m for m in available_models if m.name in models_to_test]

    if not available_models:
        print("ERROR: No TTS models available! Please install at least one model.")
        print("\nAvailable model classes:")
        for model in all_models:
            status = "✓ Available" if model.is_available() else "✗ Not installed"
            print(f"  {model.name}: {status}")
        return

    print(f"\n{'='*60}")
    print(f"TTS Model Comparison Test")
    print(f"{'='*60}")
    print(f"Test run: {timestamp}")
    print(f"Output directory: {test_run_dir}")
    print(f"Models to test: {', '.join(m.name for m in available_models)}")
    print(f"Voice reference: {voice_ref or 'default'}")
    print(f"{'='*60}\n")

    # Results tracking
    results = {
        "timestamp": timestamp,
        "voice_reference": voice_ref,
        "models": {},
        "passages": list(PASSAGES.keys())
    }

    # Generate samples for each model
    for model in available_models:
        print(f"\nTesting model: {model.name}")
        print("-" * 40)

        model_dir = test_run_dir / model.name
        model_dir.mkdir(exist_ok=True)

        results["models"][model.name] = {
            "passages": {},
            "total_time": 0,
            "total_words": 0
        }

        for passage_name, text in PASSAGES.items():
            print(f"  Generating {passage_name}...", end=" ", flush=True)

            output_file = model_dir / f"{passage_name}.wav"
            success, metrics = model.generate(text, str(output_file), voice_ref)

            if success:
                print(f"✓ ({metrics['generation_time']:.2f}s, {metrics['words_per_second']:.1f} words/sec)")
                results["models"][model.name]["passages"][passage_name] = metrics
                results["models"][model.name]["total_time"] += metrics["generation_time"]
                results["models"][model.name]["total_words"] += metrics["text_length"]
            else:
                print("✗ FAILED")
                results["models"][model.name]["passages"][passage_name] = {"error": True}

    # Calculate summary statistics
    for model_name, model_data in results["models"].items():
        if model_data["total_time"] > 0:
            model_data["average_words_per_second"] = model_data["total_words"] / model_data["total_time"]

    # Save results
    results_file = test_run_dir / "test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Create grading spreadsheet template
    create_grading_template(test_run_dir, available_models)

    # Print summary
    print(f"\n{'='*60}")
    print("Test Complete!")
    print(f"{'='*60}")
    print(f"\nResults saved to: {test_run_dir}")
    print(f"\nPerformance Summary:")
    print("-" * 40)

    for model_name, model_data in results["models"].items():
        avg_speed = model_data.get("average_words_per_second", 0)
        total_time = model_data.get("total_time", 0)
        print(f"{model_name:20s} {avg_speed:6.1f} words/sec  ({total_time:.1f}s total)")

    print(f"\n{'='*60}")
    print("Next Steps:")
    print(f"{'='*60}")
    print(f"1. Listen to samples in: {test_run_dir}")
    print(f"2. Grade samples using: {test_run_dir / 'grading_template.csv'}")
    print(f"3. Review metrics in: {test_run_dir / 'test_results.json'}")
    print()


def create_grading_template(test_dir, models):
    """Create CSV template for grading samples"""

    template_path = test_dir / "grading_template.csv"

    with open(template_path, 'w') as f:
        # Header
        f.write("Model,Passage,Naturalness (1-5),Clarity (1-5),Prosody (1-5),")
        f.write("Expressiveness (1-5),Consistency (1-5),Audiobook Suitable (1-5),")
        f.write("Average Score,Notes\n")

        # Rows for each model/passage combination
        for model in models:
            for passage_name in PASSAGES.keys():
                f.write(f"{model.name},{passage_name},,,,,,,=AVERAGE(C:H),\n")

    print(f"\nGrading template created: {template_path}")
    print("Open this file in Excel/Numbers to grade samples")


def main():
    parser = argparse.ArgumentParser(description="TTS Model Comparison Test")
    parser.add_argument("--output-dir", default="tts_comparison_test",
                       help="Output directory for test results")
    parser.add_argument("--voice-ref",
                       help="Path to reference voice file (for voice cloning)")
    parser.add_argument("--models", nargs="+",
                       help="Specific models to test (e.g., xtts-v2 bark)")

    args = parser.parse_args()

    run_comparison_test(
        output_dir=args.output_dir,
        voice_ref=args.voice_ref,
        models_to_test=args.models
    )


if __name__ == "__main__":
    main()
