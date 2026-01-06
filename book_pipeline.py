#!/usr/bin/env python3
"""
Book Pipeline - Master CLI

Modular pipeline for book processing with flexible stage selection.
Run any combination of: translate, summarize, audio.

Examples:
  # Summarize + Audio (you already have translation)
  python book_pipeline.py --input translated.md --summarize 50 --audio --voice voice_ref.wav

  # Full pipeline: Translate + Summarize + Audio
  python book_pipeline.py --input original.md --translate Russian English --summarize 30 --audio --voice voice_ref.wav

  # Just summarize
  python book_pipeline.py --input translated.md --summarize 50

  # Just audio
  python book_pipeline.py --input text.md --audio --voice voice_ref.wav
"""

import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional


class BookPipeline:
    """Master pipeline orchestrator"""

    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.current_file = self.input_file

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

    def translate(self, source_lang: str, target_lang: str) -> Path:
        """
        Stage: Translation
        Uses local_reader_batch_translator.py
        """
        print("\n" + "="*70)
        print("STAGE: TRANSLATION")
        print("="*70)
        print(f"Source: {source_lang} → Target: {target_lang}")
        print()

        # For single files, we need to chunk first if large
        file_size = self.current_file.stat().st_size

        if file_size > 50000:  # 50KB threshold
            print("File is large, chunking first...")

            # Split into chunks
            chunks_dir = self.current_file.parent / "chunks"
            cmd = [
                sys.executable,
                "local_reader_smart_splitter.py",
                str(self.current_file)
            ]
            subprocess.run(cmd, check=True)

            # Translate chunks
            cmd = [
                sys.executable,
                "local_reader_batch_translator.py",
                str(chunks_dir),
                source_lang,
                target_lang
            ]
            subprocess.run(cmd, check=True)

            # Find translated output (first file in translated/deduplicated/)
            translated_dir = chunks_dir / "translated" / "deduplicated"
            translated_files = sorted(translated_dir.glob("*.md"))

            if not translated_files:
                raise RuntimeError("Translation produced no output files")

            # If multiple chunks, combine them
            if len(translated_files) > 1:
                combined_file = translated_dir.parent / f"{self.input_file.stem}_{target_lang.lower().replace(' ', '_')}_combined.md"
                with open(combined_file, 'w', encoding='utf-8') as outf:
                    for tf in translated_files:
                        with open(tf, 'r', encoding='utf-8') as inf:
                            outf.write(inf.read())
                            outf.write('\n\n')
                self.current_file = combined_file
            else:
                self.current_file = translated_files[0]
        else:
            # Small file, use single-file translator
            cmd = [
                sys.executable,
                "translator.py",
                str(self.current_file),
                "--source-lang", source_lang,
                "--target-lang", target_lang
            ]
            subprocess.run(cmd, check=True)

            # Find output file
            output_file = self.current_file.parent / f"{self.current_file.stem}_{target_lang.lower().replace(' ', '_')}.md"
            if not output_file.exists():
                raise RuntimeError(f"Translation output not found: {output_file}")

            self.current_file = output_file

        print(f"\n✅ Translation complete: {self.current_file.name}")
        return self.current_file

    def summarize(self, target_percentage: int) -> Path:
        """
        Stage: Summarization
        Uses book_summarizer.py
        """
        print("\n" + "="*70)
        print("STAGE: SUMMARIZATION")
        print("="*70)
        print(f"Target: {target_percentage}% of original length")
        print()

        from book_summarizer import BookSummarizer

        # Read input
        with open(self.current_file, 'r', encoding='utf-8') as f:
            text = f.read()

        original_words = len(text.split())
        print(f"Original length: {original_words:,} words\n")

        # Summarize
        summarizer = BookSummarizer(target_percentage=target_percentage)
        print(f"Chunk size: {summarizer.chunk_size_words} words (~{summarizer.chunk_size_words/500:.1f} pages)\n")

        result = summarizer.summarize_document(text, target_percentage)

        # Save summary
        output_filename = f"{self.current_file.stem}_summarized_{target_percentage}pct.md"
        output_path = self.current_file.parent / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.translated_text)

        self.current_file = output_path
        print(f"\n✅ Summarization complete: {self.current_file.name}")
        return self.current_file

    def generate_audio(self, voice_ref: str, language: str = "en") -> Path:
        """
        Stage: Audio Generation
        Uses local_tts_xtts.py
        """
        print("\n" + "="*70)
        print("STAGE: AUDIO GENERATION")
        print("="*70)
        print(f"Voice: {voice_ref}")
        print(f"Language: {language}")
        print()

        voice_path = Path(voice_ref)
        if not voice_path.exists():
            raise FileNotFoundError(f"Voice reference not found: {voice_ref}")

        cmd = [
            sys.executable,
            "local_tts_xtts.py",
            str(self.current_file),
            str(voice_ref),
            language
        ]

        subprocess.run(cmd, check=True)

        print(f"\n✅ Audio generation complete")

        # Audio files are in same directory as input, in audio_xtts/
        audio_dir = self.current_file.parent / "audio_xtts"
        return audio_dir

    def run(
        self,
        translate: Optional[tuple] = None,
        summarize: Optional[int] = None,
        audio: Optional[tuple] = None
    ):
        """
        Run the pipeline with selected stages.

        Args:
            translate: (source_lang, target_lang) tuple or None
            summarize: target_percentage or None
            audio: (voice_ref, language) tuple or None
        """
        print("\n" + "="*70)
        print("BOOK PROCESSING PIPELINE")
        print("="*70)
        print(f"Input: {self.input_file}")

        stages = []
        if translate:
            stages.append(f"Translate ({translate[0]} → {translate[1]})")
        if summarize:
            stages.append(f"Summarize ({summarize}%)")
        if audio:
            stages.append(f"Audio ({audio[1]})")

        print(f"Stages: {' → '.join(stages)}")
        print("="*70)

        try:
            # Stage 1: Translation (optional)
            if translate:
                source_lang, target_lang = translate
                self.translate(source_lang, target_lang)

            # Stage 2: Summarization (optional)
            if summarize:
                self.summarize(summarize)

            # Stage 3: Audio (optional)
            if audio:
                voice_ref, language = audio
                audio_dir = self.generate_audio(voice_ref, language)

            # Final summary
            print("\n" + "="*70)
            print("🎉 PIPELINE COMPLETE!")
            print("="*70)
            print(f"Final output: {self.current_file}")
            if audio:
                print(f"Audio directory: {audio_dir}")
            print("="*70)

        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Book processing pipeline with modular stages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize existing translation + generate audio
  python book_pipeline.py --input translated.md --summarize 50 --audio --voice voice_ref.wav

  # Full pipeline: translate, summarize, audio
  python book_pipeline.py --input original.md \\
      --translate Russian "Modern English" \\
      --summarize 30 \\
      --audio --voice voice_ref.wav --lang en

  # Just summarize (no audio)
  python book_pipeline.py --input translated.md --summarize 50

  # Just audio (no summarize)
  python book_pipeline.py --input text.md --audio --voice voice_ref.wav

  # Translate + audio (no summarize)
  python book_pipeline.py --input original.md \\
      --translate Latin "Modern English" \\
      --audio --voice voice_ref.wav
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input markdown file'
    )

    parser.add_argument(
        '--translate',
        nargs=2,
        metavar=('SOURCE', 'TARGET'),
        help='Translate from SOURCE to TARGET language (e.g., Russian "Modern English")'
    )

    parser.add_argument(
        '--summarize',
        type=int,
        metavar='PERCENT',
        help='Summarize to target percentage (10-90, e.g., 50 = 50%% of original)'
    )

    parser.add_argument(
        '--audio',
        action='store_true',
        help='Generate audiobook'
    )

    parser.add_argument(
        '--voice',
        help='Path to voice reference WAV file (required if --audio)'
    )

    parser.add_argument(
        '--lang',
        default='en',
        help='Audio language code (default: en). Options: en, es, fr, de, it, pt, ru, zh-cn, ja'
    )

    args = parser.parse_args()

    # Validation
    if args.summarize and (args.summarize < 10 or args.summarize > 90):
        print(f"❌ ERROR: --summarize must be between 10-90 (got {args.summarize})")
        sys.exit(1)

    if args.audio and not args.voice:
        print("❌ ERROR: --voice is required when using --audio")
        sys.exit(1)

    if not any([args.translate, args.summarize, args.audio]):
        print("❌ ERROR: Must specify at least one stage: --translate, --summarize, or --audio")
        parser.print_help()
        sys.exit(1)

    # Create pipeline
    pipeline = BookPipeline(args.input)

    # Run stages
    pipeline.run(
        translate=tuple(args.translate) if args.translate else None,
        summarize=args.summarize,
        audio=(args.voice, args.lang) if args.audio else None
    )


if __name__ == "__main__":
    main()
