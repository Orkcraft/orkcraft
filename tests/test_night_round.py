"""🌙 The Night round (docs/design/night-round.md): the boards' stewards look over the work at night — the
cards that lie get a 🌙 when a commit or a wiki page is about them, a light model says what is new or trims
the mark, the day's code gives a few cleanup ideas as notes, and the Weekly retro sees THE WORK."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from orkcraft.core import buildings, retros, runners
from orkcraft.core.workers import scrolls
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, fastpath, growth, nightround, tasklist, weekly


# -- the rules, alone -----------------------------------------------------------------------------------

def test_a_commit_is_a_card_s_when_they_share_its_words():
    found = [nightround.Commit("a1", "Export form: validate the dates", ("src/export_form.py",)),
             nightround.Commit("b2", "Bump the version", ("orkcraft/__init__.py",)),
             nightround.Commit("c3", "Банк: новая форма карты", ())]
    assert [c.sha for c in nightround.theirs("Fix the export form when dates are empty", found)] == ["a1"]
    assert [c.sha for c in nightround.theirs("Позвонить в банк про карту", found)] == ["c3"]   # by the word's start
    assert nightround.theirs("Release", found) == []
    assert [c.sha for c in nightround.theirs("Version", found)] == ["b2"]          # one word that counts: one is enough


def test_only_the_cards_that_lie_are_looked_at():
    cards = [tasklist.Task("a", "A", "todo"), tasklist.Task("b", "B", "in_progress"), tasklist.Task("c", "C", "done"),
             tasklist.Task("d", "D", "mine"), tasklist.Task("e", "E", "mine", checked=True), tasklist.Task("f", "F", "ideas")]
    assert [c.id for c in nightround.lying(cards)] == ["a", "d"]


def test_the_model_s_words_or_nothing():
    assert nightround.parse_news("NOTHING") == "" and nightround.parse_news("nothing.") == ""
    assert nightround.parse_news("  The form was fixed in a1;\n it may be done.  ") == "The form was fixed in a1; it may be done."
    have = ["Remove the old exporter"]
    data = {"ideas": [{"title": "Remove the old exporter", "why": "dup"}, {"title": "Test the date check", "why": "new code",
                                                                          "file": "src/export_form.py"},
                      {"title": ""}, "junk", {"title": "Rename fmt()"}, {"title": "One more"}]}
    got = nightround.parse_ideas(data, 2, have)
    assert [i["title"] for i in got] == ["Test the date check", "Rename fmt()"]
    assert nightround.idea_body(got[0]).endswith("`src/export_form.py`\n🌙 from the night round")


def test_ideas_nobody_takes_make_the_round_quiet(tmp_path):
    now = dt.datetime(2026, 10, 8, 4, 40)
    assert nightround.ideas_cap(tmp_path) == 3
    nightround.keep_ideas(tmp_path, "tasks", [f"k{i}" for i in range(7)], "ideas", now)
    nightround.settle_ideas(tmp_path, {"tasks": {f"k{i}": "ideas" for i in range(4, 7)}}, now)   # k0–k3 deleted
    assert nightround.ideas_cap(tmp_path) == 1
    nightround.settle_ideas(tmp_path, {"tasks": {"k4": "ideas", "k5": "ideas"}}, now + dt.timedelta(minutes=1))
    nightround.settle_ideas(tmp_path, {"tasks": {"k4": "ideas"}}, now + dt.timedelta(minutes=2))
    assert nightround.ideas_cap(tmp_path) == 0                                    # six in a row: none
    nightround.settle_ideas(tmp_path, {"tasks": {"k4": "todo"}}, now + dt.timedelta(minutes=3))   # one taken
    assert nightround.ideas_cap(tmp_path) == 3
    assert [i["status"] for i in nightround.ideas(tmp_path)].count("taken") == 1


def test_the_night_in_one_line():
    night = nightround.Night("2026-10-08T04:40:00", ["tasks"], commits=3, news=1, ideas=2, calls=2)
    assert nightround.summary(night) == "1 card has news, 2 cleanup ideas"
    assert nightround.said(night) == "2026-10-08 04:40: 1 card has news, 2 cleanup ideas · 2 model calls."
    assert nightround.said(nightround.Night("2026-10-08T04:40:00", skipped="nothing changed since the last round")) \
        == "2026-10-08 04:40: nothing changed since the last round."
    assert nightround.summary(nightround.Night("x", commits=2), paused=True) == "no ideas: the last six were deleted"


# -- one night on a board -------------------------------------------------------------------------------

def _commit(repo: Path, path: str, text: str, message: str) -> None:
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", path], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


class Model:
    """A fake light model: a card's words (or NOTHING for the bank), the ideas as JSON."""
    def __init__(self) -> None:
        self.asked: list[str] = []

    def __call__(self, prompt: str):
        self.asked.append(prompt)
        if "cleanup" in prompt:
            return json.dumps({"ideas": [{"title": "Test the date check", "why": "the new check has no test",
                                          "file": "src/export_form.py"}]}), 0.01
        if "банк" in prompt.lower():
            return "NOTHING", 0.0
        return "The export form now checks dates (a1); the card may be done.", 0.0


