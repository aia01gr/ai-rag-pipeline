#!/usr/bin/env python3
"""
Αφαιρεί όλα τα chunks ενός PDF και από το ChromaDB και από το embedded_chunks.json.
Χρήση: python remove_pdf.py <όνομα_αρχείου.pdf>
"""

import json
import sys
import os

sys.path.insert(0, "/ai")

DB_PATH            = "/ai/chroma_db"
COLLECTION         = "pdf_documents"
EMBEDDED_CHUNKS    = "/ai/output/embedded_chunks.json"


def find_chroma_ids(collection, target):
    ids, metas = [], []
    batch_size = 5000
    offset = 0
    while True:
        batch = collection.get(include=["metadatas"], limit=batch_size, offset=offset)
        if not batch["ids"]:
            break
        ids.extend(batch["ids"])
        metas.extend(batch["metadatas"])
        offset += batch_size

    return [
        id_ for id_, meta in zip(ids, metas)
        if os.path.basename(meta.get("source_file", "")) == target
        or os.path.basename(meta.get("filename", "")) == target
    ]


def main():
    if len(sys.argv) < 2:
        print("Χρήση: python remove_pdf.py <όνομα_αρχείου.pdf>")
        sys.exit(1)

    target = os.path.basename(sys.argv[1])

    # --- ChromaDB ---
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=DB_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    try:
        collection = client.get_collection(COLLECTION)
    except Exception:
        print(f"Σφάλμα: δεν βρέθηκε η collection '{COLLECTION}' στο {DB_PATH}")
        sys.exit(1)

    chroma_total  = collection.count()
    print(f"Αναζήτηση '{target}' ...")
    print(f"  ChromaDB:          {chroma_total} chunks συνολικά")
    chroma_ids = find_chroma_ids(collection, target)
    print(f"  → βρέθηκαν:        {len(chroma_ids)} chunks")

    # --- embedded_chunks.json ---
    chunks_found = 0
    chunks_all   = []
    if os.path.exists(EMBEDDED_CHUNKS):
        with open(EMBEDDED_CHUNKS, "r", encoding="utf-8") as f:
            chunks_all = json.load(f)
        print(f"  embedded_chunks:   {len(chunks_all)} chunks συνολικά")
        chunks_keep  = [c for c in chunks_all if os.path.basename(c.get("source_file", "")) != target]
        chunks_found = len(chunks_all) - len(chunks_keep)
        print(f"  → βρέθηκαν:        {chunks_found} chunks")
    else:
        chunks_keep = []
        print(f"  embedded_chunks:   δεν βρέθηκε το {EMBEDDED_CHUNKS}")

    if not chroma_ids and not chunks_found:
        print(f"\nΔεν βρέθηκαν chunks για '{target}'.")
        print("Διαθέσιμα αρχεία στο ChromaDB:")
        all_data = collection.get(include=["metadatas"], limit=5000)
        sources = sorted({
            os.path.basename(m.get("source_file", "") or m.get("filename", ""))
            for m in all_data["metadatas"] if m.get("source_file") or m.get("filename")
        })
        for s in sources:
            print(f"  - {s}")
        sys.exit(1)

    # --- Επιβεβαίωση ---
    print()
    confirm = input(f"Αφαίρεση {len(chroma_ids)} chunks από ChromaDB και {chunks_found} από embedded_chunks.json; [y/N] ").strip().lower()
    if confirm != "y":
        print("Ακυρώθηκε.")
        sys.exit(0)

    # --- Διαγραφή από ChromaDB ---
    if chroma_ids:
        batch_size = 5000
        for i in range(0, len(chroma_ids), batch_size):
            collection.delete(ids=chroma_ids[i:i + batch_size])
        print(f"  ChromaDB:        αφαιρέθηκαν {len(chroma_ids)} chunks → έμειναν {collection.count()}")

    # --- Διαγραφή από embedded_chunks.json ---
    if chunks_found and os.path.exists(EMBEDDED_CHUNKS):
        with open(EMBEDDED_CHUNKS, "w", encoding="utf-8") as f:
            json.dump(chunks_keep, f, ensure_ascii=False)
        print(f"  embedded_chunks: αφαιρέθηκαν {chunks_found} chunks → έμειναν {len(chunks_keep)}")

    print("\nΈτοιμο.")


if __name__ == "__main__":
    main()
