#!/usr/bin/env python3
"""
Tests proving translation boundary duplication gaps.

These tests demonstrate vulnerabilities in the current dedup system:
1. Exact echo: Layer 2 catches word-for-word repeats (working)
2. Paraphrased echo: Layer 2 misses synonym-swapped repeats (gap)
3. Structured path: paragraph-by-paragraph has no dedup at all (gap)
4. Large overlap: 30-word window misses longer overlaps (gap)
"""

import sys
import re
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.llm import LLMProvider
from lib.translation.engine import OllamaTranslator
from lib.translation.deduplicate import find_exact_overlap


# =============================================================================
# Mock LLM Providers
# =============================================================================

class MockEchoLLM(LLMProvider):
    """LLM that echoes context back verbatim, simulating worst-case behavior."""

    def __init__(self):
        super().__init__(name="mock-echo", model="echo-v1")
        self.prompts_received = []

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        self.prompts_received.append(prompt)

        # Parse context from "Reference (do not repeat):\n{context}\n\n"
        context_match = re.search(
            r'Reference \(do not repeat\):\s*\n(.*?)\n\n',
            prompt,
            re.DOTALL
        )

        # Extract the actual content to "translate" (after the instruction line)
        # The prompt format is: instruction\n\ncontent  OR  Reference...\n\ninstruction\ncontent
        lines = prompt.split('\n')
        # Find content after "Translate to" or "Rewrite this" instruction
        content_start = None
        for i, line in enumerate(lines):
            if line.startswith('Translate to') or line.startswith('Rewrite this'):
                content_start = i + 1
                break

        if content_start is not None:
            actual_content = '\n'.join(lines[content_start:]).strip()
        else:
            actual_content = prompt.strip()

        # Simulate bad LLM: echo context + translate content
        if context_match:
            echoed_context = context_match.group(1).strip()
            return f"{echoed_context} {actual_content}"
        else:
            return actual_content

    def is_available(self) -> dict:
        return {"available": True, "provider": "mock-echo"}


class MockParaphraseEchoLLM(LLMProvider):
    """LLM that echoes context with synonym substitutions."""

    SYNONYMS = {
        "the": "one",
        "was": "had been",
        "very": "extremely",
        "began": "started",
        "said": "spoke",
        "large": "big",
        "small": "tiny",
        "quickly": "rapidly",
        "merely": "only",
        "desire": "wish",
        "power": "might",
        "is": "remains",
        "not": "never",
        "man": "humanity",
        "great": "remarkable",
        "that": "which",
        "and": "plus",
        "he": "one",
        "over": "above",
        "have": "possess",
        "something": "a thing",
        "what": "which thing",
    }

    def __init__(self):
        super().__init__(name="mock-paraphrase", model="paraphrase-v1")

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        context_match = re.search(
            r'Reference \(do not repeat\):\s*\n(.*?)\n\n',
            prompt,
            re.DOTALL
        )

        lines = prompt.split('\n')
        content_start = None
        for i, line in enumerate(lines):
            if line.startswith('Translate to') or line.startswith('Rewrite this'):
                content_start = i + 1
                break

        if content_start is not None:
            actual_content = '\n'.join(lines[content_start:]).strip()
        else:
            actual_content = prompt.strip()

        if context_match:
            echoed_context = context_match.group(1).strip()
            # Swap synonyms to create a paraphrase
            paraphrased = echoed_context
            for original, replacement in self.SYNONYMS.items():
                paraphrased = re.sub(
                    rf'\b{re.escape(original)}\b',
                    replacement,
                    paraphrased,
                    flags=re.IGNORECASE
                )
            return f"{paraphrased} {actual_content}"
        else:
            return actual_content

    def is_available(self) -> dict:
        return {"available": True, "provider": "mock-paraphrase"}


class MockCleanLLM(LLMProvider):
    """LLM that translates cleanly without echoing context. Control group."""

    def __init__(self):
        super().__init__(name="mock-clean", model="clean-v1")

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        lines = prompt.split('\n')
        content_start = None
        for i, line in enumerate(lines):
            if line.startswith('Translate to') or line.startswith('Rewrite this'):
                content_start = i + 1
                break

        if content_start is not None:
            return '\n'.join(lines[content_start:]).strip()
        return prompt.strip()

    def is_available(self) -> dict:
        return {"available": True, "provider": "mock-clean"}


