#!/usr/bin/env python3
"""
Αφαιρεί όλα τα chunks ενός PDF από το ChromaDB.
Χρήση: python remove_pdf_chroma.py <όνομα_αρχείου.pdf>
"""

import sys
import os

sys.path.insert(0, "/ai")

DB_PATH       = "/ai/chroma_db"
COLLECTION    = "pdf_documents"


def main():
    if len(sys.argv) < 2:
        print("Χρήση: python remove_pdf_chroma.py <όνομα_αρχείου.pdf>")
        sys.exit(1)

    target = os.path.basename(sys.argv[1])

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

    total_before = collection.count()
    print(f"Σύνολο chunks στο ChromaDB: {total_before}")
    print(f"Αναζήτηση chunks για: {target} ...")

    # Φέρνουμε τα metadata σε batches (ChromaDB limit με μεγάλες collections)
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

    matching_ids = [
        id_ for id_, meta in zip(ids, metas)
        if os.path.basename(meta.get("source_file", "")) == target
        or os.path.basename(meta.get("filename", "")) == target
    ]

    if not matching_ids:
        print(f"Δεν βρέθηκαν chunks για: {target}")
        print("\nΔιαθέσιμα αρχεία στο ChromaDB:")
        sources = sorted({
            os.path.basename(m.get("source_file", "") or m.get("filename", ""))
            for m in metas if m.get("source_file") or m.get("filename")
        })
        for s in sources:
            print(f"  - {s}")
        sys.exit(1)

    print(f"Βρέθηκαν {len(matching_ids)} chunks για '{target}'")

    confirm = input(f"Αφαίρεση {len(matching_ids)} chunks από {total_before} συνολικά; [y/N] ").strip().lower()
    if confirm != "y":
        print("Ακυρώθηκε.")
        sys.exit(0)

    # Διαγραφή σε batches (ChromaDB limit)
    batch_size = 5000
    for i in range(0, len(matching_ids), batch_size):
        collection.delete(ids=matching_ids[i:i + batch_size])

    remaining = collection.count()
    removed   = total_before - remaining
    print(f"Έτοιμο. Έμειναν {remaining} chunks ({removed} αφαιρέθηκαν).")


if __name__ == "__main__":
    main()
