"""🌾 Task Fields, one board in three parts: the orks' tasks (a kanban), the person's own to-dos (a
checklist kept in the board's file, `## My to-dos`) and the notes; in the TUI and the GUI."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, lexicon, masonry, tasklist
from orkcraft.screens.typed.tasks_view import TasksView
from orkcraft.tui import silhouettes

BOARD = ("# Mine\n\n## To Do\n- [ ] Plan the release\n## In Progress\n- [ ] Write docs\n## Done\n\n"
         "## My to-dos\n- [ ] Call the bank\n  about the card\n- [x] Pay rent\n\n## Ideas\n- 🟨 Dark mode\n")
SPEC = {"id": "todo", "title": "Todo", "icon": "📋", "orc": {"name": "Smith"}, "type": "fields"}


def test_the_persons_to_dos_live_in_the_board_file(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text(BOARD, encoding="utf-8")
    tl = tasklist.TaskList(fake_repo)
    assert [ln.id for ln in tl.lanes()] == ["todo", "in_progress", "done", "mine", "ideas"]
    mine = [(t.id, t.checked, t.kind) for t in tl.load() if t.column == tasklist.MINE]
    assert mine == [("call-the-bank", False, "mine"), ("pay-rent", True, "mine")]
    assert tl.check("call-the-bank").checked and tl.check("pay-rent", False).checked is False
    tl.add("Book a dentist", tasklist.MINE)
    text = (fake_repo / "TASKS.md").read_text(encoding="utf-8")
    assert "## My to-dos\n- [x] Call the bank\n  about the card\n- [ ] Pay rent\n- [ ] Book a dentist" in text
    assert text.index("## Done") < text.index("## My to-dos") < text.index("## Ideas")       # the order is kept
    with pytest.raises(ValueError):
        tl.check("plan-the-release")                       # only a to-do is ticked off
    with pytest.raises(ValueError):
        tl.add_lane("My to-dos")                           # not a lane of notes
    # an idea becomes a to-do, unticked; a to-do becomes a task for the orks
    before = tl.load()
    tl.move("dark-mode", tasklist.MINE)
    tl.move("call-the-bank", "todo")
    after = tl.load()
    assert next(t for t in after if t.id == "dark-mode").kind == tasklist.MINE
    assert [(e, t.id) for e, t, _ in tasklist.changes(before, after)] == [("tasks.created", "call-the-bank")]


def test_a_tasks_folder_keeps_the_to_dos_in_mine(fake_repo: Path):
    (fake_repo / "tasks" / "todo").mkdir(parents=True)
    tl = tasklist.TaskList(fake_repo, "tasks")
    card = tl.add("Water the plants", tasklist.MINE)
    f = fake_repo / "tasks" / "mine" / f"{card.id}.md"
    assert f.exists() and [ln.id for ln in tl.lanes()][-1] == "mine"
    tl.check(card.id)
    assert "done: true" in f.read_text(encoding="utf-8")
    assert tl.load()[-1].checked and tl.load()[-1].title == "Water the plants"
    tl.check(card.id)
    assert "done: false" in f.read_text(encoding="utf-8") and not tl.load()[-1].checked


def test_the_gui_shows_three_parts_closed_and_open_and_ticks_off(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text(BOARD, encoding="utf-8")
    checkpoint.ensure(fake_repo)
    assert masonry.save_spec(fake_repo, SPEC) == []
    host = Host(fake_repo, auto_commit=False)
    host.town.worker("todo")
    host.tick()
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == "todo")["card"]
    assert [(ln["id"], ln["count"]) for ln in card["lanes"]] == [("todo", 1), ("in_progress", 1), ("done", 0)]
    assert card["lanes"][1]["top"] == ["Write docs"]
    assert card["todos"] == {"open": 1, "count": 2, "top": ["Call the bank"]}
    assert card["ideas"]["count"] == 1 and card["ideas"]["top"] == ["Dark mode"]
    data = host.detail("todo")["data"]
    assert [ln["id"] for ln in data["lanes"]] == ["todo", "in_progress", "done", "ideas"]    # the checklist is apart
    assert [(c["title"], c["done"]) for c in data["todos"]["cards"]] == [("Call the bank", False), ("Pay rent", True)]
    assert host.command("act", {"id": "todo", "act": "check", "args": {"card": "call-the-bank"}})
    assert host.command("act", {"id": "todo", "act": "mine", "args": {"card": "dark-mode"}})
    added = host.command("act", {"id": "todo", "act": "add", "args": {"lane": "mine", "title": "Renew passport"}})
    assert added == "renew-passport"
    todos = host.detail("todo")["data"]["todos"]["cards"]
    assert [(c["title"], c["done"]) for c in todos] == [("Dark mode", False), ("Renew passport", False),
                                                          ("Call the bank", True), ("Pay rent", True)]
    assert host.command("act", {"id": "todo", "act": "flip", "args": {"card": "renew-passport"}}) == "todo"


def test_tasks_and_notes_modes_keep_their_screens(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text(BOARD, encoding="utf-8")
    checkpoint.ensure(fake_repo)
    assert masonry.save_spec(fake_repo, dict(SPEC, config={"mode": "tasks"})) == []
    host = Host(fake_repo, auto_commit=False)
    host.town.worker("todo")
    assert host.detail("todo")["data"]["todos"] is None
    host.tick()
    assert next(b for b in host.snapshot()["buildings"] if b["id"] == "todo")["card"]["todos"] is None


def test_the_three_parts_say_todays_words():
    say = lexicon.words
    assert (say("Ork work"), say("My chores"), say("Scribbles")) == ("Ork work", "My to-dos", "Notes")
    assert say("New chore") == "New to-do" and say("Make it my chore") == "Make it my to-do"
    assert lexicon.term("chore", many=True) == "to-dos"


def test_the_hut_is_larger_than_a_hall():
    sil = silhouettes.FIELDS
    assert len(sil.live_widths) >= 8 and sil.width > silhouettes.BARRACKS.width


@pytest.mark.asyncio
async def test_the_tui_board_holds_the_checklist_and_ticks_it_off(fake_repo: Path, monkeypatch):
    (fake_repo / "TASKS.md").write_text(BOARD, encoding="utf-8")
    assert masonry.save_spec(fake_repo, SPEC) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "todo", "tasks.created")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("todo").query_one(TasksView)
        assert [ln.id for ln in view.all_lanes()] == ["todo", "in_progress", "done", "mine", "ideas"]
        assert view.query_one("#tasks-mine").parent.parent.id == "tasks-lower"
        lines = view.hut_lines([])
        assert lines[0] == "TODO 1 PROG 1 DONE 0" and lines[1] == "⚒ Write docs" and "My chores 1/2" in lines
        assert "☐ Call the bank" in lines and "Scribbles 1" in lines and "✎ Dark mode" in lines
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        lst = view.query_one("#tasks-mine")
        lst.focus()
        lst.highlighted = 0
        await pilot.press("x")                                  # ticked off
        await pilot.pause()
        assert view.card("call-the-bank").checked and not sent
        assert "- [x] Call the bank" in (fake_repo / "TASKS.md").read_text(encoding="utf-8")
        assert view.query_one("#tasks-label-mine").visual.plain == "☐ My to-dos · 0/2"  # today's words
        assert view.query_one("#tasks-label-ideas").visual.plain == "Ideas · 1"         # the file's own, as written
