"""📋 Tasks (T1105 stage 6): three columns in TASKS.md or a tasks folder, moves send events."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, tasklist
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.tasks_view import TasksView

SIZE = (200, 46)
SPEC = {"id": "todo", "title": "Todo", "icon": "📋", "orc": {"name": "Smith"}, "type": "tasks"}


def test_a_markdown_file(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text("# My tasks\n\n## To Do\n- [ ] Buy milk\n- Buy milk\n\n## Doing\n"
                                        "- [ ] Write report\n\n## Notes\n- not a task\n\n## Done\n- [x] Call mom\n")
    tl = tasklist.TaskList(fake_repo)
    tasks = tl.load()
    assert [(t.id, t.column) for t in tasks] == [("buy-milk", "todo"), ("buy-milk-2", "todo"),
                                                  ("write-report", "in_progress"), ("call-mom", "done")]
    new = tl.add("  Fix   the bike ")
    assert (new.title, new.column) == ("Fix the bike", "todo")
    assert tl.move("write-report", "done") == ("in_progress", "done")
    text = (fake_repo / "TASKS.md").read_text()
    assert text.startswith("# My tasks") and "- [x] Write report" in text and "## In Progress" in text
    tl.rename("call-mom", "Call dad")
    assert "Call dad" in [t.title for t in tl.load()]
    before = tasks
    assert ("tasks.status_changed", "write-report") in [(e, t.id) for e, t, _ in tasklist.changes(before, tl.load())]
    with pytest.raises(ValueError):
        tasklist.TaskList(fake_repo, "../elsewhere.md")


def test_a_tasks_folder_like_a_metagraph(fake_repo: Path):
    base = fake_repo / "tasks"
    (base / "todo").mkdir(parents=True)
    (base / "in-progress").mkdir()
    (base / "todo" / "T1001.md").write_text("---\nid: T1001\ntitle: \"Ship it\"\nstatus: todo\n---\n\n# Ship it\n")
    tl = tasklist.TaskList(fake_repo, "tasks")
    assert [(t.id, t.title, t.column) for t in tl.load()] == [("T1001", "Ship it", "todo")]
    tl.move("T1001", "in_progress")
    moved = (base / "in-progress" / "T1001.md").read_text()
    assert "status: in-progress" in moved and not (base / "todo" / "T1001.md").exists()
    t = tl.add("Write docs")
    assert (base / "todo" / f"{t.id}.md").exists()
    tl.rename("T1001", "Ship it now")
    assert "# Ship it now" in (base / "in-progress" / "T1001.md").read_text()


@pytest.mark.asyncio
async def test_the_tasks_building_adds_moves_and_sends(fake_repo: Path, monkeypatch):
    (fake_repo / "TASKS.md").write_text("## To Do\n- [ ] Buy milk\n## In Progress\n## Done\n")
    assert masonry.save_spec(fake_repo, SPEC) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "todo", "tasks.status_changed")
    ts.subscribe(app.scroll, "loot", "todo", "tasks.created")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("todo").query_one(TasksView)
        assert view.mini_status() == ["To Do 1", "Doing 0", "Done 0"]
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.desktop.focus_window(app.desktop.get_window("todo"))
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"Fix bike", "enter")
        await pilot.pause()
        assert [t.title for t in view.tasks if t.column == "todo"] == ["Buy milk", "Fix bike"]
        view.query_one("#tasks-todo").focus()
        view.query_one("#tasks-todo").highlighted = 0
        await pilot.press("greater_than_sign")
        await pilot.pause()
        assert next(t for t in view.tasks if t.id == "buy-milk").column == "in_progress"
        assert [(p.kind, p.mode, p.value) for p in sent] == [("node", "tasks.created", "fix-bike"),
                                                             ("node", "tasks.status_changed", "buy-milk")]
        assert "⚒ Buy milk" in view.mini_status()
        # a hand edit of the file is seen on the next look, with a * on the hut
        (fake_repo / "TASKS.md").write_text((fake_repo / "TASKS.md").read_text().replace("## Done", "## Done\n- [x] Old"))
        sent.clear()
        view.refresh_data()
        assert [(p.mode, p.value) for p in sent] == [("tasks.created", "old")]
        assert view.mini_status()[2] == "Done 1 *"
        assert view.quick_action("tasks.new")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
