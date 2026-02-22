"""
Embedding Generation for RAG Pipeline
Supports multiple embedding providers: OpenAI, Voyage AI, and Local Models
"""

import json
import os
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict
import logging
from tqdm import tqdm
import time
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class EmbeddedChunk:
    """Chunk with its embedding vector"""
    chunk_id: str
    text: str
    embedding: List[float]
    source_file: str
    page_numbers: List[int]
    metadata: Dict

    def to_dict(self):
        data = asdict(self)
        # Convert numpy array to list if needed
        if isinstance(data['embedding'], np.ndarray):
            data['embedding'] = data['embedding'].tolist()
        return data


class EmbeddingGenerator:
    """
    Generate embeddings using various providers
    """

    def __init__(
        self,
        provider: str = 'voyage',
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        batch_size: int = 32
    ):
        """
        Initialize embedding generator

        Args:
            provider: 'openai', 'voyage', or 'sentence-transformers'
            model_name: Specific model to use
            api_key: API key for commercial providers
            batch_size: Number of texts to embed at once
        """
        self.provider = provider.lower()
        self.batch_size = batch_size
        self.api_key = api_key or os.getenv('VOYAGE_API_KEY') or os.getenv('OPENAI_API_KEY')

        # Initialize the appropriate embedding model
        if self.provider == 'openai':
            self._init_openai(model_name or 'text-embedding-3-large')
        elif self.provider == 'voyage':
            self._init_voyage(model_name or 'voyage-4-large')
        else:  # sentence-transformers (local)
            self._init_local(model_name or 'all-MiniLM-L6-v2')

        logger.info(f"Initialized {self.provider} embeddings with model: {self.model_name}")

    def _init_openai(self, model_name: str):
        """Initialize OpenAI embeddings"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            self.model_name = model_name
            self.embedding_dim = 3072 if '3-large' in model_name else 1536
        except ImportError:
            raise ImportError("Install OpenAI: pip install openai")

    def _init_voyage(self, model_name: str):
        """Initialize Voyage AI embeddings"""
        import requests as _requests
        self._voyage_session = _requests.Session()
        self._voyage_session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
        self._voyage_url = 'https://api.voyageai.com/v1/embeddings'
        self.model_name = model_name
        dim_map = {
            'voyage-4-large': 1024,
            'voyage-4': 1024,
            'voyage-4-lite': 512,
            'voyage-3-large': 1024,
            'voyage-3.5': 1024,
            'voyage-3.5-lite': 512,
        }
        self.embedding_dim = dim_map.get(model_name, 1024)

    def _init_local(self, model_name: str):
        """Initialize local sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if self.provider == 'openai':
            return self._embed_openai(texts)
        elif self.provider == 'voyage':
            return self._embed_voyage(texts)
        else:
            return self._embed_local(texts)

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI"""
        embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model_name
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)

        return embeddings

    def _embed_voyage(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        """Generate embeddings using Voyage AI REST API with retry on rate limit"""
        embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            payload = {
                'model': self.model_name,
                'input': batch,
                'input_type': input_type
            }

            for attempt in range(5):
                response = self._voyage_session.post(self._voyage_url, json=payload, timeout=60)
                if response.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/5)")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                batch_embeddings = [item['embedding'] for item in data['data']]
                embeddings.extend(batch_embeddings)
                break
            else:
                raise Exception(f"Rate limited after 5 retries for batch starting at index {i}")

        return embeddings

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers"""
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query text

        Args:
            query: Query string

        Returns:
            Embedding vector
        """
        if self.provider == 'voyage':
            # Voyage AI has different input types for queries vs documents
            return self._embed_voyage([query], input_type="query")[0]
        else:
            return self.embed_texts([query])[0]

    def process_chunks_file(
        self,
        chunks_file: str,
        output_file: str,
        resume: bool = True
    ) -> None:
        """
        Process chunks JSON file and add embeddings

        Args:
            chunks_file: Path to chunks.json from pdf_processor
            output_file: Path to save embedded chunks
            resume: Resume from checkpoint if True
        """
        # Load chunks
        logger.info(f"Loading chunks from {chunks_file}")
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        logger.info(f"Loaded {len(chunks)} chunks")

        # Check for checkpoint
        checkpoint_file = f"{output_file}.checkpoint"
        processed_ids = set()
        embedded_chunks = []

        if resume and os.path.exists(checkpoint_file):
            logger.info("Loading checkpoint...")
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                processed_ids = set(checkpoint['processed_ids'])
                logger.info(f"Resuming: {len(processed_ids)} chunks already processed")

            # Load existing embeddings
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    embedded_chunks = json.load(f)

        # Filter unprocessed chunks
        unprocessed_chunks = [c for c in chunks if c['chunk_id'] not in processed_ids]
        logger.info(f"Processing {len(unprocessed_chunks)} remaining chunks")

        # Process in batches
        batch_texts = []
        batch_chunks = []

        for chunk in tqdm(unprocessed_chunks, desc="Generating embeddings"):
            batch_texts.append(chunk['text'])
            batch_chunks.append(chunk)

            # Process batch when full
            if len(batch_texts) >= self.batch_size:
                self._process_batch(
                    batch_texts,
                    batch_chunks,
                    embedded_chunks,
                    processed_ids,
                    output_file,
                    checkpoint_file
                )
                batch_texts = []
                batch_chunks = []

        # Process remaining batch
        if batch_texts:
            self._process_batch(
                batch_texts,
                batch_chunks,
                embedded_chunks,
                processed_ids,
                output_file,
                checkpoint_file
            )

        # Final save
        self._save_embeddings(output_file, embedded_chunks)
        logger.info(f"Complete! Generated embeddings for {len(embedded_chunks)} chunks")

        # Clean up checkpoint
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)

    def _process_batch(
        self,
        batch_texts: List[str],
        batch_chunks: List[Dict],
        embedded_chunks: List[Dict],
        processed_ids: set,
        output_file: str,
        checkpoint_file: str
    ):
        """Process a batch of chunks"""
        # Generate embeddings
        embeddings = self.embed_texts(batch_texts)

        # Create embedded chunk objects
        for chunk, embedding in zip(batch_chunks, embeddings):
            embedded_chunk = EmbeddedChunk(
                chunk_id=chunk['chunk_id'],
                text=chunk['text'],
                embedding=embedding,
                source_file=chunk['source_file'],
                page_numbers=chunk['page_numbers'],
                metadata=chunk['metadata']
            )
            embedded_chunks.append(embedded_chunk.to_dict())
            processed_ids.add(chunk['chunk_id'])

        # Save checkpoint every batch
        self._save_checkpoint(checkpoint_file, processed_ids)
        self._save_embeddings(output_file, embedded_chunks)

    def _save_checkpoint(self, checkpoint_file: str, processed_ids: set):
        """Save checkpoint"""
        with open(checkpoint_file, 'w') as f:
            json.dump({'processed_ids': list(processed_ids)}, f)

    def _save_embeddings(self, output_file: str, embedded_chunks: List[Dict]):
        """Save embeddings to file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embedded_chunks, f, indent=2, ensure_ascii=False)


