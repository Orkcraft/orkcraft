"""The design system: tokens, the building UI documents, their contracts, and who may change them."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings, bus
from orkcraft.core.town import Town
from orkcraft.design import tokens, ui
from orkcraft.realm import catalog, checkpoint, masonry, steward


def test_the_tokens_hold_together():
    assert tokens.problems() == []
    assert {"title", "body", "mono", "status"} <= set(tokens.FONTS)
    assert {"ok", "wait", "fire", "error", "harness.claude"} <= set(tokens.TONES)
    assert tokens.style("title", "camp") == "camp-heading" and tokens.style("body", "office") == "office-body"
    assert tokens.css_var("fire") == "--alert"
    assert tokens.color("fire", "office").startswith("#") and tokens.space(9) == tokens.space(6)


def test_the_gui_roles_come_from_the_design_system():
    """design-system/tokens.json is the source of truth: the role classes are read from it, and every
    variable they name is one tokens.css defines."""
    import re
    css = tokens.roles_css()
    defined = set(re.findall(r"(--[\w-]+):", (tokens.SYSTEM / "tokens.css").read_text(encoding="utf-8")))
    used = set(re.findall(r"var\((--[\w-]+)\)", css))
    assert used and used <= defined, sorted(used - defined)
    for role in tokens.FONTS:
        assert f".ok-font-{role} " in css
    assert ".ok-tone-harness-claude { color: var(--harness-claude); }" in css


@pytest.mark.parametrize("type_id", sorted(catalog.TYPES))
def test_every_type_has_a_contract_and_its_default_passes(type_id):
    c = ui.contract(type_id)
    assert ui.validate(c.default, c) == []
    assert c.required() and c.describe().startswith(f"type {type_id}")


JS_BUILDINGS = Path(ui.__file__).resolve().parents[1] / "gui" / "static" / "js" / "buildings"


@pytest.mark.parametrize("type_id", sorted(ui._contract_files()))
def test_the_page_fills_every_pane_of_a_contract(type_id):
    """`panes(id, data)` of the type's page returns a function for every pane its contract names, so a
    pane the document lays out is never empty for want of a key (docs/design/building-views.md §4)."""
    page = JS_BUILDINGS / f"{type_id}.js"
    if not page.exists():
        pytest.skip(f"{type_id} has no page of its own yet")
    import re
    src = page.read_text(encoding="utf-8")
    at = src.index("export function panes(")
    body = src[at:src.index("\n}\n", at)]
    filled = set(re.findall(r"\b(\w+):\s*\(", body))
    assert set(ui.contract(type_id).panes) <= filled, sorted(set(ui.contract(type_id).panes) - filled)


def test_barracks_and_clan_fire_lay_out_their_parts_as_panes():
    assert set(ui.contract("barracks").panes) == {"head", "lanes", "task", "orks", "rules"}
    assert set(ui.contract("council").panes) == {"head", "members", "review", "document", "history"}
    assert {leaf.pane["component"] for leaf in ui.leaves(ui.default("barracks"))} >= {"board", "terminal"}


def test_a_document_kept_before_its_type_got_panes_wears_the_default():
    """A building whose scroll kept the old one-pane `main` document (or any that no longer fits its
    type's contract) gets its type's default; one that fits is kept."""
    from types import SimpleNamespace
    for type_id in ("barracks", "council"):
        main = {"version": 1, "type": type_id, "split": "column",
                "panes": [{"id": "main", "component": "view", "size": 1, "font": "body"}]}
        assert ui.current(SimpleNamespace(ui=main), type_id) == ui.default(type_id)
        kept = ui.default(type_id)
        kept["panes"][0]["title"] = "Now"
        assert ui.current(SimpleNamespace(ui=kept), type_id) == kept


def test_the_validator_says_what_to_fix():
    c = ui.contract("lake")
    doc = ui.default("lake")
    view = next(p for p in doc["panes"] if p["id"] == "view")
    view.update(component="tree", font="huge", tone="pink", hidden=True)
    doc["panes"].append({"id": "sidebar", "component": "list"})
    doc["panes"].append(dict(doc["panes"][0]))
    problems = ui.validate(doc, c)
    assert "pane view: may be markdown, diff, text, not 'tree'" in problems
    assert any("font 'huge'" in p for p in problems) and any("tone 'pink'" in p for p in problems)
    assert "pane view: is required, it cannot be hidden" in problems
    assert any(p.startswith("pane sidebar: not a pane of lake") for p in problems)
    assert "pane head: appears twice" in problems
    editor = copy.deepcopy(ui.default("lake"))
    editor["panes"][2]["hidden"] = False
    assert ui.validate(editor, c) == ["pane editor: shows and hides by itself, leave out hidden"]
    assert ui.validate(ui.default("fields"), c)[0].startswith("type:")
    deep = {"version": 1, "type": "scrolls", "split": "column", "panes": [{"id": "head", "component": "status"},
            {"split": "row", "panes": [{"split": "column", "panes": [{"split": "row", "panes": [
                {"id": "tree", "component": "tree"}, {"id": "page", "component": "markdown"}]}]}]}]}
    assert any("nest" in p for p in ui.validate(deep, ui.contract("scrolls")))
    assert ui.validate({"version": 1, "type": "lake", "split": "diagonal", "panes": []}, c)


def test_a_document_reads_in_order_and_in_one_line():
    doc = ui.default("scrolls")
    assert [(leaf.pane["id"], leaf.split) for leaf in ui.leaves(doc)] == [("head", "column"), ("tree", "row"),
                                                                           ("page", "row")]
    assert ui.outline(doc).startswith("head (status, auto") and "[tree (tree, 2" in ui.outline(doc)


def test_the_scroll_keeps_a_building_ui(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    doc = ui.default("lake")
    town.scroll.building("loot").ui = doc
    assert town.save()
    again = ts.TownScroll.from_dict(json.loads(isolated_layout_file.read_text()))
    assert again.building("loot").ui == doc and again.building("town_hall").ui is None
    assert ui.current(again.building("loot"), "lake") == doc
    assert ui.current(again.building("loot"), "fields") == ui.default("fields")     # another type: its default


def _lake(repo: Path, bid: str = "insight") -> None:
    spec = {"id": bid, "title": "Lake", "icon": "🌊", "orc": {"name": "Seer"}, "type": "lake"}
    assert masonry.save_spec(repo, spec) == []


def test_set_ui_checks_keeps_publishes_and_z_takes_it_back(fake_repo):
    _lake(fake_repo)
    town = Town(fake_repo)
    checkpoint.ensure(fake_repo)
    town.checkpoint("create", "insight", "raise lake")
    seen = []
    town.bus.subscribe(bus.UI, seen.append)
    assert buildings.ui_type(town, "insight") == "lake" and buildings.ui_type(town, "town_hall") == "town_hall"
    bad = dict(ui.default("lake"), panes=[{"id": "view", "component": "markdown"}])
    assert buildings.set_ui(town, "insight", bad) == ["panes: missing head (required)"] and not seen
    doc = ui.default("lake")
    doc["panes"][1]["size"] = 3
    doc["note"] = "the page reads larger"
    assert buildings.set_ui(town, "insight", doc, by="steward", why="larger page") == []
    assert town.scroll.building("insight").ui == doc and seen[-1].data["ui"] == doc
    assert checkpoint.history(fake_repo, "insight", 1)[0].message.startswith("ui(insight)")
    assert buildings.revert(town, "insight")
    assert town.scroll.building("insight").ui is None and seen[-1].data["ui"] == ui.default("lake")


def test_a_steward_redesigns_from_a_wish_and_is_sent_back_when_wrong(fake_repo):
    _lake(fake_repo)
    town = Town(fake_repo)
    good = ui.default("lake")
    good["panes"][0]["title"] = "Now"
    answers = [json.dumps({"proposals": [{"type": "ui", "ui": {"type": "lake"}, "why": "x"}]}),
               json.dumps({"proposals": [{"type": "ui", "ui": good, "why": "a heading on the status line"}]})]
    prompts = []

    def runner(prompt):
        prompts.append(prompt)
        return answers[len(prompts) - 1], 0.01

    report = steward.redesign(fake_repo, town.scroll, "insight", "lake", "put a heading on the status", runner=runner)
    assert report.attempts == 2 and len(report.proposals) == 1 and report.proposals[0].data["ui"] == good
    assert "THE RULES" in prompts[0] and "pane view (required)" in prompts[0] and "REJECTED" in prompts[1]
    trial = copy.deepcopy(town.scroll)
    assert steward.apply_proposal(trial, "insight", report.proposals[0].to_dict()) == "a new layout"
    assert trial.building("insight").ui == good
    assert steward.redesign(fake_repo, town.scroll, "insight", "lake", "x", budget_ok=False).error
