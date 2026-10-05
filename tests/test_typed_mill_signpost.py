"""⚙️ The Mill and 🚏 the Signpost (T1107 stage 3): deterministic steps, rule-based routes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, horn, masonry, mill, roads, signpost
from orkcraft.tui import silhouettes
from orkcraft.realm.pipes import Payload
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.mill_view import MillView
from orkcraft.screens.typed.signpost_view import SignpostView

LOG = "INFO start\nERROR db timeout id=17\nINFO ok\nERROR disk full id=42\nERROR db timeout id=17\n"


def test_mill_steps():
    out, err = mill.run(["grep: ERROR", "dedupe", "extract: id = id=(\\d+)", "pick: id", "to_json"], LOG)
    assert not err and json.loads(out) == [{"id": "17"}, {"id": "42"}]
    out, _ = mill.run(["csv", "filter: role eq admin", "template: {name} <{mail}>", "join: , "],
                      "name,mail,role\nAnn,a@x,admin\nBob,b@x,user\nCid,c@x,admin\n")
    assert out == "Ann <a@x>, Cid <c@x>"
    assert mill.run(["json", "count"], '[1, 2, 3]')[0] == '{"count": 3}'
    assert mill.run(["replace: (\\d+) => #\\1", "lower"], "Ticket 42 DONE")[0] == "ticket #42 done"
    assert mill.run(["lines", "drop: INFO", "sort: line desc", "limit: 1", "join"], LOG)[0] == "ERROR disk full id=42"
    script = f"{sys.executable} -c \"import sys; print(sys.stdin.read().count('ERROR'))\""
    assert mill.run([f"script: {script}"], LOG)[0] == "3"
    out, err = mill.run(["grep: ERROR", "json"], LOG)
    assert err.startswith("step 2 (json)") and "ERROR" in out          # the value before the failing step
    assert mill.check(["grep: (", "nonsense"]) and mill.check(["lines", "grep: x"]) == []
    bad = {"id": "m", "title": "M", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill", "config": {"steps": ["frobnicate"]}}
    assert any("unknown step" in e for e in catalog.validate(bad))


def test_mill_fixed_edges():
    assert mill.run(["join: → "], "a\nb")[0] == "a→ b"                             # not mangled by unicode_escape
    assert mill.run(['join: " | "'], "a\nb")[0] == "a | b"                         # quotes keep the spaces
    assert mill.run(["join: \\t"], "a\nb")[0] == "a\tb"
    out, err = mill.run(["replace: a"], "banana")
    assert err.startswith("step 1") and "=>" in err and out == "banana"            # no silent delete
    assert mill.run(["replace: a => "], "banana")[0] == "bnn"                       # an empty <with> deletes
    assert mill.run(['replace: , => " - "'], "a,b")[0] == "a - b"
    assert mill.check(["extract: foo", "replace: x", "filter: n gt", "filter: n bigger 2", "limit: x", "sort:"]) \
        and len(mill.check(["extract: foo", "replace: x", "filter: n bigger 2", "limit: x", "sort:"])) == 5
    out, err = mill.run(["lines", "extract: foo"], "abc")
    assert "extract: <field> = <regex>" in err
    out, err = mill.run(["csv", "filter: n bigger 2"], "n\n1\n3")
    assert "filter:" in err


def test_mill_numbers_and_dates():
    csv_text = "n,day\n10,2026-03-01\n9,2026-01-15\n100,2025-12-31\n,2026-02-01\n"
    out, _ = mill.run(["csv", "sort: n", "pick: n", "to_json"], csv_text)
    assert [r["n"] for r in json.loads(out)] == ["9", "10", "100", ""]              # numbers, the empty last
    out, _ = mill.run(["csv", "sort: n desc text", "pick: n", "to_json"], csv_text)
    assert [r["n"] for r in json.loads(out)][:3] == ["9", "100", "10"]              # text when asked
    out, _ = mill.run(["csv", "filter: n gt 9", "count"], csv_text)
    assert out == '{"count": 2}'
    out, _ = mill.run(["csv", "filter: n le 10", "count"], csv_text)
    assert out == '{"count": 2}'
    out, _ = mill.run(["csv", "filter: day ge 2026-01-01", "filter: day lt 2026-03-01", "pick: day", "to_json"], csv_text)
    assert [r["day"] for r in json.loads(out)] == ["2026-01-15", "2026-02-01"]
    out, _ = mill.run(["lines", "sort: n desc", "limit: 2", "pick: n", "to_json"], "\n".join("x" * i for i in range(1, 12)))
    assert [r["n"] for r in json.loads(out)] == [11, 10]


def test_mill_agent_steps_and_flat_map():
    seen = []

    def agent(ask, text):
        seen.append((ask, text))
        return text.upper()

    r = mill.run_full(["grep: ERROR", "agent: shout it", "lines", "pick: line"], LOG, agent=agent)
    assert not r.error and r.agent_steps == 1 and seen[0][0] == "shout it"
    assert mill.items(r.records)[0] == '{"line": "ERROR DB TIMEOUT ID=17"}' and len(r.records) == 3
    assert mill.run_full(["trim"], "a").records is None                            # text: no flat map
    r = mill.run_full([f"script: {sys.executable} -c 'import sys; sys.exit(3)' || agent: count the lines"], "a\nb",
                      agent=lambda ask, text: str(len(text.splitlines())))
    assert not r.error and r.text == "2" and r.agent_steps == 1                     # the script failed, the agent did it
    r = mill.run_full([f"script: {sys.executable} -c 'import sys; sys.exit(3)' || agent: x"], "a",
                      agent=lambda ask, text: (_ for _ in ()).throw(RuntimeError("no claude")))
    assert "the script failed" in r.error and "no claude" in r.error
    assert mill.check(["agent:", "script: make || agent:"]) and mill.check(["agent: fix it", "script: make || agent: do it"]) == []
    assert mill.model_steps(["agent: a", "script: x || agent: b", "script: y", "grep: agent"]) == 2
    assert "## Input\n\nhello" in mill.agent_prompt("do", "hello")


def test_mill_scripts_see_a_clean_environment(monkeypatch):
    monkeypatch.setenv("ORK_SECRET_TOKEN", "s3cret")
    monkeypatch.setenv("ORK_ALLOWED", "yes")
    show = f"script: {sys.executable} -c \"import os; print(os.environ.get('ORK_SECRET_TOKEN'), os.environ.get('ORK_ALLOWED'))\""
    assert mill.run([show], "")[0] == "None None"
    assert mill.run([show], "", env=["ORK_ALLOWED"])[0] == "None yes"


def P(value="", title="", kind="text", source="pit", mode="pit.text"):
    return Payload(kind, value, source, mode, title)


def test_signpost_rules():
    rules, problems = signpost.rules_of(["bugs: matches (?i)traceback|error", "links: kind text", "deploys: env == prod",
                                      "other: else", "BAD RULE: x", "x: frob it"])
    assert [r.route for r in rules] == ["bugs", "links", "deploys", "other"] and len(problems) == 2
    assert signpost.route(rules, P("Traceback (most recent call last)")) == "bugs"
    assert signpost.route(rules, P("https://x", kind="text")) == "links"
    assert signpost.route(rules[2:], P('{"env": "prod"}', kind="file")) == "deploys"
    assert signpost.route(rules[2:3], P('{"env": "dev"}')) is None
    assert signpost.routes(["a: else", "b: kind node", "a: contains x"]) == ["a", "b"]
    assert roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "signpost.routed", "bugs"), {})[0]
    assert not roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "signpost.routed", "links"), {})[0]


@pytest.mark.asyncio
async def test_the_signpost_routes_into_the_mill(fake_repo: Path, monkeypatch):
    for s in ({"id": "crossroads", "title": "Signpost", "icon": "🚏", "orc": {"name": "Grot Pointa"}, "type": "signpost",
               "config": {"rules": ["errors: matches ERROR", "rest: else"]}},
              {"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": ["grep: ERROR", "dedupe", "count"]}}):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        choices = app._road_choices("crossroads", "grinder")
        assert [c[0] for c in choices[:2]] == ["signpost.routed#errors", "signpost.routed#rest"]
        app.add_road("grinder", "crossroads", "signpost.routed#errors", None)
        app.add_road("town_hall", "grinder", "mill.done", None)
        road = app.scroll.building("grinder").roads[0]
        assert road.filter == {"route": ["errors"]} and road.label == "errors"
        signpost_view = app.desktop.get_window("crossroads").query_one(SignpostView)
        mill_view = app.desktop.get_window("grinder").query_one(MillView)
        delivered = []
        real_deliver = app.core.deliver
        monkeypatch.setattr(app.core, "deliver", lambda t, p, *a: delivered.append((t, p.title)) or real_deliver(t, p, *a))
        signpost_view.receive(P(LOG), "log", LOG)                           # → route errors → the mill
        signpost_view.receive(P("all good"), "ok", "all good")               # → route rest: no road takes it
        for _ in range(40):
            await pilot.pause(0.05)
            if mill_view.runs:
                break
        assert [d for d in delivered if d[0] == "grinder"] == [("grinder", "errors")]
        assert mill_view.runs[0].ok and mill_view.runs[0].result == '{"count": 2}'
        assert signpost_view.mini_status() == ["routes: errors, rest", "last → rest"]
        assert mill_view.quick_action("mill.run")
        app.desktop.focus_window(app.desktop.get_window("grinder"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, TextBlock)
        app.screen.query_one("#block-text").text = "lines\ncount"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.custom_specs["grinder"]["config"]["steps"] == ["lines", "count"]


@pytest.mark.asyncio
async def test_the_mill_queues_every_cart_and_flat_maps_records(fake_repo: Path, monkeypatch):
    slow = f"script: {sys.executable} -c \"import sys, time; time.sleep(0.2); print(sys.stdin.read())\""
    for s in ({"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": [slow, "lines", "pick: line"]}},
              {"id": "sink", "title": "Sink", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": ["trim"]}}):
        assert masonry.save_spec(fake_repo, s) == []
    assert catalog.size_of({"type": "mill"}) == catalog.SIZES["XS"]
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        app.add_road("sink", "grinder", "mill.item", None)
        mill_view = app.desktop.get_window("grinder").query_one(MillView)
        delivered = []
        monkeypatch.setattr(app.core, "deliver", lambda t, p, *a: delivered.append((t, p.mode, p.value)))
        for text in ("a\nb", "c", "d\ne\nf"):                       # three carts while the first still mills
            mill_view.receive(P(text), "cart", text)
        assert mill_view.running and len(mill_view.queue) == 2
        assert mill_view.hut_lines([8]) == ["⚙ +2"]
        for _ in range(100):
            await pilot.pause(0.05)
            if len(mill_view.runs) == 3 and not mill_view.running:
                break
        assert [j.input for j in reversed(mill_view.runs)] == ["a\nb", "c", "d\ne\nf"]      # nothing dropped, in order
        items = [json.loads(v)["line"] for t, mode, v in delivered if mode == "mill.item"]
        assert items == ["a", "b", "c", "d", "e", "f"]
        assert mill_view.runs[0].meta.get("items") == 3


def test_a_totem_of_old_loads_as_a_signpost():
    """Towns written before the Signpost keep their routing; the Totem's look waits for its own building."""
    old = {"id": "crossroads", "title": "Totem", "icon": "🗿", "orc": {"name": "Spirit Guide"}, "type": "totem",
           "events": ["totem.routed"], "config": {"rules": ["bugs: contains bug"]}}
    assert catalog.type_of(old).id == "signpost" and catalog.events_of(old) == ["signpost.routed"]
    new = catalog.migrate(old)
    assert (new["type"], new["icon"], new["title"], new["events"]) == ("signpost", "🚏", "Signpost", ["signpost.routed"])
    assert catalog.migrate({**old, "title": "Triage", "icon": "🔱"})["title"] == "Triage"
    assert catalog.validate(old) == []
    assert "totem" not in catalog.TYPES and "totem" in silhouettes.SILHOUETTES
    assert silhouettes.of(old).id == "signpost"
    road = ts.Road.from_dict({"id": "r", "from": "crossroads", "event": "totem.routed", "filter": {"route": ["bugs"]}})
    assert road.event == "signpost.routed"
    assert horn.pick({"crossroads/totem.routed": "alarm"}, "crossroads", "signpost.routed")[0] == "alarm"
    assert horn.pick({"totem.unmatched": "ding"}, "x", "signpost.unmatched")[0] == "ding"
