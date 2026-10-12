from pathlib import Path

from personahood_memory.harvest import (
    apply_harvest_completion,
    bootstrap_watermark,
    harvest_plan,
    harvest_tools_succeeded,
    plan_overflow,
    select_harvest_chunk,
    select_overflow,
)
from personahood_memory.layout import init_workspace
from personahood_memory.protocols import MessageRow
from personahood_memory.transcript import append_message, load_messages


def _rows(n: int, chars: int = 200) -> list[MessageRow]:
    body = "x" * chars
    return [MessageRow(id=i + 1, role="user" if i % 2 == 0 else "assistant", content=body) for i in range(n)]


def test_harvest_plan_injects_window():
    plan = harvest_plan(model_context_tokens=100_000, max_live_tokens=20_000)
    assert plan["window_tokens"] == 100_000
    assert plan["live_input_tokens"] == 20_000
    assert plan["harvest_buffer_tokens"] == 10_000


def test_select_overflow_and_chunk():
    rows = _rows(40, chars=400)
    overflow = select_overflow(rows, live_tokens=500)
    assert overflow
    chunk, tokens = select_harvest_chunk(overflow, harvest_tokens=300, force=True)
    assert chunk
    assert tokens > 0


def test_bootstrap_watermark():
    rows = _rows(10, chars=40)
    wm = bootstrap_watermark(rows, live_tokens=10_000)
    assert wm == 0 or wm < rows[-1].id


def test_apply_completion_retry_then_success():
    state = {"pending": True, "pending_through_id": 9, "pending_attempts": 0}
    state, action = apply_harvest_completion(state, through_id=9, ok=False)
    assert action == "retry"
    assert state["pending_attempts"] == 1
    state, action = apply_harvest_completion(state, through_id=9, ok=True)
    assert action == "success"
    assert state["pending"] is False
    assert state["last_harvested_message_id"] == 9


def test_harvest_tools_succeeded():
    assert harvest_tools_succeeded(["search_memory", "update_memory_wiki"])
    assert not harvest_tools_succeeded(["search_memory"])


def test_plan_overflow_writes_slice(tmp_path: Path):
    root = init_workspace(tmp_path)
    for i in range(20):
        append_message(root, "user" if i % 2 == 0 else "assistant", "word " * 80)
    # First pass bootstraps the watermark (live window not yet due).
    snap = plan_overflow(
        root,
        load_messages(root),
        model_context_tokens=8_000,
        max_live_tokens=400,
        force=False,
    )
    assert snap is None
    # Grow past the live window so overflow appears.
    for i in range(30):
        append_message(root, "user" if i % 2 == 0 else "assistant", "word " * 80)
    snap = plan_overflow(
        root,
        load_messages(root),
        model_context_tokens=8_000,
        max_live_tokens=400,
        force=True,
    )
    assert snap is not None
    assert (root / snap["slice_rel"]).is_file()
