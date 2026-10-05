"""The core without a face: a Town, its bus and its services, with no Textual app around them."""
from __future__ import annotations

from pathlib import Path

from orkcraft.core import buildings, bus, roads
from orkcraft.core.bus import Bus
from orkcraft.core.night import Night
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury
from orkcraft.realm import checkpoint
from orkcraft.scroll import road_key


def _town(repo: Path) -> tuple[Town, list]:
    town = Town(repo)
    seen: list = []
    town.bus.subscribe(bus.ANY, seen.append)
    return town, seen


def _topics(seen) -> list[str]:
    return [e.topic for e in seen]


def test_bus_delivers_to_a_topic_and_to_any_and_unsubscribes():
    b, got = Bus(), []
    off = b.subscribe("roads", lambda e: got.append(("roads", e.data)))
    b.subscribe(bus.ANY, lambda e: got.append(("any", e.topic)))
    b.publish("roads", why="test")
    off()
    b.publish("roads")
    assert got == [("roads", {"why": "test"}), ("any", "roads"), ("any", "roads")]


def test_a_town_loads_without_a_face_and_saves_its_scroll(fake_repo, isolated_layout_file):
    town, _ = _town(fake_repo)
    assert town.scroll.building("town_hall") is not None and town.building("loot") is not None
    assert town.title_of("town_hall").endswith("Town Hall")
    assert {"loot", "town_hall"} <= town.taken_ids()
    assert town.save() and isolated_layout_file.exists()


def test_raising_a_spec_and_laying_a_road_publish_what_changed(fake_repo):
    town, seen = _town(fake_repo)
    checkpoint.ensure(fake_repo)
    spec = buildings.type_spec(town, "fields")
    built = buildings.raise_spec(town, spec)
    assert built is not None and built.id in town.custom_specs and town.scroll.building(built.id) is not None

    choices = roads.choices(town, built.id, "loot")
    assert choices, "Task Fields send something the Loot can take"
    event, handler, _ = choices[0]
    road = roads.lay(town, "loot", built.id, event, handler)
    assert road is not None
    assert bus.ROADS in _topics(seen) and any(e.topic == bus.TOAST and "🛤" in e.data["message"] for e in seen)
    assert checkpoint.history(fake_repo, "loot", 1), "the road is a checkpoint in the camp's git"

    seen.clear()
    assert roads.remove(town, road_key("loot", road.id)) is not None
    assert town.scroll.building("loot").roads == [] and bus.ROADS in _topics(seen)


def test_a_refused_road_is_said_not_raised(fake_repo):
    town, seen = _town(fake_repo)
    assert roads.lay(town, "nowhere", "loot", "pit.file", None) is None
    assert [e.data["severity"] for e in seen if e.topic == bus.TOAST] == ["warning"]


def test_the_treasury_holds_the_purse_and_says_so_once(fake_repo):
    town, seen = _town(fake_repo)
    treasury = Treasury(town)
    town.scroll.budget.gold_session_limit_usd = 1.0
    assert not treasury.exhausted()
    town.snapshot.spent_usd = 2.0
    assert treasury.exhausted(quiet=True) and not seen
    assert treasury.exhausted() and _topics(seen) == [bus.TOAST]
    gold, level, lumber, _ = treasury.resources()
    assert gold.endswith("/ $1.00") and level and lumber.startswith("—")


def test_the_night_counts_its_hours(fake_repo):
    night = Night(Town(fake_repo))
    assert night.tick(quiet=True) is False and night.quiet_since
    night.elders_count = 3
    assert night.tick(quiet=False) is True
    night.morning()
    assert night.quiet_since is None and night.elders_count == 0
    assert night.next_change(quiet=False, level=3, exhausted=False) is None     # by day the orks wait


# -- deliveries and workers: a building's job with no view ---------------------------------------------

def _until(check, timeout: float = 5.0) -> bool:
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


def _typed(repo: Path, bid: str, type_id: str, **config) -> dict:
    from orkcraft.realm import masonry
    spec = {"id": bid, "title": bid.title(), "icon": "🏠", "orc": {"name": "Grunt"}, "type": type_id, "config": config}
    assert masonry.save_spec(repo, spec) == []
    return spec


def _sent(town: Town, monkeypatch) -> list:
    out: list = []
    monkeypatch.setattr(town.roads, "emit", lambda payload, meta=None: out.append(payload) or [])
    return out


def test_the_town_delivers_into_loot_and_reports_a_run(fake_repo):
    from orkcraft.realm import pipes
    from orkcraft.realm import roads as engine
    town, seen = _town(fake_repo)
    town.deliver("loot", pipes.Payload(pipes.TEXT, "# Found\n\nthings", "town_hall", "hall.audit_done", "Audit"))
    loot = next(e for e in seen if e.topic == bus.LOOT)
    assert Path(loot.data["path"]).read_text().count("things") == 1
    delivered = next(e for e in seen if e.topic == bus.DELIVERED)
    assert delivered.data["building"] == "loot" and not delivered.data["worker"]
    seen.clear()
    town.roads._on_run(engine.HandlerRun("loot", "seer", "agent", "r", 0, outcome="error", error="boom"))
    assert [e.topic for e in seen] == [bus.RUN] and seen[0].data["name"] == "seer"


