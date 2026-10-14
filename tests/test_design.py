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


def test_tokens_css_is_written_from_tokens_json():
    """design-system/tokens.css is the JSON's tokens as CSS: changed in the JSON, written by
    `python -m orkcraft.design.tokens`, never by hand."""
    assert (tokens.SYSTEM / "tokens.css").read_text(encoding="utf-8") == tokens.system_css()


def _luminance(hex_: str) -> float:
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_camps_chrome_is_wood_and_maroon_and_reads():
    """docs/design/open-questions.md Q18, color-pass.md §3: Camp's frames, labels and HUD numbers are warm wood, bone
    and maroon, not gold; bright yellow and red are kept for signals. Text reads at 4.5:1, frames and focus at 3:1."""
    import colorsys
    camp = {t["name"]: t["value"]["camp"] for t in tokens.system()["color"]["tokens"]}
    for name in ("ink-gold", "frame", "hut-frame", "frame-focus", "banner", "meter", "road-selected"):
        r, g, b = (int(camp[name][i:i + 2], 16) / 255 for i in (1, 3, 5))
        assert colorsys.rgb_to_hls(r, g, b)[2] < 0.65, f"{name} {camp[name]}: as loud as a signal"
    for ground in ("panel", "panel-raised", "banner"):
        assert _contrast(camp["ink-gold"], camp[ground]) >= 4.5, ground
    assert _contrast(camp["ink"], camp["banner"]) >= 4.5
    for ground in ("panel", "canvas"):
        assert _contrast(camp["frame"], camp[ground]) >= 3, ground
        assert _contrast(camp["frame-focus"], camp[ground]) >= 3, ground
        assert _contrast(camp["road"], camp["canvas"]) >= 3


def test_an_old_token_name_is_an_alias_with_its_new_names_value():
    """docs/design/design-system-v2.md §7: the chrome's v2 names (`wood`, `bone`, `cloth`, `ink-wood`) are the source;
    the old names stay as aliases with the same value in every theme, so nothing in the GUI changes."""
    toks = {t["name"]: t for t in tokens.system()["color"]["tokens"]}
    aliases = {n: t["aliasOf"] for n, t in toks.items() if "aliasOf" in t}
    assert aliases == {"frame": "wood", "frame-focus": "bone", "banner": "cloth", "ink-gold": "ink-wood"}
    for old, new in aliases.items():
        assert toks[old]["value"] == toks[new]["value"], old


def test_the_new_camps_world_keeps_outlines_chips_and_signals_readable():
    """docs/design/design-system-v2.md §5, §7: the ground the sprites stand on is a middle value, so a dark outline and
    a dark chip are seen on it; a chip's words read; yellow and red are only the signals'."""
    import colorsys
    camp = {t["name"]: t["value"]["camp"] for t in tokens.system()["color"]["tokens"]}
    for ground in ("world-grass", "world-grass-light", "world-grass-dark", "world-earth"):
        assert 0.12 <= _luminance(camp[ground]) <= 0.30, ground
        assert _contrast(camp[ground], camp["art-outline"]) >= 3, ground
        assert _contrast(camp[ground], camp["chip"]) >= 3, ground
    assert _contrast(camp["chip-ink"], camp["chip"]) >= 7
    for signal in ("signal-ask", "signal-fire", "signal-held"):
        assert _contrast(camp[signal], camp["chip"]) >= 3, signal
    for name, value in camp.items():
        if not name.startswith(("world-", "art-")):
            continue
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, _, s = colorsys.rgb_to_hls(r, g, b)
        loud = s > 0.6 and (h * 360 < 15 or h * 360 > 345 or 45 <= h * 360 <= 65)
        assert not loud, f"{name} {value}: a signal's yellow or red in the art"


def test_a_chip_stands_off_todays_dark_ground_by_its_wood_edge():
    """The town's ground is still the colour pass's dark earth (docs/design/color-pass.md §3) until v2's world layer
    lands, and there `chip` and `art-outline` are as dark as the ground: the chips (yards.css, layout.css) carry a 1 px
    `wood` ring inside their `art-outline` border, so they stand off it; the ❓ reads on the chip."""
    camp = {t["name"]: t["value"]["camp"] for t in tokens.system()["color"]["tokens"]}
    assert _contrast(camp["wood"], camp["chip"]) >= 3 and _contrast(camp["wood"], camp["canvas"]) >= 3
    assert _contrast(camp["signal-ask"], camp["chip"]) >= 4.5 and _contrast(camp["chip-ink"], camp["chip"]) >= 4.5


