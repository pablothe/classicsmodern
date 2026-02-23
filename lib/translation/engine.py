"""
Local Reader Translation Module

Handles translation of classic literature using local Ollama models.
Preserves Markdown structure while translating content.
"""

import re
import requests
import json
import logging
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('translation_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TranslationChunk:
    """Represents a chunk of text to be translated"""
    index: int
    content: str
    markdown_type: str  # 'header', 'paragraph', 'list', 'table', 'code'
    original_formatting: str  # Store any formatting markers


@dataclass
class TranslationResult:
    """Results from translation operation"""
    translated_text: str
    source_language: str
    target_language: str
    chunks_processed: int
    total_time_seconds: float
    model_used: str


class OllamaTranslator:
    """
    Translator using local Ollama models.
    Designed to work with zongwei/gemma3-translator models.
    """

    def __init__(
        self,
        model_name: str = "zongwei/gemma3-translator:4b",
        ollama_host: str = "http://localhost:11434",
        chunk_size_words: int = 150  # Reduced from 250 for better Latin translation (less timeout risk)
    ):
        """
        Initialize the Ollama translator.

        Args:
            model_name: Name of the Ollama model to use
            ollama_host: URL of the Ollama API server
            chunk_size_words: Target number of words per chunk
        """
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.chunk_size_words = chunk_size_words
        self.api_url = f"{ollama_host}/api/generate"

    def check_model_available(self) -> bool:
        """
        Check if the specified model is available in Ollama.

        Returns:
            True if model is available, False otherwise
        """
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(model['name'] == self.model_name for model in models)
            return False
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            print(f"Error checking model availability: {e}")
            return False

    def get_ollama_health(self) -> Dict:
        """
        Get Ollama health status and running models.

        Returns:
            Dict with health information
        """
        health = {
            'available': False,
            'models_loaded': [],
            'error': None
        }

        try:
            # Check if Ollama is running
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                health['available'] = True
                models = response.json().get('models', [])
                health['models_loaded'] = [m['name'] for m in models]
                logger.info(f"Ollama health: OK, {len(models)} models loaded")
            else:
                health['error'] = f"Ollama returned status {response.status_code}"
                logger.warning(f"Ollama health: {health['error']}")

        except requests.Timeout:
            health['error'] = "Ollama connection timeout (>5s)"
            logger.error(f"Ollama health: {health['error']}")

        except Exception as e:
            health['error'] = f"{type(e).__name__}: {e}"
            logger.error(f"Ollama health: {health['error']}")

        return health

    def _chunk_markdown_text(self, text: str) -> List[TranslationChunk]:
        """
        Split Markdown text into chunks while preserving structure.

        Args:
            text: The Markdown text to chunk

        Returns:
            List of TranslationChunk objects
        """
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_word_count = 0
        chunk_index = 0

        for line in lines:
            # Detect Markdown type
            markdown_type = self._detect_markdown_type(line)
            words_in_line = len(line.split())

            # Start new chunk if we exceed word limit and it's a good breaking point
            if (current_word_count + words_in_line > self.chunk_size_words and
                current_chunk and
                markdown_type in ['header', 'paragraph']):

                # Save current chunk
                chunk_content = '\n'.join(current_chunk)
                chunks.append(TranslationChunk(
                    index=chunk_index,
                    content=chunk_content,
                    markdown_type=markdown_type,
                    original_formatting=''
                ))
                chunk_index += 1
                current_chunk = []
                current_word_count = 0

            current_chunk.append(line)
            current_word_count += words_in_line

        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(TranslationChunk(
                index=chunk_index,
                content=chunk_content,
                markdown_type='paragraph',
                original_formatting=''
            ))

        return chunks

    def _detect_markdown_type(self, line: str) -> str:
        """
        Detect the type of Markdown element in a line.

        Args:
            line: A line of text

        Returns:
            String identifier for Markdown type
        """
        line_stripped = line.strip()

        if line_stripped.startswith('#'):
            return 'header'
        elif line_stripped.startswith('```'):
            return 'code'
        elif line_stripped.startswith('|'):
            return 'table'
        elif line_stripped.startswith('-') or line_stripped.startswith('*') or line_stripped.startswith('+'):
            return 'list'
        elif not line_stripped:
            return 'empty'
        else:
            return 'paragraph'

    def _get_last_sentences(self, text: str, count: int = 2, max_chars: int = 500) -> str:
        """
        Extract last N sentences from text, with maximum character limit.

        Args:
            text: The text to extract from
            count: Number of sentences to extract
            max_chars: Maximum characters to return (default 500)

        Returns:
            Last N sentences as a string, truncated to max_chars if needed
        """
        # Split on sentence boundaries (., !, ?)
        sentences = re.split(r'([.!?]+\s+)', text)

        # Rejoin sentence pairs (text + delimiter)
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                combined.append(sentences[i] + sentences[i + 1])
            else:
                combined.append(sentences[i])

        # Handle last element if odd number
        if len(sentences) % 2 == 1:
            combined.append(sentences[-1])

        # Get last N sentences
        result = ''.join(combined[-count:]).strip()

        # Truncate if exceeds max_chars (prevents context bloat)
        if len(result) > max_chars:
            result = result[-max_chars:]  # Keep last max_chars characters

        return result

    def _validate_translation(self, translated: str, original_chunk: str) -> bool:
        """
        Validate that the translation looks legitimate (not model commentary).

        Args:
            translated: The translated text to validate
            original_chunk: The original chunk for comparison

        Returns:
            True if translation appears valid, False if it looks like garbage
        """
        # Check for common LLM meta-commentary patterns
        garbage_patterns = [
            r"^I will (read|translate)",
            r"^I'll (read|translate)",
            r"^Let me (read|translate)",
            r"^Here is the translation",
            r"^Translation:",
            r"^The text says",
            r"^This (text|passage) (is|means)"
        ]

        for pattern in garbage_patterns:
            if re.search(pattern, translated, re.IGNORECASE | re.MULTILINE):
                return False

        # Check if the translation is suspiciously short (less than 10% of original)
        # Note: cross-language translations (e.g., French→English) can legitimately
        # produce shorter text, so we use a generous threshold
        if len(translated) < len(original_chunk) * 0.1 and len(original_chunk) > 50:
            return False

        # Check for excessive repetition (same line repeated 5+ times)
        lines = translated.split('\n')
        if len(lines) > 5:
            line_counts = {}
            for line in lines:
                stripped = line.strip()
                if stripped:
                    line_counts[stripped] = line_counts.get(stripped, 0) + 1
            # If any line appears more than 5 times, it's likely garbage
            if any(count > 5 for count in line_counts.values()):
                return False

        return True

    def _translate_chunk(
        self,
        chunk: TranslationChunk,
        source_lang: str,
        target_lang: str,
        previous_translation: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Translate a single chunk using Ollama API with optional context.

        Args:
            chunk: The chunk to translate
            source_lang: Source language
            target_lang: Target language
            previous_translation: Previously translated text for context (optional)
            progress_callback: Optional callback function(current, total)

        Returns:
            Translated text
        """
        # Construct the translation prompt (SIMPLIFIED to prevent prompt leakage)
        # LLM can auto-detect source language, we only specify target
        if previous_translation:
            # Get last 1-2 sentences from previous translation for context
            context = self._get_last_sentences(previous_translation, count=2)

            prompt = f"""Reference (do not repeat):
{context}

Translate to {target_lang}:
{chunk.content}"""
        else:
            # First chunk, no context
            prompt = f"Translate to {target_lang}:\n\n{chunk.content}"

        # Call Ollama API
        chunk_id = f"chunk_{chunk.index}"
        logger.info(f"[{chunk_id}] Starting translation ({len(chunk.content)} chars, {len(chunk.content.split())} words)")
        logger.info(f"[{chunk_id}] API: {self.api_url}, Model: {self.model_name}")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3  # Lower temperature for more consistent translations
            }
        }

        max_retries = 3
        for attempt in range(max_retries):
            request_start = time.time()
            try:
                logger.info(f"[{chunk_id}] Attempt {attempt + 1}/{max_retries} - sending request to Ollama...")

                # Set timeout to 5 minutes (Latin translation can be slow)
                response = requests.post(self.api_url, json=payload, timeout=300)

                request_duration = time.time() - request_start
                logger.info(f"[{chunk_id}] Response received in {request_duration:.1f}s (status: {response.status_code})")

                response.raise_for_status()

                result = response.json()
                translated = result.get('response', '').strip()

                logger.info(f"[{chunk_id}] Translation received ({len(translated)} chars)")
                logger.debug(f"[{chunk_id}] Preview: {translated[:100]}...")

                # Validate the translation
                if not self._validate_translation(translated, chunk.content):
                    print(f"⚠️  Warning: Chunk {chunk.index} translation failed validation (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        print(f"   Retrying with adjusted prompt...")
                        time.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        print(f"❌ ERROR: Chunk {chunk.index} produced invalid translation after {max_retries} attempts")
                        print(f"   Marking as untranslated to prevent silent language mixing")
                        logger.warning(f"Chunk {chunk.index} could not be translated after {max_retries} validation failures")
                        return f"[UNTRANSLATED]\n{chunk.content}\n[/UNTRANSLATED]"

                return translated

            except requests.Timeout:
                request_duration = time.time() - request_start
                logger.error(f"[{chunk_id}] TIMEOUT after {request_duration:.1f}s (attempt {attempt + 1}/{max_retries})")
                logger.error(f"[{chunk_id}] Chunk size: {len(chunk.content)} chars, {len(chunk.content.split())} words")
                logger.error(f"[{chunk_id}] Check Ollama status: ollama ps")

                print(f"⏰ Timeout: Chunk {chunk.index} exceeded 5 minutes (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    print(f"   Retrying with same timeout...")
                    time.sleep(2)
                    continue
                else:
                    logger.error(f"[{chunk_id}] FAILED after {max_retries} timeout attempts")
                    print(f"❌ Translation failed after {max_retries} timeout attempts")
                    print(f"   Consider: 1) Checking Ollama status, 2) Reducing chunk size, 3) Using faster model")
                    logger.warning(f"Chunk {chunk.index} could not be translated after {max_retries} timeout attempts")
                    return f"[UNTRANSLATED]\n{chunk.content}\n[/UNTRANSLATED]"

            except Exception as e:
                request_duration = time.time() - request_start
                logger.error(f"[{chunk_id}] ERROR after {request_duration:.1f}s (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}")
                logger.error(f"[{chunk_id}] Chunk size: {len(chunk.content)} chars")

                print(f"⚠️  Error translating chunk {chunk.index} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Longer pause on API errors
                    continue
                else:
                    logger.error(f"[{chunk_id}] FAILED after {max_retries} attempts")
                    print(f"❌ Translation failed after {max_retries} attempts")
                    logger.warning(f"Chunk {chunk.index} could not be translated after {max_retries} error attempts")
                    return f"[UNTRANSLATED]\n{chunk.content}\n[/UNTRANSLATED]"

        # Should never reach here, but just in case
        logger.warning(f"Chunk {chunk.index} fell through all retry logic")
        return f"[UNTRANSLATED]\n{chunk.content}\n[/UNTRANSLATED]"

    def translate_document_with_context(
        self,
        text: str,
        source_lang: Optional[str] = None,  # DEPRECATED: LLM auto-detects source
        target_lang: str = "Modern English",
        previous_context: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> TranslationResult:
        """
        Translate an entire document with optional context from previous document.

        Args:
            text: The text to translate
            source_lang: DEPRECATED - LLM auto-detects source language
            target_lang: Target language (e.g. "Modern English", "Spanish")
            previous_context: Context from previous file/chunk (optional)
            progress_callback: Optional callback function(current, total)

        Returns:
            TranslationResult object with translated text and metadata
        """
        start_time = time.time()

        # Check if model is available
        if not self.check_model_available():
            raise RuntimeError(
                f"Model '{self.model_name}' not found in Ollama. "
                f"Please run: ollama pull {self.model_name}"
            )

        # Chunk the document
        chunks = self._chunk_markdown_text(text)
        total_chunks = len(chunks)

        print(f"Translating {total_chunks} chunks from {source_lang} to {target_lang}...")

        # Translate each chunk with context
        translated_chunks = []
        untranslated_count = 0

        # Use previous document's context for first chunk (if available)
        if previous_context:
            previous_translation = previous_context
            print(f"  Using context from previous file")
        else:
            previous_translation = None

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, total_chunks)

            # Pass previous translation as context
            translated = self._translate_chunk(
                chunk,
                source_lang,
                target_lang,
                previous_translation=previous_translation
            )
            translated_chunks.append(translated)

            # Track untranslated chunks
            if '[UNTRANSLATED]' in translated:
                untranslated_count += 1
            else:
                # Only use successfully translated chunks as context
                previous_translation = translated

            # Progress indicator
            print(f"  Chunk {i+1}/{total_chunks} completed")

        # Report untranslated chunks
        if untranslated_count > 0:
            print(f"\n⚠️  {untranslated_count}/{total_chunks} chunks could not be translated")
            print(f"   Search for [UNTRANSLATED] markers in the output to find them")
            logger.warning(f"{untranslated_count}/{total_chunks} chunks were not translated")

        # Combine chunks
        translated_text = '\n\n'.join(translated_chunks)

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        return TranslationResult(
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang,
            chunks_processed=total_chunks,
            total_time_seconds=elapsed_time,
            model_used=self.model_name
        )

    def translate_document(
        self,
        text: str,
        source_lang: Optional[str] = None,  # DEPRECATED: LLM auto-detects source
        target_lang: str = "Modern English",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> TranslationResult:
        """
        Translate an entire document.

        Args:
            text: The text to translate
            source_lang: DEPRECATED - LLM auto-detects source language
            target_lang: Target language (e.g. "Modern English", "Spanish")
            progress_callback: Optional callback function(current, total)

        Returns:
            TranslationResult object with translated text and metadata
        """
        start_time = time.time()

        # Check if model is available
        if not self.check_model_available():
            raise RuntimeError(
                f"Model '{self.model_name}' not found in Ollama. "
                f"Please run: ollama pull {self.model_name}"
            )

        # Chunk the document
        chunks = self._chunk_markdown_text(text)
        total_chunks = len(chunks)

        print(f"Translating {total_chunks} chunks from {source_lang} to {target_lang}...")

        # Translate each chunk with context from previous chunk
        translated_chunks = []
        previous_translation = None
        untranslated_count = 0

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, total_chunks)

            # Pass previous translation as context (except for first chunk)
            translated = self._translate_chunk(
                chunk,
                source_lang,
                target_lang,
                previous_translation=previous_translation
            )
            translated_chunks.append(translated)

            # Track untranslated chunks
            if '[UNTRANSLATED]' in translated:
                untranslated_count += 1
            else:
                # Only use successfully translated chunks as context
                previous_translation = translated

            # Progress indicator
            print(f"  Chunk {i+1}/{total_chunks} completed")

        # Report untranslated chunks
        if untranslated_count > 0:
            print(f"\n⚠️  {untranslated_count}/{total_chunks} chunks could not be translated")
            print(f"   Search for [UNTRANSLATED] markers in the output to find them")
            logger.warning(f"{untranslated_count}/{total_chunks} chunks were not translated")

        # Combine chunks
        translated_text = '\n\n'.join(translated_chunks)

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        return TranslationResult(
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang,
            chunks_processed=total_chunks,
            total_time_seconds=elapsed_time,
            model_used=self.model_name
        )


def test_translation():
    """Test the translation module with sample text"""

    sample_text = """# Test Chapter

This is a test paragraph with some **bold text** and *italic text*.

## Subsection

- List item 1
- List item 2
- List item 3

Another paragraph with [a link](https://example.com) to test preservation.
"""

    translator = OllamaTranslator(
        model_name="zongwei/gemma3-translator:4b",
        chunk_size_words=50
    )

    # Simple progress callback
    def progress(current, total):
        print(f"Progress: {current}/{total} ({100*current/total:.1f}%)")

    try:
        result = translator.translate_document(
            text=sample_text,
            source_lang="English",
            target_lang="Spanish",
            progress_callback=progress
        )

        print("\n" + "="*60)
        print("TRANSLATION COMPLETE")
        print("="*60)
        print(f"Model: {result.model_used}")
        print(f"Chunks processed: {result.chunks_processed}")
        print(f"Time: {result.total_time_seconds:.2f} seconds")
        print("\nTranslated text:")
        print("-"*60)
        print(result.translated_text)

    except Exception as e:
        print(f"Translation failed: {e}")


if __name__ == "__main__":
    test_translation()
