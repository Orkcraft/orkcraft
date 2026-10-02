"""📚 Knowledge Base, 🗂 File Tree, 📥 Drop Zone (T1105 stage 6)."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual import events

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, shelves
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.pit_view import PitView
from orkcraft.screens.typed.files_view import FilesView
from orkcraft.screens.typed.knowledge_view import KnowledgeView

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
    before = {n.path: n.mtime for n in base.notes}
    assert shelves.note_changes(None, [base]) == []
    (fake_repo / "docs" / "new.md").write_text("# New")
    assert shelves.note_changes(before, [shelves.scan_base(fake_repo, "docs")]) == ["docs/new.md"]
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


@pytest.mark.asyncio
async def test_the_three_buildings(fake_repo: Path, tmp_path: Path, monkeypatch):
    for s in (spec("kb", "knowledge"), spec("tree", "file_tree", path="src"), spec("inbox2", "dropzone")):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for src, ev in (("kb", "knowledge.changed"), ("tree", "files.changed"), ("inbox2", "drop.file")):
        ts.subscribe(app.scroll, "town_hall", src, ev)
    opened = []
    monkeypatch.setattr(FilesView, "opener", staticmethod(opened.append))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])

        kb = app.desktop.get_window("kb").query_one(KnowledgeView)
        assert kb.mini_status() == ["1 docs"]
        (fake_repo / "docs" / "more.md").write_text("# More\n## Part\n")
        kb.refresh_data()
        assert [(p.kind, p.mode, p.value) for p in sent] == [("file", "knowledge.changed", "docs/more.md")]
        (fake_repo / "wiki").mkdir()
        (fake_repo / "wiki" / "a.md").write_text("# A")
        assert kb.quick_action("knowledge.add")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"wiki", "enter")
        await pilot.pause()
        assert kb.paths == ["docs", "wiki"] and app.custom_specs["kb"]["config"]["paths"] == ["docs", "wiki"]
        kb.read("docs/more.md")

        tree = app.desktop.get_window("tree").query_one(FilesView)
        assert tree.mini_status() == ["nothing changed", "app.py"]
        sent.clear()
        (fake_repo / "src" / "app.py").write_text("print('changed')\n")
        tree.refresh_data()
        assert [(p.mode, p.value) for p in sent] == [("files.changed", "src/app.py")]
        assert tree.mini_status()[0] == "1 changed"
        assert tree.quick_action("files.open") and opened[0][-1] == str(fake_repo / "src")

        drop = app.desktop.get_window("inbox2").query_one(PitView)
        dropped = tmp_path / "report.pdf"
        dropped.write_bytes(b"%PDF")
        sent.clear()
        app.focus_state.mode, app.focus_state.building_id = "building", "inbox2"   # the Drop Zone selected
        app.post_message(events.Paste(f"'{dropped}'"))                             # a file dragged onto it
        await pilot.pause()
        [p] = sent                                             # from outside: copied into the pit
        assert (p.kind, p.mode) == ("file", "drop.file") and p.value.startswith(".orkcraft/pit/")
        assert (fake_repo / p.value).read_bytes() == b"%PDF" and drop.mini_status()[0].endswith("report.pdf")
        inside = fake_repo / "docs" / "notes.md"
        assert drop.drop(str(inside)) == 1 and sent[-1].value == "docs/notes.md"
