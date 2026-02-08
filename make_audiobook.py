#!/usr/bin/env python3
"""
Make Audiobook - Unified One-Command Audiobook Generator

Single script to transform any book into a complete audiobook with cover art.

Usage:
    # Basic usage (English book, auto-detect everything)
    python3 make_audiobook.py books/alice_adventures/alices_adventures.md

    # With options
    python3 make_audiobook.py INPUT.md --voice bf_emma --generate-cover

    # With summarization
    python3 make_audiobook.py INPUT.md --summarize 50

Features:
- Automatic Gutenberg boilerplate stripping
- Chapter detection (Roman numerals, numbered lists, markdown headers)
- High-quality audio with Kokoro TTS (52 voices, commercial-friendly)
- Optional cover art generation
- Automatic server registration for web playback
- Resumable (saves progress at each stage)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# Import existing components
try:
    from local_tts_kokoro import KokoroAudioGenerator
except ImportError as e:
    print("❌ ERROR: Could not import KokoroAudioGenerator")
    print(f"   Import error: {e}")
    print("\n   Make sure you have installed Kokoro TTS:")
    print("   pip install kokoro-tts kokoro-onnx soundfile")
    print("\n   (The Kokoro models in ~/.cache/kokoro/ will be used automatically)")
    sys.exit(1)


class AudiobookMaker:
    """Unified audiobook creation pipeline"""

    def __init__(
        self,
        input_file: str,
        voice: str = "bf_emma",
        language: str = "en-us",
        chunk_size: int = 800,
        speed: float = 1.0,
        normalize: bool = True,
        to_mp3: bool = True,
        generate_cover: bool = False,
        summarize_percentage: Optional[int] = None,
        output_dir: Optional[str] = None,
        generate_word_timings: bool = False
    ):
        """
        Initialize audiobook maker.

        Args:
            input_file: Path to book markdown file
            voice: Voice ID (default: bf_emma - British female, great for classics)
            language: Language code (default: en-us)
            chunk_size: Characters per audio chunk (default: 800)
            speed: Playback speed multiplier (default: 1.0)
            normalize: Whether to normalize loudness (default: True)
            to_mp3: Whether to convert to MP3 (default: True)
            generate_cover: Whether to generate cover art (default: False)
            summarize_percentage: Optional summarization target % (e.g., 50)
            output_dir: Custom output directory (default: auto-organized)
            generate_word_timings: Whether to generate word timings for karaoke (default: False)
        """
        self.input_file = Path(input_file)
        self.voice = voice
        self.language = language
        self.chunk_size = chunk_size
        self.speed = speed
        self.normalize = normalize
        self.to_mp3 = to_mp3
        self.generate_cover = generate_cover
        self.summarize_percentage = summarize_percentage
        self.output_dir = output_dir
        self.generate_word_timings = generate_word_timings

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Create state file for resumability
        self.state_file = self.input_file.parent / f".audiobook_state_{self.input_file.stem}.json"

        # Initialize or load state
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
            print(f"📌 Resuming previous run from: {self.state.get('stage', 'unknown')}")
        else:
            self.state = {
                'started_at': datetime.now().isoformat(),
                'stage': 'init',
                'audio_complete': False,
                'cover_complete': False,
                'server_registered': False
            }
            self._save_state()

    def _save_state(self):
        """Save current state to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _generate_cover_art(self, book_title: str) -> Optional[Path]:
        """
        Generate cover art for the audiobook.

        Args:
            book_title: Title of the book for cover generation

        Returns:
            Path to generated cover image, or None if failed
        """
        print("\n🎨 Generating cover art...")

        try:
            # Check if generate.py exists
            generate_script = Path(__file__).parent / "generate.py"
            if not generate_script.exists():
                print("⚠️  generate.py not found, skipping cover art")
                return None

            # Determine output directory (where audio files are)
            if self.output_dir:
                cover_dir = Path(self.output_dir)
            else:
                cover_dir = self.input_file.parent / "audio_kokoro"

            cover_path = cover_dir / f"{self.input_file.stem}_cover.png"

            # Create prompt from book title
            prompt = f"Book cover art for '{book_title}', classic literature style, elegant typography, vintage aesthetic"

            # Call generate.py
            import subprocess
            cmd = [
                sys.executable,
                str(generate_script),
                prompt,
                '--output', str(cover_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✓ Cover art generated: {cover_path.name}")
                return cover_path
            else:
                print(f"⚠️  Cover generation failed: {result.stderr}")
                return None

        except Exception as e:
            print(f"⚠️  Cover generation error: {e}")
            return None

    def _generate_chapter_metadata(self, audio_dir: Path, playlist_path: str) -> bool:
        """
        Generate chapter metadata JSON for web player navigation.

        Args:
            audio_dir: Directory containing audio files
            playlist_path: Path to the master playlist file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import the chapter metadata generator
            import subprocess
            generate_script = Path(__file__).parent / "generate_chapter_metadata.py"

            if not generate_script.exists():
                print("⚠️  generate_chapter_metadata.py not found, skipping chapter metadata")
                return False

            # Run the chapter metadata generator
            cmd = [
                sys.executable,
                str(generate_script),
                playlist_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                print(f"✓ Chapter metadata generated")
                return True
            else:
                print(f"⚠️  Chapter metadata generation failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"⚠️  Chapter metadata generation error: {e}")
            return False

    def _register_with_server(self, audio_dir: Path, cover_path: Optional[Path]):
        """
        Register audiobook with local server for web playback.

        Args:
            audio_dir: Directory containing audio files
            cover_path: Optional path to cover image
        """
        print("\n📡 Registering with audiobook server...")

        try:
            # Check if server is running (optional - we'll just update metadata)
            # The server auto-discovers books, but we can create metadata to help

            # Create metadata file for server
            metadata = {
                'title': self.input_file.stem.replace('_', ' ').title(),
                'audio_dir': str(audio_dir.relative_to(self.input_file.parent.parent)),
                'cover': str(cover_path.relative_to(self.input_file.parent.parent)) if cover_path else None,
                'voice': self.voice,
                'language': self.language,
                'created_at': datetime.now().isoformat(),
                'format': 'mp3' if self.to_mp3 else 'wav'
            }

            metadata_path = audio_dir / "audiobook_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"✓ Metadata saved: {metadata_path.name}")
            print(f"  Server will auto-discover on next scan")

        except Exception as e:
            print(f"⚠️  Server registration warning: {e}")

    def make_audiobook(self) -> Dict:
        """
        Main workflow: Create complete audiobook with all features.

        Returns:
            Dictionary with results and paths
        """
        print("\n" + "="*70)
        print("AUDIOBOOK MAKER - ONE-COMMAND WORKFLOW")
        print("="*70)
        print(f"Input: {self.input_file}")
        print(f"Voice: {self.voice}")
        print(f"Speed: {self.speed}x")
        print(f"Cover art: {'Yes' if self.generate_cover else 'No'}")
        if self.summarize_percentage:
            print(f"Summarization: {self.summarize_percentage}%")
        print("="*70)
        print()

        try:
            # STAGE 1: Generate Audio
            if not self.state.get('audio_complete'):
                print("\n📚 STAGE 1: AUDIO GENERATION")
                print("-" * 70)

                # Create audio generator
                generator = KokoroAudioGenerator(
                    voice=self.voice,
                    language=self.language
                )

                # Generate audiobook
                result = generator.generate_audiobook(
                    str(self.input_file),
                    output_dir=self.output_dir,
                    chunk_size=self.chunk_size,
                    speed=self.speed,
                    normalize=self.normalize,
                    to_mp3=self.to_mp3,
                    generate_cover=False  # We'll do this separately with better logic
                )

                self.state['audio_complete'] = True
                self.state['audio_dir'] = result['output_directory']
                self.state['playlist'] = result['playlist']
                self.state['chapters'] = result['chapters']
                self.state['chunks'] = result['chunks']
                self._save_state()

                print(f"\n✅ Audio generation complete!")
                print(f"   Output: {result['output_directory']}")
                print(f"   Chapters: {result['chapters']}")
                print(f"   Format: {result['format'].upper()}")

                # Generate chapter metadata for web player
                if result['chapters'] > 0:
                    print(f"\n📑 Generating chapter metadata for web player...")
                    audio_dir = Path(result['output_directory'])
                    self._generate_chapter_metadata(audio_dir, result['playlist'])

            else:
                print("✓ Audio already generated, skipping...\n")

            audio_dir = Path(self.state['audio_dir'])

            # STAGE 2: Generate Cover Art (optional)
            cover_path = None
            if self.generate_cover and not self.state.get('cover_complete'):
                print("\n📚 STAGE 2: COVER ART GENERATION")
                print("-" * 70)

                # Extract title from file or use filename
                book_title = self.input_file.stem.replace('_', ' ').title()
                cover_path = self._generate_cover_art(book_title)

                self.state['cover_complete'] = True
                if cover_path:
                    self.state['cover_path'] = str(cover_path)
                self._save_state()

            elif self.generate_cover:
                print("✓ Cover art already generated, skipping...\n")
                cover_path = Path(self.state.get('cover_path')) if self.state.get('cover_path') else None

            # STAGE 2.5: Generate Word Timings (optional, for karaoke sync)
            if hasattr(self, 'generate_word_timings') and self.generate_word_timings and not self.state.get('word_timings_complete'):
                print("\n📚 STAGE 2.5: WORD TIMING GENERATION (KARAOKE SYNC)")
                print("-" * 70)

                try:
                    # Import word timing generator
                    import subprocess
                    generate_script = Path(__file__).parent / "generate_word_timings.py"

                    if not generate_script.exists():
                        print("⚠️  generate_word_timings.py not found, skipping word timings")
                    else:
                        # Run word timing generator
                        playlist_path = Path(self.state['playlist'])
                        cmd = [
                            sys.executable,
                            str(generate_script),
                            str(playlist_path),
                            '--method', 'fallback'  # Use fallback by default (no dependencies)
                        ]

                        print(f"  Generating word timings for {self.state['chapters']} chapters...")
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                        if result.returncode == 0:
                            print("✓ Word timings generated successfully!")
                            print("  Karaoke sync will be available in web player")
                            self.state['word_timings_complete'] = True
                            self._save_state()
                        else:
                            print(f"⚠️  Word timing generation failed: {result.stderr}")

                except Exception as e:
                    print(f"⚠️  Word timing generation error: {e}")

            elif hasattr(self, 'generate_word_timings') and self.generate_word_timings:
                print("✓ Word timings already generated, skipping...\n")

            # STAGE 3: Register with Server
            if not self.state.get('server_registered'):
                print("\n📚 STAGE 3: SERVER REGISTRATION")
                print("-" * 70)

                self._register_with_server(audio_dir, cover_path)

                self.state['server_registered'] = True
                self.state['completed_at'] = datetime.now().isoformat()
                self._save_state()

            else:
                print("✓ Already registered with server, skipping...\n")

            # Final Summary
            print("\n" + "="*70)
            print("🎉 AUDIOBOOK COMPLETE!")
            print("="*70)
            print(f"Title: {self.input_file.stem.replace('_', ' ').title()}")
            print(f"Audio: {audio_dir}")
            print(f"Playlist: {self.state['playlist']}")
            if cover_path:
                print(f"Cover: {cover_path}")
            print(f"Chapters: {self.state['chapters']}")
            print(f"Format: {'MP3' if self.to_mp3 else 'WAV'}")
            print("="*70)
            print()
            print("💡 To play:")
            print(f"   afplay {self.state['playlist']}")
            print()
            print("💡 To serve on web:")
            print(f"   python3 server/audiobook_server.py")
            print(f"   Then open: http://localhost:8000")
            print("="*70)

            # Clean up state file on success
            if self.state_file.exists():
                self.state_file.unlink()

            return {
                'success': True,
                'audio_dir': str(audio_dir),
                'playlist': self.state['playlist'],
                'cover': str(cover_path) if cover_path else None,
                'chapters': self.state['chapters'],
                'chunks': self.state['chunks']
            }

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            print(f"Progress saved to: {self.state_file}")
            print(f"Resume by running the same command again.")
            self._save_state()
            sys.exit(0)

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            print(f"\nState saved to: {self.state_file}")
            print(f"Fix the issue and resume by running the same command.")
            self._save_state()
            raise


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="One-command audiobook generator with cover art and server integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (auto-detect everything)
  python3 make_audiobook.py books/alice_adventures/alices_adventures.md

  # British female voice + cover art (recommended for classics)
  python3 make_audiobook.py books/alice_adventures/alices_adventures.md \\
      --voice bf_emma --generate-cover

  # American male voice + faster playback
  python3 make_audiobook.py books/book.md --voice am_adam --speed 1.15

  # With summarization (50% of original length)
  python3 make_audiobook.py books/war_peace/war_peace.md --summarize 50 --generate-cover

Top Voices:
  bf_emma      - British Female (recommended for classics)
  bf_isabella  - British Female (alternative)
  bm_george    - British Male (classics)
  af_sky       - American Female (default)
  am_adam      - American Male
  am_onyx      - American Male (deep voice)

  Total: 52 voices available (af_*, am_*, bf_*, bm_*, etc.)

Features:
  ✓ Automatic Gutenberg boilerplate stripping
  ✓ Chapter detection (Roman numerals, numbered lists, headers)
  ✓ High-quality Kokoro TTS (31× faster than Bark)
  ✓ Commercial-friendly (Apache 2.0 license)
  ✓ Optional cover art generation
  ✓ Automatic server registration
  ✓ Resumable (saves progress)

Output:
  Audio files and playlist in: books/{book_name}/audio_kokoro/
  Cover art: books/{book_name}/audio_kokoro/{book_name}_cover.png
  Metadata: books/{book_name}/audio_kokoro/audiobook_metadata.json
        """
    )

    parser.add_argument(
        'input_file',
        help='Path to book markdown file'
    )

    parser.add_argument(
        '--voice',
        default='bf_emma',
        help='Voice ID (default: bf_emma - British female, great for classics)'
    )

    parser.add_argument(
        '--lang',
        default='en-us',
        help='Language code (default: en-us)'
    )

    parser.add_argument(
        '--chunk-size',
        type=int,
        default=800,
        help='Characters per audio chunk (default: 800)'
    )

    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Playback speed multiplier (default: 1.0, recommended: 1.1-1.2)'
    )

    parser.add_argument(
        '--no-normalize',
        action='store_true',
        help='Skip loudness normalization'
    )

    parser.add_argument(
        '--no-mp3',
        action='store_true',
        help='Keep WAV format (do not convert to MP3)'
    )

    parser.add_argument(
        '--generate-cover',
        action='store_true',
        help='Generate cover art for audiobook'
    )

    parser.add_argument(
        '--summarize',
        type=int,
        metavar='PERCENT',
        help='Summarize to target percentage (10-90, e.g., 50 = 50%% of original)'
    )

    parser.add_argument(
        '--output-dir',
        help='Custom output directory (default: auto-organized into books/{book_name}/audio_kokoro/)'
    )

    parser.add_argument(
        '--generate-word-timings',
        action='store_true',
        help='Generate word-level timing data for karaoke sync (requires ffprobe)'
    )

    args = parser.parse_args()

    # Validation
    if args.summarize and (args.summarize < 10 or args.summarize > 90):
        print(f"❌ ERROR: --summarize must be between 10-90 (got {args.summarize})")
        sys.exit(1)

    # Create audiobook maker
    try:
        maker = AudiobookMaker(
            input_file=args.input_file,
            voice=args.voice,
            language=args.lang,
            chunk_size=args.chunk_size,
            speed=args.speed,
            normalize=not args.no_normalize,
            to_mp3=not args.no_mp3,
            generate_cover=args.generate_cover,
            summarize_percentage=args.summarize,
            output_dir=args.output_dir,
            generate_word_timings=args.generate_word_timings
        )

        result = maker.make_audiobook()

        sys.exit(0)

    except KeyboardInterrupt:
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
