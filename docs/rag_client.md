# RAG Client — MCP stdio-to-HTTP Bridge

## Σύνοψη

`rag_client.py` / `rag_client.exe` — πρόγραμμα Windows που:

- Εκτελείται ως **τοπικός MCP server** (stdio) για το Claude Desktop
- Προωθεί τα MCP μηνύματα απευθείας μέσω **HTTP** στον remote RAG server
- **Δεν χρειάζεται** SSL, OAuth, mcp-remote, SSH tunnel ή nginx

**Χαρακτηρισμός**: "MCP stdio-to-HTTP bridge" ή "Remote MCP to Local stdio adapter".
Το Claude Desktop το βλέπει ως τοπικό server — δεν ξέρει ότι μιλάει με remote machine.

---

## Αρχιτεκτονική

```
┌─────────────────────────────────────────────────────────┐
│  Windows PC                                             │
│                                                         │
│  Claude Desktop                                         │
│       │ stdin/stdout (MCP stdio protocol)               │
│       ▼                                                 │
│  rag_client.exe                                         │
│    └── MCPBridge → POST http://156.67.28.160:8000/mcp  │
│                │                                        │
└────────────────┼────────────────────────────────────────┘
                 │ HTTP (port 8000) — UFW whitelist
                 ▼
    Linux VPS 156.67.28.160
    mcp_server.py :8000/mcp  (streamable-http)
```

**Ροή μηνύματος:**
1. Claude Desktop γράφει JSON-RPC στο stdin του `rag_client.exe`
2. `rag_client.exe` το στέλνει ως POST στο `http://156.67.28.160:8000/mcp`
3. Ο Linux server απαντά (JSON ή SSE stream)
4. `rag_client.exe` γράφει την απάντηση στο stdout
5. Claude Desktop λαμβάνει την απάντηση

---

## Αρχεία

| Αρχείο | Περιγραφή |
|--------|-----------|
| `rag_client.py` | Πηγαίος κώδικας |
| `config.json` | Ρυθμίσεις (προαιρετικό) |
| `rag_client.exe` | Compiled εκτελέσιμο (PyInstaller) |

---

## Εγκατάσταση στα Windows

### Επιλογή Α — Python (development / testing)

```powershell
pip install httpx
python C:\RAGClient\rag_client.py
```

### Επιλογή Β — Compiled .exe (χωρίς Python)

#### Αυτόματα με build_exe.bat

1. Αντέγραψε στο Windows PC:
   - `rag_client.py`
   - `build_exe.bat`
   - `config.json` (προαιρετικό)

2. Κάνε διπλό κλικ στο `build_exe.bat`

3. Αποτέλεσμα: φάκελος `RAGClient\` με:
   ```
   RAGClient\
   ├── rag_client.exe   ← το τελικό εκτελέσιμο
   └── config.json      ← ρυθμίσεις
   ```

4. Αντέγραψε τον φάκελο `RAGClient\` όπου θέλεις (π.χ. `C:\RAGClient\`)

#### Χειροκίνητα (PowerShell)

```powershell
pip install httpx pyinstaller

pyinstaller --onefile --name rag_client --console `
  --hidden-import httpx `
  --hidden-import httpx._transports.default `
  --hidden-import anyio `
  --hidden-import anyio._backends._asyncio `
  rag_client.py

# Αντέγραψε αποτελέσματα
mkdir C:\RAGClient
copy dist\rag_client.exe C:\RAGClient\
copy config.json C:\RAGClient\
```

#### Σημειώσεις PyInstaller

