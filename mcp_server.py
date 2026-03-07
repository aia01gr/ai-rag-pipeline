"""
MCP Server for RAG Pipeline
Exposes vector search over PDF knowledge base as tools for Claude Desktop.
"""

import sys
import os
import logging
import time
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_DIR)
load_dotenv(dotenv_path=os.path.join(_PROJECT_DIR, ".env"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# Re-apply after FastMCP import resets logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
logging.getLogger().setLevel(logging.INFO)
# Suppress noisy third-party loggers
for _noisy in ("httpx", "httpcore", "chromadb", "opentelemetry"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_logger = logging.getLogger("mcp-server")

mcp = FastMCP("rag-pipeline", host="0.0.0.0", port=8000)

_embedder = None
_db = None


def _get_resources():
    global _embedder, _db
    if _embedder is None or _db is None:
        from embeddings_with_voyage import EmbeddingGenerator
        from vector_database import VectorDatabase
        _logger.info("Loading embedder (voyage-4-large)...")
        _embedder = EmbeddingGenerator(provider="voyage", model_name="voyage-4-large")
        _logger.info("Loading ChromaDB (pdf_documents)...")
        _db = VectorDatabase(
            db_path=os.path.join(_PROJECT_DIR, "chroma_db"),
            collection_name="pdf_documents",
        )
        _logger.info("Resources ready.")
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
    _logger.info(f"search_documents: query={query!r:.80} n_results={n_results}")
    t0 = time.monotonic()

    embedder, db = _get_resources()
    results = db.query_with_text(
        query_text=query,
        embedding_generator=embedder,
        n_results=n_results,
    )

    if not results["documents"] or not results["documents"][0]:
        _logger.info(f"search_documents: no results ({time.monotonic()-t0:.2f}s)")
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

    elapsed = time.monotonic() - t0
    _logger.info(f"search_documents: {len(parts)} results ({elapsed:.2f}s)")
    return "\n\n".join(parts)


@mcp.tool()
def list_sources() -> str:
    """List all documents available in the knowledge base."""
    _logger.info("list_sources: starting")
    t0 = time.monotonic()

    _, db = _get_resources()
    collection = db.client.get_collection(db.collection_name)

    sources: dict[str, int] = {}
    batch_size = 5000
    offset = 0

    while True:
        batch = collection.get(include=["metadatas"], limit=batch_size, offset=offset)
        if not batch["metadatas"]:
            break
        for meta in batch["metadatas"]:
            name = meta.get("filename") or meta.get("source_file", "unknown")
            sources[name] = sources.get(name, 0) + 1
        if len(batch["metadatas"]) < batch_size:
            break
        offset += batch_size

    elapsed = time.monotonic() - t0

    if not sources:
        _logger.info(f"list_sources: empty ({elapsed:.2f}s)")
        return "No documents in the knowledge base."

    _logger.info(f"list_sources: {len(sources)} docs, {sum(sources.values())} chunks ({elapsed:.2f}s)")
    lines = [f"Knowledge base contains {sum(sources.values())} chunks from {len(sources)} document(s):\n"]
    for name, count in sorted(sources.items()):
        lines.append(f"  - {name}  ({count} chunks)")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Initializing embedder and ChromaDB...", flush=True)
    _get_resources()
    print("Ready. Starting MCP server on http://0.0.0.0:8000/mcp", flush=True)
    mcp.run(transport="streamable-http")
