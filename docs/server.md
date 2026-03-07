# RAG Pipeline + MCP Server — Οδηγός Εγκατάστασης (Ubuntu 24.04)

Πλήρης οδηγός για φρέσκο server από το μηδέν.

---

## ΜΕΡΟΣ Α — Πριν το pip install

### 1. Ενημέρωση συστήματος

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Python 3.12, pip, venv

```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev
```

### 3. Βιβλιοθήκες συστήματος (απαιτούνται από Python packages)

```bash
sudo apt install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-ell \
    git
```

> - `poppler-utils` → απαιτείται από `pdf2image`
> - `tesseract-ocr` → απαιτείται από `pytesseract`
> - `tesseract-ocr-ell` → ελληνικά γράμματα για OCR (προαιρετικό)

### 4. Clone του repo από GitHub

```bash
git clone https://github.com/aia01gr/ai-rag-pipeline.git /ai
```

### 5. Δημιουργία Python virtual environment

```bash
python3 -m venv /ai/venv
```

### 6. Ενεργοποίηση venv και αναβάθμιση pip

```bash
source /ai/venv/bin/activate
pip install --upgrade pip
```

---

## ΜΕΡΟΣ Β — pip install

```bash
pip install --no-cache-dir -r /ai/requirements.txt
```

> Διαρκεί 5-15 λεπτά. Κατεβάζει και PyTorch (μεγάλο package για sentence-transformers).

---

## ΜΕΡΟΣ Γ — Μετά το pip install

### 1. Δημιουργία φακέλων

```bash
mkdir -p /ai/pdfs /ai/output /ai/chroma_db
```

### 2. Δημιουργία αρχείου .env με τα API keys

```bash
cat > /ai/.env << 'EOF'
VOYAGE_API_KEY=your_voyage_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
EOF
```

> Αντικατέστησε τις τιμές με τα πραγματικά API keys.

### 3. Τοποθέτηση PDFs

**Επιλογή Α — Αντιγραφή από άλλον server (μέσω scp):**
```bash
scp user@old-server:/ai/pdfs/*.pdf /ai/pdfs/
```

**Επιλογή Β — Αντιγραφή ChromaDB από άλλον server (αποφυγή επανεπεξεργασίας):**
```bash
scp -r user@old-server:/ai/chroma_db /ai/chroma_db
```

**Επιλογή Γ — Επεξεργασία PDFs από την αρχή (αν δεν υπάρχει chroma_db):**
```bash
source /ai/venv/bin/activate

# Εξαγωγή κειμένου (δύο επιλογές):
python /ai/chunks_with_sentencesplitter.py   # γρήγορο, lightweight
# ή
python /ai/chunks_with_Docling.py            # structure-aware, table detection

# Δημιουργία embeddings (Voyage AI):
python /ai/embeddings_with_voyage.py

# Φόρτωση στη ChromaDB:
python /ai/vector_database.py
```

Ή χρησιμοποίησε τον interactive wizard:
```bash
python /ai/01_main_program.py
```

### 4. Έλεγχος ότι το σύστημα λειτουργεί

```bash
source /ai/venv/bin/activate
python /ai/rag_pipeline_local_with_ollama.py
```

### 5. Ρύθμιση Firewall (ufw)

Άνοιξε port 8000 **μόνο για τη συγκεκριμένη IP** του PC-client:

```bash
sudo ufw allow from <IP_ΤΟΥ_PC> to any port 8000 proto tcp
sudo ufw status
```

> Για να μάθεις την public IP του PC: άνοιξε browser και πήγαινε στο https://ifconfig.me

### 6. Εκκίνηση MCP Server

```bash
source /ai/venv/bin/activate
python /ai/mcp_server.py
```

Επιτυχής εκκίνηση:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Ο server ακούει στο: `http://<SERVER_IP>:8000/mcp`

---

## ΜΕΡΟΣ Δ — Αυτόματη εκκίνηση με systemd (προαιρετικό)

Για να ξεκινάει ο MCP server αυτόματα μετά από reboot:

```bash
sudo tee /etc/systemd/system/mcp-rag.service << 'EOF'
[Unit]
Description=RAG Pipeline MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/ai
ExecStart=/ai/venv/bin/python /ai/mcp_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-rag
sudo systemctl start mcp-rag
sudo systemctl status mcp-rag
```

---

## Γρήγορος έλεγχος

```bash
# Ο server τρέχει;
curl -s --max-time 3 http://localhost:8000/sse && echo "OK" || echo "Server offline"

# Firewall rules
sudo ufw status

# Logs systemd (αν χρησιμοποιείς systemd)
journalctl -u mcp-rag -f
```

---

## Σύνοψη αρχείων

| Αρχείο / Φάκελος | Περιγραφή |
|------------------|-----------|
| `/ai/.env` | API keys (ΔΕΝ ανεβαίνει στο git) |
| `/ai/pdfs/` | Τα PDF αρχεία |
| `/ai/output/chunks.json` | Text chunks (μετά το PDF processing) |
| `/ai/output/embedded_chunks.json` | Chunks + embeddings vectors |
| `/ai/chroma_db/` | Vector database (ChromaDB) |
| `/ai/venv/` | Python virtual environment |
| `/ai/mcp_server.py` | MCP server (SSE, port 8000) |
| `/ai/chunks_with_sentencesplitter.py` | PDF → chunks (γρήγορο, pdfplumber+OCR) |
| `/ai/chunks_with_Docling.py` | PDF → chunks (structure-aware, table detection) |
| `/ai/embeddings_with_voyage.py` | Chunks → embeddings (Voyage AI) |
| `/ai/vector_database.py` | Διαχείριση ChromaDB |
| `/ai/rag_pipeline_local_with_ollama.py` | Q&A pipeline με Ollama |
| `/ai/01_main_program.py` | Setup wizard (interactive) |
| `/ai/remove_pdf.py` | Αφαίρεση PDF από ChromaDB + JSON |
| `/ai/export_from_chroma.py` | Εξαγωγή δεδομένων από ChromaDB |
| `/ai/reset.py` | Full reset (διαγραφή chroma_db + output) |

