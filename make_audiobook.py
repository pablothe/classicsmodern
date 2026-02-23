#!/usr/bin/env python3
"""
Make Audiobook - Unified One-Command Audiobook Generator

Single script to transform any book into a complete audiobook with cover art.

Usage:
    python3 make_audiobook.py books/alice_adventures/alices_adventures.md
    python3 make_audiobook.py INPUT.md --voice bf_emma --generate-cover
    python3 make_audiobook.py INPUT.md --summarize 50
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from lib.audio.kokoro import KokoroAudioGenerator
from lib.book.validator import validate_book
from lib.book.processor import BookProcessor
from lib.cover.prompts import get_book_prompt


class AudiobookMaker:
    """Unified audiobook creation pipeline."""

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
        generate_word_timings: bool = True,
        non_interactive: bool = False
    ):
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
        self.non_interactive = non_interactive

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        self.state_file = self.input_file.parent / f".audiobook_state_{self.input_file.stem}.json"

        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
            print(f"Resuming previous run from: {self.state.get('stage', 'unknown')}")
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
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _generate_cover_art(self, book_title: str) -> Optional[Path]:
        """Generate cover art, checking for existing cover first."""
        print("\nCover art check...")

        book_dir_cover = self.input_file.parent / "cover.png"
        if book_dir_cover.exists():
            print(f"  Using existing cover: {book_dir_cover.name}")
            return book_dir_cover

        print("  No existing cover found, generating new cover...")

        try:
            prompt = get_book_prompt(str(self.input_file))
            cover_path = self.input_file.parent / "cover.png"

            from lib.cover.generator import generate_image
            generate_image(
                prompt=prompt,
                output_path=str(cover_path),
                width=512,
                height=512
            )

            print(f"  Cover art generated: {cover_path.name}")
            return cover_path

        except Exception as e:
            print(f"  Cover generation error: {e}")
            return None

    def _generate_chapter_metadata(self, audio_dir: Path, playlist_path: str) -> bool:
        """Generate chapter metadata JSON for web player navigation."""
        try:
            from lib.audio.chapter_metadata import generate_chapter_metadata
            generate_chapter_metadata(Path(playlist_path))
            print("  Chapter metadata generated")
            return True
        except Exception as e:
            print(f"  Chapter metadata generation error: {e}")
            return False

    def _register_with_server(self, audio_dir: Path, cover_path: Optional[Path]):
        """Register audiobook with local server for web playback."""
        print("\nRegistering with audiobook server...")

        try:
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

            print(f"  Metadata saved: {metadata_path.name}")
            print(f"  Server will auto-discover on next scan")

        except Exception as e:
            print(f"  Server registration warning: {e}")

    def make_audiobook(self) -> Dict:
        """Main workflow: Create complete audiobook with all features."""
        print("\n" + "=" * 70)
        print("AUDIOBOOK MAKER - ONE-COMMAND WORKFLOW")
        print("=" * 70)
        print(f"Input: {self.input_file}")
        print(f"Voice: {self.voice}")
        print(f"Speed: {self.speed}x")
        print(f"Cover art: {'Yes' if self.generate_cover else 'No'}")
        if self.summarize_percentage:
            print(f"Summarization: {self.summarize_percentage}%")
        print("=" * 70)
        print()

        try:
            # STAGE 0: Pre-Flight Validation
            print("\nSTAGE 0: PRE-FLIGHT VALIDATION")
            print("-" * 70)

            validation_report = validate_book(str(self.input_file), verbose=False)

            if not validation_report.valid:
                print("  Book validation found issues:")
                for error in validation_report.errors:
                    print(f"   - {error}")
                for warning in validation_report.warnings:
                    print(f"   - {warning}")

                if validation_report.fixes:
                    print("\n  Suggested fixes:")
                    for fix in validation_report.fixes:
                        print(f"   - {fix}")

                if self.non_interactive:
                    print("\n  Validation failed. Attempting auto-fix...")
                    try:
                        processor = BookProcessor(verbose=False)
                        manifest = processor.process(self.input_file, auto_fix=True)

                        if manifest.chapters:
                            print(f"  Auto-fix succeeded: {len(manifest.chapters)} chapters detected")
                            detection_types = set(ch.detection_type for ch in manifest.chapters)
                            print(f"   Detection types: {detection_types}")
                            manifest_path = self.input_file.parent / f"{self.input_file.stem}_manifest.json"
                            manifest.save(manifest_path)
                            print(f"   Manifest saved: {manifest_path}")
                        else:
                            print("\n  Auto-fix failed: still no chapters detected.")
                            print(f"   Run: python3 validate.py {self.input_file} --auto-fix")
                            sys.exit(2)
                    except Exception as e:
                        print(f"\n  Auto-fix error: {e}")
                        print(f"   Run: python3 validate.py {self.input_file} --auto-fix")
                        sys.exit(2)

                if not self.non_interactive:
                    print("\n  Continue anyway? This may result in poor audiobook quality. (y/N): ", end="")
                    response = input().strip().lower()
                    if response != 'y':
                        print("\n  Aborted by user.")
                        print(f"   Run: python3 validate.py {self.input_file} --auto-fix")
                        return {'success': False, 'reason': 'validation_failed'}
            else:
                print("  Book validation passed!")
                feature_count = sum(validation_report.feature_support.values())
                print(f"  Feature support: {feature_count}/3 features ready")

                for feature, supported in validation_report.feature_support.items():
                    status = "+" if supported else "-"
                    print(f"   {status} {feature.title()}")

                if 'chapter_count' in validation_report.metrics:
                    print(f"   Chapters: {validation_report.metrics['chapter_count']}")
                if 'has_toc' in validation_report.metrics:
                    toc_status = "Yes" if validation_report.metrics['has_toc'] else "No"
                    print(f"   Table of Contents: {toc_status}")

            print("-" * 70 + "\n")

            # STAGE 1: Generate Audio
            if not self.state.get('audio_complete'):
                print("\nSTAGE 1: AUDIO GENERATION")
                print("-" * 70)

                generator = KokoroAudioGenerator(
                    voice=self.voice,
                    language=self.language
                )

                result = generator.generate_audiobook(
                    str(self.input_file),
                    output_dir=self.output_dir,
                    chunk_size=self.chunk_size,
                    speed=self.speed,
                    normalize=self.normalize,
                    to_mp3=self.to_mp3,
                    generate_cover=False
                )

                self.state['audio_complete'] = True
                self.state['audio_dir'] = result['output_directory']
                self.state['playlist'] = result['playlist']
                self.state['chapters'] = result['chapters']
                self.state['chunks'] = result['chunks']
                self._save_state()

                print(f"\n  Audio generation complete!")
                print(f"   Output: {result['output_directory']}")
                print(f"   Chapters: {result['chapters']}")
                print(f"   Format: {result['format'].upper()}")

                if result['chapters'] > 0:
                    print(f"\n  Generating chapter metadata for web player...")
                    audio_dir = Path(result['output_directory'])
                    self._generate_chapter_metadata(audio_dir, result['playlist'])

            else:
                print("  Audio already generated, skipping...\n")

            audio_dir = Path(self.state['audio_dir'])

            # STAGE 2: Generate Cover Art (optional)
            cover_path = None
            if self.generate_cover and not self.state.get('cover_complete'):
                print("\nSTAGE 2: COVER ART GENERATION")
                print("-" * 70)

                book_title = self.input_file.stem.replace('_', ' ').title()
                cover_path = self._generate_cover_art(book_title)

                self.state['cover_complete'] = True
                if cover_path:
                    self.state['cover_path'] = str(cover_path)
                self._save_state()

            elif self.generate_cover:
                print("  Cover art already generated, skipping...\n")
                cover_path = Path(self.state.get('cover_path')) if self.state.get('cover_path') else None

            # STAGE 2.5: Generate Word Timings (for karaoke sync)
            if self.generate_word_timings and not self.state.get('word_timings_complete'):
                print("\nSTAGE 2.5: WORD TIMING GENERATION (KARAOKE SYNC)")
                print("-" * 70)

                try:
                    from lib.audio.word_timings import generate_audiobook_word_timings, save_word_timings
                    playlist_path = Path(self.state['playlist'])
                    print(f"  Generating word timings for {self.state['chapters']} chapters...")
                    word_data = generate_audiobook_word_timings(playlist_path, method='fallback')
                    # Save to book directory
                    book_dir = playlist_path.parent
                    while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio']:
                        book_dir = book_dir.parent
                    output_path = book_dir / f"{book_dir.name}_word_timings.json"
                    save_word_timings(word_data, output_path)
                    print("  Word timings generated successfully!")
                    print("  Karaoke sync will be available in web player")
                    self.state['word_timings_complete'] = True
                    self._save_state()
                except Exception as e:
                    print(f"  Word timing generation error: {e}")

            elif self.generate_word_timings:
                print("  Word timings already generated, skipping...\n")

            # STAGE 3: Register with Server
            if not self.state.get('server_registered'):
                print("\nSTAGE 3: SERVER REGISTRATION")
                print("-" * 70)

                self._register_with_server(audio_dir, cover_path)

                self.state['server_registered'] = True
                self.state['completed_at'] = datetime.now().isoformat()
                self._save_state()

            else:
                print("  Already registered with server, skipping...\n")

            # Final Summary
            print("\n" + "=" * 70)
            print("AUDIOBOOK COMPLETE!")
            print("=" * 70)
            print(f"Title: {self.input_file.stem.replace('_', ' ').title()}")
            print(f"Audio: {audio_dir}")
            print(f"Playlist: {self.state['playlist']}")
            if cover_path:
                print(f"Cover: {cover_path}")
            print(f"Chapters: {self.state['chapters']}")
            print(f"Format: {'MP3' if self.to_mp3 else 'WAV'}")
            print("=" * 70)
            print()
            print("To play:")
            print(f"   afplay {self.state['playlist']}")
            print()
            print("To serve on web:")
            print(f"   ./start_server.sh")
            print(f"   Then open: http://localhost:8000")
            print("=" * 70)

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
            print("\n\nInterrupted by user")
            print(f"Progress saved to: {self.state_file}")
            print(f"Resume by running the same command again.")
            self._save_state()
            sys.exit(0)

        except Exception as e:
            print(f"\nERROR: {e}")
            print(f"\nState saved to: {self.state_file}")
            print(f"Fix the issue and resume by running the same command.")
            self._save_state()
            raise


def main():
    parser = argparse.ArgumentParser(
        description="One-command audiobook generator with cover art and server integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 make_audiobook.py books/alice_adventures/alices_adventures.md
  python3 make_audiobook.py INPUT.md --voice bf_emma --generate-cover
  python3 make_audiobook.py INPUT.md --voice am_adam --speed 1.15
  python3 make_audiobook.py INPUT.md --summarize 50 --generate-cover

Top Voices:
  bf_emma      - British Female (recommended for classics)
  bm_george    - British Male (classics)
  af_sky       - American Female (default)
  am_adam      - American Male
  am_onyx      - American Male (deep voice)
  Total: 52 voices available (af_*, am_*, bf_*, bm_*)
        """
    )

    parser.add_argument('input_file', help='Path to book markdown file')
    parser.add_argument('--voice', default='bf_emma',
                        help='Voice ID (default: bf_emma)')
    parser.add_argument('--lang', default='en-us',
                        help='Language code (default: en-us)')
    parser.add_argument('--chunk-size', type=int, default=800,
                        help='Characters per audio chunk (default: 800)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Playback speed multiplier (default: 1.0)')
    parser.add_argument('--no-normalize', action='store_true',
                        help='Skip loudness normalization')
    parser.add_argument('--no-mp3', action='store_true',
                        help='Keep WAV format (do not convert to MP3)')
    parser.add_argument('--generate-cover', action='store_true',
                        help='Generate cover art for audiobook')
    parser.add_argument('--summarize', type=int, metavar='PERCENT',
                        help='Summarize to target percentage (10-90)')
    parser.add_argument('--output-dir',
                        help='Custom output directory')
    parser.add_argument('--generate-word-timings', action='store_true',
                        default=True,
                        help='Generate word-level timing data for karaoke (default: enabled)')
    parser.add_argument('--no-word-timings', action='store_true',
                        help='Disable word timing generation')
    parser.add_argument('--non-interactive', action='store_true',
                        help='Skip validation prompts, fail fast (for automation)')

    args = parser.parse_args()

    if args.summarize and (args.summarize < 10 or args.summarize > 90):
        print(f"ERROR: --summarize must be between 10-90 (got {args.summarize})")
        sys.exit(1)

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
            generate_word_timings=not args.no_word_timings,
            non_interactive=args.non_interactive
        )

        maker.make_audiobook()
        sys.exit(0)

    except KeyboardInterrupt:
        sys.exit(130)

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
