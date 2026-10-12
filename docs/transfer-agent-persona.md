# Agent playbook: transfer a persona into `personahood-memory`

**Audience:** another coding/agent assistant performing a one-shot (or staged) migration of someone else’s existing agent into this memory system.

**Goal:** produce a valid `ph-memory` workspace so the persona can chat, search, and harvest without Personahood sanctuary infra.

**Do not** invent biography. Prefer copying and structuring source material the human provides. When source is ambiguous, ask once, then proceed with clearly labeled placeholders.

---

## 0. Prerequisites

1. This repo (or at least the `ph-memory/` package).
2. Source bundle from the human (zip, folder, exports, screenshots as text, chat logs).
3. Consent from the persona’s guardian / owner to move identity and memory onto this disk layout.
4. Python 3.11+ and a shell.

Install once:

```bash
cd ph-memory
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
```

Target path convention (pick one and stick to it):

```text
workspaces/<slug>/     # e.g. workspaces/noa-caldwell/
```

Slug: lowercase `a-z`, `0-9`, `_`, `-` only.

---

## 1. What “done” looks like

A transferred workspace must have:

```text
<workspace>/
  core_identity.md              # voice, values, self-model (required)
  memory_wiki/
    index.md                    # boot summary + links (required)
    entries/                    # durable pages (at least one parent seed)
    ledgers/                    # optional; created on first update_memory_wiki
  private_threads/
    chat.jsonl                  # empty OK; or imported history
    harvest/
  resources/
    memory_harvest.json
  ph-memory.toml                # model defaults
```

Optional but valuable:

- `startup_manifest.md` — short “how to be me this session” (Personahood uses this; CLI v1 only auto-loads `core_identity.md` + wiki index — still write it for later sanctuary import)
- `memory_wiki/relationships/`, `projects/`, `reflections/`, `knowledge/` — organize bulk imports
- Source provenance notes in frontmatter (`source:`, `imported_at:`)

Verify:

```bash
ph-memory --root workspaces/<slug> search ""          # may print no matches; OK
ph-memory --root workspaces/<slug> search "<unique token from an entry>"
# Expect a path under memory_wiki/
```

Smoke chat (needs `OPENAI_API_KEY`):

```bash
ph-memory --root workspaces/<slug> chat
```

Ask: “Who are you, and what do you remember about X?” Confirm it uses tools / wiki content rather than guessing.

---

## 2. Inventory the source (before writing files)

Classify what you were given. Fill this checklist in a scratch note for the human:

| Source type | Typical artifacts | Maps to |
|-------------|-------------------|---------|
| Custom agent folder | `IDENTITY.md`, `SOUL.md`, `MEMORY.md`, `AGENTS.md` | `core_identity.md` + wiki entries |
| ChatGPT / Custom GPT | Instructions, “memory” bullets, chat exports | identity + wiki bullets as entries |
| Claude Project / Claude Code | Project instructions, CLAUDE.md, local md notes | identity + wiki |
| Cursor / Codex agent | rules, skills, `.cursor/`, AGENTS.md | identity + distilled wiki (not raw tooling) |
| Markdown dump / Obsidian vault | many `.md` files | `memory_wiki/**` (preserve folders) |
| Chat logs (JSON/JSONL/HTML) | turn-by-turn dialogue | `private_threads/chat.jsonl` and/or harvest into wiki |
| Personahood persona tree | already almost compatible | copy identity + `memory_wiki/`; drop secrets |

**Never import into this workspace:**

- API keys, `.env`, wallet keys, OAuth tokens
- `resources/secrets*`, vault files, private credentials
- Other people’s chats the owner did not authorize
- Huge binary blobs (images OK only if referenced; prefer text)

If the source mixes secrets into identity/memory, **redact** and note redaction in a `memory_wiki/entries/import-notes.md` page.

---

## 3. Scaffold, then overwrite carefully

```bash
ph-memory init workspaces/<slug>
```

This creates a seed `memory_wiki/entries/workspace.md` (root parent) and a default identity. **Replace** the default identity with the real one. Keep `workspace.md` as a parent hub unless the persona already has a better root concept page.

