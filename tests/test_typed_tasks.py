"""📋 Tasks (T1105 stage 6): three columns in TASKS.md or a tasks folder, moves send events."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft.realm import tasklist

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
