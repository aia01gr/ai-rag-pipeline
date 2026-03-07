"""
Ελέγχει αν όλα τα chunks από chunks.json και chunks300.json
υπάρχουν στο chunks_from_chroma.json.
Αυτά που λείπουν αποθηκεύονται στο chunksnotexist.json.
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHROMA_FILE  = "/ai/output/chunks_from_chroma.json"
CHUNKS_FILE  = "/ai/output/chunks.json"
CHUNKS300    = "/ai/output/chunks300.json"
OUTPUT_FILE  = "/ai/output/chunksnotexist.json"


def load_chunks(path):
    p = Path(path)
    if not p.exists():
        logger.warning(f"Δεν βρέθηκε: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    logger.info("Φόρτωση chunks_from_chroma.json...")
    chroma_chunks = load_chunks(CHROMA_FILE)
    chroma_ids = {c["chunk_id"] for c in chroma_chunks}
    logger.info(f"  → {len(chroma_ids):,} chunks στη ChromaDB")

    logger.info("Φόρτωση chunks.json...")
    chunks = load_chunks(CHUNKS_FILE)
    logger.info(f"  → {len(chunks):,} chunks")

    logger.info("Φόρτωση chunks300.json...")
    chunks300 = load_chunks(CHUNKS300)
    logger.info(f"  → {len(chunks300):,} chunks")

    # Όλα τα source chunks μαζί (χωρίς duplicates βάσει chunk_id)
    all_source: dict = {}
    for c in chunks300:
        all_source[c["chunk_id"]] = c
    for c in chunks:
        all_source[c["chunk_id"]] = c

    logger.info(f"Σύνολο unique chunks προς έλεγχο: {len(all_source):,}")

    # Βρες αυτά που λείπουν από ChromaDB
    missing = [c for cid, c in all_source.items() if cid not in chroma_ids]

    logger.info(f"Missing από ChromaDB: {len(missing):,}")

    if missing:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(missing, f, indent=2, ensure_ascii=False)
        logger.info(f"Αποθηκεύτηκαν στο {OUTPUT_FILE}")

        # Στατιστικά ανά source file
        by_source: dict = {}
        for c in missing:
            src = c.get("metadata", {}).get("filename") or c.get("source_file", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        logger.info(f"Unique αρχεία με missing chunks: {len(by_source)}")
        for src, count in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {count:>5} chunks  ←  {src}")
    else:
        logger.info("Όλα τα chunks υπάρχουν στη ChromaDB. ✓")


if __name__ == "__main__":
    main()
