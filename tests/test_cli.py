import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from personahood_memory.cli import main
from personahood_memory.layout import init_workspace


def test_cli_init_and_search(tmp_path: Path, monkeypatch):
    root = tmp_path / "ws"
    assert main(["--root", str(root), "init"]) == 0
    assert (root / "memory_wiki" / "index.md").is_file()

    from personahood_memory.wiki import update_memory_wiki

    update_memory_wiki(
        root,
        entry="Alpha project kickoff",
        title="Kickoff",
        parent="memory_wiki/entries/workspace.md",
    )
    assert main(["--root", str(root), "search", "kickoff"]) == 0


def test_cli_chat_mocked_openai(tmp_path: Path, monkeypatch):
    root = tmp_path / "chatws"
    init_workspace(root)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "update_memory_wiki",
                                "arguments": json.dumps(
                                    {
                                        "title": "Note",
                                        "entry": "User likes tea.",
                                        "parent": "memory_wiki/entries/workspace.md",
                                    }
                                ),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {},
    }
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Noted."}}],
        "usage": {},
    }

    with patch("personahood_memory.openai_loop.httpx.Client") as Client:
        client = Client.return_value
        client.post.side_effect = [mock_resp, mock_resp2]
        client.__enter__ = lambda s: s
        client.__exit__ = MagicMock(return_value=False)

        # Drive one chat turn via library path used by CLI
        from personahood_memory.openai_loop import run_chat_turn
        from personahood_memory.window import fit_to_context

        messages = fit_to_context(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "Remember I like tea."},
            ],
            model_context_tokens=128000,
        )
        result = run_chat_turn(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4.1-mini",
            messages=messages,
            root=root,
            client=client,
        )
        assert result["content"] == "Noted."
        assert "update_memory_wiki" in result["tools_used"]
        assert list((root / "memory_wiki" / "entries").glob("entry_*.md"))
