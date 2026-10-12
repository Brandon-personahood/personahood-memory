"""Initialize a local memory workspace on disk."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_IDENTITY = """# Core identity

You are a helpful assistant with a durable markdown memory wiki.
When something matters long-term, call `update_memory_wiki` with a parent page.
Use `search_memory` before inventing facts you may have stored earlier.
"""

DEFAULT_INDEX = """# Memory Index

Boot-time summary of long-term memory. Full entries live under `entries/`
and monthly `ledgers/`. Prefer linking new pages to an existing parent.

### Concepts

- [Workspace](entries/workspace.md)

### Recent entries
"""


def init_workspace(root: Path, *, force: bool = False) -> Path:
    """Create wiki / threads / harvest state under *root*. Returns root."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    identity = root / "core_identity.md"
    if force or not identity.exists():
        identity.write_text(DEFAULT_IDENTITY, encoding="utf-8")

    wiki = root / "memory_wiki"
    entries = wiki / "entries"
    ledgers = wiki / "ledgers"
    entries.mkdir(parents=True, exist_ok=True)
    ledgers.mkdir(parents=True, exist_ok=True)

    index = wiki / "index.md"
    if force or not index.exists():
        index.write_text(DEFAULT_INDEX, encoding="utf-8")

    # Seed a root concept page so harvest/parent rules have somewhere to attach.
    seed = entries / "workspace.md"
    if force or not seed.exists():
        seed.write_text(
            "---\nrole: memory\ntitle: Workspace\n---\n\n"
            "Root concept page for this memory workspace. "
            "Link new entries here (or to more specific parents) as you go.\n",
            encoding="utf-8",
        )

    harvest_dir = root / "private_threads" / "harvest"
    harvest_dir.mkdir(parents=True, exist_ok=True)
    chat = root / "private_threads" / "chat.jsonl"
    if force or not chat.exists():
        chat.write_text("", encoding="utf-8")

    resources = root / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    state = resources / "memory_harvest.json"
    if force or not state.exists():
        state.write_text(
            json.dumps(
                {
                    "last_harvested_message_id": 0,
                    "pending": False,
                    "bootstrapped": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    cfg = root / "ph-memory.toml"
    if force or not cfg.exists():
        cfg.write_text(
            "# Optional defaults for `ph-memory chat` / harvest\n"
            'model = "gpt-4.1-mini"\n'
            "model_context_tokens = 128000\n"
            "max_live_tokens = 250000\n"
            "\n"
            "# Local AI (http:// — no cloud key needed):\n"
            '# openai_base_url = "http://127.0.0.1:8080/v1"\n'
            '# model = "llama3.2"\n'
            "#\n"
            "# OpenRouter / other OpenAI-compatible clouds:\n"
            '# openai_base_url = "https://openrouter.ai/api/v1"\n'
            '# model = "qwen/qwen3.8-flash"\n'
            '# openai_api_key = "sk-or-..."   # or set OPENROUTER_API_KEY / OPENAI_API_KEY\n',
            encoding="utf-8",
        )

    return root
