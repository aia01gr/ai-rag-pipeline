# remove_pdf_chunks.py — Αφαίρεση PDF από το embedded_chunks.json

Αφαιρεί όλα τα chunks ενός PDF αρχείου από το `output/embedded_chunks.json`.

## Χρήση

```bash
source /ai/venv/bin/activate
python /ai/remove_pdf_chunks.py "<όνομα_αρχείου.pdf>"
```

Αρκεί το όνομα του αρχείου — δεν χρειάζεται το πλήρες path.

## Παράδειγμα

```bash
python /ai/remove_pdf_chunks.py "Report 2022 Startups in Greece.pdf"
```

```
Φόρτωση /ai/output/embedded_chunks.json ...
Βρέθηκαν 143 chunks για 'Report 2022 Startups in Greece.pdf'
Αφαίρεση 143 chunks από 58852 συνολικά; [y/N] y
Αποθήκευση ...
Έτοιμο. Έμειναν 58709 chunks (143 αφαιρέθηκαν).
```

## Τι κάνει

1. Φορτώνει το `output/embedded_chunks.json`
2. Εντοπίζει όλα τα chunks που ανήκουν στο αρχείο
3. Ζητά επιβεβαίωση πριν διαγράψει
4. Αποθηκεύει το αρχείο χωρίς τα αφαιρεθέντα chunks

## Αν το αρχείο δεν βρεθεί

Το script εμφανίζει λίστα με τα διαθέσιμα αρχεία:

```
Δεν βρέθηκαν chunks για: wrong_name.pdf
Διαθέσιμα αρχεία:
  - Report 2022 Startups in Greece.pdf
  - Cource 2020 Curriculum for Second Year of Artificial Intelligence and Data Science.pdf
  - ...
```

## Σημειώσεις

- Το script τροποποιεί **μόνο** το `embedded_chunks.json` — δεν αγγίζει το ChromaDB (`chroma_db/`).
- Για να αφαιρεθεί το PDF και από το ChromaDB, χρησιμοποίησε το `vector_database.py`.
- Το αρχικό PDF δεν διαγράφεται από τον φάκελο `pdfs/`.
