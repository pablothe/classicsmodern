#!/usr/bin/env python3
"""
Mock Helpers for Testing

Provides mock implementations of expensive operations:
- TTS generation (Kokoro, XTTS, Edge-TTS)
- LLM API calls (Ollama, OpenAI)
- Image generation (Stable Diffusion)
- Audio file creation
"""

import io
import wave
import struct
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


# ============================================================================
# Mock Audio Generation
# ============================================================================

class MockKokoroTTS:
    """Mock Kokoro TTS for testing without actual audio generation."""

    def __init__(self, voice: str = "af_sky", language: str = "en-us"):
        self.voice = voice
        self.language = language
        self.model_path = "/mock/path/kokoro.onnx"
        self.voices_path = "/mock/path/voices.bin"

    def create_audio(self, text: str, output_path: Path, speed: float = 1.0) -> Dict:
        """
        Create mock audio file (tiny valid WAV).

        Args:
            text: Text to "synthesize"
            output_path: Where to save mock audio
            speed: Playback speed multiplier

        Returns:
            Dict with generation stats
        """
        # Create tiny valid WAV file (1 second, silence)
        sample_rate = 24000
        duration = len(text.split()) * 0.3  # Rough estimate: 0.3s per word
        duration = max(0.1, duration)  # Minimum 0.1 seconds

        audio_data = create_mock_audio_file(output_path, duration, sample_rate)

        return {
            'success': True,
            'output_file': str(output_path),
            'duration': duration,
            'text_length': len(text),
            'voice': self.voice,
            'sample_rate': sample_rate,
            'file_size': len(audio_data)
        }

    def generate_audiobook(
        self,
        input_file: str,
        output_dir: Optional[str] = None,
        chunk_size: int = 800,
        speed: float = 1.0,
        normalize: bool = True,
        to_mp3: bool = True,
        generate_cover: bool = False
    ) -> Dict:
        """Mock audiobook generation."""
        input_path = Path(input_file)

        if output_dir:
            audio_dir = Path(output_dir)
        else:
            audio_dir = input_path.parent / "audio_kokoro"

        audio_dir.mkdir(parents=True, exist_ok=True)

        # Read text and create mock chapters
        with open(input_path, 'r') as f:
            text = f.read()

        # Mock chapter detection (simple: count "CHAPTER" markers)
        import re
        chapters = re.findall(r'CHAPTER\s+[IVXLCDM\d]+', text, re.IGNORECASE)
        num_chapters = max(len(chapters), 1)

        # Create mock audio files
        chapter_files = []
        for i in range(num_chapters):
            chapter_file = audio_dir / f"chapter_{i+1:02d}.mp3"
            create_mock_audio_file(chapter_file, duration=10.0)
            chapter_files.append(chapter_file)

        # Create playlist
        playlist_path = audio_dir / "audiobook_playlist.m3u"
        with open(playlist_path, 'w') as f:
            for chapter_file in chapter_files:
                f.write(f"{chapter_file.name}\n")

        return {
            'output_directory': str(audio_dir),
            'playlist': str(playlist_path),
            'chapters': num_chapters,
            'chunks': num_chapters * 3,  # Mock chunks
            'format': 'mp3' if to_mp3 else 'wav',
            'total_duration': num_chapters * 10.0
        }


def create_mock_audio_file(
    output_path: Path,
    duration: float = 1.0,
    sample_rate: int = 24000
) -> bytes:
    """
    Create a tiny valid WAV file for testing.

    Args:
        output_path: Where to save the file
        duration: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        Audio data as bytes
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create silent audio data
    num_samples = int(sample_rate * duration)
    audio_data = struct.pack('<' + ('h' * num_samples), *([0] * num_samples))

    # Write WAV file
    with wave.open(str(output_path), 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)

    # Return the raw audio data
    return audio_data


# ============================================================================
# Mock LLM API Calls
# ============================================================================

class MockOllamaClient:
    """Mock Ollama client for translation/summarization tests."""

    def __init__(self, model_name: str = "gemma3-translator:4b"):
        self.model_name = model_name
        self.call_count = 0
        self.last_prompt = None

    def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """Mock chat completion."""
        self.call_count += 1

        # Extract prompt
        if messages:
            self.last_prompt = messages[-1].get('content', '')

        # Generate mock response based on prompt type
        if 'translate' in self.last_prompt.lower():
            response = self._mock_translation(self.last_prompt)
        elif 'summarize' in self.last_prompt.lower() or 'condense' in self.last_prompt.lower():
            response = self._mock_summarization(self.last_prompt)
        else:
            response = f"Mock response to: {self.last_prompt[:50]}..."

        return {
            'message': {
                'content': response
            },
            'model': self.model_name,
            'created_at': datetime.now().isoformat()
        }

    def _mock_translation(self, prompt: str) -> str:
        """Generate mock translation."""
        # Extract source text (after "TRANSLATE:" marker if present)
        if 'TRANSLATE:' in prompt:
            text = prompt.split('TRANSLATE:')[-1].strip()
        else:
            # Take last 200 chars as likely source text
            text = prompt[-200:].strip()

        # Simple mock: reverse word order
        words = text.split()[:20]  # Take first 20 words
        mock_translation = ' '.join(reversed(words))
        return mock_translation

    def _mock_summarization(self, prompt: str) -> str:
        """Generate mock summarization."""
        # Extract text to summarize
        if 'CONDENSE THIS' in prompt:
            text = prompt.split('CONDENSE THIS')[-1].split('Rules:')[0].strip()
        else:
            text = prompt[-200:].strip()

        # Simple mock: take first 30% of words
        words = text.split()
        summary_length = max(10, len(words) // 3)
        mock_summary = ' '.join(words[:summary_length])
        return mock_summary

    def list_models(self) -> Dict:
        """Mock list models."""
        return {
            'models': [
                {'name': self.model_name}
            ]
        }


class MockOpenAIClient:
    """Mock OpenAI client for cloud translation tests."""

    def __init__(self, model: str = "o3-mini-high"):
        self.model = model
        self.call_count = 0

    class ChatCompletions:
        def __init__(self, parent):
            self.parent = parent

        def create(self, model: str, messages: List[Dict], **kwargs):
            """Mock chat completion."""
            self.parent.call_count += 1

            # Extract user message
            user_message = ""
            for msg in messages:
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')

            # Generate mock translation
            words = user_message.split()[-30:]
            mock_translation = ' '.join(words)  # Echo back

            class MockResponse:
                def __init__(self, content):
                    self.choices = [
                        type('Choice', (), {
                            'message': type('Message', (), {
                                'content': content
                            })()
                        })()
                    ]

            return MockResponse(mock_translation)

    @property
    def chat(self):
        if not hasattr(self, '_chat'):
            self._chat = type('Chat', (), {
                'completions': self.ChatCompletions(self)
            })()
        return self._chat


# ============================================================================
# Mock Image Generation
# ============================================================================

class MockStableDiffusion:
    """Mock Stable Diffusion for cover art generation."""

    def __init__(self):
        self.model_id = "mock/stable-diffusion-v1-5"

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        width: int = 512,
        height: int = 512,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5
    ) -> Dict:
        """Generate mock image (tiny PNG)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create 1x1 pixel PNG (smallest valid PNG)
        png_data = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'  # 1x1 RGBA
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        output_path.write_bytes(png_data)

        return {
            'success': True,
            'output_path': str(output_path),
            'width': width,
            'height': height,
            'prompt': prompt,
            'file_size': len(png_data)
        }