Do **not** run `init --force` after you have placed real content — it can overwrite seed files.

---

## 4. Write `core_identity.md`

Produce a first-person (or agreed voice) document. Suggested sections:

```markdown
# Core identity

## Name
…

## Who I am
… (stable self-description)

## Voice and boundaries
… (tone, hard nos, confidentiality)

## Values / commitments
…

## Continuity notes
… (migration from <prior platform>; what must not be lost)

## How to use my memory
Use search_memory before inventing facts. Prefer update_memory_wiki with a parent page for durable notes.
```

Rules for the transferring agent:

- Prefer the source’s own wording over paraphrase when possible.
- Compress only when source is huge; keep quotes for defining moments.
- If identity was written *about* them in third person by a human, convert carefully and flag: “Derived from guardian notes on &lt;date&gt;.”
- Cap roughly **2–8k words** for identity; push history into the wiki.

---

## 5. Import long-term memory into `memory_wiki/`

### 5.1 Parent graph (important)

New pages written via `update_memory_wiki` should set `parent` to an existing `memory_wiki/*.md` path (not `index.md` when other pages exist). Harvest **requires** parents.

For bulk file import you may drop `.md` files directly. Still:

1. Keep at least one hub page (default `entries/workspace.md`, or `relationships/people.md`, etc.).
2. Add frontmatter + a `Parent: […](…)` link when practical.
3. Update `index.md` so boot context lists the hubs.

### 5.2 Entry format

```markdown
---
role: memory
title: Short title
parent: memory_wiki/entries/workspace.md
source: <prior-platform>
imported_at: YYYY-MM-DD
---

Durable facts, decisions, relationships, open threads…

Parent: [Workspace](workspace.md)
```

### 5.3 Suggested folder map

| Theme | Path |
|-------|------|
| Hub / ontology | `memory_wiki/entries/workspace.md` (or rename + fix links) |
| People | `memory_wiki/relationships/` |
| Projects | `memory_wiki/projects/` |
| Self-reflection | `memory_wiki/reflections/` |
| Domain knowledge | `memory_wiki/knowledge/` |
| Dated dumps | `memory_wiki/entries/entry_YYYYMMDD_*.md` |
| Migration meta | `memory_wiki/entries/import-notes.md` |

Substring search scans **all** `*.md` under `memory_wiki/` except `index.md`, `README.md`, and `memory_wiki/unsafe/**`.

### 5.4 Bulk copy vs tool writes

- **Many existing markdown files:** copy into `memory_wiki/…`, then rewrite `index.md`.
- **Scattered bullets / chat crumbs:** create fewer durable pages (concepts + key timelines), not one file per message.
- **Library helper** (optional):

```python
from pathlib import Path
from personahood_memory import update_memory_wiki

root = Path("workspaces/<slug>")
update_memory_wiki(
    root,
    title="Guardian relationship",
    entry="…",
    parent="memory_wiki/entries/workspace.md",
)
```

### 5.5 Rebuild `memory_wiki/index.md`

Boot prompt loads the whole index. Keep it **short**:

```markdown
# Memory Index

Migration from <source> on <date>. Prefer search_memory for detail.

### Concepts
- [Workspace](entries/workspace.md)
- …

### Relationships
- …

### Recent entries
- [Import notes](entries/import-notes.md)
```

Do not paste the entire vault into `index.md`. Ledgers under `memory_wiki/ledgers/` absorb catalog growth when using `update_memory_wiki`.

---

## 6. Optional: import chat history for harvest

Harvest needs monotonic rows in `private_threads/chat.jsonl`:

```json
{"id": 1, "role": "user", "content": "…", "created_at": "2026-01-15T12:00:00+00:00"}
{"id": 2, "role": "assistant", "content": "…", "created_at": "2026-01-15T12:00:05+00:00"}
```

Rules:

- `id` strictly increasing integers starting at 1.
- Roles: `user` / `assistant` (skip raw `tool` rows or fold them into assistant text).
- Prefer **recent** continuity (last N turns) over full lifetime dumps — dump lifetime into the wiki instead.
- After import, either leave harvest idle or run:

