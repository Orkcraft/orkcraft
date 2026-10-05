"""The design system: tokens, the building UI documents, their contracts, and who may change them."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.core import buildings, bus, runners
from orkcraft.core.town import Town
from orkcraft.design import tokens, ui
from orkcraft.realm import catalog, checkpoint, masonry, steward
from orkcraft.screens.typed.knowledge_view import KnowledgeView
from orkcraft.screens.typed.lake_view import LakeView


def test_the_tokens_hold_together():
    assert tokens.problems() == []
    assert {"title", "body", "mono", "status"} <= set(tokens.FONTS)
    assert {"ok", "wait", "fire", "error", "harness.claude"} <= set(tokens.TONES)
    assert "Cinzel" in tokens.family("title", "camp") and "Inter" in tokens.family("title", "office")
    assert tokens.color("fire", "office").startswith("#") and tokens.space(9) == tokens.space(6)


@pytest.mark.parametrize("type_id", sorted(catalog.TYPES))
def test_every_type_has_a_contract_and_its_default_passes(type_id):
    c = ui.contract(type_id)
    assert ui.validate(c.default, c) == []
    assert c.required() and c.describe().startswith(f"type {type_id}")


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


@pytest.mark.asyncio
async def test_the_tui_lays_a_view_out_as_its_document_says(fake_repo, monkeypatch):
    _lake(fake_repo)
    assert masonry.save_spec(fake_repo, {"id": "dump", "title": "Dump", "icon": "🗑️", "orc": {"name": "Lib"},
                                         "type": "scrolls"}) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        lake = app.desktop.get_window("insight").query_one(LakeView)
        assert str(lake.query_one("#lake-scroll").styles.height) == "1fr"
        doc = ui.default("lake")
        doc["panes"][0].update(title="Now", font="title", tone="fire")
        doc["panes"][1]["size"] = 4
        assert buildings.set_ui(app.core, "insight", doc) == []
        await pilot.pause()
        head = lake.query_one("#lake-head")
        assert head.border_title == "Now" and "bold" in str(head.styles.text_style)
        assert str(lake.query_one("#lake-scroll").styles.height) == "4fr"

        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        flipped = ui.default("scrolls")
        row = flipped["panes"][1]
        row["panes"] = list(reversed(row["panes"]))
        assert buildings.set_ui(app.core, "dump", flipped) == []
        await pilot.pause()
        order = [c.id for c in dump.query_one("#kb-tree").parent.children]
        assert order.index("kb-page") < order.index("kb-tree")


@pytest.mark.asyncio
async def test_d_asks_the_steward_and_enter_keeps_the_new_layout(fake_repo, monkeypatch):
    _lake(fake_repo)
    good = ui.default("lake")
    good["panes"][1]["size"] = 5
    monkeypatch.setattr(runners, "STEWARD_RUNNER",
                        lambda p: (json.dumps({"proposals": [{"type": "ui", "ui": good, "why": "a bigger page"}]}), 0.01))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        app.redesign_building("insight")
        await pilot.pause()
        await pilot.press(*"bigger page")
        await pilot.press("enter")
        for _ in range(40):
            await pilot.pause(0.05)
            if type(app.screen).__name__ == "StewardView":
                break
        assert type(app.screen).__name__ == "StewardView"
        await pilot.press("enter")
        await pilot.pause()
        assert app.scroll.building("insight").ui == good
