#!/usr/bin/env python3
"""
Book Summarizer

Summarizes translated books to a target percentage using Ollama LLM.
Preserves Markdown structure while condensing content.
"""

import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
from local_reader_translation import OllamaTranslator, TranslationChunk, TranslationResult
from local_reader_config import get_config
from book_metadata import MetadataManager, SummarizationMetadata
from book_validator import validate_book


class BookSummarizer:
    """Handles book summarization using Ollama models"""

    def __init__(self, target_percentage: int = 50, chunk_size_words: int = None, max_chunk_size: int = 1500):
        """
        Initialize book summarizer.

        Args:
            target_percentage: Target length as percentage of original (e.g., 50 = 50%)
            chunk_size_words: Words per chunk for summarization (auto-calculated if None)
            max_chunk_size: Maximum safe chunk size for 4B model (default: 1500 words ~= 2000 tokens)
        """
        self.target_percentage = target_percentage
        self.max_chunk_size = max_chunk_size

        # Conservative chunk sizing to stay within context limits
        # For aggressive compression, we'll use recursive summarization instead
        if chunk_size_words is None:
            chunk_size_words = 1200  # Safe default for all compression ratios

        # Cap at max_chunk_size for safety
        chunk_size_words = min(chunk_size_words, max_chunk_size)
        self.chunk_size_words = chunk_size_words

        # Get config and create translator (we'll reuse the Ollama infrastructure)
        config = get_config()
        self.translator = OllamaTranslator(
            model_name=config.models.default_translation_model,
            ollama_host=config.models.ollama_host,
            chunk_size_words=chunk_size_words
        )

    def _summarize_chunk(
        self,
        chunk: TranslationChunk,
        target_percentage: int,
        previous_summary: Optional[str] = None
    ) -> str:
        """
        Summarize a single chunk using Ollama API with optional context.

        Args:
            chunk: The chunk to summarize
            target_percentage: Target length as percentage of original
            previous_summary: Previously summarized text for context (optional)

        Returns:
            Summarized text
        """
        # Calculate target word count
        original_words = len(chunk.content.split())
        target_words = int(original_words * (target_percentage / 100))

        # Construct the summarization prompt
        if previous_summary:
            # Get last 1-2 sentences from previous summary for context
            context = self.translator._get_last_sentences(previous_summary, count=2)

            prompt = f"""You are condensing a text. Rewrite the following passage in approximately {target_words} words, keeping the same narrative voice and perspective.

PREVIOUS PASSAGE (for continuity only):
---
{context}
---

CONDENSE THIS PASSAGE TO ~{target_words} WORDS:
{chunk.content}

Rules:
- Keep the SAME voice (first person stays first person, third person stays third person, etc.)
- Preserve the most important ideas and events
- Maintain Markdown formatting (headers, lists, etc.)
- Do NOT write "This text discusses..." or "The author says..." - stay IN the narrative
- Output ONLY the condensed passage, no explanations"""
        else:
            # First chunk, no context
            prompt = f"""You are condensing a text. Rewrite the following passage in approximately {target_words} words, keeping the same narrative voice and perspective.

CONDENSE THIS PASSAGE TO ~{target_words} WORDS:
{chunk.content}

Rules:
- Keep the SAME voice (first person stays first person, third person stays third person, etc.)
- Preserve the most important ideas and events
- Maintain Markdown formatting (headers, lists, etc.)
- Do NOT write "This text discusses..." or "The author says..." - stay IN the narrative
- Output ONLY the condensed passage, no explanations"""

        # Call Ollama API (reuse translator's API structure)
        payload = {
            "model": self.translator.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.5  # Slightly higher for creative summarization
            }
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                import requests
                response = requests.post(self.translator.api_url, json=payload)
                response.raise_for_status()

                result = response.json()
                summarized = result.get('response', '').strip()

                # Basic validation (check it's not completely empty)
                if len(summarized.strip()) < 5:
                    print(f"⚠️  Warning: Chunk {chunk.index} summary is empty (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    else:
                        print(f"❌ ERROR: Chunk {chunk.index} produced empty summary, using original")
                        return chunk.content

                # Check for LLM refusals or meta-commentary
                if any(phrase in summarized.lower() for phrase in ["i cannot", "i can't", "i'm unable", "as an ai"]):
                    print(f"⚠️  Warning: Chunk {chunk.index} contains refusal/meta-commentary (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue

                return summarized

            except Exception as e:
                print(f"⚠️  Error summarizing chunk {chunk.index} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"❌ Summarization failed after {max_retries} attempts")
                    return chunk.content

        return chunk.content

    def summarize_document(
        self,
        text: str,
        target_percentage: int = None
    ) -> TranslationResult:
        """
        Summarize an entire document with recursive summarization for aggressive compression.

        Args:
            text: The text to summarize
            target_percentage: Override default target percentage

        Returns:
            TranslationResult object with summarized text (reusing translation infrastructure)
        """
        if target_percentage is None:
            target_percentage = self.target_percentage

        start_time = time.time()

        # Check if model is available
        if not self.translator.check_model_available():
            raise RuntimeError(
                f"Model '{self.translator.model_name}' not found in Ollama. "
                f"Please run: ollama pull {self.translator.model_name}"
            )

        # Determine if we need recursive summarization
        # For aggressive compression (< 30%), do multi-pass summarization
        if target_percentage < 30:
            print(f"🔄 Using recursive summarization for {target_percentage}% target")
            print(f"   Pass 1: Summarize to 60% (conservative)")
            print(f"   Pass 2: Summarize the summary to {target_percentage}%\n")

            # First pass: Conservative 60% compression
            first_pass = self._single_pass_summarize(text, 60, pass_number=1)

            # Second pass: Compress to final target
            print(f"\n🔄 Starting Pass 2: {target_percentage}% of Pass 1 result...")
            result = self._single_pass_summarize(first_pass, target_percentage, pass_number=2)

            elapsed_time = time.time() - start_time
            original_words = len(text.split())
            final_words = len(result.split())
            actual_percentage = (final_words / original_words * 100) if original_words > 0 else 0

            print(f"\n📊 Final Compression Stats:")
            print(f"   Original: {original_words:,} words")
            print(f"   After Pass 1 (60%): {len(first_pass.split()):,} words")
            print(f"   Final: {final_words:,} words")
            print(f"   Actual compression: {actual_percentage:.1f}% (target: {target_percentage}%)")

            return TranslationResult(
                translated_text=result,
                source_language="Original",
                target_language=f"Summarized ({target_percentage}%, 2-pass)",
                chunks_processed=-1,  # Multi-pass
                total_time_seconds=elapsed_time,
                model_used=self.translator.model_name
            )
        else:
            # Single-pass summarization for moderate compression
            return self._single_pass_summarize_full(text, target_percentage, start_time)

    def _single_pass_summarize(self, text: str, target_percentage: int, pass_number: int = 1) -> str:
        """Single pass of summarization, returns just the text"""
        chunks = self.translator._chunk_markdown_text(text)
        total_chunks = len(chunks)

        print(f"Pass {pass_number}: Summarizing {total_chunks} chunks to {target_percentage}%...")

        summarized_chunks = []
        previous_summary = None

        for i, chunk in enumerate(chunks):
            summarized = self._summarize_chunk(
                chunk,
                target_percentage,
                previous_summary=previous_summary
            )
            summarized_chunks.append(summarized)
            previous_summary = summarized
            print(f"  Chunk {i+1}/{total_chunks} completed")

        return '\n\n'.join(summarized_chunks)

    def _single_pass_summarize_full(
        self,
        text: str,
        target_percentage: int,
        start_time: float
    ) -> TranslationResult:
        """Single-pass summarization with full result object"""
        chunks = self.translator._chunk_markdown_text(text)
        total_chunks = len(chunks)

        print(f"Summarizing {total_chunks} chunks to {target_percentage}% of original length...")

        summarized_chunks = []
        previous_summary = None

        for i, chunk in enumerate(chunks):
            summarized = self._summarize_chunk(
                chunk,
                target_percentage,
                previous_summary=previous_summary
            )
            summarized_chunks.append(summarized)
            previous_summary = summarized
            print(f"  Chunk {i+1}/{total_chunks} completed")

        summarized_text = '\n\n'.join(summarized_chunks)
        elapsed_time = time.time() - start_time

        original_words = len(text.split())
        summarized_words = len(summarized_text.split())
        actual_percentage = (summarized_words / original_words * 100) if original_words > 0 else 0

        print(f"\n📊 Compression Stats:")
        print(f"   Original: {original_words:,} words")
        print(f"   Summarized: {summarized_words:,} words")
        print(f"   Actual compression: {actual_percentage:.1f}% (target: {target_percentage}%)")

        return TranslationResult(
            translated_text=summarized_text,
            source_language="Original",
            target_language=f"Summarized ({target_percentage}%)",
            chunks_processed=total_chunks,
            total_time_seconds=elapsed_time,
            model_used=self.translator.model_name
        )


def main():
    """Main function for command-line usage"""

    if len(sys.argv) < 2:
        print("Usage: python book_summarizer.py <input_file> [target_percentage] [chunk_size_words]")
        print("\nExample:")
        print("  python book_summarizer.py books/de_brevitate_vitae/de_brevitae_vitae_modern_english.md 50")
        print("  python book_summarizer.py books/alice/translated.md 10")
        print("  python book_summarizer.py books/alice/translated.md 30 1500")
        print("\nChunk size auto-scaling:")
        print("  10% target (90% compression) → 5000 words/chunk (~10 pages)")
        print("  30% target (70% compression) → 3000 words/chunk (~6 pages)")
        print("  50% target (50% compression) → 2000 words/chunk (~4 pages)")
        print("  Or specify custom chunk size as third argument")
        print("\nThis will:")
        print("  1. Read the input markdown file")
        print("  2. Auto-calculate optimal chunk size based on compression ratio")
        print("  3. Summarize to target percentage (default: 50%)")
        print("  4. Preserve Markdown structure (headers, lists, etc.)")
        print("  5. Save as '[original]_summarized_[percentage].md'")
        sys.exit(1)

    input_file = sys.argv[1]
    target_percentage = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    chunk_size_words = int(sys.argv[3]) if len(sys.argv) > 3 else None  # Auto-calculate

    # Validate percentage
    if target_percentage < 10 or target_percentage > 90:
        print(f"❌ ERROR: Target percentage must be between 10-90 (got {target_percentage})")
        sys.exit(1)

    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ ERROR: File not found: {input_file}")
        sys.exit(1)

    # Read input file
    print(f"Reading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    original_word_count = len(text.split())
    print(f"Original length: {original_word_count:,} words\n")

    # Create summarizer with auto-calculated or custom chunk size
    summarizer = BookSummarizer(target_percentage=target_percentage, chunk_size_words=chunk_size_words)
    print(f"Chunk size: {summarizer.chunk_size_words} words (~{summarizer.chunk_size_words/500:.1f} pages)\n")

    # Summarize
    try:
        result = summarizer.summarize_document(text, target_percentage)

        # Generate output filename
        output_filename = f"{input_path.stem}_summarized_{target_percentage}pct.md"
        output_path = input_path.parent / output_filename

        # Save summarized file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.translated_text)

        # Save metadata
        summarized_words = len(result.translated_text.split())
        actual_percentage = (summarized_words / original_word_count * 100) if original_word_count > 0 else 0

        # Determine if recursive summarization was used
        recursive_passes = 1
        if "2-pass" in result.target_language:
            recursive_passes = 2

        metadata = SummarizationMetadata(
            target_percentage=target_percentage,
            actual_percentage=actual_percentage,
            model=result.model_used,
            timestamp=datetime.now().isoformat(),
            original_file=str(input_path),
            word_count_original=original_word_count,
            word_count_summarized=summarized_words,
            chunks_processed=result.chunks_processed if result.chunks_processed > 0 else 0,
            duration_seconds=result.total_time_seconds,
            recursive_passes=recursive_passes
        )

        MetadataManager.add_summarization(
            output_path,
            metadata,
            book_title=input_path.stem
        )

        print("\n" + "="*70)
        print("SUMMARIZATION COMPLETE")
        print("="*70)
        print(f"Output file: {output_path}")
        print(f"Metadata: {output_path.stem}.meta.json")
        print(f"Model: {result.model_used}")
        print(f"Chunks processed: {result.chunks_processed}")
        print(f"Time: {result.total_time_seconds:.1f}s ({result.total_time_seconds/60:.1f}min)")
        print("="*70)
        print("\n✅ Ready for audiobook generation!")
        print(f"   Next step: python local_tts_xtts.py {output_path} voice_ref.wav en")
        print(f"   View metadata: python book_metadata.py {output_path}")

        # Validate summarized output
        print("\n" + "="*70)
        print("VALIDATING OUTPUT")
        print("="*70)
        validation_report = validate_book(str(output_path), verbose=False)

        if validation_report.valid:
            print("✅ Output validation passed!")
            feature_count = sum(validation_report.feature_support.values())
            print(f"✅ Feature support: {feature_count}/3 features ready")
            for feature, supported in validation_report.feature_support.items():
                icon = "✅" if supported else "❌"
                print(f"   {icon} {feature.title()}")
        else:
            print("⚠️  Output validation found issues:")
            for error in validation_report.errors:
                print(f"   ❌ {error}")
            for warning in validation_report.warnings:
                print(f"   ⚠️  {warning}")

            if validation_report.fixes:
                print("\n💡 Suggested fixes:")
                for fix in validation_report.fixes:
                    print(f"   • {fix}")

        print("="*70)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