# =============================================================================
# Test Data
# =============================================================================

NIETZSCHE_SAMPLE = """Thus spoke Zarathustra to the people gathered in the marketplace.
The will to power is not merely a desire for domination but a fundamental drive
toward self-overcoming and creative transformation. Man is something that shall
be overcome. What have you done to overcome him?

I teach you the overman. Man is a rope tied between beast and overman, a rope
over an abyss. What is great in man is that he is a bridge and not an end.
The last man blinks and says we have invented happiness.

All beings so far have created something beyond themselves. Do you want to be
the ebb of this great flood and even go back to the beasts rather than overcome
man? What is the ape to man? A laughingstock or a painful embarrassment."""


# =============================================================================
# Phase 1 Tests: Proving the Gaps
# =============================================================================

class TestExactEchoDetected:
    """Layer 2 (exact dedup) works for verbatim echoes."""

    def test_exact_echo_caught_by_find_exact_overlap(self):
        """When LLM echoes context word-for-word, find_exact_overlap detects it."""
        # Simulate: chunk 1 ends with "a rope over an abyss"
        # chunk 2 starts with "a rope over an abyss What is great"
        chunk1_output = "The will to power drives toward self-overcoming. Man is a rope over an abyss."
        chunk2_output = "a rope over an abyss. What is great in man is that he is a bridge."

        overlap = find_exact_overlap(chunk1_output, chunk2_output, max_words=30)
        assert overlap is not None
        assert "rope over an abyss" in overlap

    def test_exact_echo_through_engine_path(self):
        """Full engine path: MockEchoLLM echoes context, and consecutive chunks have overlap."""
        llm = MockEchoLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=30)

        result = translator.translate_document_with_context(
            NIETZSCHE_SAMPLE,
            source_lang="German",
            target_lang="Modern English"
        )

        # Split result back into chunks (they're joined with \n\n)
        output_chunks = [c.strip() for c in result.translated_text.split('\n\n') if c.strip()]

        # Check consecutive chunk pairs for overlap
        overlaps_found = 0
        for i in range(len(output_chunks) - 1):
            overlap = find_exact_overlap(output_chunks[i], output_chunks[i + 1], max_words=30)
            if overlap and len(overlap.split()) >= 2:
                overlaps_found += 1

        # The echo LLM should create detectable overlaps
        assert overlaps_found > 0, (
            "Expected exact overlaps from echo LLM, but none found. "
            "This means the echo mock isn't producing the expected pattern."
        )


class TestParaphrasedEchoUndetected:
    """Layer 2 misses paraphrased echoes — proving fuzzy dedup is needed."""

    def test_paraphrased_overlap_missed_by_exact_dedup(self):
        """Synonym-swapped sentences are NOT caught by find_exact_overlap."""
        original = "The will to power is not merely a desire for domination."
        paraphrased = "A will to strength is not just a wish for domination."

        overlap = find_exact_overlap(original, paraphrased, max_words=30)
        assert overlap is None, (
            f"Expected no exact match for paraphrased text, but found: {overlap}"
        )

    def test_paraphrased_echo_through_engine_undetected(self):
        """Full engine path: paraphrase echo LLM creates undetectable duplicates."""
        llm = MockParaphraseEchoLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=30)

        result = translator.translate_document_with_context(
            NIETZSCHE_SAMPLE,
            source_lang="German",
            target_lang="Modern English"
        )

        output_chunks = [c.strip() for c in result.translated_text.split('\n\n') if c.strip()]

        # Check that exact dedup finds NOTHING (proving the gap)
        exact_overlaps = 0
        for i in range(len(output_chunks) - 1):
            overlap = find_exact_overlap(output_chunks[i], output_chunks[i + 1], max_words=30)
            if overlap and len(overlap.split()) >= 2:
                exact_overlaps += 1

        assert exact_overlaps == 0, (
            "Exact dedup should NOT catch paraphrased echoes — "
            "if it does, the mock isn't paraphrasing enough."
        )

        # But the output DOES contain duplicate content (semantically)
        # We verify this by checking that chunks share significant word overlap
        # even though exact dedup misses it
        if len(output_chunks) >= 2:
            words_chunk1 = set(output_chunks[0].lower().split())
            words_chunk2_start = set(output_chunks[1].lower().split()[:30])
            shared_words = words_chunk1 & words_chunk2_start
            # Filter out common stop words
            stop_words = {'the', 'a', 'an', 'is', 'was', 'are', 'in', 'of', 'to', 'and', 'for', 'that', 'not'}
            meaningful_shared = shared_words - stop_words
            # There should be meaningful word overlap from the echo
            assert len(meaningful_shared) >= 2, (
                f"Expected semantic overlap between chunks, got shared words: {meaningful_shared}"
            )


