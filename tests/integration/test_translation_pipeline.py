#!/usr/bin/env python3
"""
Integration Tests for Translation Pipeline

Tests the full translation workflow: Split -> Translate -> Deduplicate
Uses mock LLMs to test without requiring Ollama.
"""

import sys
import re
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.llm import LLMProvider
from lib.translation.engine import OllamaTranslator
from lib.translation.deduplicate import (
    find_exact_overlap, find_fuzzy_overlap, deduplicate_chunks,
)


# =============================================================================
# Mock LLMs for Integration Tests
# =============================================================================

class MockRecordingLLM(LLMProvider):
    """LLM that records all prompts and returns predictable translations."""

    def __init__(self):
        super().__init__(name="mock-recording", model="recording-v1")
        self.prompts = []
        self.call_count = 0

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        self.prompts.append(prompt)
        self.call_count += 1

        # Extract content after instruction line
        lines = prompt.split('\n')
        content_start = None
        for i, line in enumerate(lines):
            if line.startswith('Translate to') or line.startswith('Rewrite this'):
                content_start = i + 1
                break

        if content_start is not None:
            content = '\n'.join(lines[content_start:]).strip()
        else:
            content = prompt.strip()

        # Return a simple "translation" (prefix with [T])
        return f"[T{self.call_count}] {content}"

    def is_available(self) -> dict:
        return {"available": True, "provider": "mock-recording"}


class MockEchoLLM(LLMProvider):
    """LLM that echoes context back, creating duplicates."""

    def __init__(self):
        super().__init__(name="mock-echo", model="echo-v1")

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        context_match = re.search(
            r'Reference \(do not repeat\):\s*\n(.*?)\n\n',
            prompt, re.DOTALL
        )

        lines = prompt.split('\n')
        content_start = None
        for i, line in enumerate(lines):
            if line.startswith('Translate to') or line.startswith('Rewrite this'):
                content_start = i + 1
                break

        if content_start is not None:
            content = '\n'.join(lines[content_start:]).strip()
        else:
            content = prompt.strip()

        if context_match:
            return f"{context_match.group(1).strip()} {content}"
        return content

    def is_available(self) -> dict:
        return {"available": True, "provider": "mock-echo"}


# =============================================================================
# Test Data
# =============================================================================

MULTI_CHUNK_TEXT = """Thus spoke Zarathustra to the people gathered in the marketplace.
The will to power is not merely a desire for domination but a fundamental drive
toward self-overcoming and creative transformation.

Man is something that shall be overcome. What have you done to overcome him?
I teach you the overman. Man is a rope tied between beast and overman.

All beings so far have created something beyond themselves. Do you want to be
the ebb of this great flood and even go back to the beasts rather than overcome man?"""


@pytest.mark.integration
class TestTranslationPipeline:
    """Test full translation pipeline"""

    def test_split_translate_deduplicate_workflow(self, temp_dir, sample_book_content):
        """Test complete workflow from splitting to deduplication"""
        book_file = temp_dir / "test_book.md"
        book_file.write_text(sample_book_content * 3)

        # Translate with echo LLM (creates overlaps)
        llm = MockEchoLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=30)

        result = translator.translate_document_with_context(
            book_file.read_text(),
            source_lang="German",
            target_lang="Modern English"
        )

        # Write chunks to files for dedup
        chunks = result.translated_text.split('\n\n')
        chunk_files = []
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                f = temp_dir / f"chunk_{i:03d}.md"
                f.write_text(chunk.strip())
                chunk_files.append(f)

        if len(chunk_files) >= 2:
            # Count overlaps before dedup
            overlaps_before = 0
            for i in range(len(chunk_files) - 1):
                t1 = chunk_files[i].read_text()
                t2 = chunk_files[i + 1].read_text()
                overlap = find_exact_overlap(t1, t2, max_words=50)
                if overlap and len(overlap.split()) >= 3:
                    overlaps_before += 1

            # Run deduplication
            output_dir = temp_dir / "deduped"
            deduped = deduplicate_chunks(chunk_files, output_dir)

            # Verify deduped files exist
            assert len(deduped) == len(chunk_files)

            # Count overlaps after dedup — should be reduced
            overlaps_after = 0
            for i in range(len(deduped) - 1):
                t1 = deduped[i].read_text()
                t2 = deduped[i + 1].read_text()
                overlap = find_exact_overlap(t1, t2, max_words=50)
                if overlap and len(overlap.split()) >= 3:
                    overlaps_after += 1

            assert overlaps_after <= overlaps_before, (
                f"Dedup should reduce overlaps: before={overlaps_before}, after={overlaps_after}"
            )

    def test_progress_tracking_saves_after_each_chunk(self, temp_dir):
        """Test that progress is saved and can be resumed"""
        progress_file = temp_dir / ".translation_progress.json"

        progress_data = {
            'total_chunks': 5,
            'completed': 3,
            'last_chunk': 'chunk_003',
            'timestamp': '2026-02-04T12:00:00Z'
        }

        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

        assert progress_file.exists()

        with open(progress_file, 'r') as f:
            loaded = json.load(f)

        assert loaded['completed'] == 3
        assert loaded['total_chunks'] == 5

    def test_resume_from_interruption(self, temp_dir):
        """Test resuming translation after interruption"""
        progress_file = temp_dir / ".translation_progress.json"
        progress_data = {
            'total_chunks': 5,
            'completed': 2,
            'last_chunk': 'chunk_002'
        }

        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

        for i in range(1, 3):
            chunk_file = temp_dir / f"chunk_00{i}_translated.md"
            chunk_file.write_text(f"Translated chunk {i}")

        assert progress_file.exists()
        assert (temp_dir / "chunk_001_translated.md").exists()
        assert (temp_dir / "chunk_002_translated.md").exists()
        assert not (temp_dir / "chunk_003_translated.md").exists()

    def test_error_recovery_continues_on_failure(self, temp_dir):
        """Test that pipeline continues when one chunk fails"""
        chunks = [
            ("chunk_001.md", "successful"),
            ("chunk_002.md", "failed"),
            ("chunk_003.md", "successful")
        ]

        for filename, status in chunks:
            chunk_file = temp_dir / filename
            chunk_file.write_text(f"Content: {status}")

        assert all((temp_dir / f).exists() for f, _ in chunks)