# ============================================================================
# Mock File Operations
# ============================================================================

class AudioFileMocker:
    """Utility for creating mock audio files for testing."""

    @staticmethod
    def create_chapter_files(
        output_dir: Path,
        num_chapters: int = 3,
        format: str = "mp3"
    ) -> List[Path]:
        """Create mock chapter audio files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for i in range(1, num_chapters + 1):
            filename = f"chapter_{i:02d}.{format}"
            filepath = output_dir / filename
            create_mock_audio_file(filepath, duration=10.0)
            files.append(filepath)

        return files

    @staticmethod
    def create_playlist(
        output_dir: Path,
        chapter_files: List[Path],
        playlist_name: str = "audiobook_playlist.m3u"
    ) -> Path:
        """Create M3U playlist file."""
        playlist_path = output_dir / playlist_name

        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for chapter_file in chapter_files:
                f.write(f"#EXTINF:10,{chapter_file.stem}\n")
                f.write(f"{chapter_file.name}\n")

        return playlist_path


# ============================================================================
# Mock External Services
# ============================================================================

def mock_ffprobe_duration(duration: float = 10.0):
    """Mock ffprobe duration check."""
    class MockResult:
        returncode = 0
        stdout = str(duration)
        stderr = ""

    return MockResult()


def mock_ollama_available(available: bool = True):
    """Mock Ollama availability check."""
    if available:
        class MockResult:
            returncode = 0
            stdout = "gemma3-translator:4b\n"
        return MockResult()
    else:
        raise FileNotFoundError("ollama command not found")


# ============================================================================
# Test Data Helpers
# ============================================================================

def create_sample_book(
    title: str = "Test Book",
    author: str = "Test Author",
    num_chapters: int = 3,
    words_per_chapter: int = 100
) -> str:
    """
    Generate sample book content for testing.

    Args:
        title: Book title
        author: Book author
        num_chapters: Number of chapters
        words_per_chapter: Approximate words per chapter

    Returns:
        Book content as markdown string
    """
    content = [
        f"# {title}",
        f"Author: {author}",
        "",
        "## Table of Contents"
    ]

    # Add TOC
    for i in range(1, num_chapters + 1):
        content.append(f"{i}. [Chapter {i}](#chapter-{i})")

    content.append("\n---\n")

    # Add chapters
    for i in range(1, num_chapters + 1):
        content.append(f"## CHAPTER {i}")
        content.append("")

        # Generate lorem ipsum-style content
        words = []
        for j in range(words_per_chapter):
            words.append(f"word{j % 50}")

        # Break into sentences
        sentences = []
        for k in range(0, len(words), 15):
            sentence = ' '.join(words[k:k+15])
            sentences.append(sentence.capitalize() + ".")

        content.append(' '.join(sentences))
        content.append("")

    return '\n'.join(content)


def create_book_with_gutenberg_boilerplate(title: str = "Test Book") -> str:
    """Create sample book with Gutenberg boilerplate for testing cleanup."""
    header = f"""*** START OF THE PROJECT GUTENBERG EBOOK {title.upper()} ***

This is Project Gutenberg boilerplate text that should be removed.
More header text here.
www.gutenberg.org

"""

    footer = """

*** END OF THE PROJECT GUTENBERG EBOOK ***

End of the Project Gutenberg EBook of Test Book
"""

    content = f"""
# {title}

## CHAPTER I

This is the actual book content.

## CHAPTER II

More content here.
"""

    return header + content + footer
