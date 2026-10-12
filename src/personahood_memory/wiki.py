"""Filesystem markdown wiki — search and update with parent links."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

UNSAFE_WIKI_ROOT = "memory_wiki/unsafe"
_RECENT_HEADING = "### Recent entries"
_RECENT_KEEP = 12


def is_unsafe_wiki_path(relative: str) -> bool:
    rel = relative.replace("\\", "/").lstrip("/")
    return rel == UNSAFE_WIKI_ROOT or rel.startswith(f"{UNSAFE_WIKI_ROOT}/")


def _normalize_rel(raw: str) -> str:
    rel = (raw or "").replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.lstrip("/")


def safe_path(root: Path, relative: str) -> Path:
    """Resolve *relative* under *root*; raise if it escapes the sandbox."""
    root = root.resolve()
    rel = _normalize_rel(relative)
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError(f"path escapes workspace: {relative}") from e
    return target


def existing_wiki_parents(root: Path) -> list[str]:
    wiki = root / "memory_wiki"
    if not wiki.is_dir():
        return []
    out = []
    for f in wiki.rglob("*.md"):
        rel = f.relative_to(root).as_posix()
        if f.name in ("index.md", "README.md"):
            continue
        if is_unsafe_wiki_path(rel):
            continue
        out.append(rel)
    return sorted(out)


def require_wiki_parent(
    root: Path,
    parent: str | None,
    *,
    mandatory: bool = False,
) -> str | None:
    """Return canonical parent rel, None if optional/ok without, or raise ValueError."""
    existing = existing_wiki_parents(root)
    rel = _normalize_rel(parent or "")
    if not rel:
        if not existing:
            return None
        if not mandatory:
            return None
        sample = ", ".join(existing[:8])
        extra = f" (e.g. {sample})" if sample else ""
        raise ValueError(f"parent is required — existing wiki page path{extra}")
    if rel == "memory_wiki/index.md":
        if existing and mandatory:
            raise ValueError("parent cannot be memory_wiki/index.md when other pages exist")
        return None
    if not rel.startswith("memory_wiki/") or not rel.endswith(".md"):
        raise ValueError("parent must be a memory_wiki/*.md path")
    if is_unsafe_wiki_path(rel):
        raise ValueError("parent cannot be an unsafe/quarantine path")
    if not (root / rel).is_file():
        raise ValueError(f"parent not found: {rel}")
    return rel


def append_parent_backlink(root: Path, parent_rel: str, child_rel: str, title: str) -> None:
    parent = root / parent_rel
    try:
        rel_link = Path(os.path.relpath(root / child_rel, parent.parent)).as_posix()
    except ValueError:
        rel_link = child_rel
    link = f"- [{title}]({rel_link})"
    prev = parent.read_text(encoding="utf-8") if parent.is_file() else ""
    if rel_link in prev and title in prev:
        return
    if "## See also" in prev:
        parent.write_text(prev.rstrip() + "\n" + link + "\n", encoding="utf-8")
    else:
        parent.write_text(prev.rstrip() + "\n\n## See also\n" + link + "\n", encoding="utf-8")


def record_wiki_catalog(root: Path, entry_rel: str, title: str, fname: str) -> None:
    now = datetime.now(timezone.utc)
    ym = now.strftime("%Y-%m")
    ledgers = root / "memory_wiki" / "ledgers"
    ledgers.mkdir(parents=True, exist_ok=True)
    month = ledgers / f"{ym}.md"
    href = Path(os.path.relpath(root / entry_rel, month.parent)).as_posix()
    line = f"- [{title}]({href})"
    if month.is_file():
        prev = month.read_text(encoding="utf-8")
        if href not in prev:
            month.write_text(prev.rstrip() + f"\n{line}\n", encoding="utf-8")
    else:
        month.write_text(
            f"# Entries — {ym}\n\n"
            f"Parent: [Dated entries](entries-{now.year}.md) · [wiki index](../index.md)\n\n"
            f"{line}\n",
            encoding="utf-8",
        )
    year_hub = ledgers / f"entries-{now.year}.md"
    month_link = f"- [{ym}]({ym}.md)"
    if year_hub.is_file():
        yprev = year_hub.read_text(encoding="utf-8")
        if f"]({ym}.md)" not in yprev:
            year_hub.write_text(yprev.rstrip() + f"\n{month_link}\n", encoding="utf-8")
    else:
        year_hub.write_text(
            f"# Dated entries — {now.year}\n\n"
            f"Parent: [wiki index](../index.md)\n\n{month_link}\n",
            encoding="utf-8",
        )

    idx = root / "memory_wiki" / "index.md"
    idx_prev = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
    recent_line = f"- [{title}](entries/{fname})"
    if _RECENT_HEADING in idx_prev:
        before, rest = idx_prev.split(_RECENT_HEADING, 1)
        body, _, after = rest.partition("\n### ")
        lines = [ln for ln in body.splitlines() if ln.startswith("- [")]
        lines = [recent_line] + [ln for ln in lines if ln != recent_line]
        lines = lines[:_RECENT_KEEP]
        rebuilt = before.rstrip() + f"\n\n{_RECENT_HEADING}\n" + "\n".join(lines) + "\n"
        if after:
            rebuilt += "\n### " + after
        idx.write_text(rebuilt, encoding="utf-8")
    else:
        idx.write_text(
            idx_prev.rstrip() + f"\n\n{_RECENT_HEADING}\n{recent_line}\n",
            encoding="utf-8",
        )


def search_memory(root: Path, query: str) -> list[str]:
    """Substring search over trusted memory_wiki/*.md (excludes unsafe/)."""
    q = (query or "").lower()
    hits: list[str] = []
    wiki = root / "memory_wiki"
    if not wiki.exists() or not q:
        return hits
    for f in wiki.rglob("*.md"):
        if f.name in ("index.md", "README.md"):
            continue
        rel = f.relative_to(root).as_posix()
        if is_unsafe_wiki_path(rel):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        if q in text.lower():
            hits.append(rel)
    return hits


def update_memory_wiki(
    root: Path,
    *,
    entry: str,
    title: str | None = None,
    parent: str | None = None,
    parent_mandatory: bool = False,
) -> str:
    """Write a new entry under memory_wiki/entries/. Returns relative path."""
    title = title or "memory entry"
    try:
        parent_rel = require_wiki_parent(root, parent, mandatory=parent_mandatory)
    except ValueError as e:
        raise ValueError(str(e)) from e

    wiki = root / "memory_wiki" / "entries"
    wiki.mkdir(parents=True, exist_ok=True)
    fname = f"entry_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    rel = f"memory_wiki/entries/{fname}"
    body = entry or ""
    if not body.lstrip().startswith("---"):
        fm = f"---\nrole: memory\ntitle: {title}\n"
        if parent_rel:
            fm += f"parent: {parent_rel}\n"
        body = fm + "---\n\n" + body
    if parent_rel and f"]({parent_rel})" not in body and parent_rel not in body:
        body = (
            body.rstrip()
            + f"\n\nParent: [{parent_rel}]("
            + Path(os.path.relpath(root / parent_rel, wiki)).as_posix()
            + ")\n"
        )
    safe_path(root, rel).write_text(body, encoding="utf-8")
    record_wiki_catalog(root, rel, title, fname)
    if parent_rel:
        append_parent_backlink(root, parent_rel, rel, title)
    return rel


def read_wiki_index(root: Path) -> str:
    path = root / "memory_wiki" / "index.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def read_file(root: Path, relative: str) -> str:
    """Read a UTF-8 file under the workspace (sandbox)."""
    target = safe_path(root, relative)
    if not target.is_file():
        raise FileNotFoundError(relative)
    return target.read_text(encoding="utf-8")
