# RAG Pipeline - Ubuntu 24 Setup Guide

## ΜΕΡΟΣ 1: Εντολες εγκαταστασης (τρεξε τις μια-μια)

### Ενημερωση συστηματος
```bash
sudo apt update && sudo apt upgrade -y
```

### Εγκατασταση Python 3.12 και pip
```bash
sudo apt install python3 python3-pip python3-venv -y
```

### Εγκατασταση git
```bash
sudo apt install git -y
```

### Ρυθμιση git identity
```bash
git config --global user.email "ai@a01.gr"
```

### Ρυθμιση git name
```bash
git config --global user.name "ai"
```

### Εγκατασταση GitHub CLI (gh) - βημα 1
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
```

### Εγκατασταση GitHub CLI (gh) - βημα 2
```bash
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
```

### Εγκατασταση GitHub CLI (gh) - βημα 3
```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
```

### Εγκατασταση GitHub CLI (gh) - βημα 4
```bash
sudo apt update && sudo apt install gh -y
```

### Login στο GitHub
```bash
gh auth login
```

### Εγκατασταση Node.js 20 (απαιτειται για Claude Code)
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs -y
```

### Εγκατασταση Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

### Εγκατασταση Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Κατεβασμα μοντελου qwen2.5:3b για Ollama
```bash
ollama pull qwen2.5:3b
```

### Δημιουργια φακελου project
```bash
mkdir -p ~/ai && cd ~/ai
```

### Clone του repo απο GitHub
```bash
git clone https://github.com/aia01gr/ai-rag-pipeline.git ~/ai
```

### Δημιουργια Python virtual environment
```bash
python3 -m venv ~/ai/venv
```

### Ενεργοποιηση venv
```bash
source ~/ai/venv/bin/activate
```

### Εγκατασταση βασικων Python libraries - PDF processing
```bash
pip install pdfplumber pypdf
```

### Εγκατασταση LlamaIndex core (SentenceSplitter)
```bash
pip install llama-index-core
```

### Εγκατασταση embedding dependencies
```bash
pip install numpy requests python-dotenv
```

### Εγκατασταση ChromaDB
```bash
pip install chromadb
```

### Εγκατασταση Voyage AI client
```bash
pip install voyageai
```

### Εγκατασταση Anthropic SDK
```bash
pip install anthropic
```

### Εγκατασταση sentence-transformers (backup embeddings)
```bash
pip install sentence-transformers
```

### Εγκατασταση progress bar
```bash
pip install tqdm
```

### Εγκατασταση spaCy (advanced chunking)
```bash
pip install spacy
```

### Εγκατασταση βοηθητικων libraries
```bash
pip install scikit-learn pdf2image pytesseract openai
```

### Εγκατασταση MCP SDK (για Claude Desktop integration)
```bash
pip install mcp
```

### Εναλλακτικα: ολα μαζι με requirements.txt
```bash
cd ~/ai && source venv/bin/activate && pip install -r requirements.txt
```

---

## ΜΕΡΟΣ 2: Αρχεια που πρεπει να παρεις απο το υπαρχον συστημα

| Αρχειο | Τι ειναι |
|--------|----------|
| `.env` | API keys (Voyage, Anthropic) |
| `pdfs/a.pdf` | Το PDF για RAG |
| `chroma_db/` (φακελος) | Η βαση δεδομενων με τα embeddings |

Τα `.py` αρχεια θα ερθουν αυτοματα απο το `git clone`. Τα παραπανω 3 ειναι στο `.gitignore` και δεν υπαρχουν στο repo.

---

## ΜΕΡΟΣ 3: Πως να τα βαλεις

### Δημιουργια .env με τα API keys
```bash
cat > ~/ai/.env << 'EOF'
VOYAGE_API_KEY=pa-1VoHtRuRJN6eeF8HT7i4VEAEf8MUp25VIgNeXu0YNSg
ANTHROPIC_API_KEY=SII69RONeza8IrwhhH58axgyuj5LP2Wa150rUOkK23vJjz1B#p2EKLvGdStUdnS2KcofybOD1Y-BEpjG_efP7Xif5OjM
EOF
```

### Αντιγραφη PDFs (απο USB η δικτυο)
```bash
mkdir -p ~/ai/pdfs
cp /path/to/usb/a.pdf ~/ai/pdfs/
```

### Αντιγραφη ChromaDB (απο USB η δικτυο)
```bash
cp -r /path/to/usb/chroma_db ~/ai/chroma_db
```

### Εναλλακτικα: αν δεν αντιγραψεις το chroma_db, αναδημιουργησε το
```bash
cd ~/ai && source venv/bin/activate && python pdf_processor.py
```

### Δοκιμη οτι δουλευει
```bash
cd ~/ai && source venv/bin/activate && python rag_pipeline.py
```

---

## ΜΕΡΟΣ 4: Ρυθμιση MCP Server για Claude Desktop

Ο MCP server επιτρεπει στο Claude Desktop να ψαχνει απευθειας στη βαση γνωσεων (ChromaDB).

### Δημιουργια config για Claude Desktop (Windows)

Αν τρεχεις μεσω WSL:
```bash
mkdir -p /mnt/c/Users/$USER/AppData/Roaming/Claude
cat > /mnt/c/Users/$USER/AppData/Roaming/Claude/claude_desktop_config.json << 'EOF'
{
  "mcpServers": {
    "rag-pipeline": {
      "command": "wsl.exe",
      "args": ["-e", "/home/$USER/ai/venv/bin/python", "/home/$USER/ai/mcp_server.py"],
      "cwd": "/home/$USER/ai"
    }
  }
}
EOF
```

**Σημαντικο:** Αλλαξε τα paths στο JSON ωστε να δειχνουν στο σωστο μερος (π.χ. `/home/user/ai` ή `/mnt/e/ai`).

Αν τρεχεις native Linux με Claude Desktop:
```bash
mkdir -p ~/.config/Claude
cat > ~/.config/Claude/claude_desktop_config.json << 'EOF'
{
  "mcpServers": {
    "rag-pipeline": {
      "command": "/home/$USER/ai/venv/bin/python",
      "args": ["/home/$USER/ai/mcp_server.py"],
      "cwd": "/home/$USER/ai"
    }
  }
}
EOF
```

### Δοκιμη MCP server (χωρις Claude Desktop)
```bash
cd ~/ai && source venv/bin/activate
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"0.1"}}}' | python mcp_server.py
```

### Εκκινηση
1. Κανε restart το Claude Desktop
2. Θα δεις ενα εικονιδιο σφυρι (hammer) στο chat — κλικ για να δεις τα tools
3. Ρωτα κατι σχετικο με τα PDFs και θα καλεσει αυτοματα το `search_documents`

### Διαθεσιμα tools
| Tool | Τι κανει |
|------|----------|
| `search_documents(query, n_results)` | Σημασιολογικη αναζητηση στα PDFs |
| `list_sources()` | Λιστα με τα διαθεσιμα εγγραφα στη βαση |
