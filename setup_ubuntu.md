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

### Εκκινηση Ollama
```bash
ollama serve &
```

### Κατεβασμα μοντελου qwen2.5:32b για Ollama
```bash
ollama pull qwen2.5:32b
```

### Δημιουργια φακελου project
```bash
mkdir -p ~/ai
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

### Μεταβαση στον φακελο project
```bash
cd ~/ai
```

### Εγκατασταση ολων των Python packages με requirements.txt
```bash
pip install -r requirements.txt
```

### Αν εμφανιστει error "THESE PACKAGES DO NOT MATCH THE HASHES" (proxy/firewall)
```bash
pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

Για να μην το γραφεις καθε φορα, ρυθμισε το μονιμα:
```bash
pip config set global.trusted-host "pypi.org files.pythonhosted.org"
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
VOYAGE_API_KEY=your_voyage_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
EOF
```

### Δημιουργια φακελου pdfs
```bash
mkdir -p ~/ai/pdfs
```

### Αντιγραφη PDFs (απο USB η δικτυο)
```bash
cp /path/to/usb/a.pdf ~/ai/pdfs/
```

### Αντιγραφη ChromaDB (απο USB η δικτυο)
```bash
cp -r /path/to/usb/chroma_db ~/ai/chroma_db
```

### Εναλλακτικα: αν δεν αντιγραψεις το chroma_db, αναδημιουργησε το
```bash
cd ~/ai
```
```bash
source venv/bin/activate
```
```bash
python pdf_processor.py
```

### Δοκιμη οτι δουλευει
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

## ΜΕΡΟΣ 4: Ρυθμιση MCP Server για Claude Desktop

Ο MCP server επιτρεπει στο Claude Desktop να ψαχνει απευθειας στη βαση γνωσεων (ChromaDB).

### ΠΡΟΣΟΧΗ: Σωστος φακελος config για Claude Desktop (Windows Store version)

Το Claude Desktop (Store) ΔΕΝ διαβαζει απο το κανονικο AppData. Ο σωστος φακελος ειναι:

```
C:\Users\user\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\
```

Αν το package ID διαφερει, ψαξε στο `%LocalAppData%\Packages\` φακελο που αρχιζει με `Claude_`.

### Αντιγραφη του ετοιμου config (απο WSL)

```bash
cp ~/ai/ClaudeWindows/claude_desktop_config.json "/mnt/c/Users/$USER/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json"
```

**Σημαντικο:** Αν υπαρχει ηδη `claude_desktop_config.json` με αλλες ρυθμισεις (`preferences` κλπ),
ΜΗΝ τον αντικαταστησεις ολοκληρο. Ανοιξε τον και προσθεσε μονο το τμημα `"mcpServers"`.

Το config πρεπει να περιεχει:
```json
{
  "mcpServers": {
    "rag-pipeline": {
      "command": "wsl.exe",
      "args": ["-e", "/mnt/e/ai/venv/bin/python", "/mnt/e/ai/mcp_server.py"]
    }
  }
}
```

> Αλλαξε το `/mnt/e/ai` αν το project βρισκεται σε διαφορετικο μερος.

### Δοκιμη MCP server (χωρις Claude Desktop)
```bash
source ~/ai/venv/bin/activate
```
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"protocolVersion":"2025-11-25","clientInfo":{"name":"test","version":"0.1"}}}' | python ~/ai/mcp_server.py
```

Αν επιστρεψει JSON με `"result"` — ο server δουλευει κανονικα.

### Εκκινηση
1. Κανε restart το Claude Desktop
2. Πηγαινε σε `Settings → Developer` και βεβαιωσου οτι το `rag-pipeline` εμφανιζεται **μπλε** με **running**
3. Ανοιξε **νεα συνομιλια**
4. Κλικ στο **`+`** κατω αριστερα → επιλεξε **Connectors**
5. Ρωτα κατι σχετικο με τα PDFs

### Διαθεσιμα tools
| Tool | Τι κανει |
|------|----------|
| `search_documents(query, n_results)` | Σημασιολογικη αναζητηση στα PDFs |
| `list_sources()` | Λιστα με τα διαθεσιμα εγγραφα στη βαση |
