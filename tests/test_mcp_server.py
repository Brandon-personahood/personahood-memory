from pathlib import Path

import pytest

from personahood_memory.layout import init_workspace


pytest.importorskip("mcp")


def test_build_mcp_tools(tmp_path: Path, monkeypatch):
    root = init_workspace(tmp_path)
    monkeypatch.setenv("MEMORY_ROOT", str(root))
    from personahood_memory.mcp_server import build_mcp

    mcp = build_mcp()
    # FastMCP keeps tools in _tool_manager
    names = set(mcp._tool_manager._tools.keys())  # noqa: SLF001
    assert "search_memory_tool" in names
    assert "update_memory_wiki_tool" in names
    assert "harvest_status" in names
