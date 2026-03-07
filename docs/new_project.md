# Νέο Project — Οδηγίες Reset

## Γρήγορο reset

```bash
source /ai/venv/bin/activate
python /ai/reset.py
```

Διαγράφει `chroma_db/` (1.6GB+) και `output/`, δημιουργεί `pdfs/`, επανεκκινεί τον MCP server.

---

## Βήμα-βήμα

### 1. Reset δεδομένων

```bash
python /ai/reset.py
```

### 2. Βάλε τα νέα PDFs

```bash
cp /path/to/new/*.pdf /ai/pdfs/
```

### 3. Εξαγωγή κειμένου από PDFs

```bash
source /ai/venv/bin/activate
python /ai/chunks_with_sentencesplitter.py
```

Υποστηρίζει checkpoint/resume — αν σταματήσει, τρέξε ξανά από εκεί που έμεινε.

### 4. Δημιουργία embeddings (Voyage AI)

```bash
python /ai/embeddings_with_voyage.py
```

Απαιτεί `VOYAGE_API_KEY` στο `/ai/.env`.

### 5. Φόρτωση στη ChromaDB

```bash
python /ai/vector_database.py
```

### 6. Επανεκκίνηση MCP server

```bash
sudo systemctl restart mcp-rag
sudo journalctl -u mcp-rag -f   # δες ότι φόρτωσε OK
```

### 7. (Προαιρετικό) Test

```bash
# Από Linux — άμεσο test χωρίς Claude Desktop
echo '{"jsonrpc":"2.0","method":"tools/call","id":1,"params":{"name":"list_sources","arguments":{}}}' \
  | python /ai/rag_client.py
```

---

## Χωρίς πλήρες reset — μόνο νέα PDFs

Αν θέλεις να **προσθέσεις** PDFs στο υπάρχον knowledge base:

```bash
cp new.pdf /ai/pdfs/
source /ai/venv/bin/activate
python /ai/chunks_with_sentencesplitter.py   # επεξεργάζεται μόνο τα νέα (checkpoint)
python /ai/embeddings_with_voyage.py
python /ai/vector_database.py
sudo systemctl restart mcp-rag
```

Αν θέλεις να **αφαιρέσεις** ένα PDF:

```bash
python /ai/remove_pdf.py "filename.pdf"
```

---

## Αρχεία δεδομένων

| Path | Περιεχόμενο | Μέγεθος (τυπικά) |
|---|---|---|
| `/ai/pdfs/` | Αρχικά PDF αρχεία | ποικίλλει |
| `/ai/output/chunks.json` | Text chunks από PDFs | ~1GB+ |
| `/ai/output/embedded_chunks.json` | Chunks + vectors | ~1GB+ |
| `/ai/chroma_db/` | ChromaDB vector store | ~1-2GB |
