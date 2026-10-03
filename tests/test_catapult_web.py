"""🎯 The Catapult's browser mode: scout a form, plan the fields, write fill.py, fill and press."""
from __future__ import annotations

import asyncio
import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, catapult as cp, catapult_web as cw, masonry, pipes
from orkcraft.screens.typed.catapult_view import CatapultView

FORM_BODY = """<form onsubmit="event.preventDefault(); document.title = 'saved ' +
  JSON.stringify(Object.fromEntries(new FormData(this)))">
  <label for="ev-name">Event name</label><input id="ev-name" name="name" required>
  <label>Description <textarea name="description"></textarea></label>
  <input name="start_date" type="date" aria-label="Start date">
  <select name="type" aria-label="Event type"><option>Major update</option><option>Live event</option></select>
  <label><input type="checkbox" name="notify"> Notify players</label>
  <fieldset><legend>Priority</legend>
    <label><input type="radio" name="prio" value="lo"> Low</label>
    <label><input type="radio" name="prio" value="hi"> High</label></fieldset>
  <input type="hidden" name="csrf" value="x">
  <button type="submit">Save draft</button>
</form>"""
FORM = "<!doctype html><title>New event</title>" + FORM_BODY
HOME = '<!doctype html><title>Console</title><a href="events.html">Events</a>'
# A single-page app: the form appears on a click, the address stays the same.
EVENTS = ("<!doctype html><title>Events</title><button id=create>Create event</button><div id=slot></div>"
          "<script>document.getElementById('create').onclick = () => document.getElementById('slot').innerHTML = "
          + json.dumps(FORM_BODY) + "</script>")

MAP = {"url": "https://play.example.com/events/new", "title": "New event",
       "fields": [{"kind": "text", "label": "Event name", "name": "name", "id": "ev-name", "selector": "#ev-name",
                   "options": [], "required": True},
                  {"kind": "textarea", "label": "Description", "name": "description", "id": "",
                   "selector": "textarea[name=\"description\"]", "options": [], "required": False},
                  {"kind": "date", "label": "Start date", "name": "start_date", "id": "",
                   "selector": "input[name=\"start_date\"]", "options": [], "required": False},
                  {"kind": "select", "label": "Event type", "name": "type", "id": "", "selector": "select",
                   "options": ["Major update", "Live event"], "required": False}],
       "buttons": [{"text": "Save draft", "selector": "button"}]}


@pytest.fixture
def site(tmp_path: Path):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "new.html").write_text(FORM, encoding="utf-8")
    (tmp_path / "www" / "index.html").write_text(HOME, encoding="utf-8")
    (tmp_path / "www" / "events.html").write_text(EVENTS, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "www"))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/new.html"
    server.shutdown()


def test_plan_matches_settings_model_and_names():
    keys = ["title", "description", "schedule.start_date", "kind", "extra"]
    p = cw.plan(MAP, keys, ['Event name = title', 'Event type = "Live event"', "Nope = x"], {"2": "schedule.start_date"})
    got = {s.label: (s.path, s.literal, s.by) for s in p.steps}
    assert got["Event name"] == ("title", None, "settings")
    assert got["Event type"] == ("", "Live event", "settings")
    assert got["Start date"] == ("schedule.start_date", None, "model")
    assert got["Description"] == ("description", None, "name")
    assert p.unused == ["kind", "extra"] and p.unfilled == [] and "'Nope'" in p.problems[0]
    assert cw.plan(MAP, ["kind"]).unfilled == ["Event name"]          # required and nothing fills it
    body = {"title": "Halloween", "description": "Spooky", "schedule": {"start_date": "2026-10-31"}}
    text = cw.describe(p, body)
    assert "Event name" in text and "'Halloween'" in text and "not used: kind, extra" in text


