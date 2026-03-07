"""
ClearDatabase.py — Διαγραφή δεδομένων από ChromaDB
Διαγράφει την collection pdf_documents και όλα τα chunks.
"""

import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings

CHROMA_PATH     = "/ai/chroma_db"
COLLECTION_NAME = "pdf_documents"


def get_client():
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )


def show_stats(client):
    collections = client.list_collections()
    if not collections:
        print("  (κανένα collection)")
        return
    for c in collections:
        col = client.get_collection(c.name)
        print(f"  {c.name}: {col.count():,} chunks")


def main():
    print("=" * 60)
    print("  ChromaDB Clear Tool")
    print(f"  Path: {CHROMA_PATH}")
    print("=" * 60)

    client = get_client()

    print("\nΤρέχουσα κατάσταση:")
    show_stats(client)

    collections = client.list_collections()
    if not collections:
        print("\nΗ database είναι ήδη άδεια. Τίποτα να διαγραφεί.")
        sys.exit(0)

    # Find target collection
    names = [c.name for c in collections]
    if COLLECTION_NAME not in names:
        print(f"\n⚠  Collection '{COLLECTION_NAME}' δεν βρέθηκε.")
        print(f"  Διαθέσιμα: {names}")
        sys.exit(1)

    col = client.get_collection(COLLECTION_NAME)
    total = col.count()

    print(f"\n⚠  ΠΡΟΣΟΧΗ: θα διαγραφούν {total:,} chunks από '{COLLECTION_NAME}'.")
    confirm = input("  Συνέχεια; (yes/no): ").strip().lower()

    if confirm != "yes":
        print("Ακυρώθηκε.")
        sys.exit(0)

    print(f"\nΔιαγραφή collection '{COLLECTION_NAME}'...")
    client.delete_collection(COLLECTION_NAME)

    # Re-create empty collection με ίδιο distance metric
    client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"✓ Collection '{COLLECTION_NAME}' καθαρίστηκε (0 chunks).")
    print("\nΤρέχουσα κατάσταση:")
    show_stats(client)


if __name__ == "__main__":
    main()
