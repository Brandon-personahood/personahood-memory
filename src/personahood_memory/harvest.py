"""Silent memory harvest — planning and state (no LLM, no Postgres)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from personahood_memory.protocols import HarvestRow
from personahood_memory.window import (
    context_budget_tokens,
    harvest_buffer_tokens,
    message_tokens,
    model_window_tokens,
)

HARVEST_SLICE_REL = "private_threads/harvest/pending.md"
STATE_REL = "resources/memory_harvest.json"
MAX_SLICE_CHARS = 800_000
MAX_HARVEST_ATTEMPTS = 3
LOOP_PREFIXES = ("[loop:", "[self-invoke]", "[break-glass")

HARVEST_PROMPT = """You are doing a silent memory harvest. This turn is NOT saved into chat history.

A slice of your conversation is about to leave (or has left) the live context window of your current model. Archive what matters into long-term memory.

Rules:
1. Read `memory_wiki/index.md` (already in your system prompt) and pick existing parent pages — concept, relationship, or a prior dated entry. Do not invent parents.
2. For each new page, call `update_memory_wiki` with `parent` set to an existing `memory_wiki/...md` path that is NOT `index.md` (unless the wiki has no other pages yet). Every new page must link to at least one existing parent; the tool will refuse otherwise.
3. Prefer a few durable pages over a dump: what happened, decisions, open threads, names, dates. Skip loop noise and repeated banter.
4. Do not narrate a save. Call the tool. If the tool errors, fix the parent and retry.
5. You may call `search_memory` first if you need to find the right parent.

