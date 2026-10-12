# personahood-memory

Portable **filesystem wiki memory**, live **context window** fitting, and silent
**harvest** planning — without Personahood sanctuary infra.

Works on **Linux, macOS, and Windows**. Talks to any **OpenAI-compatible**
Chat Completions API that supports tool/function calling (local servers,
OpenRouter, OpenAI, Groq, etc.).

## Install (Linux / macOS / Windows)

Needs **Python 3.10+**.

```bash
cd ph-memory
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev]"
ph-memory --help
```

If `ph-memory` is not found after install:

```bash
# Scripts often land on PATH via the venv; without a venv they may be in ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
ph-memory --help

# Always works:
python -m personahood_memory --help
```

## Quick start 1 — Local AI (LAN / this machine)

Point at an OpenAI-compatible server (Ollama, llama.cpp, vLLM, LM Studio, …).
No cloud API key required for plain `http://` endpoints.

```bash
ph-memory init ./my-agent
```

Edit `my-agent/ph-memory.toml`:

```toml
openai_base_url = "http://fedora:8080/v1"   # or http://127.0.0.1:11434/v1
model = "llama3.2"                          # whatever /v1/models lists
model_context_tokens = 128000
max_live_tokens = 32000                     # keep ≤ your model's context
```

Then:

```bash
ph-memory --root ./my-agent chat
```

Same thing via environment variables:

```bash
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export PH_MEMORY_MODEL=llama3.2
ph-memory --root ./my-agent chat
```

| Stack | Typical base URL |
|-------|------------------|
| Ollama | `http://HOST:11434/v1` |
| LM Studio | `http://HOST:1234/v1` |
| llama.cpp / many vLLM docks | `http://HOST:8080/v1` |

The server must expose `POST …/v1/chat/completions` **with tools**. Check:

```bash
curl -s "$OPENAI_BASE_URL/models"
```

## Quick start 2 — OpenRouter (or other OpenAI-compatible clouds)

Use your provider key as `OPENAI_API_KEY` (OpenRouter also accepts `OPENROUTER_API_KEY`)
and set the base URL to that provider’s Chat Completions root.

**OpenRouter:**

```bash
ph-memory init ./my-agent
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENROUTER_API_KEY=sk-or-...          # or OPENAI_API_KEY
export PH_MEMORY_MODEL=qwen/qwen3.8-flash    # any tool-capable model id
ph-memory --root ./my-agent chat
```

Or in `my-agent/ph-memory.toml`:

```toml
openai_base_url = "https://openrouter.ai/api/v1"
openai_api_key = "sk-or-..."                 # prefer env for secrets
model = "qwen/qwen3.8-flash"
model_context_tokens = 1000000
max_live_tokens = 250000
```

**OpenAI:**

```bash
export OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL defaults to https://api.openai.com/v1
export PH_MEMORY_MODEL=gpt-4.1-mini
ph-memory --root ./my-agent chat
```

**Other OpenAI-compatible hosts** (Together, Groq, Fireworks, Azure-compatible
gateways, etc.): same pattern — set `OPENAI_BASE_URL` to their `…/v1` root,
`OPENAI_API_KEY` to their key, and `PH_MEMORY_MODEL` / `model` to their model id.

## In chat

The model can call `search_memory`, `update_memory_wiki`, and `read_file`.
When history grows past the live window, a harvest slice is scheduled — run
`ph-memory harvest` (or type `/harvest`) to archive it into the wiki.

```bash
ph-memory --root ./my-agent search "decision"
ph-memory --root ./my-agent harvest --force
```

## Workspace layout

```
workspace/
  core_identity.md
  memory_wiki/
    index.md
    entries/
    ledgers/
  private_threads/
    chat.jsonl
    harvest/pending.md
  resources/memory_harvest.json
  ph-memory.toml
```

Search is **substring only** (no vector DB yet). New wiki pages should link to an
existing parent under `memory_wiki/` (required during harvest).

## Library

```python
from pathlib import Path
from personahood_memory import init_workspace, search_memory, update_memory_wiki, fit_to_context

root = init_workspace(Path("./my-agent"))
update_memory_wiki(root, entry="We chose SQLite.", title="Storage", parent="memory_wiki/entries/workspace.md")
print(search_memory(root, "sqlite"))
```

See [SPEC.md](SPEC.md) for module boundaries.

## Claude Code (Phase 2 — use your subscription, not API credits)

Claude Code is the agent; this package is only memory tools over MCP:

```bash
pip install -e ".[mcp]"
# configure examples/claude-code.mcp.json → project .mcp.json with MEMORY_ROOT
```

Full steps: **[docs/claude-code.md](docs/claude-code.md)**.  
Important: unset `ANTHROPIC_API_KEY` so Claude Code bills your Pro/Max plan, not API.

## Transferring another agent’s persona

To migrate someone else’s existing agent (ChatGPT memory, Claude project, Soul/Memory
files, Obsidian vault, etc.) into this layout, follow the agent playbook:

**[docs/transfer-agent-persona.md](docs/transfer-agent-persona.md)**

How to find it:

- From this package root: `ph-memory/docs/transfer-agent-persona.md`
- From the monorepo root: `ph-memory/docs/transfer-agent-persona.md`
- Open or `@`-mention that path in Cursor, or tell another agent:
  “Read `ph-memory/docs/transfer-agent-persona.md` and transfer this persona.”

## Config reference

| Source | Keys |
|--------|------|
| Env | `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_BASE_URL`, `PH_MEMORY_MODEL` |
| `ph-memory.toml` | `model`, `model_context_tokens`, `max_live_tokens`, `openai_base_url`, `openai_api_key` |

- **Local `http://` endpoints:** API key optional (a placeholder `local` Bearer is sent).
- **HTTPS cloud endpoints** (OpenAI, OpenRouter, …): a real API key is required.