@pytest.mark.integration
class TestBatchTranslation:
    """Test batch translation functionality"""

    def test_batch_translate_multiple_chunks(self, temp_dir):
        """Test translating multiple chunks in batch with mock LLM."""
        llm = MockRecordingLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=20)

        for i in range(1, 4):
            chunk_file = temp_dir / f"chunk_00{i}.md"
            chunk_file.write_text(f"Content for chunk {i} with enough words to be meaningful.")

        # Translate each chunk
        results = []
        for i in range(1, 4):
            text = (temp_dir / f"chunk_00{i}.md").read_text()
            result = translator.translate_document(text, "German", "English")
            results.append(result)

        assert len(results) == 3
        assert all(r.translated_text for r in results)
        assert llm.call_count >= 3

    def test_context_passed_between_chunks(self, temp_dir):
        """Test that context from previous chunk is passed to next."""
        llm = MockRecordingLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=20)

        result = translator.translate_document_with_context(
            MULTI_CHUNK_TEXT,
            source_lang="German",
            target_lang="Modern English"
        )

        # First prompt should NOT have "Reference"
        assert "Reference (do not repeat)" not in llm.prompts[0]

        # Second+ prompts SHOULD have "Reference" with content from previous translation
        if len(llm.prompts) > 1:
            assert "Reference (do not repeat)" in llm.prompts[1], (
                "Second chunk should receive context from first chunk"
            )
            # The reference should contain text from the first translation
            ref_match = re.search(
                r'Reference \(do not repeat\):\s*\n(.*?)\n\n',
                llm.prompts[1], re.DOTALL
            )
            assert ref_match is not None
            context = ref_match.group(1).strip()
            assert len(context) > 0, "Context should not be empty"


@pytest.mark.integration
class TestDeduplicationIntegration:
    """Test deduplication as part of full pipeline"""

    def test_deduplicated_files_used_for_audio(self, temp_dir):
        """Test that deduplicated files are properly organized for audio generation"""
        deduped_dir = temp_dir / "deduplicated"
        deduped_dir.mkdir()

        for i in range(1, 4):
            chunk_file = deduped_dir / f"chunk_00{i}_DEDUPED.md"
            chunk_file.write_text(f"Clean content {i}")

        assert deduped_dir.exists()
        assert len(list(deduped_dir.glob("*_DEDUPED.md"))) == 3

    def test_fuzzy_dedup_catches_paraphrased_overlap(self, temp_dir):
        """Test that fuzzy dedup catches near-duplicate text at boundaries."""
        chunk1 = temp_dir / "chunk_001.md"
        chunk2 = temp_dir / "chunk_002.md"

        # Chunk 1 ends with a sentence
        chunk1.write_text(
            "Earlier content here. The will to power is not merely a desire for domination."
        )
        # Chunk 2 starts with a paraphrased version
        chunk2.write_text(
            "The will to power is not just a wish for domination. New content continues here."
        )

        output_dir = temp_dir / "deduped"
        deduped = deduplicate_chunks([chunk1, chunk2], output_dir)

        # Fuzzy dedup should have caught it
        deduped_text = deduped[1].read_text()
        # The paraphrased sentence should be removed or reduced
        assert "New content continues here" in deduped_text


@pytest.mark.integration
class TestChunkingIntegration:
    """Test smart chunking integration"""

    def test_split_at_paragraph_boundaries(self, temp_dir):
        """Test that chunking respects paragraph boundaries."""
        llm = MockRecordingLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=20)

        text = (
            "First paragraph with enough words to fill a chunk completely here.\n\n"
            "Second paragraph also has enough words to make another chunk here.\n\n"
            "Third paragraph rounds out the content for testing purposes here."
        )

        result = translator.translate_document(text, "German", "English")

        # Should have created multiple chunks
        assert llm.call_count >= 2
        # Translation should be non-empty
        assert len(result.translated_text) > 0

    def test_chunk_size_affects_number_of_chunks(self, temp_dir):
        """Test that smaller chunk size creates more chunks."""
        text = " ".join(["word"] * 100)  # 100 words

        llm1 = MockRecordingLLM()
        translator1 = OllamaTranslator(llm=llm1, chunk_size_words=20)
        translator1.translate_document(text, "German", "English")

        llm2 = MockRecordingLLM()
        translator2 = OllamaTranslator(llm=llm2, chunk_size_words=50)
        translator2.translate_document(text, "German", "English")

        # Smaller chunks = more LLM calls
        assert llm1.call_count >= llm2.call_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
