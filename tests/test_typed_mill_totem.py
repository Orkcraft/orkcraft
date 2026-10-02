"""⚙️ The Mill and 🗿 the Totem (T1107 stage 3): deterministic steps, rule-based routes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, masonry, mill, roads, totem
from orkcraft.realm.pipes import Payload
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.mill_view import MillView
from orkcraft.screens.typed.totem_view import TotemView

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


def P(value="", title="", kind="text", source="pit", mode="pit.text"):
    return Payload(kind, value, source, mode, title)


def test_totem_rules():
    rules, problems = totem.rules_of(["bugs: matches (?i)traceback|error", "links: kind text", "deploys: env == prod",
                                      "other: else", "BAD RULE: x", "x: frob it"])
    assert [r.route for r in rules] == ["bugs", "links", "deploys", "other"] and len(problems) == 2
    assert totem.route(rules, P("Traceback (most recent call last)")) == "bugs"
    assert totem.route(rules, P("https://x", kind="text")) == "links"
    assert totem.route(rules[2:], P('{"env": "prod"}', kind="file")) == "deploys"
    assert totem.route(rules[2:3], P('{"env": "dev"}')) is None
    assert totem.routes(["a: else", "b: kind node", "a: contains x"]) == ["a", "b"]
    assert roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "totem.routed", "bugs"), {})[0]
    assert not roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "totem.routed", "links"), {})[0]


@pytest.mark.asyncio
async def test_the_totem_routes_into_the_mill(fake_repo: Path, monkeypatch):
    for s in ({"id": "crossroads", "title": "Totem", "icon": "🗿", "orc": {"name": "Spirit Guide"}, "type": "totem",
               "config": {"rules": ["errors: matches ERROR", "rest: else"]}},
              {"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": ["grep: ERROR", "dedupe", "count"]}}):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        choices = app._road_choices("crossroads", "grinder")
        assert [c[0] for c in choices[:2]] == ["totem.routed#errors", "totem.routed#rest"]
        app.add_road("grinder", "crossroads", "totem.routed#errors", None)
        app.add_road("town_hall", "grinder", "mill.done", None)
        road = app.scroll.building("grinder").roads[0]
        assert road.filter == {"route": ["errors"]} and road.label == "errors"
        totem_view = app.desktop.get_window("crossroads").query_one(TotemView)
        mill_view = app.desktop.get_window("grinder").query_one(MillView)
        delivered = []
        real_deliver = app.deliver_payload
        monkeypatch.setattr(app, "deliver_payload", lambda t, p, *a: delivered.append((t, p.title)) or real_deliver(t, p, *a))
        totem_view.receive(P(LOG), "log", LOG)                           # → route errors → the mill
        totem_view.receive(P("all good"), "ok", "all good")               # → route rest: no road takes it
        for _ in range(40):
            await pilot.pause(0.05)
            if mill_view.runs:
                break
        assert [d for d in delivered if d[0] == "grinder"] == [("grinder", "errors")]
        assert mill_view.runs[0].ok and mill_view.runs[0].result == '{"count": 2}'
        assert totem_view.mini_status() == ["routes: errors, rest", "last → rest"]
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