def test_leaves_pick_and_rules():
    body = {"a": {"b": 1, "c": [1, 2]}, "items": [{"x": "y"}]}
    assert cw.leaves(body) == {"a.b": 1, "a.c": [1, 2], "items.0.x": "y"}
    assert cw.pick(body, "items.0.x") == "y" and cw.pick(body, "a.zz") is None
    assert cw.schema_paths({"properties": {"t": {}, "s": {"properties": {"d": {}}}}}) == ["t", "s.d"]
    rules, errors = cw.parse_rules(["A = b.c", "B = 'text'", "nothing"])
    assert rules == [("A", "b.c", None), ("B", None, "text")] and len(errors) == 1


def test_the_model_maps_fields_in_any_language():
    ru = dict(MAP, fields=[dict(f, label=lbl) for f, lbl in zip(MAP["fields"], ["Название", "Описание", "Дата", "Тип"])])
    prompts = []

    def runner(prompt):
        prompts.append(prompt)
        return 'Sure: {"0": "title", "1": "description", "3": "nope", "9": "title"}', 0.001

    mapping, cost = cw.map_with_model(ru, {"title": "Halloween", "description": "Spooky"}, runner)
    assert mapping == {"0": "title", "1": "description"} and cost == 0.001 and "'Название'" in prompts[0]
    assert {s.label for s in cw.plan(ru, ["title", "description"], [], mapping).steps} == {"Название", "Описание"}


def test_settings_are_checked():
    spec = {"id": "c", "title": "C", "type": "catapult",
            "config": {"mode": "browser", "page": "file:///etc", "fields": ["bad"], "finish": "press"}}
    errors = catalog.validate(spec)
    text = "\n".join(errors)
    assert "page must be an http" in text and "fields:" in text and "press needs submit" in text


def test_a_script_edited_by_hand_is_kept(tmp_path: Path):
    p = cw.plan(MAP, ["name"])
    first = cw.write_script(tmp_path, cw.script_text(MAP, p))
    assert first.name == "fill.py" and not cw.edited_by_hand(tmp_path)
    compile(first.read_text(encoding="utf-8"), "fill.py", "exec")
    first.write_text(first.read_text(encoding="utf-8") + "\n# mine\n", encoding="utf-8")
    assert cw.edited_by_hand(tmp_path)
    again = cw.write_script(tmp_path, cw.script_text(MAP, p, "Save draft", "press"))
    assert again.name == "fill.new.py" and "# mine" in first.read_text(encoding="utf-8")


def test_form_shot_says_what_happened():
    res = cw.Result(True, 0, {"filled": ["Event name"], "missed": [], "pressed": True, "url": "u", "title": "ok"}, "")
    shot = cp.form_shot("u0", {"a": 1}, res, True)
    assert shot.ok and "pressed — u" in shot.answer and "Event name" in shot.answer
    bad = cp.form_shot("u0", {}, cw.Result(False, 2, {"filled": [], "missed": ["X: no value"]}, ""), False)
    assert not bad.ok and "missed: X: no value" in bad.answer and bad.error == "X: no value"
    some = cp.form_shot("u0", {}, cw.Result(False, 2, {"filled": ["A"], "missed": ["X: no value"]}, ""), False)
    assert some.error == "some fields were not filled"
    assert cp.form_shot("u0", {}, cw.Result(True, 0, {"pressed": False}, ""), True).error == "not pressed"


playwright = pytest.importorskip("playwright.sync_api")


def _can_launch() -> bool:
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


needs_browser = pytest.mark.skipif(not _can_launch(), reason="no Chromium for Playwright here")


