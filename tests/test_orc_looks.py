"""Orc looks and visual badges (T1104 stage 1): lead / resident / worker, harness pairs,
the Roster by roads, and the Recruiter preview (stage 4)."""
from __future__ import annotations

import json
from pathlib import Path


from orkcraft import scroll as ts
from orkcraft.realm import looks, roads
from orkcraft.realm.orcs import RESIDENT, Orc, garrison_badge

SIZE = (200, 50)


def test_scheme_parts_and_badges():
    pair = [{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}]
    styles = [st for _, st in looks.scheme_parts(pair)]
    assert styles[0] == looks.HARNESS_STYLE["agy"] and styles[-1] == looks.HARNESS_STYLE["claude"]
    assert looks.scheme_long(pair) == "write: agy → review: claude"
    lead = Orc("Warchief", "kanban", RESIDENT, lead=True, harness=[{"role": "run", "harness": "claude"}])
    scribe = Orc("Scribe", "digest", RESIDENT, kind="chain")
    assert garrison_badge([lead, scribe]) == "🧌 Warchief+1 ✻ 🔨 💤"
    assert scribe.badge == "🪧 Scribe 🔨 💤"


def _scribe(app):
    ts.add_handler(app.scroll, "town_hall", "Scribe", kind="chain", chain=[{"op": "count"}], why="counting is enough")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="scribe")


async def _settle(pilot, n=3):
    for _ in range(n):
        await pilot.pause()


GOOD = {"name": "Crier", "role": "done digest", "kind": "chain", "why": "a template is enough",
        "chain": [{"op": "template", "md": "✅ {id} — {title}"}],
        "roads": [{"from": "loot", "event": "on_selection_change", "filter": {"node_status": ["done"]}}]}


def _examples(repo: Path) -> None:
    path = roads.examples_file(repo, "town_hall", "seer")
    path.parent.mkdir(parents=True)
    titles = ["Ship login", "Plan the auth migration", "Fix calendar", "Docs", "Cache warmup", "CI"]
    with path.open("w") as f:
        for i, t in enumerate(titles):
            f.write(json.dumps({"inputs": [{"id": f"T10{i}0", "title": t}], "output": f"✅ T10{i}0 — {t}"}) + "\n")


DEMOTE = {"proposals": [{"type": "demote", "orc": "seer", "why": "always id and title",
                         "chain": [{"op": "template", "md": "✅ {id} — {title}"}]}]}


def test_a_scroll_saved_with_the_old_moai_loads_with_the_signpost():
    from orkcraft.scroll import OrcSpec
    assert OrcSpec("a", "A", avatar="🗿", kind="chain").avatar == "🪧"
    assert OrcSpec("b", "B", avatar="🗿🧌", kind="hybrid").avatar == "🪧🧌"
    assert OrcSpec("c", "C").avatar == "🧌"
