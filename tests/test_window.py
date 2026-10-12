from personahood_memory.window import (
    context_budget_tokens,
    estimate_tokens,
    fit_to_context,
    harvest_buffer_tokens,
    message_tokens,
)


def test_estimate_tokens():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2


def test_context_budget_respects_max_live():
    budget = context_budget_tokens(model_context_tokens=1_000_000, max_live_tokens=50_000)
    assert budget == 50_000


def test_harvest_buffer_clamped():
    assert harvest_buffer_tokens(32_000) == 4_000  # floor
    assert harvest_buffer_tokens(1_000_000) == 50_000  # ceiling


def test_fit_to_context_keeps_system_and_last():
    messages = [{"role": "system", "content": "sys"}]
    for i in range(20):
        messages.append({"role": "user", "content": "x" * 400})
        messages.append({"role": "assistant", "content": "y" * 400})
    messages.append({"role": "user", "content": "latest"})
    fitted = fit_to_context(
        messages, model_context_tokens=8_000, max_live_tokens=2_000
    )
    assert fitted[0]["role"] == "system"
    assert fitted[-1]["content"] == "latest"
    assert any("context compacted" in (m.get("content") or "") for m in fitted)
    # Compaction notice is appended after fitting and may slightly exceed the cap.
    total = sum(message_tokens(m) for m in fitted)
    assert total < sum(message_tokens(m) for m in messages)
    assert len(fitted) < len(messages)