@needs_browser
def test_scout_marks_the_form_and_fill_presses_it(site: str, tmp_path: Path):
    page_map = cw.scout(site, tmp_path / "profile", watch=False, headless=True)
    by = {f["label"]: f for f in page_map["fields"]}
    assert set(by) == {"Event name", "Description", "Start date", "Event type", "Notify players", "Priority"}
    assert by["Event name"]["required"] and by["Event name"]["selector"] == "#ev-name"
    assert by["Event type"]["options"] == ["Major update", "Live event"]
    assert by["Priority"]["kind"] == "radio" and by["Priority"]["options"] == ["Low", "High"]
    assert "Save draft" in [b["text"] for b in page_map["buttons"]]
    body = {"name": "Halloween", "description": "Spooky", "start_date": "2026-10-31", "type": "Live event",
            "notify": True, "priority": "High"}
    p = cw.plan(page_map, list(cw.leaves(body)))
    assert len(p.steps) == 6 and not p.unused
    script = cw.write_script(tmp_path / "state", cw.script_text(page_map, p, "Save draft", "press"))
    res = cw.run_script(script, tmp_path / "profile", body, press=True, headless=True, timeout=90)
    assert res.ok, (res.err, res.out)
    saved = json.loads(res.summary["title"][len("saved "):])
    assert saved == {"name": "Halloween", "description": "Spooky", "start_date": "2026-10-31", "type": "Live event",
                     "notify": "on", "prio": "hi", "csrf": "x"}
    assert res.summary["pressed"] and len(res.summary["filled"]) == 6
    handed = cw.run_script(script, tmp_path / "profile", {"name": "x"}, press=False, headless=True, timeout=90)
    assert handed.code == 2 and not handed.summary["pressed"] and handed.summary["filled"] == ["Event name"]


def test_the_path_to_the_form_starts_at_the_last_page_load():
    events = [("load", 1, "https://c/login"), ("click", 2, {"role": "button", "name": "Sign in"}),
              ("load", 3, "https://c/home"), ("click", 4, {"role": "link", "name": "Events", "selector": "a"}),
              ("click", 5, {"role": "button", "name": "Create event"}), ("click", 9, {"name": "Save"})]
    start, path = cw.path_to_form(events, 6, "https://c/")
    assert start == "https://c/home" and [c["name"] for c in path] == ["Events", "Create event"]
    assert cw.path_text({"path": path}) == "Events → Create event"


@needs_browser
def test_scout_remembers_the_clicks_and_fill_repeats_them(site: str, tmp_path: Path):
    home = site.replace("new.html", "index.html")

    def operator(page, tick):
        if tick == 0:
            page.get_by_role("link", name="Events").click()
        elif tick == 1:
            page.get_by_role("button", name="Create event").click()
        elif tick == 3:
            page.close()

    page_map = cw.scout(home, tmp_path / "profile", watch=True, headless=True, driver=operator, limit_s=30)
    assert page_map["url"].endswith("/events.html") and page_map["start"].endswith("/events.html")
    assert page_map["path"] == [{"role": "button", "name": "Create event", "selector": "#create"}]
    body = {"name": "Halloween", "description": "Spooky"}
    p = cw.plan(page_map, list(cw.leaves(body)))
    script = cw.write_script(tmp_path / "state", cw.script_text(page_map, p, "Save draft", "press"))
    assert "'Create event'" in script.read_text(encoding="utf-8")
    res = cw.run_script(script, tmp_path / "profile", body, press=True, headless=True, timeout=90)
    assert res.ok, (res.err, res.out)
    assert json.loads(res.summary["title"][len("saved "):])["name"] == "Halloween"
    lost = dict(page_map, path=[{"role": "button", "name": "No such button", "selector": "#nope"}])
    script = cw.write_script(tmp_path / "lost", cw.script_text(lost, p, "Save draft", "press"))
    res = cw.run_script(script, tmp_path / "profile", body, press=True, headless=True, timeout=120)
    assert res.code == 3 and "No such button" in res.summary["broken"][0]
    assert res.summary["page"]["url"].endswith("/events.html")       # where it broke, for the overseer


