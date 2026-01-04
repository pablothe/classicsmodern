#!/usr/bin/env python3
"""
Local TTS Audio Generation using XTTS-v2 (Coqui TTS)

Generates high-quality audiobooks locally using voice cloning with XTTS-v2.
No API costs, fully local processing with optional FFmpeg post-processing.

Requirements:
    pip install TTS==0.27.3
    brew install ffmpeg  # macOS
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    from TTS.api import TTS
except ImportError:
    print("❌ ERROR: TTS library not installed")
    print("\nPlease install Coqui TTS:")
    print("  pip install TTS==0.27.3")
    sys.exit(1)


class XTTSAudioGenerator:
    """Local TTS audio generation using XTTS-v2 with voice cloning"""

    # XTTS-v2 model
    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Supported languages (XTTS-v2 is multilingual)
    LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "ko", "hu"]

    def __init__(self, reference_voice: str = None, language: str = "en"):
        """
        Initialize XTTS-v2 audio generator.

        Args:
            reference_voice: Path to reference voice WAV file (10-30s, clean, mono, 24kHz recommended)
            language: Target language code (default: "en")
        """
        self.reference_voice = reference_voice
        self.language = language

        if language not in self.LANGUAGES:
            print(f"⚠️  Warning: '{language}' may not be fully supported. Recommended: {', '.join(self.LANGUAGES)}")

        print("Loading XTTS-v2 model (this may take a moment)...")
        self.tts = TTS(model_name=self.MODEL_NAME, progress_bar=False, gpu=False)
        print("✓ Model loaded successfully")

        # Verify reference voice if provided
        if reference_voice:
            ref_path = Path(reference_voice)
            if not ref_path.exists():
                raise FileNotFoundError(f"Reference voice not found: {reference_voice}")
            print(f"✓ Using reference voice: {ref_path.name}")

    def clean_text_for_speech(self, text: str) -> str:
        """
        Clean markdown text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown

        Returns:
            Cleaned text suitable for TTS
        """
        # Remove markdown headers but keep text
        text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)

        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # Remove emphasis symbols
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        # Remove image references
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def chunk_text(self, text: str, max_chars: int = 1500) -> List[str]:
        """
        Split text into chunks for better TTS quality.
        XTTS-v2 works best with paragraph-sized chunks (500-1500 chars).

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""
        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            # If adding this paragraph exceeds limit
            if len(current_chunk) + len(paragraph) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # If paragraph itself is too long, split by sentences
                if len(paragraph) > max_chars:
                    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 1 > max_chars:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                                current_chunk = sentence
                            else:
                                # Force split very long sentences
                                chunks.append(sentence[:max_chars])
                                current_chunk = sentence[max_chars:]
                        else:
                            current_chunk += " " + sentence if current_chunk else sentence
                else:
                    current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def generate_audio_chunk(self, text: str, output_path: Path) -> Path:
        """
        Generate audio for a single text chunk using XTTS-v2.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file

        Returns:
            Path to generated audio file
        """
        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.tts.tts_to_file(
            text=text,
            speaker_wav=self.reference_voice,
            language=self.language,
            file_path=str(output_path)
        )

        print(f"✓ Saved: {output_path.name}")
        return output_path

    def post_process_audio(
        self,
        input_file: Path,
        output_file: Path,
        speed: float = 1.15,
        normalize: bool = True,
        convert_to_mp3: bool = False
    ) -> Path:
        """
        Post-process audio with FFmpeg for better quality.

        Args:
            input_file: Input WAV file
            output_file: Output file path
            speed: Speed multiplier (1.15 = 15% faster, reduces "draggy" feel)
            normalize: Apply loudness normalization
            convert_to_mp3: Convert final output to MP3

        Returns:
            Path to processed audio file
        """
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Warning: ffmpeg not found, skipping post-processing")
            return input_file

        print(f"  Post-processing (speed={speed}x, normalize={normalize})...", end=" ", flush=True)

        # Build ffmpeg filter chain
        filters = []

        # Speed adjustment
        if speed != 1.0:
            # Handle speeds > 2.0 by chaining filters
            if speed > 2.0:
                filters.append("atempo=2.0")
                remaining = speed / 2.0
                while remaining > 1.0:
                    next_tempo = min(remaining, 2.0)
                    filters.append(f"atempo={next_tempo}")
                    remaining /= next_tempo
            else:
                filters.append(f"atempo={speed}")

        # Loudness normalization (audiobook-friendly)
        if normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

        filter_string = ",".join(filters) if filters else None

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', str(input_file)]

        if filter_string:
            cmd.extend(['-filter:a', filter_string])

        # Output format
        if convert_to_mp3:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '128k'])

        cmd.append(str(output_file))

        # Run ffmpeg
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ FFmpeg error: {result.stderr}")
            return input_file

        print(f"✓ Processed: {output_file.name}")
        return output_file

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: str = None,
        chunk_size: int = 1500,
        speed: float = 1.15,
        normalize: bool = True,
        to_mp3: bool = True
    ) -> dict:
        """
        Generate complete audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            chunk_size: Characters per chunk (500-1500 recommended)
            speed: Speed multiplier (1.15 recommended, reduces "robotic" feel)
            normalize: Apply loudness normalization
            to_mp3: Convert to MP3 (smaller files)

        Returns:
            Dictionary with generation results
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Read and clean text
        print(f"Reading: {input_file}")
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        print("Cleaning text for speech...")
        clean_text = self.clean_text_for_speech(raw_text)

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"Text ready: {char_count:,} characters, {word_count:,} words")

        # Chunk text
        print(f"Chunking text (max {chunk_size} chars per chunk)...")
        chunks = self.chunk_text(clean_text, chunk_size)
        print(f"Created {len(chunks)} audio chunks\n")

        # Create output directory
        if output_dir is None:
            output_dir = input_path.parent / "audio_xtts"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate base filename
        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("LOCAL TTS AUDIO GENERATION (XTTS-v2)")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Language: {self.language}")
        print(f"Reference voice: {Path(self.reference_voice).name if self.reference_voice else 'None'}")
        print(f"Chunks: {len(chunks)}")
        print(f"Post-processing: speed={speed}x, normalize={normalize}, mp3={to_mp3}")
        print("="*70)
        print()

        # Generate audio for each chunk
        audio_files = []
        raw_dir = output_dir / "raw" if (speed != 1.0 or normalize or to_mp3) else output_dir
        raw_dir.mkdir(exist_ok=True)

        for i, chunk_text in enumerate(chunks, 1):
            # Generate raw audio
            raw_filename = f"{base_name}_chunk{i:03d}_raw.wav"
            raw_path = raw_dir / raw_filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            try:
                self.generate_audio_chunk(chunk_text, raw_path)

                # Post-process if requested
                if speed != 1.0 or normalize or to_mp3:
                    ext = "mp3" if to_mp3 else "wav"
                    processed_filename = f"{base_name}_chunk{i:03d}.{ext}"
                    processed_path = output_dir / processed_filename

                    final_path = self.post_process_audio(
                        raw_path,
                        processed_path,
                        speed=speed,
                        normalize=normalize,
                        convert_to_mp3=to_mp3
                    )
                    audio_files.append(final_path)
                else:
                    audio_files.append(raw_path)

            except Exception as e:
                print(f"✗ ERROR: {e}")
                raise

        # Generate playlist
        ext = "mp3" if to_mp3 else "wav"
        playlist_path = output_dir / f"{base_name}_audiobook_{timestamp}.m3u"
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for audio_file in audio_files:
                f.write(f"#EXTINF:-1,{audio_file.stem}\n")
                f.write(f"{audio_file.name}\n")

        print(f"\n✓ Playlist created: {playlist_path.name}")

        print("\n" + "="*70)
        print("AUDIO GENERATION COMPLETE")
        print("="*70)
        print(f"Total files: {len(audio_files)}")
        print(f"Format: {ext.upper()}")
        print(f"Playlist: {playlist_path}")
        print(f"Output directory: {output_dir}")
        print("="*70)

        return {
            'audio_files': [str(f) for f in audio_files],
            'playlist': str(playlist_path),
            'chunks': len(chunks),
            'word_count': word_count,
            'output_directory': str(output_dir),
            'format': ext
        }


def prepare_reference_voice(input_file: str, output_file: str = "voice_ref_clean.wav"):
    """
    Prepare a clean reference voice sample for XTTS-v2.
    Converts to mono, 24kHz, PCM WAV format.

    Args:
        input_file: Input audio file (any format)
        output_file: Output WAV file

    Returns:
        Path to prepared reference voice
    """
    print(f"Preparing reference voice from: {input_file}")

    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ERROR: ffmpeg not found")
        print("\nPlease install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        return None

    output_path = Path(output_file)

    # Convert to clean reference format
    cmd = [
        'ffmpeg', '-y',
        '-i', input_file,
        '-ac', '1',              # Mono
        '-ar', '24000',          # 24kHz sample rate
        '-c:a', 'pcm_s16le',     # 16-bit PCM
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ ERROR: {result.stderr}")
        return None

    print(f"✓ Reference voice ready: {output_path}")
    print(f"  Format: 24kHz, Mono, 16-bit PCM WAV")

    return str(output_path)


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Local TTS Audio Generation using XTTS-v2")
        print("="*70)
        print("\nUsage:")
        print("  python local_tts_xtts.py <input_file> [reference_voice] [language] [options]")
        print("\nExamples:")
        print("  # Basic usage (default voice)")
        print("  python local_tts_xtts.py translated.md")
        print()
        print("  # With voice cloning")
        print("  python local_tts_xtts.py translated.md voice_ref.wav en")
        print()
        print("  # Prepare reference voice first")
        print("  python local_tts_xtts.py --prepare-voice input.m4a voice_ref.wav")
        print()
        print("  # Spanish audiobook with custom voice")
        print("  python local_tts_xtts.py libro_traducido.md voz_referencia.wav es")
        print("\nSupported languages:")
        print(f"  {', '.join(XTTSAudioGenerator.LANGUAGES)}")
        print("\nReference Voice Tips:")
        print("  • 10-30 seconds of clear speech")
        print("  • No music, no reverb, consistent mic distance")
        print("  • Mono audio at 22-24kHz recommended")
        print("  • Clean, dry voice works best")
        print("\nPost-Processing (automatic via FFmpeg):")
        print("  • Speed: 1.15x (reduces 'robotic' feel)")
        print("  • Normalization: -16 LUFS (audiobook standard)")
        print("  • Format: MP3 @ 128kbps")
        print("\nRequirements:")
        print("  pip install TTS==0.27.3")
        print("  brew install ffmpeg  # macOS")
        sys.exit(1)

    # Handle --prepare-voice mode
    if sys.argv[1] == "--prepare-voice":
        if len(sys.argv) < 3:
            print("Usage: python local_tts_xtts.py --prepare-voice <input_audio> [output.wav]")
            sys.exit(1)

        input_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else "voice_ref_clean.wav"

        prepare_reference_voice(input_file, output_file)
        sys.exit(0)

    # Parse arguments
    input_file = sys.argv[1]
    reference_voice = sys.argv[2] if len(sys.argv) > 2 else None
    language = sys.argv[3] if len(sys.argv) > 3 else "en"

    try:
        generator = XTTSAudioGenerator(
            reference_voice=reference_voice,
            language=language
        )

        result = generator.generate_audiobook(
            input_file,
            chunk_size=1500,      # Optimal for XTTS-v2
            speed=1.15,           # 15% faster (reduces robotic feel)
            normalize=True,       # Audiobook-standard loudness
            to_mp3=True          # Smaller files
        )

        print("\n✅ Success! Audio files ready to play.")
        print(f"\n💡 Tip: Play with: afplay {result['playlist']}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
