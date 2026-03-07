#!/usr/bin/env python3
"""
Reset the RAG pipeline for a new project.

Διαγράφει:
  - chroma_db/       (vector database)
  - output/          (chunks + embeddings)

Δημιουργεί:
  - pdfs/            (άδειος φάκελος για τα νέα PDFs)

Ο MCP server επανεκκινείται αυτόματα (systemd).
"""

import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

DIRS_TO_DELETE = [
    os.path.join(PROJECT_DIR, "chroma_db"),
    os.path.join(PROJECT_DIR, "output"),
]

DIRS_TO_CREATE = [
    os.path.join(PROJECT_DIR, "pdfs"),
    os.path.join(PROJECT_DIR, "output"),
]


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer == "y"


def human_size(path: str) -> str:
    total = 0
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    elif os.path.isfile(path):
        total = os.path.getsize(path)
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.0f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def main():
    print("=" * 50)
    print("  RAG Pipeline — Full Reset")
    print("=" * 50)
    print()
    print("Τα παρακάτω θα διαγραφούν:")
    for d in DIRS_TO_DELETE:
        if os.path.exists(d):
            size = human_size(d)
            print(f"  ✗  {d}  ({size})")
        else:
            print(f"  -  {d}  (δεν υπάρχει)")
    print()

    if not confirm("Συνέχεια;"):
        print("Ακύρωση.")
        sys.exit(0)

    print()

    # Delete
    for d in DIRS_TO_DELETE:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  Διαγράφηκε: {d}")

    # Create fresh dirs
    for d in DIRS_TO_CREATE:
        os.makedirs(d, exist_ok=True)
        print(f"  Δημιουργήθηκε: {d}")

    # Restart MCP server so it doesn't hold stale state
    print()
    print("Επανεκκίνηση MCP server...")
    result = subprocess.run(
        ["systemctl", "restart", "mcp-rag"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  MCP server επανεκκινήθηκε.")
    else:
        print(f"  Προσοχή: systemctl restart απέτυχε: {result.stderr.strip()}")
        print("  Τρέξε χειροκίνητα: sudo systemctl restart mcp-rag")

    print()
    print("=" * 50)
    print("  Reset ολοκληρώθηκε!")
    print("=" * 50)
    print()
    print("Επόμενα βήματα:")
    print("  1. Βάλε τα νέα PDFs στο:  /ai/pdfs/")
    print("  2. source /ai/venv/bin/activate")
    print("  3. python /ai/chunks_with_sentencesplitter.py")
    print("  4. python /ai/embeddings_with_voyage.py")
    print("  5. python /ai/vector_database.py")
    print("  6. sudo systemctl restart mcp-rag")
    print()


if __name__ == "__main__":
    main()
