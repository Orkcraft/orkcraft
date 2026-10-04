"""📋 Tasks (T1105 stage 6): three columns in TASKS.md or a tasks folder, moves send events."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes, tasklist
from orkcraft.screens.dialogs import TextBlock, TextPrompt
from orkcraft.screens.typed.tasks_view import TasksView

SIZE = (200, 46)
SPEC = {"id": "todo", "title": "Todo", "icon": "📋", "orc": {"name": "Smith"}, "type": "tasks"}


def test_a_markdown_file(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text("# My tasks\n\n## To Do\n- [ ] Buy milk\n- Buy milk\n\n## Doing\n"
                                        "- [ ] Write report\n\n## Notes\n- not a task\n\n## Done\n- [x] Call mom\n")
    tl = tasklist.TaskList(fake_repo)
    tasks = tl.tasks()
    assert [(t.id, t.column) for t in tasks] == [("buy-milk", "todo"), ("buy-milk-2", "todo"),
                                                  ("write-report", "in_progress"), ("call-mom", "done")]
    assert [(t.id, t.kind) for t in tl.load() if t.column == "notes"] == [("not-a-task", "note")]   # a sticker
    new = tl.add("  Fix   the bike ")
    assert (new.title, new.column) == ("Fix the bike", "todo")
    assert tl.move("write-report", "done") == ("in_progress", "done")
    text = (fake_repo / "TASKS.md").read_text()
    assert text.startswith("# My tasks") and "- [x] Write report" in text and "## In Progress" in text
    assert "## Notes\n- not a task" in text                          # writing keeps the lanes of notes
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


def test_cards_have_text_colour_and_lanes_of_notes(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text("# Board\n\nSome words about the board.\n\n## To Do\n- [ ] Ship it\n"
                                        "  with the changelog\n  - and the tag\n## Ideas\n- 🟨 Dark mode\n"
                                        "  people ask for it\n## Done\n")
    tl = tasklist.TaskList(fake_repo)
    cards = {t.id: t for t in tl.load()}
    assert cards["ship-it"].body == "with the changelog\n- and the tag" and cards["ship-it"].kind == "task"
    idea = cards["dark-mode"]                                   # the colour is not part of the id
    assert (idea.kind, idea.color, idea.column, idea.body) == ("note", "🟨", "ideas", "people ask for it")
    assert [ln.id for ln in tl.lanes()] == ["todo", "in_progress", "done", "ideas"]

    assert tasklist.next_color(idea.title) == "🟩 Dark mode" and tasklist.next_color("🟪 x") == "x"
    tl.edit("dark-mode", tasklist.next_color(idea.title), "people ask for it\nand it is cheap")
    tl.move("dark-mode", "todo")                                # a note moved into a status lane is a task
    tl.add("Retro questions", "questions", "what went well?")   # a new lane of notes is made
    text = (fake_repo / "TASKS.md").read_text()
    assert text.startswith("# Board\n\nSome words about the board.")
    assert "- [ ] 🟩 Dark mode\n  people ask for it\n  and it is cheap" in text
    assert "## Ideas" in text and "## Questions\n- Retro questions\n  what went well?" in text
    after = tl.load()
    assert [e for e, *_ in tasklist.changes(list(cards.values()), after)] == ["tasks.created", "notes.created"]
    tl.remove("ship-it")
    assert "ship-it" not in [t.id for t in tl.load()] and "Ship it" not in (fake_repo / "TASKS.md").read_text()


def test_a_folder_board_keeps_notes_in_subfolders(fake_repo: Path):
    base = fake_repo / "tasks"
    (base / "todo").mkdir(parents=True)
    (base / "todo" / "T1.md").write_text("---\ntitle: \"Ship it\"\nstatus: todo\n---\n\n# Ship it\n\nThe details.\n")
    tl = tasklist.TaskList(fake_repo, "tasks")
    note = tl.add("Dark mode", "ideas", "people ask")
    assert (base / "ideas" / "dark-mode.md").exists() and note.kind == "note"
    assert [ln.id for ln in tl.lanes()][-1] == "ideas"
    cards = {t.id: t for t in tl.load()}
    assert cards["T1"].body == "The details." and cards["dark-mode"].body == "people ask"
    tl.edit("T1", body="New details.")
    assert (base / "todo" / "T1.md").read_text().endswith("# Ship it\n\nNew details.\n")
    tl.move("T1", "ideas")                                      # a task becomes a note: its status goes
    assert "status: note" in (base / "ideas" / "T1.md").read_text()
    tl.remove("dark-mode")
    assert not (base / "ideas" / "dark-mode.md").exists()


@pytest.mark.asyncio
async def test_the_board_adds_notes_flips_colours_and_sends(fake_repo: Path, monkeypatch):
    (fake_repo / "TASKS.md").write_text("## To Do\n- [ ] Buy milk\n## In Progress\n## Done\n")
    spec = dict(SPEC, config={"lanes": ["Ideas"]})
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for event in ("tasks.created", "notes.created", "tasks.sent", "tasks.status_changed"):
        ts.subscribe(app.scroll, "town_hall", "todo", event)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("todo").query_one(TasksView)
        assert [ln.id for ln in view.visible_lanes()] == ["todo", "in_progress", "done", "ideas"]
        assert view.query_one("#tasks-ideas")                 # the lane is on the board before any note
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        view.add("Dark mode", "ideas", "people ask for it")
        await pilot.pause()
        assert [(p.mode, p.title, p.ref) for p in sent] == [("notes.created", "Dark mode", "todo:dark-mode")]
        assert "🗒 1 note" in view.mini_status()[-1] and view.tasks == [view.card("buy-milk")]

        lst = view.query_one("#tasks-ideas")
        lst.focus()
        lst.highlighted = 0
        await pilot.press("c")                                  # a colour
        await pilot.pause()
        assert view.card("dark-mode").color == "🟨"
        sent.clear()
        await pilot.press("s")                                  # sent down the roads as it is
        await pilot.pause()
        assert [(p.mode, p.value) for p in sent] == [("tasks.sent", "Dark mode\n\npeople ask for it")]
        sent.clear()
        await pilot.press("t")                                  # the note becomes a task in To Do
        await pilot.pause()
        assert view.card("dark-mode").column == "todo" and [p.mode for p in sent] == ["tasks.created"]

        sent.clear()
        app.deliver_payload("todo", pipes.Payload(pipes.TEXT, "# Release notes\n\nwrite them for v0.2", "pit",
                                                  "pit.text", ""), "", "# Release notes\n\nwrite them for v0.2")
        await pilot.pause()
        card = view.card("release-notes")
        assert card is not None and (card.column, card.body) == ("todo", "write them for v0.2")

        view.query_one("#tasks-todo").focus()
        view.query_one("#tasks-todo").highlighted = 0
        await pilot.press("e")                                  # the card in full
        await pilot.pause()
        assert isinstance(app.screen, TextBlock)
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_the_modes_show_a_kanban_or_a_wall(fake_repo: Path):
    (fake_repo / "TASKS.md").write_text("## To Do\n- [ ] Buy milk\n## Ideas\n- Dark mode\n## Done\n")
    for mode, lanes in (("tasks", ["todo", "in_progress", "done"]), ("notes", ["ideas"])):
        assert masonry.save_spec(fake_repo, dict(SPEC, id=f"b_{mode}", config={"mode": mode})) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        kanban = app.desktop.get_window("b_tasks").query_one(TasksView)
        wall = app.desktop.get_window("b_notes").query_one(TasksView)
        assert [ln.id for ln in kanban.visible_lanes()] == ["todo", "in_progress", "done"]
        assert [ln.id for ln in wall.visible_lanes()] == ["ideas"]
        assert wall.mini_status()[0] == "🗒 1 note" and "🗒" not in " ".join(kanban.mini_status())
        wall.receive(pipes.Payload(pipes.TEXT, "Ask about pricing", "pit", "pit.text", ""), "", "")
        assert [t.title for t in wall.notes] == ["Dark mode", "Ask about pricing"]   # a cart is a note here