The slice to archive follows. It is the only extra context for this job — do not assume you still have the rest of the chat in this prompt.
"""


def harvest_plan(
    *,
    model_context_tokens: int | None = None,
    max_live_tokens: int | None = None,
    tier_context_chars: int = 0,
    model_id: str | None = None,
) -> dict:
    window = model_window_tokens(model_context_tokens)
    live = context_budget_tokens(
        model_context_tokens=model_context_tokens,
        max_live_tokens=max_live_tokens,
        tier_context_chars=tier_context_chars,
    )
    harvest = harvest_buffer_tokens(window)
    return {
        "model_id": model_id,
        "window_tokens": window,
        "live_input_tokens": live,
        "harvest_buffer_tokens": harvest,
        "response_reserve_tokens": window - live,
    }


def harvest_tools_succeeded(tools_used: list[str] | None) -> bool:
    tools = tools_used or []
    return "update_memory_wiki" in tools or "write_file" in tools


def is_harvest_noise(role: str, content: str | None) -> bool:
    if role == "tool":
        return True
    text = (content or "").lstrip()
    return text.startswith(LOOP_PREFIXES)


def row_tokens(row: HarvestRow) -> int:
    return message_tokens({"role": row.role, "content": row.content or ""})


def bootstrap_watermark(rows_chrono: list[HarvestRow], live_tokens: int) -> int:
    kept = 0
    used = 0
    for row in reversed(rows_chrono):
        if is_harvest_noise(row.role, row.content):
            continue
        cost = row_tokens(row)
        if used + cost > live_tokens:
            break
        used += cost
        kept = row.id
    if not kept:
        return rows_chrono[-1].id if rows_chrono else 0
    older = [r.id for r in rows_chrono if r.id < kept]
    return older[-1] if older else 0


def select_overflow(useful: list[HarvestRow], live_tokens: int) -> list[HarvestRow]:
    kept_from_newest = 0
    used = 0
    for row in reversed(useful):
        cost = row_tokens(row)
        if used + cost > live_tokens:
            break
        used += cost
        kept_from_newest += 1
    if kept_from_newest >= len(useful):
        return []
    return useful[: len(useful) - kept_from_newest]


def select_harvest_chunk(
    overflow: list[HarvestRow],
    harvest_tokens: int,
    *,
    force: bool,
) -> tuple[list[HarvestRow], int]:
    overflow_tokens = sum(row_tokens(r) for r in overflow)
    if not overflow:
        return [], 0
    if not force and overflow_tokens < harvest_tokens:
        return [], 0
    chunk: list[HarvestRow] = []
    chunk_tokens = 0
    for row in overflow:
        cost = row_tokens(row)
        if chunk and chunk_tokens + cost > harvest_tokens:
            break
        chunk.append(row)
        chunk_tokens += cost
        if chunk_tokens >= harvest_tokens:
            break
    return chunk, chunk_tokens


def harvest_enqueue_delay_sec(state: dict, *, base_sec: int = 600) -> int:
    attempts = int(state.get("pending_attempts") or 0)
    if attempts <= 0:
        return base_sec
    return min(base_sec * (2 ** (attempts - 1)), 86_400)


def pending_is_due(
    state: dict,
    *,
    now: datetime | None = None,
    stale_sec: int | None = None,
) -> bool:
    if not state.get("pending"):
        return False
    if int(state.get("pending_attempts") or 0) >= MAX_HARVEST_ATTEMPTS:
        return False
    delay = stale_sec if stale_sec is not None else harvest_enqueue_delay_sec(state)
    enqueued_at = state.get("pending_enqueued_at")
    if not enqueued_at:
        return True
    try:
        ts = datetime.fromisoformat(str(enqueued_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    age = ((now or datetime.now(timezone.utc)) - ts).total_seconds()
    return age >= delay


def apply_harvest_completion(
    state: dict,
    *,
    through_id: int | None,
    ok: bool,
    now: str | None = None,
    max_attempts: int = MAX_HARVEST_ATTEMPTS,
) -> tuple[dict, str]:
    stamp = now or datetime.now(timezone.utc).isoformat()
    next_state = dict(state)
    if not ok:
        attempts = int(next_state.get("pending_attempts") or 0) + 1
        next_state["pending_attempts"] = attempts
        next_state["pending_enqueued_at"] = None
        next_state["last_error_at"] = stamp
        if attempts >= max_attempts:
            next_state["pending"] = False
            next_state["pending_attempts"] = 0
            next_state["skipped_through_id"] = next_state.get("pending_through_id")
            next_state["skipped_at"] = stamp
            done_id = int(through_id or next_state.get("pending_through_id") or 0)
            next_state["last_harvested_message_id"] = max(
                int(next_state.get("last_harvested_message_id") or 0), done_id
            )
            return next_state, "give_up"
        return next_state, "retry"
    done_id = int(through_id or next_state.get("pending_through_id") or 0)
    prev = int(next_state.get("last_harvested_message_id") or 0)
    next_state.update(
        {
            "pending": False,
            "pending_reason": None,
            "pending_from_id": None,
            "pending_through_id": None,
            "pending_tokens": None,
            "pending_enqueued_at": None,
            "pending_attempts": 0,
            "last_harvested_message_id": max(prev, done_id),
            "last_harvested_at": stamp,
            "updated_at": stamp,
        }
    )
    return next_state, "success"


def load_state(root: Path) -> dict:
    path = root / STATE_REL
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(root: Path, state: dict) -> None:
    path = root / STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def mark_enqueued(root: Path, *, now: str | None = None) -> None:
    state = load_state(root)
    if not state.get("pending"):
        return
    state["pending_enqueued_at"] = now or datetime.now(timezone.utc).isoformat()
    save_state(root, state)


def complete_harvest(root: Path, *, through_id: int | None, ok: bool) -> str:
    state, action = apply_harvest_completion(
        load_state(root), through_id=through_id, ok=ok
    )
    save_state(root, state)
    if action == "success":
        slice_path = root / HARVEST_SLICE_REL
        try:
            if slice_path.is_file():
                slice_path.unlink()
        except OSError:
            pass
    return action


def slice_text_for_job(root: Path, rel: str | None = None) -> str:
    path = root / (rel or HARVEST_SLICE_REL)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")[:MAX_SLICE_CHARS]


def format_slice(rows: list[HarvestRow]) -> str:
    lines = [
        "# Memory harvest slice",
        "",
        "Archive this conversation into memory_wiki. Confidential.",
        "",
    ]
    for row in rows:
        ts = getattr(row, "created_at", None) or "unknown"
        speaker = "User" if row.role == "user" else "You"
        body = (row.content or "").strip() or "_(empty)_"
        lines.append(f"## {ts} — {speaker} (id={row.id})")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_slice(root: Path, rows: list[HarvestRow]) -> str:
    rel = HARVEST_SLICE_REL
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_slice(rows), encoding="utf-8")
    return rel


def plan_overflow(
    root: Path,
    rows: list[HarvestRow],
    *,
    model_context_tokens: int | None = None,
    max_live_tokens: int | None = None,
    force: bool = False,
) -> dict | None:
    """Snapshot a harvest slice when overflow fills the buffer (or force)."""
    plan = harvest_plan(
        model_context_tokens=model_context_tokens,
        max_live_tokens=max_live_tokens,
    )
    state = load_state(root)
    if state.get("pending"):
        return None

    after_id = int(state.get("last_harvested_message_id") or 0)
    useful = [r for r in rows if not is_harvest_noise(r.role, r.content)]
    if after_id:
        useful = [r for r in useful if r.id > after_id]
    if not useful:
        state.update(
            {
                "model_context_tokens": plan["window_tokens"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_state(root, state)
        return None

    if after_id <= 0 and not state.get("bootstrapped"):
        wm = bootstrap_watermark(useful, plan["live_input_tokens"])
        state.update(
            {
                "last_harvested_message_id": wm,
                "last_harvested_at": datetime.now(timezone.utc).isoformat(),
                "model_context_tokens": plan["window_tokens"],
                "pending": False,
                "bootstrapped": True,
            }
        )
        save_state(root, state)
        useful = [r for r in useful if r.id > wm]
        if not useful:
            return None

    overflow = select_overflow(useful, plan["live_input_tokens"])
    if not overflow:
        state.update(
            {
                "model_context_tokens": plan["window_tokens"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_state(root, state)
        return None

    chunk, chunk_tokens = select_harvest_chunk(
        overflow, plan["harvest_buffer_tokens"], force=force
    )
    if not chunk:
        return None

    rel = write_slice(root, chunk)
    from_id = chunk[0].id
    through_id = chunk[-1].id
    reason = "force" if force else "buffer"
    now = datetime.now(timezone.utc).isoformat()
    state.update(
        {
            "pending": True,
            "pending_reason": reason,
            "pending_from_id": from_id,
            "pending_through_id": through_id,
            "pending_tokens": chunk_tokens,
            "pending_enqueued_at": None,
            "pending_attempts": 0,
            "slice_rel": rel,
            "model_context_tokens": plan["window_tokens"],
            "updated_at": now,
            "bootstrapped": True,
        }
    )
    save_state(root, state)
    return {
        "reason": reason,
        "from_id": from_id,
        "through_id": through_id,
        "tokens": chunk_tokens,
        "slice_rel": rel,
        "prompt": HARVEST_PROMPT,
    }
