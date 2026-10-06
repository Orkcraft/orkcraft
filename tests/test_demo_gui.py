"""The GUI's demo: the dashboard set with every building type, each with state to show — and no
network, no model."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from orkcraft import demo
from orkcraft.realm import catalog, forge


def _wait(cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def test_the_gui_opens_the_dashboard_set_and_the_tui_the_eight_roles(monkeypatch, tmp_path: Path):
    import orkcraft.cli as cli
    built = []

    class Launch:
        @staticmethod
        def run(root, *a, **kw):
            return 0

    monkeypatch.setattr(cli, "_gui", lambda quiet=False: Launch)
    monkeypatch.setattr(demo, "build", lambda path, reset=False, set_name="main": built.append(set_name) or tmp_path)
    monkeypatch.setattr(cli.OrkcraftApp, "run", lambda self: None)
    assert cli.main(["gui", "--demo"]) == 0 and cli.main(["--demo", "tui"]) == 0
    assert cli.main(["gui", "--demo", "--browser"]) == 0 and cli.main(["--demo-set", "managers", "gui", "--demo"]) == 0
    assert cli.main(["--demo"]) == 0                    # the window is the default
    assert built == ["dashboard", "main", "dashboard", "managers", "dashboard"]


def test_a_sandbox_of_another_set_or_an_older_demo_is_built_again(tmp_path: Path):
    root = demo.build(tmp_path / "d", set_name="managers")
    (root / "extra.md").write_text("x")
    assert demo.build(root, set_name="managers") == root and (root / "extra.md").exists()     # kept
    marker = root / demo.MARKER
    marker.write_text(marker.read_text().replace(f"demo {demo.VERSION}", "demo 1"))
    demo.build(root, set_name="managers")
    assert not (root / "extra.md").exists() and f"demo {demo.VERSION}" in marker.read_text()


@pytest.fixture
def dashboard(tmp_path: Path, monkeypatch):
    from orkcraft.gui.host import Host
    from orkcraft.realm import feeds, jobs, mailbox, roads
    root = demo.build(tmp_path / "dash", set_name="dashboard")
    called = []
    monkeypatch.setattr(roads, "run_agent", lambda *a, **k: called.append(("agent", a)) or ("x", 1.0, None))
    monkeypatch.setattr(jobs, "run_work", lambda *a, **k: called.append(("work", a)) or ("x", 1.0, None, ""))
    monkeypatch.setattr(mailbox, "look", lambda *a, **k: called.append(("imap", a)) or mailbox.Look())
    monkeypatch.setattr(feeds, "look", lambda *a, **k: called.append(("feed", a)) or feeds.Look())
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    yield host, root, called
    host.close()


def test_every_building_type_stands_with_a_card_to_show(dashboard):
    host, root, called = dashboard
    snap = host.snapshot()
    types = {b["type"] for b in snap["buildings"]}
    assert types == set(catalog.TYPES) - {"custom", "lake"}
    for b in snap["buildings"]:
        if b["type"] != "town_hall":          # the Town Hall's card is its Build and Ask
            assert b["card"] or b["status_plain"], b["id"]
    assert not any(b["type"] == "lake" for b in snap["buildings"])         # Lake is the town's window
    by_id = {b["id"]: b for b in snap["buildings"]}
    assert by_id["camp"]["card"]["asks"] and by_id["council"]["card"]["cycle"] == 2
    days = by_id["days"]["card"]
    assert any(m["now"] for m in days["beats"]) and any(m["doc"] for m in days["beats"])
    assert {m["kind"] for m in days["beats"]} == {"meeting", "schedule", "limit"}          # all three, overlaid
    assert called == []                                   # no model, no mailbox, no feed asked


def test_the_watchtower_and_the_forge_answer_from_the_sandbox(dashboard):
    host, root, called = dashboard
    tower = host.town.workers["post"]
    tower.refresh_data()
    shown, more = tower.counters()
    assert [label for label, _ in shown][0] == "gmail" and more is not None             # +N more past four
    assert {label for label, _ in tower.counters(8)[0]} >= {"gmail", "slack", "jira"}
    assert tower.failing("jira") and not tower.failing("mail") and not tower.failing("slack")
    assert "401" in tower.why("jira")
    smith = host.town.workers["branches"]
    assert _wait(lambda: smith.snap is not None and any(b.pr for b in smith.snap.branches))
    prs = {b.name: b.pr.number for b in smith.snap.branches if b.pr}
    assert prs == {"feature/pricing-page": 14, "feature/login": 12, "docs/barracks": 13}
    assert not smith.last_merge.ok and smith.last_merge.conflicts == ["src/billing.py"]
    smith.pick("feature/login")
    assert _wait(lambda: smith.comments.get("feature/login"))
    assert [c["author"] for c in smith.comments["feature/login"]] == ["ann", "grub-bot", "dana"]
    smith.merged(forge.Result(True, "docs/barracks", "main", "abc1234", "docs"))
    kept = (smith.state_dir / "merges.jsonl").read_text().splitlines()
    assert len(kept) == 3 and json.loads(kept[-1])["result"]["branch"] == "docs/barracks"
    assert called == []


def test_the_orks_screens_ask_their_questions(dashboard):
    host, root, called = dashboard
    assert set(host.sessions.keys()) == {"pool:camp/grub", "pool:camp/snaga"}

    def asking():
        host.refresh_roster()
        return len(host.snapshot()["alerts"]) >= 2
    assert _wait(asking)
    questions = {a["title"] for a in host.snapshot()["alerts"]}
    assert any("release-notes.md" in q for q in questions) and any("price" in q for q in questions)
