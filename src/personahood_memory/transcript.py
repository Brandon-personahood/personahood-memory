"""JSONL chat transcript with monotonic ids for harvest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from personahood_memory.protocols import MessageRow

CHAT_REL = "private_threads/chat.jsonl"


def chat_path(root: Path) -> Path:
    return root / CHAT_REL


def load_messages(root: Path) -> list[MessageRow]:
    path = chat_path(root)
    if not path.is_file():
        return []
    rows: list[MessageRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "id" not in data or "role" not in data:
            continue
        rows.append(
            MessageRow(
                id=int(data["id"]),
                role=str(data["role"]),
                content=data.get("content"),
                created_at=data.get("created_at"),
            )
        )
    return rows


def append_message(root: Path, role: str, content: str) -> MessageRow:
    path = chat_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_messages(root)
    next_id = (existing[-1].id + 1) if existing else 1
    row = MessageRow(
        id=next_id,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "id": row.id,
                    "role": row.role,
                    "content": row.content,
                    "created_at": row.created_at,
                }
            )
            + "\n"
        )
    return row


def history_dicts(root: Path) -> list[dict]:
    """OpenAI-style history from the transcript (no tool rows)."""
    out = []
    for row in load_messages(root):
        if row.role in ("user", "assistant", "system"):
            d = {"role": row.role, "content": row.content or ""}
            if row.created_at:
                d["created_at"] = row.created_at
            out.append(d)
    return out
