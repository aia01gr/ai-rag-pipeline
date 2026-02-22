"""
Advanced Chunking Strategies for RAG Pipeline
Includes sentence-based, token-based, and recursive chunking
"""

import re
from typing import List, Dict
from dataclasses import dataclass
import tiktoken  # For accurate token counting


@dataclass
class ChunkStats:
    """Statistics about chunking results"""
    total_chunks: int
    avg_chunk_size: int
    min_chunk_size: int
    max_chunk_size: int
    avg_tokens: int
    total_tokens: int


class AdvancedChunker:
    """
    Advanced chunking strategies for optimal RAG performance
    """

    def __init__(self, model_name: str = "cl100k_base"):
        """
        Initialize with tokenizer for accurate token counting

        Args:
            model_name: Tokenizer model (cl100k_base for GPT-4/Claude)
        """
        try:
            self.tokenizer = tiktoken.get_encoding(model_name)
        except:
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Rough estimate: 1 token ≈ 4 characters
            return len(text) // 4

    def chunk_by_sentences(
        self,
        text: str,
        max_tokens: int = 512,
        overlap_sentences: int = 1
    ) -> List[str]:
        """
        Chunk by sentences - preserves sentence boundaries
        Better for question answering tasks

        Args:
            text: Input text
            max_tokens: Maximum tokens per chunk
            overlap_sentences: Number of sentences to overlap

        Returns:
            List of text chunks
        """
        # Split into sentences (basic regex - can use spaCy for better accuracy)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # If single sentence exceeds max_tokens, split it
            if sentence_tokens > max_tokens:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                # Split long sentence by characters
                chunks.extend(self._split_long_text(sentence, max_tokens))
                continue

            # If adding sentence exceeds limit, save current chunk
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunks.append(' '.join(current_chunk))

                # Keep overlap sentences
                if overlap_sentences > 0:
                    current_chunk = current_chunk[-overlap_sentences:]
                    current_tokens = sum(self.count_tokens(s) for s in current_chunk)
                else:
                    current_chunk = []
                    current_tokens = 0

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def chunk_by_tokens(
        self,
        text: str,
        chunk_size: int = 512,
        overlap_tokens: int = 50
    ) -> List[str]:
        """
        Chunk by exact token count
        Most accurate for API token limits

        Args:
            text: Input text
            chunk_size: Target tokens per chunk
            overlap_tokens: Overlapping tokens between chunks

        Returns:
            List of text chunks
        """
        if not self.tokenizer:
            raise ValueError("Tokenizer not available. Install tiktoken.")

        # Encode entire text
        tokens = self.tokenizer.encode(text)

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            # Extract chunk
            end_idx = start_idx + chunk_size
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

            # Move start position (with overlap)
            start_idx = end_idx - overlap_tokens

        return chunks

    def chunk_recursive(
        self,
        text: str,
        chunk_size: int = 1000,
        separators: List[str] = None
    ) -> List[str]:
        """
        Recursive chunking - tries to split by hierarchy of separators
        Best for preserving document structure

        Args:
            text: Input text
            chunk_size: Target size in characters
            separators: List of separators in priority order

        Returns:
            List of text chunks
        """
        if separators is None:
            separators = [
                "\n\n\n",  # Section breaks
                "\n\n",    # Paragraph breaks
                "\n",      # Line breaks
                ". ",      # Sentences
                " ",       # Words
                ""         # Characters
            ]

        return self._recursive_split(text, chunk_size, separators)

    def _recursive_split(
        self,
        text: str,
        chunk_size: int,
        separators: List[str]
    ) -> List[str]:
        """Helper for recursive splitting"""
        chunks = []

        # Base case: text is small enough
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        # Try each separator
        for separator in separators:
            if separator in text:
                splits = text.split(separator)

                current_chunk = ""
                for split in splits:
                    # Add separator back except for last split
                    test_chunk = current_chunk + separator + split if current_chunk else split

                    if len(test_chunk) <= chunk_size:
                        current_chunk = test_chunk
                    else:
                        # Current chunk is full
                        if current_chunk:
                            chunks.append(current_chunk)

                        # If split itself is too large, recursively split it
                        if len(split) > chunk_size:
                            remaining_separators = separators[separators.index(separator) + 1:]
                            chunks.extend(
                                self._recursive_split(split, chunk_size, remaining_separators)
                            )
                            current_chunk = ""
                        else:
                            current_chunk = split

                if current_chunk:
                    chunks.append(current_chunk)

                return chunks

        # No separators worked, split by chunk_size
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    def _split_long_text(self, text: str, max_tokens: int) -> List[str]:
        """Split text that exceeds max_tokens"""
        max_chars = max_tokens * 4  # Rough estimate
        return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

    def chunk_by_semantic_similarity(
        self,
        text: str,
        max_chunk_size: int = 1000,
        similarity_threshold: float = 0.5
    ) -> List[str]:
        """
        Advanced: Chunk based on semantic similarity between sentences
        Groups semantically similar sentences together

        Requires: sentence-transformers library

        Args:
            text: Input text
            max_chunk_size: Maximum chunk size in characters
            similarity_threshold: Similarity threshold for grouping

        Returns:
            List of text chunks
        """
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
        except ImportError:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers scikit-learn")

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if not sentences:
            return []

        # Generate embeddings
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(sentences)

        # Group sentences by similarity
        chunks = []
        current_chunk = [sentences[0]]
        current_embedding = embeddings[0:1]

        for i in range(1, len(sentences)):
            # Calculate similarity with current chunk
            similarity = cosine_similarity(
                current_embedding.mean(axis=0).reshape(1, -1),
                embeddings[i].reshape(1, -1)
            )[0][0]

            # Check if we should add to current chunk
            chunk_text = ' '.join(current_chunk + [sentences[i]])

            if similarity >= similarity_threshold and len(chunk_text) <= max_chunk_size:
                current_chunk.append(sentences[i])
                current_embedding = np.vstack([current_embedding, embeddings[i:i+1]])
            else:
                # Start new chunk
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentences[i]]
                current_embedding = embeddings[i:i+1]

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def calculate_stats(self, chunks: List[str]) -> ChunkStats:
        """Calculate statistics for chunk quality assessment"""
        chunk_sizes = [len(chunk) for chunk in chunks]
        chunk_tokens = [self.count_tokens(chunk) for chunk in chunks]

        return ChunkStats(
            total_chunks=len(chunks),
            avg_chunk_size=sum(chunk_sizes) // len(chunks) if chunks else 0,
            min_chunk_size=min(chunk_sizes) if chunks else 0,
            max_chunk_size=max(chunk_sizes) if chunks else 0,
            avg_tokens=sum(chunk_tokens) // len(chunks) if chunks else 0,
            total_tokens=sum(chunk_tokens)
        )


