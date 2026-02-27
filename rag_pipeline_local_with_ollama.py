"""
Complete RAG Pipeline with Ollama (local LLM) Integration
"""

import os
import json
import requests
from typing import List, Dict, Optional
import logging
from dotenv import load_dotenv

load_dotenv()

from embeddings_with_voyage import EmbeddingGenerator
from vector_database import VectorDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Complete RAG pipeline integrating embeddings, vector DB, and Ollama
    """

    def __init__(
        self,
        vector_db_path: str = "./chroma_db",
        collection_name: str = "pdf_documents",
        embedding_provider: str = "voyage",
        embedding_model: str = "voyage-4-large",
        ollama_model: str = "qwen2.5:32b",
        ollama_url: str = "http://localhost:11434"
    ):
        # Initialize components
        self.vector_db = VectorDatabase(
            db_path=vector_db_path,
            collection_name=collection_name
        )

        self.embedding_generator = EmbeddingGenerator(
            provider=embedding_provider,
            model_name=embedding_model
        )

        self.ollama_model = ollama_model
        self.ollama_url = ollama_url

        logger.info(f"RAG Pipeline initialized with Ollama model: {ollama_model}")

    def retrieve(
        self,
        query: str,
        n_results: int = 10,
        metadata_filter: Optional[Dict] = None,
        use_hybrid_search: bool = False
    ) -> List[Dict]:
        logger.info(f"Retrieving context for query: {query}")

        query_embedding = self.embedding_generator.embed_query(query)

        if use_hybrid_search:
            results = self.vector_db.hybrid_search(
                query_embedding=query_embedding,
                query_text=query,
                n_results=n_results
            )
            retrieved_chunks = results['results']
        else:
            results = self.vector_db.query(
                query_embedding=query_embedding,
                n_results=n_results,
                where=metadata_filter
            )

            retrieved_chunks = []
            for i in range(len(results['ids'][0])):
                retrieved_chunks.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i]
                })

        logger.info(f"Retrieved {len(retrieved_chunks)} relevant chunks")
        return retrieved_chunks

    def format_context(self, chunks: List[Dict]) -> str:
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get('metadata', {})
            source = metadata.get('filename', 'Unknown')
            pages = metadata.get('page_numbers', '')

            context_part = f"""[Source {i}: {source}, Pages {pages}]
{chunk['document']}
"""
            context_parts.append(context_part)

        return "\n\n".join(context_parts)

    def _query_ollama(self, prompt: str, system: str, temperature: float = 0.7) -> str:
        """Query Ollama API"""
        response = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.ollama_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            },
            timeout=600
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def query(
        self,
        question: str,
        n_results: int = 10,
        metadata_filter: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        return_sources: bool = True
    ) -> Dict:
        # Retrieve relevant chunks
        chunks = self.retrieve(
            query=question,
            n_results=n_results,
            metadata_filter=metadata_filter
        )

        context = self.format_context(chunks)

        if system_prompt is None:
            system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.

Instructions:
- Answer the question using ONLY the information from the provided context
- If the context doesn't contain enough information to answer, say so
- Cite sources by referencing [Source N] when using information
- Be precise and accurate
- If the answer requires information from multiple sources, synthesize them coherently"""

        user_message = f"""Context:
{context}

Question: {question}

Please answer the question based on the context provided above."""

        logger.info(f"Querying Ollama ({self.ollama_model})...")
        answer = self._query_ollama(user_message, system_prompt, temperature)

        result = {
            'answer': answer,
            'question': question,
            'model': self.ollama_model
        }

        if return_sources:
            result['sources'] = [
                {
                    'source': chunk['metadata'].get('filename', 'Unknown'),
                    'pages': chunk['metadata'].get('page_numbers', ''),
                    'text': chunk['document'][:200] + '...'
                }
                for chunk in chunks
            ]

        logger.info("Generated answer")
        return result

    def conversational_query(
        self,
        question: str,
        conversation_history: List[Dict],
        n_results: int = 10
    ) -> Dict:
        chunks = self.retrieve(query=question, n_results=n_results)
        context = self.format_context(chunks)

        messages = conversation_history.copy()
        messages.append({
            "role": "user",
            "content": f"""Context:
{context}

Question: {question}"""
        })

        response = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.ollama_model,
                "messages": messages,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        answer = response.json()["message"]["content"]

        messages.append({
            "role": "assistant",
            "content": answer
        })

        return {
            'answer': answer,
            'conversation_history': messages,
            'sources': chunks
        }

    def batch_query(
        self,
        questions: List[str],
        n_results: int = 10,
        save_results: bool = True,
        output_file: str = "rag_results.json"
    ) -> List[Dict]:
        results = []

        for i, question in enumerate(questions, 1):
            logger.info(f"Processing question {i}/{len(questions)}")

            try:
                result = self.query(question, n_results=n_results)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing question: {e}")
                results.append({
                    'question': question,
                    'error': str(e)
                })

        if save_results:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {output_file}")

        return results


def interactive_mode(pipeline: RAGPipeline):
    """Interactive Q&A mode"""
    print("\n" + "="*70)
    print("RAG INTERACTIVE MODE")
    print("="*70)
    print("Ask questions about your documents. Type 'quit' to exit.\n")

    while True:
        question = input("\nYour question: ").strip()

        if question.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            result = pipeline.query(question, n_results=5)

            print("\n" + "-"*70)
            print("ANSWER:")
            print("-"*70)
            print(result['answer'])

            print("\n" + "-"*70)
            print(f"SOURCES ({len(result['sources'])} documents):")
            print("-"*70)
            for i, source in enumerate(result['sources'][:3], 1):
                print(f"{i}. {source['source']} (Pages {source['pages']})")

        except Exception as e:
            print(f"\nError: {e}")


def main():
    """Example usage"""
    pipeline = RAGPipeline(
        vector_db_path="./chroma_db",
        embedding_provider="voyage",
        embedding_model="voyage-4-large",
        ollama_model="qwen2.5:32b"
    )

    # Single query example
    result = pipeline.query(
        question="What is machine learning?",
        n_results=3
    )

    print("\nQuestion:", result['question'])
    print("\nAnswer:", result['answer'])
    print(f"\nSources: {len(result['sources'])} documents")

    # Interactive mode
    # interactive_mode(pipeline)


if __name__ == '__main__':
    main()