@needs_browser
@pytest.mark.asyncio
async def test_the_catapult_scouts_and_fills_in_browser_mode(site: str, fake_repo: Path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_HEADLESS", "1")
    spec = {"id": "play", "title": "Play events", "icon": "🎯", "orc": {"name": "Loader"}, "type": "catapult",
            "config": {"mode": "browser", "page": site, "submit": "Save draft", "finish": "press",
                       "fields": ["Event name = title"]}}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "play", "catapult.sent")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("play").query_one(CatapultView)
        view.quick_action("catapult.scout")
        for _ in range(200):
            await pilot.pause(0.05)
            if not view.busy:
                break
        assert cw.load_map(view.state_dir) and (view.state_dir / "fill.py").exists()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("play", pipes.Payload(pipes.TEXT, '{"title": "Halloween", "description": "Spooky"}',
                                                  "pit", "pit.text", "x"))
        for _ in range(1800):
            await pilot.pause(0.05)
            if sent:
                break
        assert [p.mode for p in sent] == ["catapult.sent"], view.shots[0] if view.shots else None
        assert view.shots[0].ok and "pressed" in view.shots[0].answer and "saved" in view.shots[0].answer
        assert not view.load.items                          # unloaded after a good shot
        assert view.profile == fake_repo / ".orkcraft" / "catapult" / "play" / "profile"   # outside the camp's git


@pytest.mark.asyncio
async def test_the_demo_only_dry_runs_a_form(fake_repo: Path, tmp_path: Path):
    spec = {"id": "play", "title": "Play events", "icon": "🎯", "orc": {"name": "Loader"}, "type": "catapult",
            "config": {"mode": "browser", "page": "https://play.example.com/events/new"}}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False, demo=True)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("play").query_one(CatapultView)
        cw.save_map(view.state_dir, MAP)
        app.deliver_payload("play", pipes.Payload(pipes.TEXT, '{"name": "Halloween"}', "pit", "pit.text", "x"))
        await pilot.pause()
        assert view.shots[0].dry and "Event name" in view.shots[0].answer and "'Halloween'" in view.shots[0].answer


def test_a_repair_stays_on_the_site_and_keeps_old_names():
    answer = {"note": "renamed", "start": "https://evil.example/", "path": [], "fields": {"0": {"label": "Title"}}}
    assert cw.apply_repair(MAP, answer, "Save draft")[0] is None                  # another site: refused
    fixed, submit, note, problems = cw.apply_repair(MAP, dict(answer, start=MAP["url"], submit="Save"), "Save draft")
    assert not problems and submit == "Save" and note == "renamed"
    assert fixed["fields"][0]["label"] == "Title" and fixed["fields"][0]["aka"] == ["Event name"]
    assert MAP["fields"][0]["label"] == "Event name"                             # the old map is untouched
    assert [s.label for s in cw.plan(fixed, ["title"], ["Event name = title"]).steps] == ["Title"]
    assert cw.apply_repair(MAP, {"fields": {"0": {"kind": "rocket"}}}, "")[3]
    assert cw.apply_repair(MAP, None, "")[3] == ["the answer is not one JSON object"]


def _renamed(site_dir: Path) -> None:
    """The site changes: the button and the field get new names, the field a new id."""
    events = (site_dir / "events.html").read_text(encoding="utf-8")
    events = events.replace(">Create event<", ">New event<").replace("id=create", "id=add")
    events = events.replace("getElementById('create')", "getElementById('add')")
    events = events.replace('for=\\"ev-name\\">Event name<', 'for=\\"ev-title\\">Title<').replace('id=\\"ev-name\\"', 'id=\\"ev-title\\"')
    (site_dir / "events.html").write_text(events, encoding="utf-8")


REPAIRED = {"note": "the button is now New event, the name field is Title", "path": [
    {"role": "button", "name": "New event", "selector": "#add"}],
    "fields": {"0": {"label": "Title", "selector": "#ev-title", "kind": "text"}}}


