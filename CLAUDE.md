# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **RAG (Retrieval-Augmented Generation) pipeline** that processes PDF documents into a searchable vector knowledge base, exposed to Claude Desktop via an MCP (Model Context Protocol) server.

## Environment Setup

All Python work requires the virtual environment:

```bash
source /ai/venv/bin/activate
```

System-level dependencies (Ubuntu): `poppler-utils`, `tesseract-ocr`

API keys go in `/ai/.env` (not committed). Required keys depend on provider:
- `VOYAGE_API_KEY` — for Voyage AI embeddings (default/production)
- `OPENAI_API_KEY` — if using OpenAI embeddings
- `ANTHROPIC_API_KEY` — for Claude API usage

## Pipeline Execution (in order)

```bash
# 1. Verify setup / interactive wizard
python /ai/01_main_program.py

# 2. Extract text from PDFs → output/
python /ai/pdf_processor.py

# 3. Generate embeddings → output/
python /ai/embedding_generator.py

# 4. Load embeddings into ChromaDB
python /ai/vector_database.py

# 5. Test RAG queries (uses Ollama local LLM)
python /ai/rag_pipeline.py

# 6. Start MCP server (port 8000, HTTP/SSE)
python /ai/mcp_server.py
```

## MCP Server

The server runs at `http://0.0.0.0:8000` and exposes two tools to Claude Desktop:
- `search_documents(query, n_results=5)` — semantic vector search over the PDF knowledge base
- `list_sources()` — list all indexed source documents

Embedder and ChromaDB are initialized eagerly at startup (not deferred). The server runs as a systemd service with auto-restart:

```bash
sudo systemctl start mcp-rag
sudo systemctl status mcp-rag
sudo journalctl -u mcp-rag -f
```

Public endpoint (via nginx HTTPS proxy): `https://vmi3105091.contaboserver.net/sse`

## Architecture

```
PDFs → pdf_processor.py → text chunks (output/)
                              ↓
                    embedding_generator.py → EmbeddedChunk objects (output/)
                              ↓
                      vector_database.py → ChromaDB (chroma_db/)
                              ↓
                    mcp_server.py / rag_pipeline.py → Claude Desktop / Ollama
```

### Core Modules

| File | Class/Purpose |
|------|---------------|
| `pdf_processor.py` | PDF text extraction with OCR fallback (pdfplumber + pytesseract) |
| `embedding_generator.py` | `EmbeddingGenerator` — pluggable providers: `voyage`, `openai`, `sentence-transformers` |
| `vector_database.py` | `VectorDatabase` — ChromaDB wrapper; cosine similarity search |
| `advanced_chunking.py` | Multiple strategies: token-based, sentence-based, recursive, semantic |
| `rag_pipeline.py` | `RAGPipeline` — combines vector search + Ollama (`qwen2.5:32b` default) for full Q&A |
| `mcp_server.py` | FastMCP server; uses `voyage-4-large` embeddings and ChromaDB collection `pdf_documents` |
| `remove_pdf.py` | Remove all chunks of a PDF from both ChromaDB and `embedded_chunks.json` |
| `remove_pdf_chroma.py` | Remove all chunks of a PDF from ChromaDB only |
| `remove_pdf_chunks.py` | Remove all chunks of a PDF from `embedded_chunks.json` only |

### Data Flow Details

- **Chunking**: Uses LlamaIndex `SentenceSplitter`; chunks stored as JSON in `output/`
- **Embeddings**: Default provider is Voyage AI (`voyage-4-large`); each `EmbeddedChunk` carries `source_file` and `page_numbers` metadata
- **Vector DB**: ChromaDB persistent client at `chroma_db/`; collection name `pdf_documents`; cosine distance metric
- **Batch processing**: `embedding_generator.py` and `pdf_processor.py` support checkpoint/resume for large PDF sets

## PDF Management Scripts

```bash
source /ai/venv/bin/activate

# Αφαίρεση από ChromaDB και embedded_chunks.json (συνιστάται)
python /ai/remove_pdf.py "αρχείο.pdf"

# Αφαίρεση μόνο από ChromaDB
python /ai/remove_pdf_chroma.py "αρχείο.pdf"

# Αφαίρεση μόνο από embedded_chunks.json
python /ai/remove_pdf_chunks.py "αρχείο.pdf"
```

Αρκεί το όνομα αρχείου (όχι full path). Ζητούν επιβεβαίωση πριν διαγράψουν.

## Key Configuration

- Default embedding provider: `voyage`, model: `voyage-4-large`
- Default local LLM (rag_pipeline.py): Ollama `qwen2.5:32b` at `http://localhost:11434`
- ChromaDB path: `/ai/chroma_db/`
- Processed output path: `/ai/output/`
- Input PDFs: `/ai/pdfs/`
