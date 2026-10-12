"""Thin OpenAI Chat Completions tool loop for memory tools."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from personahood_memory.wiki import read_file, search_memory, update_memory_wiki

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Substring search over memory_wiki/*.md (trusted pages only).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory_wiki",
            "description": (
                "Create a new memory_wiki/entries page. Prefer setting parent to an "
                "existing memory_wiki/*.md path (not index.md when other pages exist)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry": {"type": "string"},
                    "title": {"type": "string"},
                    "parent": {"type": "string"},
                },
                "required": ["entry"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file under the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


def dispatch_tool(
    root,
    name: str,
    arguments: dict,
    *,
    parent_mandatory: bool = False,
) -> str:
    if name == "search_memory":
        hits = search_memory(root, str(arguments.get("query") or ""))
        return "\n".join(hits) if hits else "no matches"
    if name == "update_memory_wiki":
        try:
            return update_memory_wiki(
                root,
                entry=str(arguments.get("entry") or ""),
                title=arguments.get("title"),
                parent=arguments.get("parent"),
                parent_mandatory=parent_mandatory,
            )
        except ValueError as e:
            return f"error: {e}"
    if name == "read_file":
        try:
            return read_file(root, str(arguments.get("path") or ""))
        except (OSError, ValueError, FileNotFoundError) as e:
            return f"error: {e}"
    return f"error: unknown tool {name}"


def run_chat_turn(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict],
    root,
    max_rounds: int = 8,
    parent_mandatory: bool = False,
    client: httpx.Client | None = None,
    on_tool: Callable[[str, dict, str], None] | None = None,
) -> dict[str, Any]:
    """Run until the model stops calling tools. Returns content + tools_used."""
    owns_client = client is None
    client = client or httpx.Client(timeout=180.0)
    tools_used: list[str] = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # OpenRouter recommends these; harmless elsewhere.
    if "openrouter.ai" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/personahood/personahood-memory"
        headers["X-Title"] = "personahood-memory"
    try:
        for _ in range(max_rounds):
            resp = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "tools": TOOL_DEFINITIONS,
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:800]}")
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                content = message.get("content") or ""
                return {
                    "content": content,
                    "tools_used": tools_used,
                    "usage": data.get("usage") or {},
                }
            messages.append(message)
            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = dispatch_tool(
                    root, name, args, parent_mandatory=parent_mandatory
                )
                tools_used.append(name)
                if on_tool:
                    on_tool(name, args, result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or name,
                        "content": result,
                    }
                )
        return {
            "content": "(stopped after max tool rounds)",
            "tools_used": tools_used,
            "usage": {},
        }
    finally:
        if owns_client:
            client.close()
