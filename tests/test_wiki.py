from pathlib import Path

import pytest

from personahood_memory.layout import init_workspace
from personahood_memory.wiki import (
    require_wiki_parent,
    search_memory,
    update_memory_wiki,
)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return init_workspace(tmp_path)


def test_update_and_search(root: Path):
    rel = update_memory_wiki(
        root,
        entry="Chose Postgres for the API.",
        title="DB choice",
        parent="memory_wiki/entries/workspace.md",
    )
    assert rel.startswith("memory_wiki/entries/")
    assert (root / rel).is_file()
    hits = search_memory(root, "postgres")
    assert rel in hits
    idx = (root / "memory_wiki" / "index.md").read_text(encoding="utf-8")
    assert "DB choice" in idx
    parent = (root / "memory_wiki" / "entries" / "workspace.md").read_text(encoding="utf-8")
    assert "See also" in parent


def test_parent_mandatory_for_harvest(root: Path):
    with pytest.raises(ValueError, match="parent is required"):
        require_wiki_parent(root, None, mandatory=True)


def test_first_parent_optional_when_empty(tmp_path: Path):
    # Empty wiki (no seed pages)
    wiki = tmp_path / "memory_wiki" / "entries"
    wiki.mkdir(parents=True)
    (tmp_path / "memory_wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
    assert require_wiki_parent(tmp_path, None, mandatory=True) is None
