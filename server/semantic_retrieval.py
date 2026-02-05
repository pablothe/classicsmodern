#!/usr/bin/env python3
"""
Semantic Retrieval for Hybrid RAG System

Provides semantic chunking and vector search for precise information retrieval.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple
import hashlib
import pickle


class SemanticChunker:
    """
    Chunk book text into semantically coherent segments.

    Strategy: Paragraph-based chunking with size constraints
    - Respects paragraph boundaries (markdown line breaks)
    - Target: 200-400 tokens per chunk (~150-300 words)
    - Maintains chapter context
    """

    def __init__(self, target_words_per_chunk: int = 150, max_words_per_chunk: int = 250):
        """
        Initialize chunker.

        Args:
            target_words_per_chunk: Target chunk size in words (reduced from 250 to 150 for better precision)
            max_words_per_chunk: Maximum chunk size before force-splitting (reduced from 400 to 250)
        """
        self.target_words = target_words_per_chunk
        self.max_words = max_words_per_chunk

    def chunk_book(self, book_text: str, book_metadata: Dict = None) -> List[Dict]:
        """
        Chunk book into semantic segments.

        Args:
            book_text: Full book text (markdown)
            book_metadata: Optional metadata (title, author, chapters)

        Returns:
            List of chunks:
            [
                {
                    'chunk_id': 0,
                    'text': '...',
                    'word_count': 250,
                    'chapter_num': 1,
                    'chapter_title': 'The Horror in Clay',
                    'position_pct': 5.2
                },
                ...
            ]
        """
        # Detect chapter boundaries first
        chapters = self._detect_chapters(book_text)

        # Split into paragraphs (double newline = paragraph break)
        paragraphs = [p.strip() for p in book_text.split('\n\n') if p.strip()]

        chunks = []
        current_chunk = []
        current_word_count = 0
        current_position = 0
        total_chars = len(book_text)

        for para_idx, paragraph in enumerate(paragraphs):
            para_words = len(paragraph.split())

            # Determine current chapter context
            current_chapter = self._get_chapter_at_position(current_position, chapters)

            # Check if paragraph is a chapter header
            is_chapter_header = self._is_chapter_header(paragraph)

            if is_chapter_header and current_chunk:
                # Save current chunk before chapter boundary
                chunks.append(self._create_chunk(
                    chunk_id=len(chunks),
                    text='\n\n'.join(current_chunk),
                    word_count=current_word_count,
                    chapter_context=current_chapter,
                    position=current_position,
                    total_chars=total_chars
                ))
                current_chunk = []
                current_word_count = 0

            # Check if adding this paragraph exceeds limits
            if current_word_count + para_words > self.max_words and current_chunk:
                # Save current chunk
                chunks.append(self._create_chunk(
                    chunk_id=len(chunks),
                    text='\n\n'.join(current_chunk),
                    word_count=current_word_count,
                    chapter_context=current_chapter,
                    position=current_position,
                    total_chars=total_chars
                ))
                current_chunk = []
                current_word_count = 0

            # Add paragraph to current chunk
            current_chunk.append(paragraph)
            current_word_count += para_words
            current_position += len(paragraph) + 2  # +2 for '\n\n'

            # Check if we've reached target size
            if current_word_count >= self.target_words:
                chunks.append(self._create_chunk(
                    chunk_id=len(chunks),
                    text='\n\n'.join(current_chunk),
                    word_count=current_word_count,
                    chapter_context=current_chapter,
                    position=current_position,
                    total_chars=total_chars
                ))
                current_chunk = []
                current_word_count = 0

        # Add remaining chunk
        if current_chunk:
            current_chapter = self._get_chapter_at_position(current_position, chapters)
            chunks.append(self._create_chunk(
                chunk_id=len(chunks),
                text='\n\n'.join(current_chunk),
                word_count=current_word_count,
                chapter_context=current_chapter,
                position=current_position,
                total_chars=total_chars
            ))

        return chunks

    def _detect_chapters(self, text: str) -> List[Dict]:
        """Detect chapter boundaries in text"""
        lines = text.split('\n')
        chapters = []

        patterns = [
            re.compile(r'#{1,3}\s*(CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\.?\s*(.*?)$', re.IGNORECASE),
            re.compile(r'^(\d+)\.\s+(.+?)$'),
            re.compile(r'^([IVXLCDM]+)[\.:\-]\s+(.+?)$'),
        ]

        for i, line in enumerate(lines):
            for pattern in patterns:
                match = pattern.search(line.strip())
                if match:
                    chapters.append({
                        'line': i,
                        'text': line.strip()
                    })
                    break

        return chapters

    def _get_chapter_at_position(self, position: int, chapters: List[Dict]) -> Dict:
        """Find which chapter contains this position"""
        # Simplified: return chapter info or None
        return {'number': None, 'title': None}

    def _is_chapter_header(self, text: str) -> bool:
        """Check if text is a chapter header"""
        patterns = [
            r'#{1,3}\s*(CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)',
            r'^\d+\.\s+[A-Z]',
            r'^[IVXLCDM]+\.\s+[A-Z]',
        ]
        return any(re.match(pattern, text.strip()) for pattern in patterns)

    def _create_chunk(self, chunk_id: int, text: str, word_count: int,
                     chapter_context: Dict, position: int, total_chars: int) -> Dict:
        """Create chunk metadata"""
        return {
            'chunk_id': chunk_id,
            'text': text,
            'word_count': word_count,
            'chapter_num': chapter_context.get('number'),
            'chapter_title': chapter_context.get('title'),
            'position_pct': (position / total_chars * 100) if total_chars > 0 else 0,
            'preview': text[:100] + '...' if len(text) > 100 else text
        }


class VectorStore:
    """
    Simple vector store for semantic search.

    Uses sentence-transformers for embeddings and numpy for similarity.
    """

    def __init__(self, embedding_model: str = 'all-MiniLM-L6-v2'):
        """
        Initialize vector store.

        Args:
            embedding_model: Sentence transformer model name
        """
        self.embedding_model = embedding_model
        self.chunks = []
        self.embeddings = None
        self._model = None

    def _load_model(self):
        """Lazy load embedding model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.embedding_model)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )

    def add_chunks(self, chunks: List[Dict]):
        """
        Add chunks to vector store and compute embeddings.

        Args:
            chunks: List of chunk dicts from SemanticChunker
        """
        self._load_model()

        self.chunks = chunks
        texts = [chunk['text'] for chunk in chunks]

        print(f"Computing embeddings for {len(texts)} chunks...")
        self.embeddings = self._model.encode(texts, show_progress_bar=True)
        print(f"✓ Embeddings computed: {self.embeddings.shape}")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """
        Search for most relevant chunks.

        Args:
            query: User question
            top_k: Number of results to return

        Returns:
            List of (chunk, similarity_score) tuples, sorted by relevance
        """
        if self.embeddings is None:
            raise ValueError("No embeddings loaded. Call add_chunks() first.")

        self._load_model()

        # Encode query
        query_embedding = self._model.encode([query])[0]

        # Compute cosine similarity
        import numpy as np
        from numpy.linalg import norm

        similarities = []
        for i, chunk_embedding in enumerate(self.embeddings):
            similarity = np.dot(query_embedding, chunk_embedding) / (
                norm(query_embedding) * norm(chunk_embedding)
            )
            similarities.append((self.chunks[i], float(similarity)))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def save(self, filepath: Path):
        """Save vector store to disk"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'chunks': self.chunks,
                'embeddings': self.embeddings,
                'embedding_model': self.embedding_model
            }, f)

    @classmethod
    def load(cls, filepath: Path) -> 'VectorStore':
        """Load vector store from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        store = cls(embedding_model=data['embedding_model'])
        store.chunks = data['chunks']
        store.embeddings = data['embeddings']
        return store


