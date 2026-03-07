#!/usr/bin/env python3
"""
Αφαιρεί όλα τα chunks ενός PDF από το embedded_chunks.json.
Χρήση: python remove_pdf_chunks.py <όνομα_αρχείου.pdf>
"""

import json
import sys
import os

EMBEDDED_CHUNKS = "/ai/output/embedded_chunks.json"


def main():
    if len(sys.argv) < 2:
        print("Χρήση: python remove_pdf_chunks.py <όνομα_αρχείου.pdf>")
        sys.exit(1)

    target = sys.argv[1]

    if not os.path.exists(EMBEDDED_CHUNKS):
        print(f"Σφάλμα: δεν βρέθηκε το {EMBEDDED_CHUNKS}")
        sys.exit(1)

    print(f"Φόρτωση {EMBEDDED_CHUNKS} ...")
    with open(EMBEDDED_CHUNKS, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    before = len(chunks)

    # Αντιστοιχία με basename ή full path
    filtered = [
        c for c in chunks
        if os.path.basename(c.get("source_file", "")) != os.path.basename(target)
    ]

    removed = before - len(filtered)

    if removed == 0:
        print(f"Δεν βρέθηκαν chunks για: {target}")
        print("Διαθέσιμα αρχεία:")
        sources = sorted({os.path.basename(c.get("source_file", "")) for c in chunks})
        for s in sources:
            print(f"  - {s}")
        sys.exit(1)

    print(f"Βρέθηκαν {removed} chunks για '{os.path.basename(target)}'")

    confirm = input(f"Αφαίρεση {removed} chunks από {before} συνολικά; [y/N] ").strip().lower()
    if confirm != "y":
        print("Ακυρώθηκε.")
        sys.exit(0)

    print("Αποθήκευση ...")
    with open(EMBEDDED_CHUNKS, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False)

    print(f"Έτοιμο. Έμειναν {len(filtered)} chunks ({removed} αφαιρέθηκαν).")


if __name__ == "__main__":
    main()