# Model recommendations
EMBEDDING_MODELS = {
    'openai': {
        'text-embedding-3-large': {
            'dim': 3072,
            'cost_per_1M': 0.13,
            'description': 'Best quality, higher cost'
        },
        'text-embedding-3-small': {
            'dim': 1536,
            'cost_per_1M': 0.02,
            'description': 'Good quality, lower cost'
        }
    },
    'voyage': {
        'voyage-4-large': {
            'dim': 1024,
            'cost_per_1M': 0.18,
            'description': 'Best quality for search/RAG'
        },
        'voyage-4': {
            'dim': 1024,
            'cost_per_1M': 0.10,
            'description': 'Balanced quality/cost'
        },
        'voyage-4-lite': {
            'dim': 512,
            'cost_per_1M': 0.02,
            'description': 'Fast and lightweight'
        }
    },
    'sentence-transformers': {
        'all-MiniLM-L6-v2': {
            'dim': 384,
            'cost_per_1M': 0.0,
            'description': 'Fast, lightweight, FREE'
        },
        'all-mpnet-base-v2': {
            'dim': 768,
            'cost_per_1M': 0.0,
            'description': 'Better quality, FREE'
        },
        'BAAI/bge-large-en-v1.5': {
            'dim': 1024,
            'cost_per_1M': 0.0,
            'description': 'SOTA quality, FREE'
        }
    }
}


def print_model_recommendations():
    """Print embedding model options"""
    print("\n" + "="*70)
    print("EMBEDDING MODEL RECOMMENDATIONS")
    print("="*70)

    for provider, models in EMBEDDING_MODELS.items():
        print(f"\n{provider.upper()}:")
        for model_name, info in models.items():
            print(f"  • {model_name}")
            print(f"    - Dimensions: {info['dim']}")
            print(f"    - Cost per 1M tokens: ${info['cost_per_1M']}")
            print(f"    - {info['description']}")


def main():
    """Example usage"""
    print_model_recommendations()

    # Using Voyage AI voyage-4-large (API key from .env)
    generator = EmbeddingGenerator(
        provider='voyage',
        model_name='voyage-4-large',
        batch_size=32
    )

    # Process chunks file
    generator.process_chunks_file(
        chunks_file='./chunks.json',
        output_file='./embedded_chunks.json',
        resume=True
    )


if __name__ == '__main__':
    main()