| | |
|--|--|
| Μέγεθος .exe | ~15-20 MB (περιλαμβάνει Python runtime + httpx) |
| Windows Defender | Μπορεί να εμφανιστεί warning για νέο .exe — επίλεξε "Run anyway" |
| Antivirus | Αν μπλοκάρει, πρόσθεσε εξαίρεση για `C:\RAGClient\` |
| Python version | Χρειάζεται Python 3.10+ για build (όχι για run) |

Αντέγραψε `dist\rag_client.exe` + `config.json` στον φάκελο εγκατάστασης.

---

## Ρύθμιση

### config.json (προαιρετικό — δίπλα στο .exe)

```json
{
  "ssh_host": "156.67.28.160",
  "ssh_user": "root",
  "ssh_key": "C:\\Users\\user\\.ssh\\id_ed25519",
  "mcp_port": 8000,
  "mcp_endpoint": "/mcp"
}
```

Αν δεν υπάρχει `config.json`, χρησιμοποιούνται οι default τιμές παραπάνω.

### Claude Desktop — claude_desktop_config.json

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-pipeline": {
      "command": "C:\\RAGClient\\rag_client.exe"
    }
  }
}
```

Ή με Python:
```json
{
  "mcpServers": {
    "rag-pipeline": {
      "command": "python",
      "args": ["C:\\RAGClient\\rag_client.py"]
    }
  }
}
```

---

## Απαιτήσεις

**Windows PC:**
- Windows 10 / 11 (x64)
- Δικτυακή πρόσβαση στο port **8000** του 156.67.28.160 (η IP πρέπει να είναι στη UFW whitelist)

**Linux VPS:**
- MCP server τρέχει με `streamable-http` transport στο port 8000
- UFW: `ufw allow from <windows-ip> to any port 8000`

**Δεν απαιτείται:**
- Python, Node.js ή runtime (αν compiled ως .exe)
- SSL/TLS certificates
- OAuth ή authentication
- SSH key ή SSH tunnel
- nginx

---

## Κώδικας — Βασικές Κλάσεις

### MCPBridge
Μεταφράζει MCP stdio ↔ HTTP streamable-http:
- `POST http://156.67.28.160:8000/mcp` με `Accept: application/json, text/event-stream`
- Αποθηκεύει `Mcp-Session-Id` από την πρώτη απάντηση
- Retry με backoff: 3 απόπειρες (0s → 1s → 3s)
- Session ID reset αν πάρει HTTP 404/410
- Χειρίζεται JSON responses και SSE streams
- Error handling με JSON-RPC error responses

### Main loop
- Διαβάζει JSON-RPC από stdin (newline-delimited)
- Προωθεί στο MCPBridge
- Γράφει απαντήσεις στο stdout

---

## Σύγκριση με mcp-remote

| | mcp-remote | rag_client |
|--|------------|------------|
| OAuth discovery | Ναι — **κολλάει** | Δεν υπάρχει |
| SSL απαίτηση | Όχι | Όχι |
| SSH tunnel | Ξεχωριστό | **Ενσωματωμένο** |
| Transport | http-first/sse | streamable-http |
| Windows .exe | Όχι | **Ναι** |
| Εξαρτήσεις | Node.js + npm | Καμία (.exe) |
| Συμβατότητα MCP SDK | Προβλήματα v1.26 | Πλήρης |

---

## Logging

### rag_client (Windows)

Γράφει logs σε δύο μέρη:
- **stderr** → εμφανίζεται στα logs του Claude Desktop (`%APPDATA%\Claude\logs\`)
- **rag_client.log** → αρχείο δίπλα στο .exe (π.χ. `C:\RAGClient\rag_client.log`)

Μορφή: `2026-01-15 10:23:45 INFO  initialize → HTTP 200 (0.45s)`

### mcp-server (Linux)

```bash
sudo journalctl -u mcp-rag -f
```

Παράδειγμα output:
```
2026-01-15 10:23:44 INFO  mcp-server: Resources ready.
2026-01-15 10:23:45 INFO  mcp-server: search_documents: query='...' n_results=5
2026-01-15 10:23:46 INFO  mcp-server: search_documents: 5 results (0.82s)
```

---

## Troubleshooting

**"Cannot reach MCP server"** → Βεβαιώσου ότι ο MCP server τρέχει στον Linux:
```bash
sudo systemctl status mcp-rag
```

**Claude Desktop δεν βλέπει tools** → Δες τα logs του Claude Desktop:
`%APPDATA%\Claude\logs\`

**Test χωρίς Claude Desktop:**
```powershell
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | python rag_client.py
```

**Δες το log αρχείο:**
```powershell
type C:\RAGClient\rag_client.log
```
