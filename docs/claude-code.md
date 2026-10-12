# Claude Code + personahood-memory (subscription, no API credits)

## Idea

- **Claude Code** (logged in with Claude Pro / Max) is the chat agent and the LLM.
- **personahood-memory MCP** only touches the filesystem wiki + harvest planning.
- No OpenAI / OpenRouter / Anthropic **API** key is required for normal use.

Billing note: Claude Code uses your **subscription** when authenticated via
`claude login` / OAuth. If `ANTHROPIC_API_KEY` is set in the environment, Claude Code
**prefers the API key and bills API credits** — unset it for subscription-only use.
Check with `/status` inside Claude Code.

## Setup

```bash
cd ph-memory
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[mcp]"
ph-memory init ../workspaces/my-agent
```

### Project `.mcp.json` (recommended)

Copy [`examples/claude-code.mcp.json`](../examples/claude-code.mcp.json) to your
project root (or merge into an existing `.mcp.json`), then edit paths:

```json
{
  "mcpServers": {
    "personahood-memory": {
      "command": "python",
      "args": ["-m", "personahood_memory.mcp_server"],
      "env": {
        "MEMORY_ROOT": "/absolute/path/to/workspaces/my-agent"
      }
    }
  }
}
```

Use the same Python that has `personahood-memory` installed (venv `python` path
is safest). On Windows, point `command` at `.venv\\Scripts\\python.exe`.

Restart Claude Code / reconnect MCP (`/mcp`). You should see tools such as
`search_memory_tool`, `update_memory_wiki_tool`, `harvest_status`, etc.

### Optional CLAUDE.md snippet

Add to the project (or agent workspace) so Claude prefers the wiki:

```markdown
## Long-term memory

This project uses the personahood-memory MCP.
- Before inventing durable facts, call search_memory_tool.
- To save lasting notes, call update_memory_wiki_tool with parent
  `memory_wiki/entries/workspace.md` (or a better existing parent).
- Periodically call harvest_status; if pending, read the slice, archive with
  update_memory_wiki_tool (parents required), then harvest_complete.
```

## Harvest without API credits

`ph-memory harvest` normally calls an LLM via OpenAI-compatible HTTP.
Under Claude Code you can avoid that:

1. `harvest_prepare` (or let chat append to `chat.jsonl` via a small helper later)
2. Claude reads `harvest_status` / the pending slice
3. Claude writes wiki pages with `update_memory_wiki_tool`
4. `harvest_complete`

Today the interactive `ph-memory chat` transcript is separate from Claude Code’s
own conversation. For full harvest-from-Claude-chat, either:

- paste/import important turns into `private_threads/chat.jsonl`, or
- treat Claude’s session as ephemeral and put durables only in the wiki (simplest).

## Verify subscription mode

In Claude Code:

```
/status
```

Confirm auth is subscription / OAuth, not an Anthropic API key. Then ask Claude to
search memory for a known imported fact.

## Codex (same pattern)

Codex can shell out to `ph-memory` CLI or run the same MCP server if/when MCP is
supported in your Codex setup. The library API is identical.