@pytest.fixture
def night(fake_repo, monkeypatch):
    monkeypatch.setattr(scrolls, "SETTLE_S", 3600)
    page = fake_repo / "llm-wiki" / "general" / "pages" / "export.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Export\n\nThe export form writes CSV.\n", encoding="utf-8")
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    kb = _raised(host, "scrolls", sources=[])
    host.town.worker(kb).refresh()
    bid = _raised(host, "fields")
    model = Model()
    monkeypatch.setattr(runners, "ROUND_RUNNER", model)
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda p: ("Title", 0.0))
    return host, bid, model


def _act(host, bid, act, **args):
    return host.command("act", {"id": bid, "act": act, "args": args})


def _cards(host, bid) -> dict:
    data = host.detail(bid)["data"]
    cards = [c for ln in data["lanes"] for c in ln["cards"]] + data["todos"]["cards"]
    return {c["title"]: {**c, "lane": next((ln["id"] for ln in data["lanes"] if c in ln["cards"]), "mine")} for c in cards}


def _run(host, now):
    work = retros.round_job(host.town, now, force=True)
    if work is not None:
        retros.round_done(host.town, work())


def test_a_night_marks_the_cards_that_lie_and_adds_ideas(night, fake_repo):
    host, bid, model = night
    _act(host, bid, "add", lane="todo", title="Fix the export form dates")
    _act(host, bid, "add", lane="mine", title="Позвонить в банк про карту")
    _act(host, bid, "add", lane="mine", title="Export form dates for the accountant")
    host.command("act", {"id": bid, "act": "private", "args": {"card": "export-form-dates-for-the-accountant"}})
    _act(host, bid, "add", lane="in_progress", title="Export form rework")            # an ork works it: not lying
    nightround.mark_run(fake_repo, dt.datetime.now() - dt.timedelta(hours=1))
    _commit(fake_repo, "src/export_form.py", "def check(d): return d\n", "Export form: validate the dates")
    _commit(fake_repo, "src/bank.py", "CARD = 1\n", "Банк: форма карты")
    _run(host, dt.datetime.now())

    cards = _cards(host, bid)
    news = cards["Fix the export form dates"]["news"]
    assert news["words"].startswith("The export form now checks dates")
    assert [s for _, s in news["commits"]] == ["Export form: validate the dates"]
    assert cards["Позвонить в банк про карту"]["news"] is None                 # the model trimmed it: NOTHING
    assert cards["Export form dates for the accountant"]["news"]["words"] == ""      # personal: the rules' mark, no model
    assert not any("accountant" in p.lower() for p in model.asked)
    assert cards["Export form rework"]["news"] is None
    idea = cards["Test the date check"]
    assert idea["lane"] == "ideas" and idea["idea"] and idea["kind"] == "note"
    assert "src/export_form.py" in idea["body"]
    assert sum("cleanup" in p for p in model.asked) == 1
    said = [n for n in growth.news(fake_repo) if n.kind == "round"]
    assert [n.text for n in said] == ["Night round: 2 cards have news, 1 cleanup idea"]
    assert said[0].building == bid and said[0].tab == "work" and said[0].icon == "🌙"
    last = nightround.nights(fake_repo)[-1]
    assert (last.commits, last.news, last.told, last.ideas, last.calls) == (3, 2, 1, 1, 3)        # the project's first commit is within the hour too
    sent = (fake_repo / ".orkcraft" / "fields" / bid / "sent.jsonl").read_text(encoding="utf-8")
    assert "night-round" in sent and "export" not in sent.lower().split('"card"')[0]

    # Seen takes the 🌙 off
    _act(host, bid, "news_seen", card="fix-the-export-form-dates")
    assert _cards(host, bid)["Fix the export form dates"]["news"] is None

    # the next night: nothing changed — no model at all, the night is written down as skipped
    model.asked.clear()
    _run(host, dt.datetime.now() + dt.timedelta(minutes=1))
    assert model.asked == []
    assert nightround.nights(fake_repo)[-1].skipped == "nothing changed since the last round"
    assert len([n for n in growth.news(fake_repo) if n.kind == "round"]) == 1

    # the idea deleted: the round learns it (one of the three in a row that make it quieter)
    _act(host, bid, "remove", card=idea["id"])
    _run(host, dt.datetime.now() + dt.timedelta(minutes=2))
    assert [i["status"] for i in nightround.ideas(fake_repo)] == ["dropped"]


