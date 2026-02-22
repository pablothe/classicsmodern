#!/usr/bin/env python3
"""
Hybrid RAG System - Combines semantic search with full-section retrieval

Architecture:
1. Question classifier determines retrieval strategy
2. SPECIFIC_FACTUAL → Semantic search (top 5-10 chunks, ~1-2K tokens)
3. BROAD_SUMMARY → Full section retrieval (~8K tokens)
"""

from pathlib import Path
from typing import Dict, List
from server.question_classifier import classify_question
from server.semantic_retrieval import build_vector_store_for_book, VectorStore
from server.llm_chat import BookTools


class HybridRAG:
    """
    Hybrid retrieval-augmented generation system.

    Combines:
    - Semantic search (for specific factual questions)
    - Full section retrieval (for summaries and overviews)
    """

    def __init__(self, book_path: Path, chapters_metadata: List[Dict] = None):
        """
        Initialize hybrid RAG system.

        Args:
            book_path: Path to book markdown file
            chapters_metadata: Optional chapter metadata
        """
        self.book_path = book_path
        self.chapters_metadata = chapters_metadata

        # Initialize both retrieval systems
        self.book_tools = BookTools(book_path, chapters_metadata)
        self.vector_store = None  # Lazy load

    def _ensure_vector_store(self):
        """Lazy load vector store (only when needed for semantic search)"""
        if self.vector_store is None:
            cache_dir = self.book_path.parent / '.vector_cache'
            print(f"[Hybrid RAG] Building vector store for {self.book_path.name}...")
            self.vector_store = build_vector_store_for_book(
                self.book_path,
                cache_dir=cache_dir
            )
            print(f"[Hybrid RAG] ✓ Vector store ready")

    def retrieve_context(self, question: str) -> Dict:
        """
        Retrieve relevant context based on question type.

        Args:
            question: User question

        Returns:
            {
                'context': str,  # Retrieved text
                'method': 'semantic_search' | 'full_section',
                'question_type': 'SPECIFIC_FACTUAL' | 'BROAD_SUMMARY',
                'confidence': 'high' | 'medium' | 'low',
                'metadata': dict  # Additional info (chunks retrieved, etc.)
            }
        """
        # Classify question
        classification = classify_question(question)
        question_type = classification['type']
        confidence = classification['confidence']

        print(f"[Hybrid RAG] Question type: {question_type} (confidence: {confidence})")
        print(f"[Hybrid RAG] Reasoning: {classification['reasoning']}")

        if question_type == 'SPECIFIC_FACTUAL':
            return self._semantic_search_retrieval(question, classification)
        else:
            return self._full_section_retrieval(question, classification)

    def _semantic_search_retrieval(self, question: str, classification: Dict) -> Dict:
        """
        Retrieve relevant chunks using semantic search.

        Strategy:
        - Search for top 5 most relevant chunks
        - Combine into single context (~1-2K tokens)
        - Rerank by position (place most relevant at start/end to avoid "lost in middle")
        """
        self._ensure_vector_store()

        # Search for top 5 chunks
        results = self.vector_store.search(question, top_k=5)

        # Rerank: Put highest similarity at start, second-highest at end
        # (helps with "lost in the middle" problem)
        if len(results) >= 3:
            reranked = [
                results[0],  # Highest similarity (start)
                *results[2:-1],  # Middle results
                results[1],  # Second-highest (end)
            ]
        else:
            reranked = results

        # Combine chunks
        context_parts = []
        for i, (chunk, score) in enumerate(reranked):
            context_parts.append(
                f"[Chunk {i+1}, Similarity: {score:.2f}, Position: {chunk['position_pct']:.1f}% through book]\n"
                f"{chunk['text']}"
            )

        context = '\n\n---\n\n'.join(context_parts)

        # Calculate stats
        total_words = sum(chunk['word_count'] for chunk, _ in reranked)

        return {
            'context': context,
            'method': 'semantic_search',
            'question_type': classification['type'],
            'confidence': classification['confidence'],
            'metadata': {
                'chunks_retrieved': len(reranked),
                'total_words': total_words,
                'avg_similarity': sum(score for _, score in reranked) / len(reranked),
                'chunks_info': [
                    {
                        'position_pct': chunk['position_pct'],
                        'similarity': score,
                        'preview': chunk['preview']
                    }
                    for chunk, score in reranked
                ]
            }
        }

    def _full_section_retrieval(self, question: str, classification: Dict) -> Dict:
        """
        Retrieve full section using existing BookTools.

        Strategy:
        - Parse question to extract section reference (chapter, percentage, etc.)
        - Retrieve full section(s)
        """
        # Try to extract section from question
        question_lower = question.lower()

        # Check for chapter references
        import re
        chapter_match = re.search(r'chapter\s+(\d+|[ivxlcdm]+)', question_lower)
        if chapter_match:
            chapter_str = chapter_match.group(1)
            if chapter_str.isdigit():
                chapter_num = int(chapter_str)
            else:
                # Roman numeral conversion (simplified)
                roman_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
                           'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10}
                chapter_num = roman_map.get(chapter_str, 1)

            context = self.book_tools.get_chapter(chapter_num)
            method_detail = f'chapter_{chapter_num}'
        # Check for percentage references
        elif 'first' in question_lower or 'beginning' in question_lower:
            context = self.book_tools.get_book_section(0, 25)
            method_detail = 'first_25_percent'
        elif 'middle' in question_lower:
            context = self.book_tools.get_book_section(25, 75)
            method_detail = 'middle_50_percent'
        elif 'end' in question_lower or 'last' in question_lower:
            context = self.book_tools.get_book_section(75, 100)
            method_detail = 'last_25_percent'
        else:
            # Default: first 25%
            context = self.book_tools.get_book_section(0, 25)
            method_detail = 'default_first_25_percent'

        # Calculate stats
        word_count = len(context.split())

        return {
            'context': context,
            'method': 'full_section',
            'question_type': classification['type'],
            'confidence': classification['confidence'],
            'metadata': {
                'method_detail': method_detail,
                'total_words': word_count
            }
        }


