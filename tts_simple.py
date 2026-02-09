#!/usr/bin/env python3
"""
Simple TTS Module - Pure text-to-speech without chapter logic

This module provides a clean, single-responsibility TTS interface.
It converts text to audio. Nothing more, nothing less.

The orchestrator (make_audiobook.py) handles:
- Chapter detection
- Chapter iteration
- File organization

This module handles:
- Text cleaning for speech
- Safe chunking for TTS
- Audio generation
- Audio combination

Usage:
    from tts_simple import SimpleKokoroTTS

    tts = SimpleKokoroTTS(voice="bf_emma")
    audio_file = tts.generate_audio_from_text(
        "This is my text to convert.",
        Path("output.mp3")
    )
"""

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import sys
import os

# Try to import Kokoro
try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: kokoro-onnx library not installed")
    print("\nPlease install Kokoro TTS:")
    print("  pip install kokoro-tts kokoro-onnx soundfile")
    print("\nOr activate the virtual environment:")
    print("  source venv/bin/activate")
    KOKORO_AVAILABLE = False

# Try to import soundfile
try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: soundfile library not installed")
    print("\nPlease install soundfile:")
    print("  pip install soundfile")
    SOUNDFILE_AVAILABLE = False


class SimpleKokoroTTS:
    """
    Simple TTS wrapper for Kokoro that focuses solely on text-to-speech conversion.
    No chapter detection, no book structure understanding, just pure TTS.
    """

    # Voice constants
    VOICE_AF_SKY = 'af_sky'
    VOICE_BF_EMMA = 'bf_emma'
    VOICE_BM_GEORGE = 'bm_george'
    VOICE_AM_ADAM = 'am_adam'

    def __init__(self,
                 voice: str = VOICE_AF_SKY,
                 language: str = 'en-us',
                 chunk_size: int = 800,
                 speed: float = 1.0,
                 normalize: bool = True):
        """
        Initialize the TTS engine.

        Args:
            voice: Kokoro voice ID (e.g., 'af_sky', 'bf_emma')
            language: Language code (default 'en-us')
            chunk_size: Max characters per TTS chunk (800 is safe for phonemes)
            speed: Playback speed multiplier (1.0 = normal)
            normalize: Whether to normalize audio loudness
        """
        self.voice = voice
        self.language = language
        self.chunk_size = chunk_size
        self.speed = speed
        self.normalize = normalize
        self.model = None

    def _load_model(self):
        """Load Kokoro model if not already loaded."""
        if self.model is None and KOKORO_AVAILABLE:
            print(f"Loading Kokoro model with voice: {self.voice}")
            self.model = Kokoro(voice=self.voice, lang=self.language)
            print("✓ Model loaded")

    def clean_text_for_speech(self, text: str) -> str:
        """
        Clean text for natural speech synthesis.

        Args:
            text: Raw text (may contain markdown, special chars, etc.)

        Returns:
            Cleaned text suitable for TTS
        """
        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

        # Remove markdown bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'__([^_]+)__', r'\1', text)      # Bold alt
        text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic alt

        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove anchor tags
        text = re.sub(r'\{#[^}]+\}', '', text)

        # Convert bullet points to pauses
        text = re.sub(r'^\s*[-*+]\s+', '• ', text, flags=re.MULTILINE)

        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
        text = re.sub(r'[ \t]+', ' ', text)     # Collapse spaces

        # Fix quotes for speech
        text = re.sub(r'[""]', '"', text)  # Normalize quotes
        text = re.sub(r'['']', "'", text)  # Normalize apostrophes

        # Ensure sentences end with proper punctuation for natural pauses
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and not line[-1] in '.!?:;,—':
                # Add period if line doesn't end with punctuation
                line += '.'
            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)
        return text.strip()

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks safe for TTS processing.

        Args:
            text: Cleaned text to chunk

        Returns:
            List of text chunks
        """
        chunks = []

        # Split into sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        for sentence in sentences:
            # If adding this sentence would exceed limit
            if len(current_chunk) + len(sentence) + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " "
                current_chunk += sentence

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def generate_audio_chunk(self, text: str, chunk_num: int, temp_dir: Path) -> Path:
        """
        Generate audio for a single text chunk.

        Args:
            text: Text to convert to speech
            chunk_num: Chunk number for filename
            temp_dir: Directory for temporary files

        Returns:
            Path to generated audio file
        """
        if not KOKORO_AVAILABLE:
            print("⚠️ Kokoro not available, skipping chunk generation")
            return None

        self._load_model()

        output_file = temp_dir / f"chunk_{chunk_num:04d}.wav"

        try:
            # Generate audio with Kokoro
            samples, sample_rate = self.model(text)

            # Save as WAV using soundfile
            if SOUNDFILE_AVAILABLE:
                sf.write(str(output_file), samples, sample_rate)
            else:
                # Fallback: save as numpy array (won't be playable)
                import numpy as np
                np.save(str(output_file.with_suffix('.npy')), samples)
                print(f"⚠️ Saved as .npy (soundfile not available)")

            return output_file

        except Exception as e:
            print(f"⚠️ Error generating chunk {chunk_num}: {e}")
            # Return None on error, let caller handle
            return None

    def combine_audio_files(self, audio_files: List[Path], output_file: Path) -> Path:
        """
        Combine multiple audio files into one.

        Args:
            audio_files: List of audio file paths to combine
            output_file: Output file path

        Returns:
            Path to combined audio file
        """
        if not audio_files:
            raise ValueError("No audio files to combine")

        if len(audio_files) == 1:
            # Just copy the single file
            import shutil
            shutil.copy(audio_files[0], output_file)
            return output_file

        # Create concat list for ffmpeg
        concat_file = output_file.parent / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for audio_file in audio_files:
                f.write(f"file '{audio_file.absolute()}'\n")

        # Combine with ffmpeg
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(output_file.with_suffix('.wav'))
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()
            return output_file.with_suffix('.wav')
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Error combining audio: {e}")
            concat_file.unlink()
            raise

    def post_process_audio(self, input_file: Path, output_file: Path) -> Path:
        """
        Post-process audio (speed adjustment, normalization, MP3 conversion).

        Args:
            input_file: Input WAV file
            output_file: Output file path (extension determines format)

        Returns:
            Path to processed audio file
        """
        filters = []

        # Speed adjustment
        if self.speed != 1.0:
            if self.speed <= 2.0:
                filters.append(f"atempo={self.speed}")
            else:
                # Chain multiple atempo filters for >2x speed
                remaining = self.speed
                while remaining > 1.0:
                    factor = min(remaining, 2.0)
                    filters.append(f"atempo={factor}")
                    remaining /= factor

        # Normalization
        if self.normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', str(input_file)]

        if filters:
            cmd.extend(['-af', ','.join(filters)])

        # Output format based on extension
        if output_file.suffix.lower() == '.mp3':
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '128k'])
        else:
            cmd.extend(['-c:a', 'copy'])

        cmd.append(str(output_file))

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Post-processing failed: {e}")
            # Return original file if processing fails
            return input_file

    def generate_audio_from_text(self,
                                text: str,
                                output_file: Path,
                                verbose: bool = True) -> Path:
        """
        Main public method: Convert text to audio file.

        This is the primary interface - takes text, returns audio.
        No knowledge of books, chapters, or document structure needed.

        Args:
            text: Text to convert to speech
            output_file: Path for output audio file
            verbose: Print progress messages

        Returns:
            Path to generated audio file
        """
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create temp directory for chunks
        temp_dir = output_file.parent / f".temp_{output_file.stem}"
        temp_dir.mkdir(exist_ok=True)

        try:
            # Step 1: Clean text
            if verbose:
                print("Cleaning text for speech...")
            clean_text = self.clean_text_for_speech(text)

            # Step 2: Chunk text
            if verbose:
                print(f"Chunking text (max {self.chunk_size} chars per chunk)...")
            chunks = self.chunk_text(clean_text)
            if verbose:
                print(f"Created {len(chunks)} chunks")

            # Step 3: Generate audio for each chunk
            audio_files = []
            for i, chunk in enumerate(chunks, 1):
                if verbose:
                    print(f"  [{i}/{len(chunks)}] Generating audio ({len(chunk)} chars)...", end=" ")

                chunk_audio = self.generate_audio_chunk(chunk, i, temp_dir)
                if chunk_audio:
                    audio_files.append(chunk_audio)
                    if verbose:
                        print("✓")
                else:
                    if verbose:
                        print("✗")

            if not audio_files:
                raise ValueError("No audio chunks were generated successfully")

            # Step 4: Combine chunks
            if verbose:
                print("Combining audio chunks...")
            combined_wav = temp_dir / "combined.wav"
            combined_audio = self.combine_audio_files(audio_files, combined_wav)

            # Step 5: Post-process (speed, normalize, format conversion)
            if verbose:
                print("Post-processing audio...")
            final_audio = self.post_process_audio(combined_audio, output_file)

            if verbose:
                print(f"✓ Audio saved: {final_audio}")

            # Clean up temp files
            for f in temp_dir.glob("*"):
                f.unlink()
            temp_dir.rmdir()

            return final_audio

        except Exception as e:
            # Clean up on error
            if temp_dir.exists():
                for f in temp_dir.glob("*"):
                    f.unlink()
                temp_dir.rmdir()
            raise


def test_simple_tts():
    """Quick test of the simple TTS module."""

    test_text = """
    # Test Chapter

    This is a **test** of the simple TTS module.
    It should handle markdown formatting properly.

    - First bullet point
    - Second bullet point

    The end.
    """

    tts = SimpleKokoroTTS(voice="af_sky")
    output = Path("test_simple_tts.mp3")

    print("Testing Simple TTS Module")
    print("=" * 60)

    try:
        audio_file = tts.generate_audio_from_text(test_text, output)
        print(f"\n✅ Success! Audio generated: {audio_file}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

    return True


if __name__ == "__main__":
    # Run test if executed directly
    test_simple_tts()