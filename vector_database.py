"""
Vector Database Setup and Management
Uses ChromaDB for local storage
"""

import json
import os
from typing import List, Dict, Optional, Tuple
import logging
from tqdm import tqdm
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VectorDatabase:
    """
    Local vector database using ChromaDB
    """

    def __init__(
        self,
        db_path: str = "./chroma_db",
        collection_name: str = "pdf_documents"
    ):
        """
        Initialize vector database

        Args:
            db_path: Path to store the database
            collection_name: Name of the collection
        """
        self.db_path = db_path
        self.collection_name = collection_name

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        logger.info(f"Initialized ChromaDB at {db_path}")

    def create_collection(
        self,
        reset: bool = False,
        distance_metric: str = "cosine"
    ) -> chromadb.Collection:
        """
        Create or get collection

        Args:
            reset: Delete existing collection if True
            distance_metric: 'cosine', 'l2', or 'ip' (inner product)

        Returns:
            ChromaDB collection
        """
        if reset:
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted existing collection: {self.collection_name}")
            except:
                pass

        collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": distance_metric}
        )

        logger.info(f"Collection '{self.collection_name}' ready (metric: {distance_metric})")
        return collection

    def load_embeddings(
        self,
        embedded_chunks_file: str,
        batch_size: int = 1000,
        reset: bool = False
    ) -> int:
        """
        Load embeddings into vector database

        Args:
            embedded_chunks_file: Path to embedded_chunks.json
            batch_size: Number of embeddings to add at once
            reset: Reset collection before loading

        Returns:
            Number of chunks loaded
        """
        # Load embedded chunks
        logger.info(f"Loading embeddings from {embedded_chunks_file}")
        with open(embedded_chunks_file, 'r', encoding='utf-8') as f:
            embedded_chunks = json.load(f)

        logger.info(f"Loaded {len(embedded_chunks)} embedded chunks")

        # Deduplicate by chunk_id (keep last occurrence)
        seen = {}
        for chunk in embedded_chunks:
            seen[chunk['chunk_id']] = chunk
        if len(seen) < len(embedded_chunks):
            logger.warning(f"Removed {len(embedded_chunks) - len(seen)} duplicate chunk IDs")
        embedded_chunks = list(seen.values())

        # Create collection
        collection = self.create_collection(reset=reset)

        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in tqdm(embedded_chunks, desc="Preparing data"):
            ids.append(chunk['chunk_id'])
            embeddings.append(chunk['embedding'])
            documents.append(chunk['text'])

            # Flatten metadata for ChromaDB
            metadata = {
                'source_file': chunk['source_file'],
                'page_numbers': str(chunk['page_numbers']),  # Convert list to string
                'filename': chunk['metadata'].get('filename', ''),
                'title': chunk['metadata'].get('title', ''),
                'author': chunk['metadata'].get('author', ''),
            }
            metadatas.append(metadata)

        # Add to collection in batches
        logger.info("Adding embeddings to database...")
        for i in tqdm(range(0, len(ids), batch_size), desc="Uploading batches"):
            end_idx = min(i + batch_size, len(ids))

            collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

        logger.info(f"Successfully loaded {len(ids)} chunks into database")
        return len(ids)

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict:
        """
        Query the vector database

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Metadata filters (e.g., {'source_file': 'doc.pdf'})
            where_document: Document content filters

        Returns:
            Query results
        """
        collection = self.client.get_collection(self.collection_name)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document
        )

        return results

    def query_with_text(
        self,
        query_text: str,
        embedding_generator,
        n_results: int = 10,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Query using text (will generate embedding)

        Args:
            query_text: Query string
            embedding_generator: EmbeddingGenerator instance
            n_results: Number of results to return
            where: Metadata filters

        Returns:
            Query results
        """
        # Generate query embedding
        query_embedding = embedding_generator.embed_query(query_text)

        # Query database
        return self.query(query_embedding, n_results, where)

    def get_collection_stats(self) -> Dict:
        """Get statistics about the collection"""
        try:
            collection = self.client.get_collection(self.collection_name)
            count = collection.count()

            return {
                'collection_name': self.collection_name,
                'total_chunks': count,
                'db_path': self.db_path
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def delete_by_source(self, source_file: str) -> int:
        """
        Delete all chunks from a specific source file

        Args:
            source_file: Path to source file

        Returns:
            Number of chunks deleted
        """
        collection = self.client.get_collection(self.collection_name)

        # Get chunks from this source
        results = collection.get(
            where={'source_file': source_file}
        )

        if results['ids']:
            collection.delete(ids=results['ids'])
            logger.info(f"Deleted {len(results['ids'])} chunks from {source_file}")
            return len(results['ids'])

        return 0

    def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        n_results: int = 10,
        keyword_weight: float = 0.3
    ) -> Dict:
        """
        Hybrid search combining vector similarity and keyword matching

        Args:
            query_embedding: Query embedding
            query_text: Query text for keyword matching
            n_results: Number of results
            keyword_weight: Weight for keyword matching (0-1)

        Returns:
            Combined results
        """
        collection = self.client.get_collection(self.collection_name)

        # Vector search
        vector_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results * 2  # Get more for reranking
        )

        # Keyword search using where_document
        # Extract important keywords from query
        keywords = query_text.lower().split()

        # Simple keyword scoring (can be improved with BM25)
        scored_results = []
        for i, doc in enumerate(vector_results['documents'][0]):
            doc_lower = doc.lower()

            # Vector similarity score (distance)
            vector_score = 1 - vector_results['distances'][0][i]

            # Keyword score
            keyword_score = sum(1 for kw in keywords if kw in doc_lower) / len(keywords)

            # Combined score
            combined_score = (
                (1 - keyword_weight) * vector_score +
                keyword_weight * keyword_score
            )

            scored_results.append({
                'id': vector_results['ids'][0][i],
                'document': doc,
                'metadata': vector_results['metadatas'][0][i],
                'score': combined_score,
                'vector_score': vector_score,
                'keyword_score': keyword_score
            })

        # Sort by combined score
        scored_results.sort(key=lambda x: x['score'], reverse=True)

        return {
            'results': scored_results[:n_results],
            'total_found': len(scored_results)
        }


def main():
    """Example usage"""
    # Initialize database
    db = VectorDatabase(
        db_path="./chroma_db",
        collection_name="pdf_documents"
    )

    # Load embeddings
    num_loaded = db.load_embeddings(
        embedded_chunks_file='./embedded_chunks.json',
        batch_size=1000,
        reset=False  # Set True to start fresh
    )

    # Get stats
    stats = db.get_collection_stats()
    print(f"\nDatabase Stats:")
    print(f"  Collection: {stats['collection_name']}")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Location: {stats['db_path']}")

    # Example query (requires embedding generator)
    # from embedding_generator import EmbeddingGenerator
    # generator = EmbeddingGenerator(provider='sentence-transformers')
    # results = db.query_with_text(
    #     query_text="What is machine learning?",
    #     embedding_generator=generator,
    #     n_results=5
    # )


if __name__ == '__main__':
    main()