def compare_chunking_strategies(text: str):
    """
    Compare different chunking strategies on sample text
    """
    chunker = AdvancedChunker()

    strategies = {
        'Fixed Size': lambda: [text[i:i+1000] for i in range(0, len(text), 800)],
        'Sentences': lambda: chunker.chunk_by_sentences(text, max_tokens=512),
        'Recursive': lambda: chunker.chunk_recursive(text, chunk_size=1000),
        'Tokens': lambda: chunker.chunk_by_tokens(text, chunk_size=512, overlap_tokens=50),
    }

    print("Chunking Strategy Comparison\n" + "="*50)

    for name, strategy in strategies.items():
        try:
            chunks = strategy()
            stats = chunker.calculate_stats(chunks)

            print(f"\n{name}:")
            print(f"  Total chunks: {stats.total_chunks}")
            print(f"  Avg size: {stats.avg_chunk_size} chars ({stats.avg_tokens} tokens)")
            print(f"  Range: {stats.min_chunk_size} - {stats.max_chunk_size} chars")
            print(f"  Total tokens: {stats.total_tokens}")
        except Exception as e:
            print(f"\n{name}: Error - {e}")


if __name__ == '__main__':
    # Example usage
    sample_text = """
    Artificial intelligence is transforming the way we work. Machine learning models
    can now perform tasks that once required human intelligence. Natural language
    processing enables computers to understand and generate human language.

    Deep learning, a subset of machine learning, uses neural networks with multiple
    layers. These networks can learn hierarchical representations of data. This has
    led to breakthroughs in computer vision, speech recognition, and language understanding.

    The future of AI looks promising. Researchers are working on making models more
    efficient and interpretable. There's also a growing focus on AI safety and ethics.
    """ * 10  # Repeat to make longer text

    compare_chunking_strategies(sample_text)