def test_a_waiting_carts_chip_names_it_by_a_short_ref():
    from orkcraft.gui.state import cart_ref
    assert cart_ref("view:outputs:review:16307ea4") == "16307ea4"
    assert cart_ref("view:pool:t42") == "t42"
    assert cart_ref("term:claude-1234-abcdef") == ""                      # a terminal's prompt is not a cart
    assert cart_ref("spec:a-very-long-reference-name") == ""


def test_a_question_is_yellow_everywhere():
    """design-system-v2.md §12 answer 2: `alert` (a question waiting, the `fire` tone) is the question's yellow,
    `signal-ask`, in every theme; red stays for an error or 🔥 (`alert-hot`, `signal-fire`); it reads on the panels."""
    toks = {t["name"]: t["value"] for t in tokens.system()["color"]["tokens"]}
    assert toks["alert"] == toks["signal-ask"]
    assert toks["alert-hot"] == toks["signal-fire"]
    for theme, value in toks["alert"].items():
        for ground in ("panel", "canvas", "panel-raised"):
            assert _contrast(value, toks[ground][theme]) >= 4.5, (theme, ground)


def test_generated_reference_sheets_stay_out_of_the_package():
    """docs/design/design-system-v2.md §12 answer 1, color-pass.md §10: the generated reference sheets live in
    docs/design/img/references/ (the docs do not ship); nothing under design-system/, which the wheel carries, is one."""
    system = Path(__file__).resolve().parent.parent / "design-system"
    generated = [p for p in system.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg") or "Generated_Image" in p.name]
    assert generated == []


def test_the_camps_placeholder_sprites_keep_v2s_grid_and_say_they_are_placeholders():
    """design-system-v2.md §11: every camp/ sprite has its manifest row, sits on the grid of 8 (a frame of a strip
    too), and is marked a placeholder until the artist's replaces it (color-pass.md §10b)."""
    import struct
    camp = Path(__file__).resolve().parent.parent / "design-system" / "sprites" / "camp"
    rows = json.loads((camp / "manifest.json").read_text(encoding="utf-8"))["sprites"]
    files = {p.relative_to(camp).as_posix() for p in camp.rglob("*.png")}
    listed = {r["file"] for r in rows} | {r["map"] for r in rows if "map" in r}
    assert files == listed
    for r in rows:
        assert r["placeholder"] is True and r["licence"].startswith("placeholder"), r["file"]
        w, h = struct.unpack(">II", (camp / r["file"]).read_bytes()[16:24])         # the PNG's IHDR
        assert [w, h] == r["size"] and w == r["frame"][0] * r["frames"], r["file"]
        assert not (r["frame"][0] % 8 or r["frame"][1] % 8), r["file"]


def test_motion_is_tokens_and_the_gui_names_only_those():
    """docs/design/design-system-v2.md §10, §12 Q6: the motion values are a token group, written into tokens.css; a
    duration is in ms or s, work moves at 8 fps, and every `--motion-*` the GUI's stylesheets name is one of them."""
    import re
    motion = {t["name"]: t["value"] for t in tokens.system()["motion"]["tokens"]}
    assert motion["motion-frame"] == "125ms" and motion["motion-cover"] == "250ms"
    for name, value in motion.items():
        assert re.fullmatch(r"\d+(ms|s|px)|cubic-bezier\([\d., ]+\)", value), (name, value)
    css = (tokens.SYSTEM / "tokens.css").read_text(encoding="utf-8")
    assert all(f"--{name}: {value};" in css for name, value in motion.items())
    static = Path(tokens.__file__).resolve().parents[1] / "gui" / "static"
    used = {m for f in static.rglob("*.css") for m in re.findall(r"var\(--(motion-[\w-]+)\)", f.read_text(encoding="utf-8"))}
    assert used and used <= set(motion), sorted(used - set(motion))


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
    if "export const work = false" in src:          # no Work window: its card and Info (lighter-buildings.md §2)
        pytest.skip(f"{type_id} has no Work window; its contract stays so its saved documents load")
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