def build_vector_store_for_book(book_path: Path, cache_dir: Path = None) -> VectorStore:
    """
    Build vector store for a book (with caching).

    Args:
        book_path: Path to book markdown file
        cache_dir: Directory to cache vector stores

    Returns:
        VectorStore ready for searching
    """
    # Check cache
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(exist_ok=True)

        # Create cache key from book content hash
        with open(book_path, 'rb') as f:
            content_hash = hashlib.md5(f.read()).hexdigest()

        cache_file = cache_dir / f"{book_path.stem}_{content_hash}.pkl"

        if cache_file.exists():
            print(f"Loading cached vector store from {cache_file}")
            return VectorStore.load(cache_file)

    # Build fresh vector store
    print(f"Building vector store for {book_path.name}...")

    with open(book_path, 'r', encoding='utf-8') as f:
        book_text = f.read()

    # Chunk book (using smaller chunks for better precision)
    chunker = SemanticChunker(target_words_per_chunk=150, max_words_per_chunk=250)
    chunks = chunker.chunk_book(book_text)
    print(f"✓ Created {len(chunks)} chunks")

    # Build vector store
    store = VectorStore()
    store.add_chunks(chunks)

    # Cache it
    if cache_dir:
        store.save(cache_file)
        print(f"✓ Cached vector store to {cache_file}")

    return store


# ============================================================================
# Testing
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python semantic_retrieval.py <book.md> [query]")
        sys.exit(1)

    book_path = Path(sys.argv[1])
    query = sys.argv[2] if len(sys.argv) > 2 else "How is the creature described?"

    # Build vector store
    store = build_vector_store_for_book(book_path, cache_dir=Path('.vector_cache'))

    # Test search
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print(f"{'='*80}\n")

    results = store.search(query, top_k=5)

    for i, (chunk, score) in enumerate(results, 1):
        print(f"Result {i} (similarity: {score:.3f})")
        print(f"Position: {chunk['position_pct']:.1f}% through book")
        print(f"Word count: {chunk['word_count']}")
        print(f"Preview: {chunk['preview']}")
        print(f"{'-'*80}\n")