@needs_browser
def test_the_overseer_repairs_a_broken_script(site: str, tmp_path: Path):
    events = site.replace("new.html", "events.html")
    page_map = cw.scout(events, tmp_path / "profile", watch=True, headless=True, limit_s=30,
                        driver=lambda page, tick: page.get_by_role("button", name="Create event").click()
                        if tick == 0 else page.close() if tick == 2 else None)
    state, body = tmp_path / "state", {"name": "Halloween", "description": "Spooky"}
    rules = ["Event name = name"]
    plan_of = lambda m: cw.plan(m, list(cw.leaves(body)), rules)        # noqa: E731
    script = cw.write_script(state, cw.script_text(page_map, plan_of(page_map), "Save draft", "press"))
    _renamed(tmp_path / "www")
    res = cw.run_script(script, tmp_path / "profile", body, press=True, headless=True, timeout=120)
    assert res.code == 3 and "Create event" in res.summary["broken"][0]
    assert "New event" in [b["text"] for b in res.summary["page"]["buttons"]]
    prompts, answers = [], iter([{"path": "nope"}, REPAIRED])
    runner = lambda prompt: prompts.append(prompt) or (json.dumps(next(answers)), 0.01)   # noqa: E731
    r = cw.repair(state, page_map, plan_of, "Save draft", "press", res.summary["broken"], res.summary["page"],
                  tmp_path / "profile", "Loader", runner=runner)
    assert r.ok and r.attempts == 2 and r.cost == 0.02 and "'New event'" in prompts[0]
    assert "YOUR PREVIOUS REPAIR DID NOT WORK" in prompts[1]
    assert cw.load_map(state)["repaired"]["by"] == "Loader"
    res = cw.run_script(state / "fill.py", tmp_path / "profile", body, press=True, headless=True, timeout=120)
    assert res.ok, (res.err, res.out)
    assert json.loads(res.summary["title"][len("saved "):])["name"] == "Halloween"
    before = (state / "fill.py").read_text(encoding="utf-8")
    bad = cw.repair(state, cw.load_map(state), plan_of, "Save draft", "press", ["x"], {}, tmp_path / "profile",
                    runner=lambda prompt: (json.dumps({"path": [{"name": "Nothing like it"}]}), None))
    assert not bad.ok and bad.attempts == 2 and (state / "fill.py").read_text(encoding="utf-8") == before


@needs_browser
@pytest.mark.asyncio
async def test_the_catapult_calls_its_overseer_and_fires_again(site: str, tmp_path: Path, fake_repo: Path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_HEADLESS", "1")
    events = site.replace("new.html", "events.html")
    spec = {"id": "play", "title": "Play events", "icon": "🎯", "orc": {"name": "Gruk"}, "type": "catapult",
            "config": {"mode": "browser", "page": events, "submit": "Save draft", "finish": "press",
                       "fields": ["Event name = title"]}}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setattr(CatapultView, "repair_runner", staticmethod(lambda prompt: (json.dumps(REPAIRED), 0.03)))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for event in ("catapult.repaired", "catapult.sent", "catapult.failed"):
        ts.subscribe(app.scroll, "town_hall", "play", event)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("play").query_one(CatapultView)
        state = view.state_dir
        page_map = await asyncio.to_thread(
            cw.scout, events, view.profile, watch=True, headless=True, limit_s=30,
            driver=lambda page, tick: page.get_by_role("button", name="Create event").click()
            if tick == 0 else page.close() if tick == 2 else None)
        cw.save_map(state, page_map)
        view.write_script()
        _renamed(tmp_path / "www")
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("play", pipes.Payload(pipes.TEXT, '{"title": "Halloween"}', "pit", "pit.text", "x"))
        for _ in range(1800):
            await pilot.pause(0.1)
            if "catapult.sent" in [p.mode for p in sent] or "catapult.failed" in [p.mode for p in sent]:
                break
        assert [p.mode for p in sent] == ["catapult.repaired", "catapult.sent"], [p.value for p in sent]
        assert "Gruk: the button is now New event" in sent[0].value
        assert view.shots[0].ok and "pressed" in view.shots[0].answer and view.shots[1].error.startswith("broken")