# ============================================================================
# Testing
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python hybrid_rag.py <book.md>")
        sys.exit(1)

    book_path = Path(sys.argv[1])

    # Initialize hybrid RAG
    print(f"Initializing Hybrid RAG for {book_path.name}...")
    rag = HybridRAG(book_path)

    # Test questions
    test_questions = [
        "How is Cthulhu described in the first 25% of the book?",
        "What does Alice look like?",
        "Summarize chapter 5",
        "What happens in the beginning?",
        "Who is the main character?",
    ]

    for question in test_questions:
        print(f"\n{'='*80}")
        print(f"QUESTION: {question}")
        print(f"{'='*80}\n")

        result = rag.retrieve_context(question)

        print(f"Method: {result['method']}")
        print(f"Question Type: {result['question_type']}")
        print(f"Confidence: {result['confidence']}")

        if result['method'] == 'semantic_search':
            meta = result['metadata']
            print(f"Chunks Retrieved: {meta['chunks_retrieved']}")
            print(f"Total Words: {meta['total_words']}")
            print(f"Avg Similarity: {meta['avg_similarity']:.3f}")
            print(f"\nChunks:")
            for i, chunk_info in enumerate(meta['chunks_info'], 1):
                print(f"  {i}. Position: {chunk_info['position_pct']:.1f}%, "
                      f"Similarity: {chunk_info['similarity']:.3f}")
                print(f"     {chunk_info['preview']}")
        else:
            meta = result['metadata']
            print(f"Method Detail: {meta['method_detail']}")
            print(f"Total Words: {meta['total_words']}")

        print(f"\nContext Preview (first 500 chars):")
        print(result['context'][:500] + "...")
