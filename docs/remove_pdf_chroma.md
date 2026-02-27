# remove_pdf_chroma.py — Αφαίρεση PDF από το ChromaDB

Αφαιρεί όλα τα chunks ενός PDF αρχείου από το ChromaDB (`chroma_db/`).

## Χρήση

```bash
source /ai/venv/bin/activate
python /ai/remove_pdf_chroma.py "<όνομα_αρχείου.pdf>"
```

Αρκεί το όνομα του αρχείου — δεν χρειάζεται το πλήρες path.

## Παράδειγμα

```bash
python /ai/remove_pdf_chroma.py "Report 2022 Startups in Greece.pdf"
```

```
Σύνολο chunks στο ChromaDB: 58061
Αναζήτηση chunks για: Report 2022 Startups in Greece.pdf ...
Βρέθηκαν 143 chunks για 'Report 2022 Startups in Greece.pdf'
Αφαίρεση 143 chunks από 58061 συνολικά; [y/N] y
Έτοιμο. Έμειναν 57918 chunks (143 αφαιρέθηκαν).
```

## Αν το αρχείο δεν βρεθεί

```
Δεν βρέθηκαν chunks για: wrong_name.pdf

Διαθέσιμα αρχεία στο ChromaDB:
  - Report 2022 Startups in Greece.pdf
  - Cource 2020 Curriculum for Second Year of Artificial Intelligence and Data Science.pdf
  - ...
```

## Σημειώσεις

- Τροποποιεί **μόνο** το ChromaDB — δεν αγγίζει το `output/embedded_chunks.json`.
- Για πλήρη αφαίρεση ενός PDF χρησιμοποίησε και τα δύο scripts:

```bash
python /ai/remove_pdf_chroma.py  "αρχείο.pdf"   # αφαίρεση από ChromaDB
python /ai/remove_pdf_chunks.py  "αρχείο.pdf"   # αφαίρεση από embedded_chunks.json
```

- Το αρχικό PDF δεν διαγράφεται από τον φάκελο `pdfs/`.
- Μετά την αφαίρεση δεν χρειάζεται restart του MCP server.
