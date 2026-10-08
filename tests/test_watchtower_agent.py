"""🗼 The Watchtower through Claude (docs/design/watchtower-quick-add.md §7): a headless agent with the person's
own connector, read-only tools only, the answer by schema, the cost to Spend, a ceiling a day — on recorded
runs, no model asked."""
from __future__ import annotations

import datetime as dt
import json
import subprocess

import pytest

from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, feeds, feeds_agent, masonry
from orkcraft.sources import telemetry
from tests.test_watchtower_quickadd import _until

LINE = ("agent: tool=claude server=atlassian tools=searchJiraIssuesUsingJql,getJiraIssue every=30m "
        "ask=new comments and mentions in Jira")
ITEMS = [{"key": "WEB-7", "version": "2026-10-07T10:12:00.000+0000", "title": "Login fails", "text": "repro attached",
          "author": "Bob", "url": "https://acme.atlassian.net/browse/WEB-7", "at": "2026-10-07T10:12:00Z", "mention": False},
         {"key": "WEB-9", "version": "2026-10-07T10:20:00.000+0000", "title": "Pricing", "text": "@Ann please check",
          "author": "Cy", "at": "2026-10-07T10:20:00Z", "mention": True}]


def events(items=None, error="", status="connected", cost=0.03, denied=(), structured=True) -> str:
    out = [{"type": "system", "subtype": "init", "mcp_servers": [{"name": "atlassian", "status": status}]}]
    result = {"type": "result", "subtype": "success", "total_cost_usd": cost,
              "permission_denials": [{"tool_name": t} for t in denied]}
    if structured:
        result["structured_output"] = {"items": ITEMS if items is None else items, "error": error}
    else:
        result["result"] = "Here is what I found: ..."
    return "\n".join(json.dumps(e) for e in out + [result])


class Run:
    """A fake `claude -p`: answers in turn, remembers the argv."""

    def __init__(self, *answers) -> None:
        self.answers, self.argv = list(answers), []

    def __call__(self, argv):
        self.argv.append(argv)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(argv, 0, answer, "")


def feed(line=LINE):
    f, err = feeds.parse(line)
    assert not err, err
    return f


def test_a_look_reads_the_schema_and_composes_the_ids_itself():
    run = Run(events())
    got = feeds_agent.look(feed(), "2026-10-07T10:00:00+00:00", ["WEB-1:old"], run)
    assert got.error == "" and got.cost == 0.03
    assert [(i.key, i.mention, i.title) for i in got.items] == [
        ("WEB-7:2026-10-07T10:12:00.000+0000", False, "Bob: Login fails"),
        ("WEB-9:2026-10-07T10:20:00.000+0000", True, "@ Cy: Pricing")]
    argv = run.argv[0]
    allowed = argv[argv.index("--allowedTools") + 1]
    assert allowed == "mcp__atlassian__searchJiraIssuesUsingJql,mcp__atlassian__getJiraIssue"
    assert "Bash" in argv[argv.index("--disallowedTools") + 1] and "--json-schema" in argv
    assert "since 2026-10-07T10:00:00+00:00" in argv[2] and "WEB-1:old" in argv[2]
    assert any(src == "claude watch atlassian" and usd == 0.03
               for _, usd, src in telemetry.charges(dt.datetime.now().astimezone() - dt.timedelta(minutes=1)))


@pytest.mark.parametrize("answer, kind, says", [
    (events(status="needs-auth"), "login", "needs a login — run /mcp"),
    ("\n".join([json.dumps({"type": "system", "subtype": "init", "mcp_servers": [{"name": "slack", "status": "connected"}]}),
                json.dumps({"type": "result", "structured_output": {"items": [], "error": ""}})]),
     "target", "has no atlassian server"),
    (events(items=[], error="403 The app is not installed on this instance"), "target", "atlassian said: 403"),
    (events(denied=["mcp__atlassian__createJiraIssue"]), "network", "it tried mcp__atlassian__createJiraIssue"),
])
def test_what_a_failed_look_says(answer, kind, says):
    got = feeds_agent.look(feed(), run=Run(answer))
    assert got.kind == kind and says in got.error and got.items == []


def test_an_answer_not_by_schema_is_asked_once_more_then_waits():
    run = Run(events(structured=False), events())
    assert len(feeds_agent.look(feed(), run=run).items) == 2 and len(run.argv) == 2
    run = Run(events(structured=False))
    got = feeds_agent.look(feed(), run=run)
    assert "not the list asked for" in got.error and len(run.argv) == 2 and got.cost == pytest.approx(0.06)
    got = feeds_agent.look(feed(), run=Run(subprocess.TimeoutExpired("claude", 90)))
    assert (got.kind, got.error) == ("network", "agent: Claude did not answer in 90 s")


def test_the_line_and_when_it_looks():
    assert "server=" in feeds.parse("agent: tools=x ask=hi")[1]
    assert "minutes" in feeds.parse("agent: server=s tools=x every=soon ask=hi")[1]
    assert feed().identity == "agent|atlassian|new comments and mentions in Jira"
    f = feed(LINE.replace("every=30m", "every=2m"))
    assert feeds_agent.every(f) == 10 and feeds_agent.ceiling(f) == 0.50          # 10 min at the fastest
    now = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.timezone.utc)
    assert feeds_agent.due(feed(), "2026-10-07T11:50:00+00:00", 0.0, now) == "not yet"
    assert feeds_agent.due(feed(), "2026-10-07T11:00:00+00:00", 0.0, now) == ""
    assert "ceiling ($0.50) reached" in feeds_agent.due(feed(), "", 0.5, now)
    assert "agy cannot be held" in feeds_agent.look(feed(LINE.replace("tool=claude", "tool=agy"))).error


@pytest.fixture
def tower(fake_repo, monkeypatch):
    monkeypatch.setattr(WatchtowerWorker, "agent_runner", staticmethod(Run(events(cost=0.2))))   # before it starts
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower",
            "config": {"feeds": [LINE]}}
    assert masonry.save_spec(fake_repo, spec) == []
    checkpoint.ensure(fake_repo)
    return Host(fake_repo, auto_commit=False)


def test_the_tower_looks_every_thirty_minutes_spends_and_stops_at_its_ceiling(tower):
    w = tower.town.worker("tower")
    w.refresh_data()
    assert _until(lambda: w.checked and not w._looking)
    assert w.signals == [] and w.spent_today(feed()) == pytest.approx(0.2)        # the first look marks seen
    st = w._state()
    assert set(st["feeds_seen"][feed().identity]) == {i["key"] + ":" + i["version"] for i in ITEMS}
    calls = len(WatchtowerWorker.agent_runner.argv)
    w.refresh_data()                                                              # 2 min later: not yet its time
    assert _until(lambda: not w._looking) and len(WatchtowerWorker.agent_runner.argv) == calls
    assert feed().identity in w._state()["feeds_seen"]                            # what it saw is kept meanwhile
    w._save_state(agent_at={feed().identity: "2026-01-01T00:00:00+00:00"},
                  agent_spend={feed().identity: {"day": dt.date.today().isoformat(), "usd": 0.5}})
    w.refresh_data()
    row = tower.detail("tower")["data"]["listed"][0]
    assert row["label"] == "Through Claude" and "≈ $0.50 today" in row["line"] and "ceiling ($0.50) reached" in row["line"]
    assert len(WatchtowerWorker.agent_runner.argv) == calls and not row["editable"]
