# Personahood Memory — SPEC

## Purpose

Portable **long-term memory** for agents: a markdown wiki on disk, a live chat
context window with cost-aware caps, and silent **harvest** planning that
archives overflow into the wiki.

This package has **no** dependency on Personahood sanctuary APIs, Postgres,
Docker residents, billing, or OpenRouter.

## Layers

| Layer | Package path | Owns |
|-------|----------------|------|
| Library | `personahood_memory.wiki`, `.window`, `.harvest`, `.layout` | On-disk wiki, token budgets, harvest state machine |
| CLI harness | `personahood_memory.cli` | Local `init` / `chat` / `search` / `harvest` with OpenAI |
| Phase 2 MCP | `personahood_memory.mcp_server` | Claude Code (subscription) tools over MEMORY_ROOT |

## On-disk workspace

```
workspace/
  core_identity.md
  memory_wiki/
    index.md
    entries/
    ledgers/YYYY-MM.md
  private_threads/
    chat.jsonl          # monotonic message ids for harvest
    harvest/pending.md
  resources/
    memory_harvest.json
  ph-memory.toml        # optional defaults
```

## Library contracts

- **Wiki:** substring `search_memory`; `update_memory_wiki` requires a parent page
  when other pages exist (mandatory during harvest). Index keeps a short Recent
  list; monthly ledgers absorb the catalog.
- **Window:** `fit_to_context(messages, *, model_context_tokens=…,
  max_live_tokens=…)`. No model catalog import — callers inject window size.
- **Harvest:** pure planning over `MessageRow` (id, role, content). State and
  slice files live under the workspace root (`Path`), not persona IDs.

## Explicit non-goals (v1)

- Semantic / vector search (LanceDB later)
- Guest quarantine / unsafe wiki
- Personahood file_registry, billing, supervisor job queue
- Full resident agent tool surface (bash, images, peer threads)

## Phase 2 — Claude Code (subscription)

- MCP server: `python -m personahood_memory.mcp_server` (`pip install -e ".[mcp]"`)
- Tools do **filesystem only** (no LLM inside the server)
- Claude Code on Pro/Max OAuth supplies the model — **not** Anthropic API credits;
  unset `ANTHROPIC_API_KEY` so the subscription is used
- Docs: [`docs/claude-code.md`](docs/claude-code.md),
  example [`examples/claude-code.mcp.json`](examples/claude-code.mcp.json)
- **Codex:** same library/CLI; MCP if supported, else shell out to `ph-memory`