def test_a_lake_worker_shows_edits_and_saves_without_a_view(fake_repo, monkeypatch):
    from orkcraft import scroll as ts
    from orkcraft.core.workers.lake import LakeWorker
    from orkcraft.realm import pipes
    _typed(fake_repo, "insight", "lake")
    town, seen = _town(fake_repo)
    ts.subscribe(town.scroll, "town_hall", "insight", "lake.viewed")
    ts.subscribe(town.scroll, "town_hall", "insight", "lake.saved")
    sent = _sent(town, monkeypatch)
    lake = town.worker("insight")
    assert isinstance(lake, LakeWorker) and town.worker("insight") is lake and lake.mini_status() == ["nothing shown"]
    assert not lake.open()                                              # nothing shown: nothing to edit

    town.deliver("insight", pipes.Payload(pipes.FILE, "README.md", "loot", "files.selected", "README.md"))
    assert next(e for e in seen if e.topic == bus.DELIVERED).data["worker"]
    assert _until(lambda: sent)                                          # looked at in a thread, then shown
    assert lake.view.kind == "markdown" and [p.mode for p in sent] == ["lake.viewed"]
    assert bus.WORKER in _topics(seen)

    readme = fake_repo / "README.md"
    assert lake.open() and lake.text == readme.read_text()
    lake.typed("> a note\n" + lake.text)
    assert lake.dirty and lake.edit_note == "● unsaved"
    assert lake.save() and readme.read_text().startswith("> a note\n") and lake.edit_note.startswith("saved")
    readme.write_text("someone else\n")
    assert not lake.save("mine\n") and lake.conflict and readme.read_text() == "someone else\n"
    assert not lake.close() and lake.editing                            # nothing is lost
    assert lake.save("mine\n", force=True) and lake.close(reload=False) and not lake.editing
    assert sent[-1].mode == "lake.saved" and sent[-1].value == "README.md"


def test_a_fields_worker_keeps_the_board_and_says_what_changed(fake_repo, monkeypatch):
    from orkcraft import scroll as ts
    from orkcraft.realm import pipes
    (fake_repo / "TASKS.md").write_text("## To Do\n- [ ] Buy milk\n## In Progress\n## Done\n")
    _typed(fake_repo, "todo", "fields", lanes=["Ideas"])
    town, seen = _town(fake_repo)
    for event in ("tasks.created", "tasks.status_changed", "notes.created", "tasks.sent"):
        ts.subscribe(town.scroll, "town_hall", "todo", event)
    sent = _sent(town, monkeypatch)
    fields = town.worker("todo")
    assert fields.mini_status() == ["To Do 1", "Doing 0", "Done 0"]
    assert [ln.id for ln in fields.visible_lanes()] == ["todo", "in_progress", "done", "ideas"]

    assert fields.add("Fix bike") is not None and fields.move("buy-milk", "in_progress")
    town.deliver("todo", pipes.Payload(pipes.TEXT, "# Release notes\n\nfor v0.2", "pit", "pit.text", ""), "",
                 "# Release notes\n\nfor v0.2")
    assert fields.card("release-notes").body == "for v0.2"
    assert fields.add("Dark mode", "ideas") is not None and fields.flip("dark-mode") == "todo"
    assert fields.send("fix-bike")
    assert [(p.mode, p.value.splitlines()[0]) for p in sent] == [
        ("tasks.created", "fix-bike"), ("tasks.status_changed", "buy-milk"), ("tasks.created", "release-notes"),
        ("notes.created", "Dark mode"), ("tasks.created", "dark-mode"), ("tasks.sent", "Fix bike")]
    sent.clear()
    (fake_repo / "TASKS.md").write_text((fake_repo / "TASKS.md").read_text().replace("## Done", "## Done\n- [x] Old"))
    fields.refresh()                                                    # a hand edit is seen on the next look
    assert [(p.mode, p.value) for p in sent] == [("tasks.created", "old")] and fields.mini_status()[2] == "Done 1 *"
    assert bus.WORKER in _topics(seen)


def test_a_scrolls_worker_runs_its_librarian_and_halts(fake_repo, monkeypatch):
    import threading
    from orkcraft import scroll as ts
    from orkcraft.core.workers.scrolls import ScrollsWorker
    from orkcraft.realm import pipes, wiki
    go = threading.Event()
    calls = []

    def librarian(harness, prompt, workdir, cancel, model, env, resume):
        calls.append(workdir)
        if not go.is_set() and cancel.wait(5):
            raise InterruptedError("stopped")
        (workdir / "pages" / "how-to" / "release.md").write_text("# Release\n\nTag it.\n")
        return "added a page", 0.01, 10, ""

    monkeypatch.setattr(ScrollsWorker, "work_runner", staticmethod(librarian))
    monkeypatch.setenv("ORKCRAFT_WIKI_AUTO", "0")
    _typed(fake_repo, "dump", "scrolls", sources=["docs"], commit=False)
    town, seen = _town(fake_repo)
    for event in ("wiki.updated", "knowledge.chunks"):
        ts.subscribe(town.scroll, "town_hall", "dump", event)
    sent = _sent(town, monkeypatch)
    dump = town.worker("dump")
    assert dump.status() == "NO WIKI" and dump.pending.new == ["docs/notes.md"]

    assert dump.ingest() and dump.running == "ingest" and not dump.ingest()   # one librarian at a time
    assert _until(lambda: len(calls) == 1)
    assert town.halt() == 1                                             # 🛑 stops it; the backlog waits

    def done() -> bool:                                                 # the librarian's thread has finished
        return not any(t.name == "wiki-ingest-dump" and t.is_alive() for t in threading.enumerate())

    assert _until(done) and not dump.running
    assert dump.log.read()[0].outcome == "interrupted" and dump.status() == "PENDING"
    assert any(e.topic == bus.RUN and e.data["run"].outcome == "interrupted" for e in seen)

    go.set()
    assert dump.ingest() and _until(done)
    assert dump.status() == "FRESH" and wiki.page_count(dump.pages) == 1 and sent[-1].mode == "wiki.updated"
    town.deliver("dump", pipes.Payload(pipes.TEXT, "how do we release?", "loot", "pit.text", "q"))
    assert sent[-1].mode == "knowledge.chunks" and "how do we release?" in sent[-1].value
