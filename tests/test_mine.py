"""⛏️ The Mine at work (core/workers/mine.py, docs/design/mine.md): a question searched by every tool alone,
checked, searched again, the dispute asked of the person in Answers, the report kept in the Wiki and sent on;
the limit; repeats only with a Calendar; its window in the GUI."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, drumbeat, roads

PLAN = {"sub": [{"q": "When does the free tier end?", "answer_if": "the price page"}]}


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    return built.id


def _wait(fn, s: float = 30.0) -> bool:
    """Polls `fn` until it holds: the Mine works on its own threads, so wait for the last thing a step does."""
    end = time.monotonic() + s
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(0.02)
    return False


def _found(*items) -> str:
    return json.dumps({"findings": [{"sub": 1, "claim": c, "sources": [{"url": u, "quote": ""}]} for c, u in items]})


class Agents:
    """Fake tools: what each answers to a plan, a search, a second search, a grouping, a debate."""

    def __init__(self, cost: float = 0.1):
        self.calls: list[tuple[str, bool, str]] = []
        self.cost = cost

    def __call__(self, tool, prompt, workdir, env, cancel, model="", web=False, **_):
        self.calls.append((tool, web, prompt[:40]))
        assert workdir != Path.cwd() and not any(workdir.iterdir())      # an empty folder, never the project
        if "Do not search" in prompt:
            return json.dumps(PLAN), self.cost, None
        if '"groups"' in prompt:
            return json.dumps({"groups": [[1, 3], [2]], "conflicts": [[0, 1]]}), self.cost, None
        if "not settled yet" in prompt:
            return _found(("The free tier ends on 1 March", f"https://{tool}-more.com/x")), self.cost, None
        if tool == "hermes":
            return _found(("It ends for new accounts only", "https://acme.com/blog")), self.cost, None
        return _found(("The free tier ends on 1 March", f"https://{tool}.com/pricing")), self.cost, None


def test_a_research_is_checked_asked_and_kept(fake_repo, isolated_layout_file, monkeypatch):
    agents = Agents()
    monkeypatch.setattr(roads, "run_agent", agents)
    host = _host(fake_repo)
    wiki = _raised(host, "scrolls")
    bid = _raised(host, "mine", tools=["claude", "hermes"], rounds=1)
    w = host.town.worker(bid)
    sent = []
    host.town.emit_typed = lambda b, ev, value, title="", *a, **k: sent.append((ev, value, title)) or True

    rid = host.command("act", {"id": bid, "act": "ask", "args": {"question": "When does Acme's free tier end?"}})
    # the cycle marks the research waiting, then says so (`mine.asked`): wait for the saying
    assert _wait(lambda: w.get(rid)["status"] == "waiting" and sent and sent[-1][0] == "mine.asked"), w.get(rid)
    r = w.get(rid)
    assert {t for t, web, _ in agents.calls if web} == {"claude", "hermes"}       # every tool searched, with the web
    assert r["round"] == 1 and r["cost"] > 0 and set(r["per_tool"]) == {"claude", "hermes"}
    assert sent[-1][0] == "mine.asked"

    key, title, context, answers = w.orders_alert()                              # in Answers, both sides
    assert "Disputed" in title and "against" in context and [a for a, _ in answers] == ["more", "a", "b", "keep"]
    snap = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)
    assert snap["card"]["waiting"] == 1 and {t["id"] for t in snap["card"]["tools"]} == {"claude", "hermes"}

    w.answer_alert("a")                                                          # the person accepts the first
    assert w.get(rid)["status"] == "done" and w.orders_alert() is None
    ev, value, title = sent[-1]
    assert ev == "mine.reported" and value.startswith("notes/inbox/") and "✓ 1" in title
    note = (fake_repo / value).read_text(encoding="utf-8")
    assert note.startswith("---\nkind: research") and "Confirmed by you" in note
    assert host.town.worker(wiki).pending                                         # the Wiki takes it in

    from orkcraft.gui.views import mine as view
    d = view.detail(w)
    assert d["reports"][0]["id"] == rid and d["reports"][0]["counts"]["confirmed"] == 1
    opened = view.ACTS["open"](w, {"id": rid})
    assert opened["groups"] and opened["report"].startswith("# When does")


def test_the_limit_stops_a_research_and_says_so(fake_repo, isolated_layout_file, monkeypatch):
    monkeypatch.setattr(roads, "run_agent", Agents(cost=0.6))
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["claude", "codex"], wiki="")
    w = host.town.worker(bid)
    rid = w.ask("Anything", limit=1.0)
    assert _wait(lambda: w.get(rid)["status"] in ("done", "failed", "waiting"))
    r = w.get(rid)
    assert r["stopped"].startswith("Stopped at the limit") and r["cost"] <= 1.0 + 2 * 0.6
    assert "Stopped at the limit" in w.report_text(r)
    w.save_config({"month_limit": 0.5})
    with pytest.raises(ValueError, match="month"):
        w.ask("Another")


def test_no_web_tool_no_research(fake_repo, isolated_layout_file, monkeypatch):
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["pi", "cursor"])                          # neither can search the web
    with pytest.raises(CommandError, match="search the web"):
        host.command("act", {"id": bid, "act": "ask", "args": {"question": "Q"}})


def test_repeats_need_a_calendar_and_show_on_it(fake_repo, isolated_layout_file, monkeypatch):
    agents = Agents()
    monkeypatch.setattr(roads, "run_agent", agents)
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["claude", "codex"], wiki="")
    w = host.town.worker(bid)
    with pytest.raises(ValueError, match="Calendar"):
        w.set_repeat("Pricing news", "weekly mon 09:00")
    _raised(host, "war_drum")
    with pytest.raises(ValueError, match="Not a schedule"):
        w.set_repeat("Pricing news", "now and then")
    assert w.set_repeat("Pricing news", "daily 09:00", 2.0)
    jobs = drumbeat.jobs(host.town.scroll, host.town.custom_specs)
    assert any(j.ref == bid and j.what == "research" and j.expr == "daily 09:00" and "≤ $2.00" in j.title for j in jobs)

    w.tick(dt.datetime(2026, 10, 8, 8, 59))
    w.tick(dt.datetime(2026, 10, 8, 9, 0))                                       # due: it runs
    assert _wait(lambda: w.researches and w.researches[0]["status"] in ("done", "waiting"))
    assert w.researches[0]["trigger"] == "repeat" and w.researches[0]["limit"] == 2.0
    assert w.set_repeat("Pricing news", "") and w.repeats == []


def test_a_cart_is_a_question(fake_repo, isolated_layout_file, monkeypatch):
    monkeypatch.setattr(roads, "run_agent", Agents())
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["claude", "codex"], wiki="")
    w = host.town.worker(bid)
    from orkcraft.realm import pipes
    w.receive(pipes.Payload("text", "Compare the plans\nonly 2026 prices", "fields", "tasks.created", ref="todo:t1"),
              "Acme pricing", "")
    r = w.researches[0]
    assert r["question"] == "Acme pricing" and r["must"] == ["Compare the plans", "only 2026 prices"]
    assert r["ref"] == "todo:t1" and r["trigger"] == "road"


def test_search_more_on_a_dispute_runs_one_more_round(fake_repo, isolated_layout_file, monkeypatch):
    agents = Agents()
    monkeypatch.setattr(roads, "run_agent", agents)
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["claude", "hermes"], rounds=0, wiki="")
    w = host.town.worker(bid)
    rid = w.ask("When does Acme's free tier end?")
    assert _wait(lambda: w.get(rid)["status"] == "waiting")
    before = len(agents.calls)
    w.answer_alert("more")
    assert _wait(lambda: w.get(rid)["status"] in ("waiting", "done") and w.running is None)
    assert w.get(rid)["round"] == 1 and any("not settled yet" in p or p.startswith("You check facts")
                                            for _t, _w, p in agents.calls[before:])
    w.answer_alert("keep")
    assert w.get(rid)["status"] == "done" and "## Disputed" in w.report_text(w.get(rid))


def test_with_one_tool_no_round_spends_on_what_it_could_never_confirm(fake_repo, isolated_layout_file, monkeypatch):
    """A confirmed finding needs two minds; with one tool every finding stays one source, and the rounds searched the
    web again and again for nothing. They are left out: one search, its report."""
    agents = Agents()
    monkeypatch.setattr(roads, "run_agent", agents)
    host = _host(fake_repo)
    bid = _raised(host, "mine", tools=["claude"], rounds=3, wiki="")
    w = host.town.worker(bid)
    rid = host.command("act", {"id": bid, "act": "ask", "args": {"question": "When does Acme's free tier end?"}})
    assert _wait(lambda: w.get(rid)["status"] in ("done", "waiting", "failed")), w.get(rid)
    r = w.get(rid)
    assert r["round"] == 0
    assert sum(1 for _t, web, _p in agents.calls if web) == 1                   # the one search, no more
