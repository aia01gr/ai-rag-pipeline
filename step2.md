# Step 2 — Εντολες μετα το pip install -r requirements.txt

Τρεξε τις παρακατω εντολες με τη σειρα.

---

## 1. Εγκατασταση Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 2. Εκκινηση Ollama και κατεβασμα μοντελου

```bash
ollama serve &
```
```bash
ollama pull qwen2.5:3b
```

Για αυτοματη εκκινηση με το συστημα:
```bash
sudo systemctl enable ollama
```
```bash
sudo systemctl start ollama
```

---

## 3. Δημιουργια .env με τα API keys

```bash
cat > ~/ai/.env << 'EOF'
VOYAGE_API_KEY=your_voyage_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
EOF
```

---

## 4. Αντιγραφη PDFs

```bash
mkdir -p ~/ai/pdfs
```
```bash
cp /path/to/a.pdf ~/ai/pdfs/
```

---

## 5. ChromaDB

### Αν εχεις backup:
```bash
cp -r /path/to/chroma_db ~/ai/chroma_db
```

### Αν δεν εχεις backup — αναδημιουργια απο τα PDFs:
```bash
cd ~/ai
```
```bash
source venv/bin/activate
```
```bash
python pdf_processor.py
```

---

## 6. Δοκιμη RAG pipeline

```bash
cd ~/ai
```
```bash
source venv/bin/activate
```
```bash
python rag_pipeline.py
```

---

## 7. Δοκιμη MCP server

```bash
source ~/ai/venv/bin/activate
```
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"protocolVersion":"2025-11-25","clientInfo":{"name":"test","version":"0.1"}}}' | python ~/ai/mcp_server.py
```

Αν επιστρεψει JSON με `"result"` — ο server ειναι ετοιμος.

---

## 8. Config για Claude Desktop (μονο αν τρεχεις μεσω WSL)

```bash
cp ~/ai/ClaudeWindows/claude_desktop_config.json "/mnt/c/Users/$USER/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json"
```

Μετα κανε restart το Claude Desktop και ελεγξε `Settings → Developer` οτι το `rag-pipeline` εμφανιζεται **running**.

---

## Αντιμετωπιση προβληματων

| Σφαλμα | Αιτια | Λυση |
|--------|-------|------|
| `Connection refused port 11434` | Ollama δεν τρεχει | `ollama serve &` |
| `ollama: command not found` | Ollama δεν εχει εγκατασταθει | Βημα 1 παραπανω |
| `VOYAGE_API_KEY not found` | Δεν υπαρχει το .env | Βημα 3 παραπανω |
| `chroma_db not found` | Δεν υπαρχει η βαση | Βημα 5 παραπανω |
| Hash mismatch στο pip | Proxy/firewall | `pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
