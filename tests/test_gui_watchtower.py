"""🗼 Watchtower in the core and in the GUI: the worker without a face, its card, detail and acts."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.core.town import Town
from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.design import ui
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, masonry, watch

PR = {"id": "102", "type": "PullRequestEvent", "actor": {"login": "ann"}, "created_at": "2026-10-02T05:10:00Z",
      "payload": {"action": "opened", "pull_request": {"number": 12, "title": "Login form", "html_url": "https://gh/12"}}}
PUSH = {"id": "101", "type": "PushEvent", "actor": {"login": "bob"},
        "payload": {"ref": "refs/heads/main", "commits": [{"message": "fix parser"}]}}


def _until(check, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


@pytest.fixture
def gh(monkeypatch):
    events = {"now": [PUSH]}
    monkeypatch.setattr(WatchtowerWorker, "gh_runner", staticmethod(
        lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(events["now"]), stderr="")))
    return events


def _tower(repo: Path, **config) -> None:
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower",
            "config": {"github": "me/app", **config}}
    assert masonry.save_spec(repo, spec) == []


def test_the_watchtower_worker_listens_without_a_face(fake_repo, gh, monkeypatch):
    _tower(fake_repo, feeds=["slack: token=T_NOPE channels=C1"])
    town = Town(fake_repo)
    ts.subscribe(town.scroll, "town_hall", "tower", "watch.github")
    sent: list = []
    monkeypatch.setattr(town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    w = town.worker("tower")
    assert isinstance(w, WatchtowerWorker) and w.shown() == ["slack", "github"]
    assert _until(lambda: w.checked)                                       # the first look: a baseline
    assert w.signals == [] and w.failing("slack") and "T_NOPE" in w.why("slack") and w.status() == "ERROR"
    assert w.hut_lines([10] * 4) == ["slack  ERR", "github   0", "", ""]
    gh["now"] = [PR, PUSH]
    w.check_now()
    assert _until(lambda: sent) and sent[-1].mode == "watch.github" and w.unread()[0].title.startswith("PR #12")
    assert w.open_new() is w.signals[0] and w.unread() == [] and "Login form" in w.reading["markdown"]
    w.add_signal(watch.Signal(watch.now_iso(), "webhook", "POST /deploy", '{"env": "prod"}', "/deploy"))
    assert w.mark_read() == 1 and w.mark_read() == 0


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_the_watchtower_in_the_gui_card_detail_and_acts(fake_repo, gh):
    _tower(fake_repo, cron="every 15m", feeds=["slack: token=T_NOPE channels=C1", "jira: site=x.atlassian.net user=T_ATL_USER token=T_ATL_TOKEN",
                                                "figma: token=T_FIGMA files=AbC"])
    host = _host(fake_repo)
    w = host.town.worker("tower")
    assert _until(lambda: w.checked)
    hut = lambda: next(b for b in host.snapshot()["buildings"] if b["id"] == "tower")["card"]
    card = hut()
    assert [s["label"] for s in card["sources"]] == ["slack", "jira", "figma"] and card["sources"][0]["n"] == "ERR"
    assert card["more"] == {"count": 2, "n": "0"}                          # github and cron fold into +2 more
    assert card["new"] == 0 and card["failing"] >= 1                         # slack fails: no token
    gh["now"] = [PR, PUSH]
    act = lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})
    act("check_now")
    assert _until(lambda: w.signals and w.checked and not w._looking)
    for i in range(3):
        w.add_signal(watch.Signal(f"2026-10-02T05:1{i}:00", "webhook", f"POST /deploy/{i}", "{}", f"/deploy/{i}"))
    d = host.detail("tower")
    assert [leaf.pane["id"] for leaf in ui.leaves(d["ui"])] == ["sources", "feed", "item"]
    data = d["data"]
    assert [(s["id"], s["new"]) for s in data["sources"]] == [("slack", 0), ("jira", 0), ("figma", 0), ("github", 1),
                                                              ("cron", 0)]
    assert [s["source"] for s in data["latest"]] == ["webhook", "github"]   # the newest per source
    assert data["sources"][0]["why"] and data["new"] == 4 and data["settings"]["github"] == "me/app"
    pr = next(s for s in data["signals"] if s["source"] == "github")
    assert pr["title"].startswith("PR #12") and not pr["read"]

    assert act("read", key=pr["key"]) == pr["key"]
    reading = host.detail("tower")["data"]["reading"]
    assert reading["key"] == pr["key"] and "Login form" in reading["html"]
    assert act("read_all", source="webhook") == 3 and len(w.unread()) == 0
    with pytest.raises(CommandError):
        act("read", key="gone")
    assert act("intent", intent="  user   feedback ") and w.intent == "user feedback"
    assert host.detail("tower")["data"]["intent"] == "user feedback" and not act("intent", intent="user feedback")
    assert act("open_new")                                                  # nothing new: the newest
    w.signals.clear()
    with pytest.raises(CommandError):
        act("open_new")


def test_a_mail_title_says_who_it_is_from():
    from orkcraft.gui.views.watchtower import _who
    assert _who("Ann: Lunch?") == ("Ann", "Lunch?")
    assert _who("@ ann in #dev: the build is red", "slack") == ("ann in #dev", "the build is red")
    assert _who("PR #12 opened: Login form", "github") == ("", "PR #12 opened: Login form")
    assert _who("⏰ every 15m") == ("", "⏰ every 15m")


def test_the_closed_card_previews_the_newest_unread_signal(fake_repo, gh):
    """The card's preview is the newest unread signal, not the newest one; with all read, the newest (read)
    (docs/design/watchtower-automation.md §2 H)."""
    from orkcraft.gui.views import watchtower as view
    _tower(fake_repo)
    host = _host(fake_repo)
    w = host.town.worker("tower")
    assert _until(lambda: w.checked)
    w.add_signal(watch.Signal("2026-10-02T05:10:00", "webhook", "POST /older", "{}", "/older"))
    w.add_signal(watch.Signal("2026-10-02T05:20:00", "webhook", "POST /newer", "{}", "/newer"))
    w.mark_read([w.signals[0]])                                             # the newest is read
    latest = view.card(w)["latest"]
    assert [(s["title"], s["read"], s["at"]) for s in latest] == [("POST /older", False, "05:10")]
    w.mark_read()
    assert [(s["title"], s["read"]) for s in view.card(w)["latest"]] == [("POST /newer", True)]
    assert view.card(w)["new"] == 0


def test_add_a_source_shows_its_services_in_groups():
    """The picker's groups in their order, each with its word from the glossary; Calendar has no service yet."""
    from orkcraft.core.workers.watchtower_add import Adding
    from orkcraft.realm import lexicon, quickadd
    groups = Adding.groups()
    assert [g["label"] for g in groups] == ["Messengers", "Mail", "Code", "Other"]
    assert lexicon.term("source_group.calendar") == "Calendar"
    assert {s.id for s in quickadd.SERVICES.values() if s.group == "messengers"} == {"slack", "discord"}
    assert {s.id for s in quickadd.SERVICES.values() if s.group == "code"} == {"github", "gitlab"}
    assert all(s.group in quickadd.GROUPS for s in quickadd.SERVICES.values())
