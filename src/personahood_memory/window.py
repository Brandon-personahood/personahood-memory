"""Token-budget context assembly (portable — no model catalog)."""

from __future__ import annotations

import os

DEFAULT_MODEL_CONTEXT_TOKENS = int(os.environ.get("MODEL_CONTEXT_TOKENS", "128000"))
CHARS_PER_TOKEN = 4
MESSAGE_OVERHEAD_TOKENS = 4
MIN_WINDOW_TOKENS = 4000
MAX_RESERVE_TOKENS = 32_000
MIN_RESERVE_TOKENS = 4_000
MAX_HARVEST_TOKENS = 50_000
MIN_HARVEST_TOKENS = 4_000
MAX_LIVE_CONTEXT_TOKENS = int(os.environ.get("MAX_LIVE_CONTEXT_TOKENS", "250000"))


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _content_token_estimate(content: str | list | None) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return estimate_tokens(content)
    total = 0
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype == "text":
            total += estimate_tokens(str(part.get("text") or ""))
        elif ptype == "image_url":
            total += 800
        else:
            total += estimate_tokens(str(part))
    return total


def message_tokens(m: dict) -> int:
    content = m.get("content")
    if isinstance(content, list):
        return _content_token_estimate(content) + MESSAGE_OVERHEAD_TOKENS
    return estimate_tokens(str(content or "")) + MESSAGE_OVERHEAD_TOKENS


def model_window_tokens(model_context_tokens: int | None = None) -> int:
    """Usable catalog window; fall back to env default when unset."""
    if model_context_tokens:
        return max(int(model_context_tokens), MIN_WINDOW_TOKENS)
    return max(DEFAULT_MODEL_CONTEXT_TOKENS, MIN_WINDOW_TOKENS)


def response_reserve_for_window(window: int) -> int:
    env = os.environ.get("MODEL_RESPONSE_RESERVE_TOKENS")
    if env:
        try:
            return max(int(env), 1)
        except ValueError:
            pass
    return max(MIN_RESERVE_TOKENS, min(MAX_RESERVE_TOKENS, window // 16))


def harvest_buffer_tokens(window: int) -> int:
    """~10% of the model window, clamped to 4k–50k."""
    return max(MIN_HARVEST_TOKENS, min(MAX_HARVEST_TOKENS, window // 10))


def context_budget_tokens(
    *,
    model_context_tokens: int | None = None,
    max_live_tokens: int | None = None,
    tier_context_chars: int = 0,
) -> int:
    """Usable input budget: window minus reserve, capped by max_live_tokens."""
    window = model_window_tokens(model_context_tokens)
    budget = max(window - response_reserve_for_window(window), 1000)
    cap = MAX_LIVE_CONTEXT_TOKENS if max_live_tokens is None else int(max_live_tokens)
    budget = min(budget, cap)
    if tier_context_chars and tier_context_chars > 0:
        budget = min(budget, max(tier_context_chars // CHARS_PER_TOKEN, 1000))
    return budget


def _compaction_notice(
    omitted: int, *, from_ts: str | None = None, to_ts: str | None = None
) -> dict:
    span = ""
    if from_ts and to_ts:
        span = f" (about {from_ts} → {to_ts})"
    return {
        "role": "system",
        "content": (
            f"[context compacted: {omitted} earlier message"
            f"{'s' if omitted != 1 else ''} from this conversation did not fit "
            f"the current model's context window{span}. They are not deleted. "
            "A silent memory-harvest archives leaving slices into memory_wiki "
            "(each new page must link to an existing parent page). "
            "Raw text: `private_threads/chat.jsonl` or "
            "`private_threads/harvest/pending.md` if a harvest is in flight. "
            "Long-term recall: search_memory.]"
        ),
    }


def fit_to_context(
    messages: list[dict],
    *,
    model_context_tokens: int | None = None,
    max_live_tokens: int | None = None,
    tier_context_chars: int = 0,
) -> list[dict]:
    """Keep system + latest user; fill remaining budget with newest history first."""
    if len(messages) <= 2:
        return messages

    budget = context_budget_tokens(
        model_context_tokens=model_context_tokens,
        max_live_tokens=max_live_tokens,
        tier_context_chars=tier_context_chars,
    )

    system = messages[0] if messages[0].get("role") == "system" else None
    last = messages[-1]
    middle = messages[1:-1] if system else messages[:-1]

    fixed = (message_tokens(system) if system else 0) + message_tokens(last)
    remaining = budget - fixed

    kept_reversed: list[dict] = []
    omitted = 0
    omitted_from = omitted_to = None
    for m in reversed(middle):
        cost = message_tokens(m)
        if cost > remaining:
            omitted = len(middle) - len(kept_reversed)
            dropped = middle[:omitted]
            omitted_from = _msg_ts(dropped[0]) if dropped else None
            omitted_to = _msg_ts(dropped[-1]) if dropped else None
            break
        remaining -= cost
        kept_reversed.append(m)

    result: list[dict] = []
    if system:
        result.append(system)
    if omitted:
        result.append(_compaction_notice(omitted, from_ts=omitted_from, to_ts=omitted_to))
    result.extend(reversed(kept_reversed))
    result.append(last)
    return result


def _msg_ts(m: dict) -> str | None:
    raw = m.get("created_at")
    if raw is None:
        return None
    text = str(raw)
    return text[:16].replace("T", " ") if len(text) >= 16 else text