def test_a_board_can_stay_out_and_the_demo_never_looks(night, fake_repo):
    host, bid, model = night
    spec = dict(host.town.custom_specs[bid])
    assert buildings.set_spec(host.town, bid, {**spec, "config": {**spec.get("config", {}), "night_round": False}}) == []
    assert retros.round_job(host.town, dt.datetime.now(), force=True) is None
    assert nightround.nights(fake_repo)[-1].skipped == "no Task Fields board takes part"
    fastpath.save_settings(fake_repo, {"round_at": ""})                  # off: never due on its clock
    assert retros.round_job(host.town, dt.datetime.now()) is None and len(nightround.nights(fake_repo)) == 1


def test_the_round_comes_on_its_clock_once(night, fake_repo, monkeypatch):
    host, bid, model = night
    monkeypatch.delenv("ORKCRAFT_NIGHT_ROUND")
    at = dt.datetime(2026, 10, 8, 4, 40, 10)
    assert retros.round_job(host.town, at - dt.timedelta(minutes=5)) is None and nightround.last_run(fake_repo) is None
    work = retros.round_job(host.town, at)                               # due: it looks (and marks the night)
    if work is not None:
        retros.round_done(host.town, work())
    assert nightround.last_run(fake_repo) == at.replace(microsecond=0)
    assert retros.round_job(host.town, at + dt.timedelta(minutes=1)) is None   # not again the same night
    assert len(nightround.nights(fake_repo)) == 1
    monkeypatch.setenv("ORKCRAFT_NIGHT_ROUND", "0")
    assert retros.round_job(host.town, at + dt.timedelta(days=1)) is None      # the tests' switch: never by the clock


def test_settings_turn_it_off_and_look_now(night, fake_repo):
    host, bid, model = night
    s = host.command("town.settings", {})
    assert s["round"]["on"] and s["round"]["at"] == "04:40" and s["round"]["said"] == "It has not looked yet."
    assert not host.command("town.settings.set", {"round": False})["round"]["on"]
    assert fastpath.settings(fake_repo)["round_at"] == ""
    assert host.command("town.settings.set", {"round": True})["round"]["on"]
    got = host.command("round.now", {})
    assert got["round_said"].endswith("nothing changed since the last round.") or "looking now" in got["round_said"]


def test_the_weekly_retro_sees_the_work(night, fake_repo):
    host, bid, model = night
    _act(host, bid, "add", lane="todo", title="Split the exporter module")
    _act(host, bid, "add", lane="mine", title="Renew the passport soon")
    host.command("act", {"id": bid, "act": "private", "args": {"card": "renew-the-passport-soon"}})
    nightround.first_seen(fake_repo, bid, ["split-the-exporter-module"], dt.datetime.now() - dt.timedelta(days=20))
    text = nightround.work_text(fake_repo, host.town.custom_specs)
    assert f"## board {bid}: 2 open" in text
    assert "- task, 20 days: Split the exporter module" in text
    assert "Renew … (personal)" in text and "passport" not in text
    asked = []
    weekly.run(fake_repo, host.town.scroll, host.town.custom_specs,
               lambda p: (asked.append(p), ('{"summary": "ok", "items": []}', 0.0))[1])
    assert "THE WORK" in asked[0] and "Split the exporter module" in asked[0] and '"Work: …"' in asked[0]