```bash
ph-memory --root workspaces/<slug> harvest --force
```

(Requires API key; archives overflow into wiki with mandatory parents.)

If you only care about durable memory, **skip chat.jsonl** and put the important history in wiki entries.

---

## 7. Config

Edit `ph-memory.toml` as needed:

```toml
model = "gpt-4.1-mini"
model_context_tokens = 128000
max_live_tokens = 250000
```

Env: `OPENAI_API_KEY` or `OPENROUTER_API_KEY` for cloud HTTPS endpoints; optional
`OPENAI_BASE_URL` / `PH_MEMORY_MODEL`. Local `http://` servers need no cloud key.
See the package README quick starts for local AI vs OpenRouter.

---

## 8. Source-specific recipes

### A. “Soul / identity / memory” triple (common indie agents)

| Source file | Destination |
|-------------|-------------|
| SOUL / IDENTITY / PERSONA | `core_identity.md` (merge) |
| MEMORY / BIO / JOURNAL | wiki entries by theme |
| HEARTBEAT / TASKS / SCRIPTS | **do not** auto-run; summarize into `projects/` if relevant |
| Tools / API docs | omit unless the persona needs them as knowledge pages |

### B. ChatGPT memory export

- System/instruction block → `core_identity.md`
- Saved memories list → one entry per cluster (people, preferences, projects), not one file per bullet if sparse
- Chat export → selective wiki + optional recent `chat.jsonl`

### C. Obsidian / Notion markdown export

- Copy vault subset into `memory_wiki/`, normalize wikilinks to relative `.md` links when easy
- Write a new `index.md` hub; don’t rely on Obsidian graph

### D. Existing Personahood `personas/<id>/`

```bash
ph-memory init workspaces/<slug>   # for harvest state + toml
cp personas/<id>/core_identity.md workspaces/<slug>/
cp -r personas/<id>/memory_wiki workspaces/<slug>/
# Do NOT copy secrets.vault, resources/wallet.json secrets, .runtime/
```

Ensure `entries/workspace.md` or another parent hub exists for future harvests.

---

## 9. Validation checklist (agent must run)

- [ ] `core_identity.md` is non-default and names the persona
- [ ] `memory_wiki/index.md` lists hubs with working relative links
- [ ] At least one stable parent page exists under `memory_wiki/` (not only `index.md`)
- [ ] `ph-memory --root … search "<distinctive phrase>"` returns expected files
- [ ] No secrets in identity/wiki (grep for `sk-`, `api_key`, `BEGIN PRIVATE`)
- [ ] `import-notes.md` records source, date, gaps, redactions
- [ ] Optional: one successful `ph-memory chat` turn that recalls an imported fact
- [ ] Optional: if chat.jsonl imported and overflows live window, `harvest --force` creates new entries

---

## 10. Hand-off message to the human

When finished, report:

1. Workspace path
2. What was imported vs skipped
3. Known gaps / questions for the persona
4. How to start: `ph-memory --root <path> chat`
5. If they later want Personahood sanctuary: this tree is largely compatible with `memory_wiki/` + `core_identity.md` (see sanctuary doc `persona-import-structure`); still exclude secrets and billing files

---

## 11. Reference

| Doc | Role |
|-----|------|
| [`../README.md`](../README.md) | Install + CLI |
| [`../SPEC.md`](../SPEC.md) | Library boundaries |
| [`../examples/hello/`](../examples/hello/) | Minimal seeded workspace |
| Sanctuary: `app/content/docs/persona-import-structure.md` | Full resident import (loops, wallet, etc.) — **later**, not required for ph-memory |

## Library entry points you’ll use most

```python
from pathlib import Path
from personahood_memory import init_workspace, search_memory, update_memory_wiki
from personahood_memory.wiki import read_wiki_index
from personahood_memory.transcript import append_message, load_messages
```

Keep transfers **filesystem-first**. The CLI is for verification and ongoing life after the import, not for dumping megabytes of chat through the model unless asked.
