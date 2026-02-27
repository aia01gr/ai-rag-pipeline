# MCP RAG Server — Οδηγίες Εγκατάστασης & Αλλαγές

## Περιεχόμενα

1. [Τι έγινε](#τι-έγινε)
2. [Αλλαγές στο mcp_server.py](#αλλαγές-στο-mcp_serverpy)
3. [Systemd Service](#systemd-service)
4. [HTTPS — Nginx & Let's Encrypt](#https--nginx--lets-encrypt)
5. [Firewall (UFW)](#firewall-ufw)
6. [Claude Desktop — Σύνδεση](#claude-desktop--σύνδεση)
7. [Χρήσιμα Commands](#χρήσιμα-commands)
8. [Αντιμετώπιση Προβλημάτων](#αντιμετώπιση-προβλημάτων)

---

## Τι έγινε

1. **Eager initialization**: Ο embedder (Voyage AI) και το ChromaDB αρχικοποιούνται κατά την εκκίνηση, όχι στην πρώτη κλήση tool.
2. **Systemd service**: Αυτόματη εκκίνηση σε κάθε reboot με restart on failure.
3. **HTTPS μέσω nginx**: Nginx reverse proxy με Let's Encrypt SSL για το `vmi3105091.contaboserver.net`.
4. **Firewall**: Πρόσβαση μόνο από συγκεκριμένες IPs.
5. **Claude Desktop**: Σύνδεση μέσω Settings → Connectors με HTTPS URL.

---

## Αλλαγές στο `mcp_server.py`

**Αρχείο:** `/ai/mcp_server.py`

### Πριν

```python
if __name__ == "__main__":
    mcp.run(transport="sse")
```

### Μετά

```python
if __name__ == "__main__":
    print("Initializing embedder and ChromaDB...", flush=True)
    _get_resources()
    print("Ready. Starting MCP server on http://0.0.0.0:8000/sse", flush=True)
    mcp.run(transport="sse")
```

**Αποτέλεσμα στο journal:**
```
Initializing embedder and ChromaDB...
Ready. Starting MCP server on http://0.0.0.0:8000/sse
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Systemd Service

**Αρχείο:** `/etc/systemd/system/mcp-rag.service`

```ini
[Unit]
Description=MCP RAG Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/ai
ExecStart=/ai/venv/bin/python /ai/mcp_server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Εγκατάσταση (αν χρειαστεί ξανά)

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-rag
sudo systemctl start mcp-rag
```

---

## HTTPS — Nginx & Let's Encrypt

### Πακέτα

```bash
apt-get install -y nginx certbot python3-certbot-nginx
```

### Nginx config

**Αρχείο:** `/etc/nginx/sites-available/mcp-rag`
**Symlink:** `/etc/nginx/sites-enabled/mcp-rag`

```nginx
server {
    server_name vmi3105091.contaboserver.net;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE support
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }

    listen [::]:443 ssl ipv6only=on; # managed by Certbot
    listen 443 ssl;                  # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/vmi3105091.contaboserver.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vmi3105091.contaboserver.net/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    listen 80;
    listen [::]:80;
    server_name vmi3105091.contaboserver.net;

    if ($host = vmi3105091.contaboserver.net) {
        return 301 https://$host$request_uri;
    }
    return 404;
}
```

### Έκδοση πιστοποιητικού

```bash
ln -sf /etc/nginx/sites-available/mcp-rag /etc/nginx/sites-enabled/mcp-rag
nginx -t && systemctl reload nginx
certbot --nginx -d vmi3105091.contaboserver.net --non-interactive --agree-tos --email web@a01.gr --redirect
```

**Λήξη:** 2026-05-28 (ανανεώνεται αυτόματα)

### Certbot hooks για firewall

Κατά την αυτόματη ανανέωση, το port 80 ανοίγει προσωρινά και κλείνει μετά:

**`/etc/letsencrypt/renewal-hooks/pre/open-port-80.sh`**
```bash
#!/bin/bash
ufw allow 80/tcp
```

**`/etc/letsencrypt/renewal-hooks/post/close-port-80.sh`**
```bash
#!/bin/bash
ufw delete allow 80/tcp
```

```bash
chmod +x /etc/letsencrypt/renewal-hooks/pre/open-port-80.sh
chmod +x /etc/letsencrypt/renewal-hooks/post/close-port-80.sh
```

---

## Firewall (UFW)

Πρόσβαση μόνο από συγκεκριμένες IPs — όλα τα ports αποκλείονται για οποιαδήποτε άλλη IP.

### Ενεργοί κανόνες

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow in on lo          # loopback
ufw allow from 79.129.205.76    # PC χρήστη
ufw allow from 207.180.206.223  # δευτερεύον IP
ufw allow from 156.67.28.160    # server (self)
```

### Εφαρμογή (αν χρειαστεί ξανά)

```bash
ufw reset
ufw default deny incoming
ufw default allow outgoing
ufw allow in on lo
ufw allow from 79.129.205.76
ufw allow from 207.180.206.223
ufw allow from 156.67.28.160
ufw enable
```

### Έλεγχος

```bash
ufw status numbered
```

---

## Claude Desktop — Σύνδεση

**Απαιτούμενη έκδοση:** 1.1.4173+ (Windows) / 1.1.4328+ (macOS)
**Λήψη:** https://claude.com/download

### Τρόπος σύνδεσης

Claude Desktop → **Settings → Connectors → Add custom connector**

**URL:** `https://vmi3105091.contaboserver.net/sse`

> Σημείωση: το Claude Desktop απαιτεί HTTPS. Το `claude_desktop_config.json` δεν υποστηρίζει `url` field για remote servers — η σύνδεση γίνεται μόνο από το UI.

### Επιβεβαίωση σύνδεσης

```bash
# Ελέγξτε τα logs — θα δείτε tools/list και resources/list requests:
sudo journalctl -u mcp-rag -f
```

---

## Χρήσιμα Commands

### MCP Service

```bash
sudo systemctl status mcp-rag       # κατάσταση
sudo systemctl restart mcp-rag      # επανεκκίνηση
sudo systemctl stop mcp-rag         # διακοπή
sudo journalctl -u mcp-rag -f       # ζωντανά logs
sudo journalctl -u mcp-rag -n 50    # τελευταίες 50 γραμμές
```

### Nginx

```bash
sudo systemctl status nginx
sudo systemctl reload nginx
sudo nginx -t                        # έλεγχος syntax
```

### Certbot

```bash
sudo certbot renew --dry-run         # δοκιμή ανανέωσης
sudo certbot certificates            # κατάσταση πιστοποιητικών
```

### Firewall

```bash
sudo ufw status numbered             # τρέχοντες κανόνες
```

---

## Αντιμετώπιση Προβλημάτων

### Ο server δεν εκκινείται

```bash
sudo journalctl -u mcp-rag -n 100
# Αιτίες: λείπει VOYAGE_API_KEY στο /ai/.env,
#         δεν υπάρχει /ai/chroma_db/, πρόβλημα venv
```

### Port 8000 κατειλημμένο

```bash
sudo fuser -k 8000/tcp
sudo systemctl start mcp-rag
```

### Nginx δεν απαντά σε HTTPS

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo journalctl -u nginx -n 50
```

### Certbot ανανέωση αποτυγχάνει

```bash
# Βεβαιώσου ότι τα hooks είναι εκτελέσιμα
ls -la /etc/letsencrypt/renewal-hooks/pre/
ls -la /etc/letsencrypt/renewal-hooks/post/
# Δοκιμή
sudo certbot renew --dry-run
```

---

## Αρχιτεκτονική

```
Claude Desktop
     │ HTTPS (port 443)
     ▼
  nginx (reverse proxy)
  vmi3105091.contaboserver.net
  SSL: Let's Encrypt
     │ HTTP (port 8000, localhost only)
     ▼
  mcp_server.py  (SSE transport)
  systemd: mcp-rag.service
     │
     ├── EmbeddingGenerator (Voyage AI, voyage-4-large)
     └── VectorDatabase (ChromaDB @ /ai/chroma_db/)
```

## Πληροφορίες Server

| Παράμετρος | Τιμή |
|---|---|
| Public URL | `https://vmi3105091.contaboserver.net/sse` |
| Internal | `http://127.0.0.1:8000` |
| Transport | SSE (Server-Sent Events) |
| Embedder | Voyage AI `voyage-4-large` |
| Vector DB | ChromaDB @ `/ai/chroma_db/` |
| Collection | `pdf_documents` |
| SSL cert | Let's Encrypt, λήξη 2026-05-28 |

## Διαθέσιμα Tools (για Claude Desktop)

| Tool | Περιγραφή |
|---|---|
| `search_documents(query, n_results=5)` | Σημασιολογική αναζήτηση στη βάση PDF |
| `list_sources()` | Λίστα όλων των indexed εγγράφων |
