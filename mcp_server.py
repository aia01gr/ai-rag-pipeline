"""
MCP Server for RAG Pipeline
Exposes vector search over PDF knowledge base as tools for Claude Desktop.
"""

import sys
import os
import logging

# Suppress all INFO logging before any imports so that EmbeddingGenerator /
# VectorDatabase init messages don't leak into the stdio transport.
logging.basicConfig(level=logging.WARNING, force=True)

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from embedding_generator import EmbeddingGenerator  # noqa: E402
from vector_database import VectorDatabase  # noqa: E402

# Re-apply after imports (their basicConfig calls may have reset the level)
logging.getLogger().setLevel(logging.WARNING)

# --- initialise shared objects once at import time ---
_embedder = EmbeddingGenerator(provider="voyage", model_name="voyage-4-large")
_db = VectorDatabase(db_path="./chroma_db", collection_name="pdf_documents")

mcp = FastMCP("rag-pipeline")


@mcp.tool()
def search_documents(query: str, n_results: int = 5) -> str:
    """Search the PDF knowledge base using semantic vector search.

    Args:
        query: Natural-language question or search phrase.
        n_results: Number of chunks to return (default 5).

    Returns:
        Matching document chunks with source information.
    """
    results = _db.query_with_text(
        query_text=query,
        embedding_generator=_embedder,
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
        similarity = 1 - dist  # cosine distance → similarity
        parts.append(
            f"--- Result {i} (similarity {similarity:.3f}) ---\n"
            f"Source: {source}  |  Pages: {pages}\n\n"
            f"{doc}"
        )

    return "\n\n".join(parts)


@mcp.tool()
def list_sources() -> str:
    """List all documents available in the knowledge base."""
    collection = _db.client.get_collection(_db.collection_name)
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
    mcp.run(transport="stdio")
