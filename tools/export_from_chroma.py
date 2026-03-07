"""
Export ChromaDB → chunks.json and/or embedded_chunks.json

Χρήση:
    python export_from_chroma.py                          # και τα δύο
    python export_from_chroma.py --chunks-only            # μόνο chunks.json (text, no vectors)
    python export_from_chroma.py --embedded-only          # μόνο embedded_chunks.json
    python export_from_chroma.py --out-dir /path/to/dir  # custom output dir
"""

import argparse
import json
import ast
import logging
from pathlib import Path

import chromadb
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHROMA_PATH      = "/ai/chroma_db"
COLLECTION_NAME  = "pdf_documents"
BATCH_SIZE       = 2000  # πόσα records ανά get() call


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    return collection


def export(chunks_out: str | None, embedded_out: str | None) -> None:
    collection = get_collection()
    total = collection.count()
    logger.info(f"Total records in ChromaDB: {total:,}")

    chunks_list   = []  # για chunks.json
    embedded_list = []  # για embedded_chunks.json

    need_embeddings = embedded_out is not None

    for offset in tqdm(range(0, total, BATCH_SIZE), desc="Exporting from ChromaDB"):
        result = collection.get(
            offset=offset,
            limit=BATCH_SIZE,
            include=["documents", "metadatas"] + (["embeddings"] if need_embeddings else []),
        )

        ids        = result["ids"]
        documents  = result["documents"]
        metadatas  = result["metadatas"]
        embeddings = result.get("embeddings", [None] * len(ids))

        for i, chunk_id in enumerate(ids):
            meta = metadatas[i]

            # page_numbers αποθηκεύτηκε ως string "[1, 2]" — το μετατρέπουμε πίσω
            raw_pages = meta.get("page_numbers", "[]")
            try:
                page_numbers = ast.literal_eval(raw_pages)
            except Exception:
                page_numbers = []

            if chunks_out:
                chunks_list.append({
                    "chunk_id":    chunk_id,
                    "text":        documents[i],
                    "source_file": meta.get("source_file", ""),
                    "page_numbers": page_numbers,
                    "chunk_index": -1,   # δεν αποθηκεύεται στη ChromaDB
                    "total_chunks": -1,
                    "char_count":  len(documents[i]),
                    "metadata": {
                        "filename": meta.get("filename", ""),
                        "title":    meta.get("title", ""),
                        "author":   meta.get("author", ""),
                        "source_file": meta.get("source_file", ""),
                    },
                })

            if embedded_out:
                embedded_list.append({
                    "chunk_id":    chunk_id,
                    "text":        documents[i],
                    "source_file": meta.get("source_file", ""),
                    "page_numbers": page_numbers,
                    "chunk_index": -1,
                    "total_chunks": -1,
                    "char_count":  len(documents[i]),
                    "metadata": {
                        "filename": meta.get("filename", ""),
                        "title":    meta.get("title", ""),
                        "author":   meta.get("author", ""),
                        "source_file": meta.get("source_file", ""),
                    },
                    "embedding": embeddings[i],
                })

    if chunks_out:
        Path(chunks_out).parent.mkdir(parents=True, exist_ok=True)
        with open(chunks_out, "w", encoding="utf-8") as f:
            json.dump(chunks_list, f, indent=2, ensure_ascii=False)
        logger.info(f"chunks.json  → {chunks_out}  ({len(chunks_list):,} chunks)")

    if embedded_out:
        Path(embedded_out).parent.mkdir(parents=True, exist_ok=True)
        with open(embedded_out, "w", encoding="utf-8") as f:
            json.dump(embedded_list, f, indent=2, ensure_ascii=False)
        logger.info(f"embedded_chunks.json → {embedded_out}  ({len(embedded_list):,} chunks)")

    # Στατιστικά ανά αρχείο
    source_counts: dict = {}
    for item in (chunks_list or embedded_list):
        src = item["metadata"].get("filename") or item["source_file"]
        source_counts[src] = source_counts.get(src, 0) + 1
    logger.info(f"Unique source files: {len(source_counts):,}")


def main():
    parser = argparse.ArgumentParser(description="Export ChromaDB to JSON files")
    parser.add_argument("--chunks-only",   action="store_true", help="Export only chunks.json (no vectors)")
    parser.add_argument("--embedded-only", action="store_true", help="Export only embedded_chunks.json (with vectors)")
    parser.add_argument("--out-dir",       default="/ai/output", help="Output directory (default: /ai/output)")
    args = parser.parse_args()

    out_dir = args.out_dir

    if args.chunks_only:
        chunks_out   = f"{out_dir}/chunks_from_chroma.json"
        embedded_out = None
    elif args.embedded_only:
        chunks_out   = None
        embedded_out = f"{out_dir}/embedded_from_chroma.json"
    else:
        chunks_out   = f"{out_dir}/chunks_from_chroma.json"
        embedded_out = f"{out_dir}/embedded_from_chroma.json"

    export(chunks_out, embedded_out)


if __name__ == "__main__":
    main()
