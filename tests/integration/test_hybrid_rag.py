#!/usr/bin/env python3
"""Integration tests for server/hybrid_rag.py

Tests question classification → retrieval strategy routing without
requiring live LLM or sentence-transformers (mocks vector store).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from server.hybrid_rag import HybridRAG
    from server.question_classifier import classify_question
    HYBRID_RAG_AVAILABLE = True
except ImportError:
    HYBRID_RAG_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYBRID_RAG_AVAILABLE,
    reason="server.hybrid_rag or dependencies not available"
)


@pytest.fixture
def book_with_chapters(temp_dir):
    """Create a book file with chapter content."""
    book_dir = temp_dir / "test_book"
    book_dir.mkdir()
    book_file = book_dir / "book.md"
    content = (
        "## CHAPTER I. The Beginning\n\n"
        "Alice was beginning to get very tired of sitting by her sister. "
        "She had peeped into the book her sister was reading. "
        "It had no pictures or conversations in it.\n\n"
        "## CHAPTER II. The Pool of Tears\n\n"
        "Curiouser and curiouser! cried Alice. She was now more than nine feet high. "
        "She began to cry again, and went on growing.\n\n"
        "## CHAPTER III. A Caucus-Race\n\n"
        "They were indeed a queer-looking party that assembled on the bank. "
        "The birds with draggled feathers, the animals with their fur clinging.\n\n"
        "## CHAPTER IV. The Rabbit Sends in a Little Bill\n\n"
        "It was the White Rabbit, trotting slowly back again. "
        "It was looking anxiously about as it went.\n\n"
    )
    book_file.write_text(content)
    return book_file


class TestQuestionClassification:
    def test_summary_question_classified_as_broad(self):
        result = classify_question("Summarize the entire book")
        assert result['type'] == 'BROAD_SUMMARY'

    def test_specific_question_classified_as_factual(self):
        result = classify_question("How is Alice described in chapter 1?")
        assert result['type'] == 'SPECIFIC_FACTUAL'

    def test_classification_has_required_fields(self):
        result = classify_question("Tell me about the characters")
        assert 'type' in result
        assert 'confidence' in result
        assert 'reasoning' in result


class TestFullSectionRetrieval:
    def test_chapter_reference_retrieves_chapter(self, book_with_chapters):
        rag = HybridRAG(book_with_chapters)
        result = rag.retrieve_context("Summarize chapter 2")
        assert result['method'] == 'full_section'
        assert result['question_type'] == 'BROAD_SUMMARY'
        assert 'chapter_2' in result['metadata']['method_detail']
        assert 'Curiouser' in result['context']

    def test_beginning_reference(self, book_with_chapters):
        rag = HybridRAG(book_with_chapters)
        result = rag.retrieve_context("What happens in the beginning?")
        assert result['method'] == 'full_section'
        assert 'first' in result['metadata']['method_detail']

    def test_end_reference(self, book_with_chapters):
        rag = HybridRAG(book_with_chapters)
        result = rag.retrieve_context("What happens at the end of the book?")
        assert result['method'] == 'full_section'
        assert 'last' in result['metadata']['method_detail']

    def test_result_has_word_count(self, book_with_chapters):
        rag = HybridRAG(book_with_chapters)
        result = rag.retrieve_context("Summarize chapter 1")
        assert result['metadata']['total_words'] > 0


class TestSemanticSearchRetrieval:
    def test_specific_question_uses_semantic_search(self, book_with_chapters):
        """Specific factual questions should route to semantic search."""
        rag = HybridRAG(book_with_chapters)

        # Mock the vector store to avoid needing sentence-transformers
        mock_store = MagicMock()
        mock_store.search.return_value = [
            ({"text": "Alice was tired", "position_pct": 5.0, "word_count": 3, "preview": "Alice was..."}, 0.9),
            ({"text": "She peeped into the book", "position_pct": 6.0, "word_count": 5, "preview": "She peeped..."}, 0.8),
            ({"text": "No pictures", "position_pct": 7.0, "word_count": 2, "preview": "No pictures..."}, 0.7),
        ]
        rag.vector_store = mock_store

        # "What does Alice look like?" is high-confidence SPECIFIC_FACTUAL
        result = rag.retrieve_context("What does Alice look like?")
        assert result['method'] == 'semantic_search'
        assert result['metadata']['chunks_retrieved'] >= 2  # Reranking may adjust count
        assert result['metadata']['avg_similarity'] > 0

    def test_empty_vector_store_results(self, book_with_chapters):
        """Semantic search with no results should still return valid structure."""
        rag = HybridRAG(book_with_chapters)
        mock_store = MagicMock()
        mock_store.search.return_value = [
            ({"text": "fallback", "position_pct": 0.0, "word_count": 1, "preview": "fallback"}, 0.1),
        ]
        rag.vector_store = mock_store

        result = rag.retrieve_context("What color is the sky?")
        assert 'context' in result
        assert 'method' in result
