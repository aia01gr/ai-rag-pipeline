# Ρύθμιση Claude Desktop με RAG Pipeline (από την αρχή)

---

## Βήμα 1 — Εγκατάσταση Claude Desktop

1. Κατέβασε το Claude Desktop από το Microsoft Store ή από το anthropic.com
2. Εγκατέστησέ το κανονικά και άνοιξέ το μια φορά για να δημιουργηθούν οι φάκελοι
3. Κλείσε το Claude Desktop

---

## Βήμα 2 — Βρες τον σωστό φάκελο config

Το Claude Desktop (Store version) ΔΕΝ διαβάζει από το κανονικό AppData.
Ο σωστός φάκελος είναι:

```
C:\Users\user\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\
```

> **Προσοχή:** Το `Claude_pzs8sxrjxfjjc` είναι το package ID. Αν διαφέρει στο σύστημά σου,
> άνοιξε το File Explorer, πήγαινε στο `%LocalAppData%\Packages\` και ψάξε φάκελο που αρχίζει με `Claude_`.

---

## Βήμα 3 — Αντίγραφο του config αρχείου

### Από WSL (προτεινόμενο):
```bash
cp /mnt/e/ai/ClaudeWindows/claude_desktop_config.json \
   "/mnt/c/Users/user/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json"
```

### Από Windows File Explorer:
1. Άνοιξε το αρχείο `ClaudeWindows\claude_desktop_config.json` από αυτόν τον φάκελο
2. Αντίγραψέ το στο:
   `C:\Users\user\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\`

> **Προσοχή:** Αν υπάρχει ήδη `claude_desktop_config.json` στον προορισμό,
> ΜΗΝ τον διαγράψεις — άνοιξέ τον και πρόσθεσε μόνο το τμήμα `"mcpServers"` μέσα στο υπάρχον JSON.

---

## Βήμα 4 — Έλεγχος του config αρχείου

Άνοιξε το `claude_desktop_config.json` που αντέγραψες και βεβαιώσου ότι περιέχει:

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

Αν υπάρχουν και άλλες ρυθμίσεις (π.χ. `preferences`), κράτα τες — απλώς πρόσθεσε το `mcpServers`.

---

## Βήμα 5 — Βεβαιώσου ότι το WSL και το venv είναι έτοιμα

Από WSL, τρέξε:

```bash
# Έλεγχος ότι το venv υπάρχει
ls /mnt/e/ai/venv/bin/python

# Έλεγχος ότι το .env υπάρχει με τα API keys
cat /mnt/e/ai/.env

# Έλεγχος ότι το ChromaDB υπάρχει
ls /mnt/e/ai/chroma_db/
```

Αν κάτι λείπει, δες το `setup_ubuntu.md` για οδηγίες εγκατάστασης.

---

## Βήμα 5β — Εγκατάσταση Python packages

### Κανονική εγκατάσταση:
```bash
cd /mnt/e/ai && source venv/bin/activate
pip install -r requirements.txt
```

### Αν εμφανιστεί error "THESE PACKAGES DO NOT MATCH THE HASHES":
Ο server έχει proxy/firewall που κάνει SSL inspection. Χρησιμοποίησε:
```bash
pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

Για να μην το γράφεις κάθε φορά, ρύθμισέ το μόνιμα:
```bash
pip config set global.trusted-host "pypi.org files.pythonhosted.org"
```

---

## Βήμα 6 — Εκκίνηση Claude Desktop

1. Άνοιξε το Claude Desktop
2. Πήγαινε σε `Settings → Developer`
3. Βεβαιώσου ότι το `rag-pipeline` εμφανίζεται με **μπλε χρώμα** και γράφει **running**
4. Αν γράφει error, δες το Βήμα 7

---

## Βήμα 7 — Αντιμετώπιση προβλημάτων

### Αν το rag-pipeline δείχνει error:

**Δοκίμασε τον server χειροκίνητα από WSL:**
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"protocolVersion":"2025-11-25","clientInfo":{"name":"test","version":"0.1"}}}' \
  | /mnt/e/ai/venv/bin/python /mnt/e/ai/mcp_server.py 2>/tmp/mcp_err.txt

cat /tmp/mcp_err.txt
```

Αν επιστρέψει JSON με `"result"` — ο server δουλεύει και το πρόβλημα είναι αλλού.
Αν επιστρέψει error — δες το μήνυμα σφάλματος.

**Έλεγξε τα logs του Claude Desktop:**
```bash
cat "/mnt/c/Users/user/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/logs/mcp-server-rag-pipeline.log"
```

---

## Βήμα 8 — Χρήση του RAG από το Claude Desktop

1. Άνοιξε **νέα συνομιλία** (τα tools δεν εμφανίζονται σε παλιές)
2. Κλικ στο **`+`** κάτω αριστερά
3. Επίλεξε **Connectors**
4. Ρώτα κάτι σχετικό με τα PDFs σου

### Παραδείγματα ερωτήσεων:
```
Ψάξε στα έγγραφα για πληροφορίες σχετικά με [θέμα]
Τι λέει το PDF για [ερώτηση];
Κάνε αναζήτηση: [λέξη-κλειδί]
```

---

## Σημαντικές πληροφορίες

| Στοιχείο | Τιμή |
|----------|------|
| Config path (Store) | `%LocalAppData%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\` |
| Config path (λάθος) | `%AppData%\Roaming\Claude\` ← ΜΗΝ το χρησιμοποιείς |
| MCP server | `/mnt/e/ai/mcp_server.py` |
| Python venv | `/mnt/e/ai/venv/bin/python` |
| ChromaDB | `/mnt/e/ai/chroma_db/` |
| Logs | `...LocalCache\Roaming\Claude\logs\mcp-server-rag-pipeline.log` |
