"""
MCP Server for RAG Pipeline
Exposes vector search over PDF knowledge base as tools for Claude Desktop.
"""

import sys
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING, force=True)

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_DIR)
load_dotenv(dotenv_path=os.path.join(_PROJECT_DIR, ".env"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# Re-apply after FastMCP import resets logging
logging.getLogger().setLevel(logging.WARNING)

mcp = FastMCP("rag-pipeline", host="0.0.0.0", port=8000)

# --- All heavy imports and init happen only on first tool call ---
_embedder = None
_db = None


def _get_resources():
    global _embedder, _db
    if _embedder is None or _db is None:
        from embeddings_with_voyage import EmbeddingGenerator
        from vector_database import VectorDatabase
        _embedder = EmbeddingGenerator(provider="voyage", model_name="voyage-4-large")
        _db = VectorDatabase(
            db_path=os.path.join(_PROJECT_DIR, "chroma_db"),
            collection_name="pdf_documents",
        )
    return _embedder, _db


@mcp.tool()
def search_documents(query: str, n_results: int = 5) -> str:
    """Search the PDF knowledge base using semantic vector search.

    Args:
        query: Natural-language question or search phrase.
        n_results: Number of chunks to return (default 5).

    Returns:
        Matching document chunks with source information.
    """
    embedder, db = _get_resources()
    results = db.query_with_text(
        query_text=query,
        embedding_generator=embedder,
        n_results=n_results,
    )

    if not results["documents"] or not results["documents"][0]:
        return "No results found."

    parts: list[str] = []
    for i, (doc, meta, dist) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ),
        1,
    ):
        source = meta.get("filename") or meta.get("source_file", "unknown")
        pages = meta.get("page_numbers", "")
        similarity = 1 - dist
        parts.append(
            f"--- Result {i} (similarity {similarity:.3f}) ---\n"
            f"Source: {source}  |  Pages: {pages}\n\n"
            f"{doc}"
        )

    return "\n\n".join(parts)


@mcp.tool()
def list_sources() -> str:
    """List all documents available in the knowledge base."""
    _, db = _get_resources()
    collection = db.client.get_collection(db.collection_name)
    all_meta = collection.get(include=["metadatas"])

    sources: dict[str, int] = {}
    for meta in all_meta["metadatas"]:
        name = meta.get("filename") or meta.get("source_file", "unknown")
        sources[name] = sources.get(name, 0) + 1

    if not sources:
        return "No documents in the knowledge base."

    lines = [f"Knowledge base contains {sum(sources.values())} chunks from {len(sources)} document(s):\n"]
    for name, count in sorted(sources.items()):
        lines.append(f"  - {name}  ({count} chunks)")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Initializing embedder and ChromaDB...", flush=True)
    _get_resources()
    print("Ready. Starting MCP server on http://0.0.0.0:8000/sse", flush=True)
    mcp.run(transport="sse")
