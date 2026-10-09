"""📚 Knowledge Base, 🗂 File Tree, 📥 Drop Zone (T1105 stage 6)."""
from __future__ import annotations

from pathlib import Path


from orkcraft.realm import shelves

SIZE = (200, 46)


def spec(bid: str, kind: str, **config) -> dict:
    return {"id": bid, "title": bid.title(), "icon": "📚", "orc": {"name": "Sage"}, "type": kind,
            **({"config": config} if config else {})}


def test_knowledge_scan_and_changes(fake_repo: Path):
    (fake_repo / "docs" / "guide.md").write_text("---\ntitle: The Guide\n---\n# Ignored H1\n## Setup\n## Usage\n")
    (fake_repo / "docs" / ".hidden").mkdir()
    (fake_repo / "docs" / ".hidden" / "x.md").write_text("# x")
    assert shelves.default_bases(fake_repo) == ["docs"]
    base = shelves.scan_base(fake_repo, "docs")
    by = {n.path: n for n in base.notes}
    assert set(by) == {"docs/guide.md", "docs/notes.md"}
    assert by["docs/guide.md"].title == "The Guide" and by["docs/guide.md"].headings == ["Setup", "Usage"]
    assert shelves.scan_base(fake_repo, "../x").error


def test_file_tree_changes_and_drops(fake_repo: Path, tmp_path: Path):
    assert shelves.top_entries(fake_repo) == ["docs/", "loot/", "src/", "README.md"]
    seen, fresh = shelves.file_changes(None, fake_repo, shelves.changed_files(fake_repo))
    assert fresh == []
    (fake_repo / "src" / "app.py").write_text("print('x')\n")
    seen, fresh = shelves.file_changes(seen, fake_repo, shelves.changed_files(fake_repo))
    assert fresh == ["src/app.py"]
    seen, fresh = shelves.file_changes(seen, fake_repo, shelves.changed_files(fake_repo))
    assert fresh == []
    spaced = tmp_path / "my file.txt"
    spaced.write_text("x")
    other = tmp_path / "b.txt"
    other.write_text("y")
    assert shelves.dropped_paths(f"'{spaced}' {other}") == [spaced.resolve(), other.resolve()]
    assert shelves.dropped_paths(str(spaced).replace(" ", "\\ ")) == [spaced.resolve()]
    assert shelves.dropped_paths(str(spaced)) == [spaced.resolve()]                  # bare, with a space
    assert shelves.dropped_paths(f"file://{str(spaced).replace(' ', '%20')}") == [spaced.resolve()]
    assert shelves.dropped_paths("/no/such/file") == []
