"""MCP server for Claude Code / other MCP clients — no LLM API credits.

The host agent (e.g. Claude Code on a Pro/Max subscription) supplies the model.
This server only does filesystem wiki + harvest planning under MEMORY_ROOT.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from personahood_memory.harvest import load_state, plan_overflow, slice_text_for_job
from personahood_memory.transcript import load_messages
from personahood_memory.wiki import read_file, read_wiki_index, search_memory, update_memory_wiki


def _root() -> Path:
    raw = os.environ.get("MEMORY_ROOT") or os.environ.get("PH_MEMORY_ROOT") or "."
    return Path(raw).expanduser().resolve()


def build_mcp():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "personahood-memory",
        instructions=(
            "Durable markdown memory for this workspace. "
            "Use search_memory before inventing facts. "
            "Use update_memory_wiki with a parent path for durable notes. "
            "When harvest_status shows pending, read the slice and archive via update_memory_wiki "
            "(parent required), then the human can clear state with ph-memory harvest after tools succeed — "
            "or call harvest_complete after writing wiki pages."
        ),
    )

    @mcp.tool()
    def search_memory_tool(query: str) -> str:
        """Substring search over memory_wiki/*.md (trusted pages only)."""
        hits = search_memory(_root(), query)
        return "\n".join(hits) if hits else "no matches"

    @mcp.tool()
    def update_memory_wiki_tool(
        entry: str,
        title: str = "memory entry",
        parent: str = "memory_wiki/entries/workspace.md",
    ) -> str:
        """Create a memory_wiki/entries page linked to an existing parent."""
        try:
            return update_memory_wiki(
                _root(),
                entry=entry,
                title=title or "memory entry",
                parent=parent or None,
                parent_mandatory=False,
            )
        except ValueError as e:
            return f"error: {e}"

    @mcp.tool()
    def read_workspace_file(path: str) -> str:
        """Read a UTF-8 file under the memory workspace root."""
        try:
            return read_file(_root(), path)
        except (OSError, ValueError, FileNotFoundError) as e:
            return f"error: {e}"

    @mcp.tool()
    def memory_index() -> str:
        """Return memory_wiki/index.md (boot summary)."""
        return read_wiki_index(_root()) or "(empty index)"

    @mcp.tool()
    def harvest_status() -> str:
        """Show harvest watermark / pending slice info."""
        root = _root()
        state = load_state(root)
        pending = bool(state.get("pending"))
        out = {
            "root": str(root),
            "pending": pending,
            "last_harvested_message_id": state.get("last_harvested_message_id"),
            "pending_from_id": state.get("pending_from_id"),
            "pending_through_id": state.get("pending_through_id"),
            "pending_tokens": state.get("pending_tokens"),
            "slice_rel": state.get("slice_rel"),
        }
        if pending:
            out["slice_preview"] = slice_text_for_job(root)[:4000]
        return json.dumps(out, indent=2)

    @mcp.tool()
    def harvest_prepare(force: bool = False) -> str:
        """Plan overflow and write private_threads/harvest/pending.md if due.

        Does not call an LLM — Claude Code should read the slice and call
        update_memory_wiki, then harvest_complete.
        """
        root = _root()
        model_ctx = int(os.environ.get("PH_MEMORY_MODEL_CONTEXT", "128000"))
        max_live = int(os.environ.get("PH_MEMORY_MAX_LIVE", "250000"))
        snap = plan_overflow(
            root,
            load_messages(root),
            model_context_tokens=model_ctx,
            max_live_tokens=max_live,
            force=force,
        )
        if not snap:
            return json.dumps({"ok": True, "scheduled": False, "state": load_state(root)})
        return json.dumps({"ok": True, "scheduled": True, **snap}, indent=2)

    @mcp.tool()
    def harvest_complete(ok: bool = True) -> str:
        """Advance harvest watermark after you archived the pending slice into the wiki."""
        from personahood_memory.harvest import complete_harvest

        root = _root()
        state = load_state(root)
        through = state.get("pending_through_id")
        action = complete_harvest(
            root,
            through_id=int(through) if through is not None else None,
            ok=ok,
        )
        return json.dumps({"action": action, "state": load_state(root)}, indent=2)

    return mcp


def main() -> None:
    build_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
