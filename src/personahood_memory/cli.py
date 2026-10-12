"""ph-memory — local CLI harness for the portable memory library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from personahood_memory import __version__
from personahood_memory.config import load_settings
from personahood_memory.harvest import (
    HARVEST_PROMPT,
    complete_harvest,
    harvest_tools_succeeded,
    load_state,
    plan_overflow,
    slice_text_for_job,
)
from personahood_memory.layout import init_workspace
from personahood_memory.openai_loop import run_chat_turn
from personahood_memory.transcript import append_message, history_dicts, load_messages
from personahood_memory.wiki import read_wiki_index, search_memory
from personahood_memory.window import fit_to_context


def _root_arg(ns: argparse.Namespace) -> Path:
    return Path(ns.root).expanduser().resolve()


def cmd_init(ns: argparse.Namespace) -> int:
    root = _root_arg(ns)
    init_workspace(root, force=ns.force)
    print(f"Initialized memory workspace at {root}")
    return 0


def cmd_search(ns: argparse.Namespace) -> int:
    root = _root_arg(ns)
    hits = search_memory(root, ns.query)
    if not hits:
        print("no matches")
        return 0
    print("\n".join(hits))
    return 0


def cmd_harvest(ns: argparse.Namespace) -> int:
    root = _root_arg(ns)
    settings = load_settings(root, model=ns.model)
    rows = load_messages(root)
    snap = plan_overflow(
        root,
        rows,
        model_context_tokens=settings.model_context_tokens,
        max_live_tokens=settings.max_live_tokens,
        force=ns.force,
    )
    if not snap:
        state = load_state(root)
        print(
            "No harvest slice pending "
            f"(wm={state.get('last_harvested_message_id')}, pending={state.get('pending')})"
        )
        return 0
    print(
        f"Pending harvest: {snap['tokens']} tok, ids {snap['from_id']}-{snap['through_id']} "
        f"({snap['reason']})"
    )
    if ns.dry_run:
        return 0
    auth_err = settings.require_inference_auth()
    if auth_err:
        print(f"{auth_err} Slice written; fix auth and re-run harvest.", file=sys.stderr)
        return 1

    index = read_wiki_index(root)
    if len(index) > 40_000:
        index = index[:40_000] + "\n\n[... index truncated ...]\n"
    slice_text = slice_text_for_job(root, snap.get("slice_rel"))
    prompt = HARVEST_PROMPT + "\n\n" + (slice_text or "(empty slice)")
    system = (
        "# Memory harvest job\n"
        "Archive the conversation slice into memory_wiki using update_memory_wiki. "
        "Pick parent pages from the index. Do not roleplay — call tools.\n\n"
        f"# Memory wiki index\n{index}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    def on_tool(name: str, _args: dict, result: str) -> None:
        print(f"  tool {name} -> {result[:120]}")

    result = run_chat_turn(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.model,
        messages=messages,
        root=root,
        parent_mandatory=True,
        on_tool=on_tool,
    )
    ok = harvest_tools_succeeded(result.get("tools_used"))
    action = complete_harvest(root, through_id=snap["through_id"], ok=ok)
    print(f"harvest_ok={ok} action={action} tools={result.get('tools_used')}")
    if result.get("content"):
        print(result["content"][:500])
    return 0 if ok else 2


def _build_system(root: Path) -> str:
    identity = ""
    id_path = root / "core_identity.md"
    if id_path.is_file():
        identity = id_path.read_text(encoding="utf-8")
    index = read_wiki_index(root)
    return (
        f"# Core Identity\n{identity}\n\n"
        f"# Memory wiki index\n{index}\n\n"
        "# Tools\n"
        "Long-term memory is in memory_wiki/. Use search_memory and update_memory_wiki. "
        "New pages should set parent to an existing memory_wiki/*.md path when possible.\n"
    )


def cmd_chat(ns: argparse.Namespace) -> int:
    root = _root_arg(ns)
    if not (root / "memory_wiki" / "index.md").is_file():
        init_workspace(root)
        print(f"(auto-initialized {root})")
    settings = load_settings(root, model=ns.model)
    auth_err = settings.require_inference_auth()
    if auth_err:
        print(auth_err, file=sys.stderr)
        return 1

    print(
        f"ph-memory {__version__} · {root} · model={settings.model} · "
        f"endpoint={settings.openai_base_url}"
    )
    print("Type a message, or /quit. Tools: search_memory, update_memory_wiki, read_file.\n")

    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user:
            continue
        if user in ("/quit", "/exit", ":q"):
            return 0
        if user == "/harvest":
            ns.force = True
            ns.dry_run = False
            cmd_harvest(ns)
            continue

        append_message(root, "user", user)
        history = history_dicts(root)
        # Drop the just-appended user from middle; rebuild with system + hist + user
        prior = history[:-1] if history and history[-1]["role"] == "user" else history
        messages = [{"role": "system", "content": _build_system(root)}]
        messages.extend(prior)
        messages.append({"role": "user", "content": user})
        messages = fit_to_context(
            messages,
            model_context_tokens=settings.model_context_tokens,
            max_live_tokens=settings.max_live_tokens,
        )

        def on_tool(name: str, args: dict, result: str) -> None:
            preview = json.dumps(args)[:80]
            print(f"  [{name} {preview}] -> {result[:100]}")

        try:
            result = run_chat_turn(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.model,
                messages=messages,
                root=root,
                on_tool=on_tool,
            )
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            continue

        content = (result.get("content") or "").strip() or "(empty reply)"
        append_message(root, "assistant", content)
        print(f"assistant> {content}\n")

        # Opportunistic harvest scheduling (slice only; archive via /harvest or next force)
        plan_overflow(
            root,
            load_messages(root),
            model_context_tokens=settings.model_context_tokens,
            max_live_tokens=settings.max_live_tokens,
            force=False,
        )
        state = load_state(root)
        if state.get("pending") and not state.get("pending_enqueued_at"):
            print(
                f"(harvest pending: {state.get('pending_tokens')} tok — "
                "run `ph-memory harvest` or /harvest)\n"
            )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ph-memory",
        description="Portable Personahood memory wiki + local OpenAI chat harness.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--root",
        default=".",
        help="Workspace directory (default: cwd)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Scaffold a memory workspace")
    init_p.add_argument("dir", nargs="?", default=None, help="Target directory (sets --root)")
    init_p.add_argument("--force", action="store_true", help="Overwrite seed files")
    init_p.set_defaults(func=cmd_init)

    search_p = sub.add_parser("search", help="Substring search memory_wiki")
    search_p.add_argument("query")
    search_p.set_defaults(func=cmd_search)

    harvest_p = sub.add_parser("harvest", help="Plan and/or run a memory harvest")
    harvest_p.add_argument("--force", action="store_true", help="Harvest even small overflow")
    harvest_p.add_argument("--dry-run", action="store_true", help="Write/plan slice only")
    harvest_p.add_argument("--model", default=None)
    harvest_p.set_defaults(func=cmd_harvest)

    chat_p = sub.add_parser("chat", help="Interactive chat with OpenAI + memory tools")
    chat_p.add_argument("--model", default=None)
    chat_p.set_defaults(func=cmd_chat)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if getattr(ns, "dir", None):
        ns.root = ns.dir
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