class TestLargeOverlapUndetected:
    """30-word window is too small for long overlapping passages."""

    def test_50_word_overlap_missed_with_30_word_window(self):
        """Exact overlap of 50 words is not fully detected with max_words=30."""
        overlap_text = " ".join([f"word{i}" for i in range(50)])
        text1 = f"prefix text here {overlap_text}"
        text2 = f"{overlap_text} suffix text here"

        result = find_exact_overlap(text1, text2, max_words=30)

        if result:
            # Should find at most 30 words, missing the full 50-word overlap
            assert len(result.split()) <= 30
            assert len(result.split()) < 50, (
                "With max_words=30, should not detect full 50-word overlap"
            )
        # Even finding partial overlap is OK — the point is the full overlap is missed

    def test_50_word_overlap_detected_with_larger_window(self):
        """Same overlap IS detected when window is increased to 50+."""
        overlap_text = " ".join([f"word{i}" for i in range(50)])
        text1 = f"prefix text here {overlap_text}"
        text2 = f"{overlap_text} suffix text here"

        result = find_exact_overlap(text1, text2, max_words=60)
        assert result is not None
        assert len(result.split()) == 50


class TestCleanTranslationNoFalsePositives:
    """Control: clean LLM output should have no overlaps."""

    def test_clean_llm_no_overlaps(self):
        """A well-behaved LLM that doesn't echo context produces no overlaps."""
        llm = MockCleanLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=30)

        result = translator.translate_document_with_context(
            NIETZSCHE_SAMPLE,
            source_lang="German",
            target_lang="Modern English"
        )

        output_chunks = [c.strip() for c in result.translated_text.split('\n\n') if c.strip()]

        for i in range(len(output_chunks) - 1):
            overlap = find_exact_overlap(output_chunks[i], output_chunks[i + 1], max_words=30)
            if overlap:
                assert len(overlap.split()) < 3, (
                    f"Clean LLM should not produce overlaps, but found: '{overlap}'"
                )


class TestContextPromptStructure:
    """Verify the prompt sent to the LLM includes context correctly."""

    def test_second_chunk_receives_reference_context(self):
        """The second chunk's prompt should contain 'Reference (do not repeat):' with previous text."""
        llm = MockEchoLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=30)

        translator.translate_document_with_context(
            NIETZSCHE_SAMPLE,
            source_lang="German",
            target_lang="Modern English"
        )

        # First prompt should NOT have "Reference" (no previous context)
        assert "Reference (do not repeat)" not in llm.prompts_received[0]

        # Second+ prompts SHOULD have "Reference"
        if len(llm.prompts_received) > 1:
            assert "Reference (do not repeat)" in llm.prompts_received[1], (
                "Second chunk prompt should include reference context from first chunk"
            )

    def test_context_limited_to_2_sentences(self):
        """Context passed to LLM is limited to last 2 sentences, not entire previous chunk."""
        llm = MockEchoLLM()
        translator = OllamaTranslator(llm=llm, chunk_size_words=20)

        # Use text with many sentences per chunk
        long_text = (
            "First sentence of the text. Second sentence follows here. "
            "Third sentence is also present. Fourth sentence ends this part. "
            "Fifth sentence begins a new thought. Sixth sentence continues it. "
            "Seventh sentence wraps up. Eighth sentence is the conclusion."
        )

        translator.translate_document_with_context(
            long_text,
            source_lang="German",
            target_lang="Modern English"
        )

        if len(llm.prompts_received) > 1:
            second_prompt = llm.prompts_received[1]
            ref_match = re.search(
                r'Reference \(do not repeat\):\s*\n(.*?)\n\n',
                second_prompt,
                re.DOTALL
            )
            if ref_match:
                context = ref_match.group(1)
                # Context should be limited (max 500 chars, ~2 sentences)
                assert len(context) <= 500, (
                    f"Context should be <= 500 chars, got {len(context)}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
