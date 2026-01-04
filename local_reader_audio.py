#!/usr/bin/env python3
"""
Local Reader Audio Generation

Generates audiobooks from translated text using OpenAI TTS.
Future: Will support local TTS (Orpheus-3B).
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from local_reader_utils import TextProcessor
from local_reader_config import get_config

# Load environment variables from .env file
load_dotenv()


class AudioGenerator:
    """Generates audio from text using OpenAI TTS API"""

    def __init__(self, voice: str = "alloy", format: str = "mp3"):
        """
        Initialize audio generator.

        Args:
            voice: OpenAI voice to use (alloy, echo, fable, onyx, nova, shimmer)
            format: Audio format (mp3, wav, flac)
        """
        self.voice = voice
        self.format = format

        # Initialize OpenAI client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set.\n"
                "Please create a .env file with: OPENAI_API_KEY=your_key_here"
            )

        self.client = OpenAI(api_key=api_key)

    def clean_text_for_speech(self, text: str) -> str:
        """
        Clean text for natural speech synthesis.

        Args:
            text: Raw text with possible Markdown

        Returns:
            Cleaned text suitable for TTS
        """
        # Use the utility function to strip Markdown
        clean_text = TextProcessor.strip_markdown(text)

        # Remove image references
        clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)

        # Remove URLs
        clean_text = re.sub(r'http[s]?://\S+', '', clean_text)

        # Remove excessive whitespace
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
        clean_text = re.sub(r'[ \t]+', ' ', clean_text)

        # Remove special markers (like ----)
        clean_text = re.sub(r'^[-=*_]{3,}$', '', clean_text, flags=re.MULTILINE)

        return clean_text.strip()

    def chunk_text_for_audio(self, text: str, max_chars: int = 3000) -> list[str]:
        """
        Split text into chunks suitable for TTS API.

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (OpenAI limit is ~4096)

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
                        # If sentence is still too long, force split
                        if len(sentence) > max_chars:
                            # Force split at max_chars boundaries
                            for i in range(0, len(sentence), max_chars):
                                chunk_part = sentence[i:i + max_chars]
                                if current_chunk and len(current_chunk) + len(chunk_part) + 1 > max_chars:
                                    chunks.append(current_chunk.strip())
                                    current_chunk = chunk_part
                                else:
                                    current_chunk += " " + chunk_part if current_chunk else chunk_part
                        elif len(current_chunk) + len(sentence) + 1 > max_chars:
                            chunks.append(current_chunk.strip())
                            current_chunk = sentence
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
        Generate audio for a single text chunk.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file

        Returns:
            Path to generated audio file
        """
        print(f"  Generating audio ({len(text)} chars)...", end=" ", flush=True)

        response = self.client.audio.speech.create(
            model="tts-1",
            voice=self.voice,
            input=text,
            response_format=self.format
        )

        # Save audio file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response.stream_to_file(output_path)

        print(f"✓ Saved: {output_path.name}")
        return output_path

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: str = None,
        single_file: bool = False
    ) -> dict:
        """
        Generate audiobook from text file.

        Args:
            input_file: Path to text/markdown file
            output_dir: Output directory (auto-generated if None)
            single_file: If True, combine all chunks (may hit API limits)

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

        print(f"Cleaning text for speech...")
        clean_text = self.clean_text_for_speech(raw_text)

        word_count = len(clean_text.split())
        char_count = len(clean_text)

        print(f"Text ready: {char_count:,} characters, {word_count:,} words")

        # Chunk text
        print(f"Chunking text...")
        chunks = self.chunk_text_for_audio(clean_text)
        print(f"Created {len(chunks)} audio chunks\n")

        # Create output directory
        if output_dir is None:
            output_dir = input_path.parent / "audio"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate base filename
        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("="*70)
        print("AUDIO GENERATION")
        print("="*70)
        print(f"Input: {input_file}")
        print(f"Output directory: {output_dir}")
        print(f"Voice: {self.voice}")
        print(f"Format: {self.format}")
        print(f"Chunks: {len(chunks)}")
        print("="*70)
        print()

        # Generate audio for each chunk
        audio_files = []
        for i, chunk_text in enumerate(chunks, 1):
            chunk_filename = f"{base_name}_part{i:03d}_{self.voice}_{timestamp}.{self.format}"
            chunk_path = output_dir / chunk_filename

            print(f"[{i}/{len(chunks)}]", end=" ")
            try:
                audio_path = self.generate_audio_chunk(chunk_text, chunk_path)
                audio_files.append(audio_path)
            except Exception as e:
                print(f"✗ ERROR: {e}")
                raise

        # Generate playlist
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
        print(f"Playlist: {playlist_path}")
        print(f"Output directory: {output_dir}")
        print("="*70)

        return {
            'audio_files': [str(f) for f in audio_files],
            'playlist': str(playlist_path),
            'chunks': len(chunks),
            'word_count': word_count,
            'output_directory': str(output_dir)
        }


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Usage: python local_reader_audio.py <input_file> [voice] [format]")
        print("\nExample:")
        print("  python local_reader_audio.py books/crime_punishment/chunks/translated/chunk_001_modern_spanish_4b.md")
        print("  python local_reader_audio.py translated.md fable mp3")
        print("\nAvailable voices:")
        print("  alloy   - Neutral, balanced")
        print("  echo    - Clear male voice")
        print("  fable   - British accent, storytelling")
        print("  onyx    - Deep male voice")
        print("  nova    - Young female voice")
        print("  shimmer - Soft female voice")
        print("\nFormats: mp3, wav, flac")
        print("\nNote: Requires OPENAI_API_KEY environment variable")
        sys.exit(1)

    input_file = sys.argv[1]
    voice = sys.argv[2] if len(sys.argv) > 2 else "fable"
    format = sys.argv[3] if len(sys.argv) > 3 else "mp3"

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n❌ ERROR: OPENAI_API_KEY not found")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        print("\nOr create a .env file with:")
        print("  OPENAI_API_KEY=your-api-key-here")
        sys.exit(1)

    try:
        generator = AudioGenerator(voice=voice, format=format)
        result = generator.generate_audiobook(input_file)

        print("\n✅ Success! Audio files ready to play.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
