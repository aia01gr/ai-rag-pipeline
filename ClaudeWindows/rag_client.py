#!/usr/bin/env python3
"""
RAG Client - MCP stdio-to-HTTP bridge
Τρέχει στα Windows ως τοπικός MCP server για το Claude Desktop.
Συνδέεται απευθείας στον Linux MCP server μέσω HTTP.

Χρήση:
  python rag_client.py
  rag_client.exe  (compiled με PyInstaller)

Claude Desktop config (claude_desktop_config.json):
  {
    "mcpServers": {
      "rag-pipeline": {
        "command": "C:\\RAGClient\\rag_client.exe"
      }
    }
  }
"""

import asyncio
import io
import json
import logging
import sys
import time
from pathlib import Path

import httpx

# Force UTF-8 on Windows stdout/stderr (default is CP1252)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _load_config() -> dict:
    cfg_path = _exe_dir() / "config.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


_CFG = _load_config()

MCP_URL = _CFG.get("mcp_url", "http://156.67.28.160:8000/mcp")

# ---------------------------------------------------------------------------
# Logging → stderr + file (rag_client.log)
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("rag-client")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    log_path = _exe_dir() / "rag_client.log"
    try:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"Cannot open log file {log_path}: {e}")

    return logger


_log = _setup_logging()


def log(msg: str):
    _log.info(msg)


# ---------------------------------------------------------------------------
# Startup health probe
# ---------------------------------------------------------------------------

async def _probe_server(url: str, timeout: float = 5.0) -> bool:
    """Return True if the MCP server responds to a GET request."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            _log.info(f"Health probe OK → HTTP {r.status_code}")
            return True
    except Exception as e:
        _log.warning(f"Health probe failed: {e}")
        return False


# ---------------------------------------------------------------------------
# MCP Bridge: stdio ↔ HTTP streamable-http
# ---------------------------------------------------------------------------

# Retry delays in seconds: immediate attempt, then 1s wait, then 3s wait
_RETRY_DELAYS = [0, 1.0, 3.0]


class MCPBridge:
    def __init__(self, url: str):
        self.url = url
        self.session_id: str | None = None
        self.client = httpx.AsyncClient(timeout=120.0)

    async def send(self, message: dict):
        method = message.get("method", "?")
        msg_id = message.get("id")

        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            if delay > 0:
                _log.info(f"Retry {attempt}/{len(_RETRY_DELAYS)} in {delay}s (method={method})")
                await asyncio.sleep(delay)

            success = await self._try_send(message, method, msg_id)
            if success:
                return

            # Notifications have no id — no point retrying, server won't reply anyway
            if msg_id is None:
                return

        _log.error(f"{method} failed after {len(_RETRY_DELAYS)} attempts")
        if msg_id is not None:
            self._error(msg_id, -32603, f"Cannot reach MCP server after {len(_RETRY_DELAYS)} attempts")

    async def _try_send(self, message: dict, method: str, msg_id) -> bool:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        t0 = time.monotonic()
        try:
            async with self.client.stream(
                "POST",
                self.url,
                content=json.dumps(message),
                headers=headers,
                timeout=120.0,
            ) as response:
                status = response.status_code

                # Session expired or unknown — reset and let retry re-establish
                if status in (404, 410):
                    _log.warning(f"Session rejected (HTTP {status}), resetting session ID")
                    self.session_id = None
                    return False

                response.raise_for_status()

                sid = response.headers.get("Mcp-Session-Id")
                if sid and sid != self.session_id:
                    _log.debug(f"Session ID: {sid}")
                    self.session_id = sid

                content_type = response.headers.get("content-type", "")
                written = 0

                if "text/event-stream" in content_type:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:].strip()
                            if data:
                                self._write(data)
                                written += 1
                else:
                    body = await response.aread()
                    text = body.decode(errors="replace").strip()
                    if text:
                        self._write(text)
                        written += 1

                elapsed = time.monotonic() - t0
                _log.debug(f"{method} → HTTP {status} ({written} msg, {elapsed:.2f}s)")
                return True

        except httpx.HTTPStatusError as e:
            elapsed = time.monotonic() - t0
            _log.error(f"{method} HTTP {e.response.status_code} ({elapsed:.2f}s)")
            return False

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            elapsed = time.monotonic() - t0
            _log.error(f"{method} connection error ({elapsed:.2f}s): {e}")
            return False

        except Exception as e:
            elapsed = time.monotonic() - t0
            _log.error(f"{method} unexpected error ({elapsed:.2f}s): {e}")
            return False

    def _write(self, text: str):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def _error(self, req_id, code: int, msg: str):
        err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}
        self._write(json.dumps(err))

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main():
    _log.info(f"RAG Client starting → {MCP_URL}")

    reachable = await _probe_server(MCP_URL)
    if not reachable:
        _log.warning("MCP server not reachable at startup — will retry on each request")

    bridge = MCPBridge(MCP_URL)
    loop = asyncio.get_event_loop()

    try:
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except Exception:
                break

            if not line:
                break

            line = line.strip()
            if not line:
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError as e:
                _log.warning(f"Invalid JSON: {e}")
                continue

            await bridge.send(message)

    finally:
        await bridge.close()
        _log.info("RAG Client stopped.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
