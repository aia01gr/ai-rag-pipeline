# Ollama — Resource Usage & Configuration

## Role in the Pipeline

Ollama is used **only** by `rag_pipeline_local_with_ollama.py` for local LLM inference.
The MCP server (`mcp_server.py`) does **not** use Ollama — it only uses:
- Voyage AI API for embeddings
- ChromaDB for vector search

```
PDFs → chunks → embeddings (Voyage AI) → ChromaDB → MCP server → Claude Desktop
                                                          ↑
                                              (no Ollama involved)

rag_pipeline_local_with_ollama.py → ChromaDB + Ollama → answer
                                              ↑
                                      (standalone script, not MCP)
```

## Default Model

| Parameter | Value |
|-----------|-------|
| Model | `qwen2.5:32b` |
| Endpoint | `http://localhost:11434` |
| Configured in | `rag_pipeline_local_with_ollama.py` |

## Resource Usage

### RAM

| State | RAM |
|-------|-----|
| Idle (no model loaded) | ~40 MB |
| Model loaded (`qwen2.5:32b`) | ~19 GB |
| System total | 47 GB |
| Available when model loaded | ~28 GB |

The model is loaded into RAM on first query and stays loaded until Ollama unloads it (default timeout: 5 minutes of inactivity).

### CPU

- Inference runs on **CPU only** (no GPU on this server)
- `qwen2.5:32b` is a 32-billion parameter model — expect slow inference on CPU
- Typical: several minutes per response depending on answer length

### Storage

- Model stored at `/usr/share/ollama/.ollama/models/` (or `~/.ollama/models/`)
- `qwen2.5:32b` requires ~20 GB disk space

## Useful Commands

```bash
# Check Ollama status
systemctl status ollama

# List downloaded models
ollama list

# Check running models (loaded in RAM)
ollama ps

# Pull a model
ollama pull qwen2.5:32b

# Remove a model
ollama rm qwen2.5:32b

# Run a quick test
ollama run qwen2.5:32b "Hello"
```

## Using a Lighter Model

If `qwen2.5:32b` is too slow or memory-intensive, switch to a smaller model in `rag_pipeline_local_with_ollama.py`:

```python
pipeline = RAGPipeline(
    ollama_model="qwen2.5:7b"   # ~5 GB RAM, much faster
)
```

Other options:

| Model | RAM | Speed |
|-------|-----|-------|
| `qwen2.5:7b` | ~5 GB | Fast |
| `qwen2.5:14b` | ~10 GB | Medium |
| `qwen2.5:32b` | ~19 GB | Slow (CPU) |
| `llama3.2:3b` | ~2 GB | Very fast |

## Note on Embedding Compatibility

Ollama reads the text chunks retrieved from ChromaDB — it does **not** interact with the embeddings directly. The embeddings (created by Voyage AI `voyage-4-large`) are used only for the vector search step. The retrieved chunk text is then passed as context to Ollama, so any Ollama model is compatible with any embedding model.
