"""The UX bench paints a picture again and lays a window out again (docs/design/improve-buildings.md §6.2): a draft
from the image tool with the style's own prompt, Reset to the shipped one, Apply onto this machine's pictures (served
before the design system's), and a window's UI document laid out by its steward and given to every building of the
type. The image tool is a fake: nothing is painted for real."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings, runners
from orkcraft.design import tokens
from orkcraft.gui import server
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, jobs, painter

PNG = painter.PNG + b"\x00" * 40
HOUSE = "sprites/buildings/barracks/header.png"


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str) -> str:
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, type_id))
    host.refresh_roster()
    return built.id


def _until(cond, s: float = 5.0) -> bool:
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_the_prompt_keeps_the_style_and_says_the_region():
    text = painter.prompt("sprite", HOUSE, "make it cuter", {"x": 0.25, "y": 0.0, "w": 0.5, "h": 0.5})
    assert "style of the reference picture exactly" in text and "make it cuter" in text
    assert "from 25% to 75% of the width" in text and "out.png" in text
    assert painter.kind_of("sprites/intents/logic.png") == "icon" and painter.kind_of("sprites/orks/ork.png") == "ork"
    assert painter.kind_of("../etc/passwd") == "" and painter.kind_of("sprites/fx/fire.png") == ""


def test_a_picture_is_painted_reset_and_applied_on_this_machine(fake_repo, isolated_layout_file, monkeypatch):
    host = _host(fake_repo)
    bench = _raised(host, "ux_lab")
    act = lambda name, **a: host.command("act", {"id": bench, "act": name, "args": a})
    act("pick", type="barracks")
    asked = []

    def work(tool, prompt, folder, cancel, model="", *a, **kw):
        asked.append((tool, prompt, (folder / "reference.png").read_bytes()[:8]))
        (folder / "out.png").write_bytes(PNG)
        return "rounder roof", None, None, ""

    monkeypatch.setattr(jobs, "run_work", work)
    act("paint", path=HOUSE, words="make it cuter", region={"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3})
    assert _until(lambda: act("draft", path=HOUSE)["src"].startswith("data:image/png;base64,"))
    assert asked[0][0] == "agy" and asked[0][2] == painter.PNG and "Change ONLY the region" in asked[0][1]
    act("apply", path=HOUSE)
    own = tokens.assets_dir() / HOUSE
    assert own.read_bytes() == PNG and (tokens.assets_dir() / "sprites/buildings/barracks/header@2x.png").is_file()
    assert server.resolve(f"/ds/{HOUSE}") == own.resolve()                     # served before the design system's
    assert HOUSE in host.detail(bench)["data"]["own"]
    act("reset", path=HOUSE)
    got = act("draft", path=HOUSE)
    assert got["shipped"] and got["src"]
    act("apply", path=HOUSE)
    assert not own.exists() and server.resolve(f"/ds/{HOUSE}") == (tokens.SYSTEM / HOUSE).resolve()
    with pytest.raises(CommandError, match="Nothing to apply"):
        act("apply", path=HOUSE)
    with pytest.raises(CommandError, match="No such picture"):
        act("paint", path="../../etc/passwd", words="x")


def test_a_tool_that_paints_nothing_says_so(fake_repo, isolated_layout_file, monkeypatch):
    host = _host(fake_repo)
    bench = _raised(host, "ux_lab")
    act = lambda name, **a: host.command("act", {"id": bench, "act": name, "args": a})
    act("pick", type="barracks")
    monkeypatch.setattr(jobs, "run_work", lambda *a, **k: ("I cannot make pictures", None, None, ""))
    act("paint", path=HOUSE, words="make it cuter")
    assert _until(lambda: "made no picture" in act("draft", path=HOUSE)["error"])


def test_a_window_is_laid_out_again_for_every_building_of_the_type(fake_repo, isolated_layout_file, monkeypatch):
    host = _host(fake_repo)
    bench, a, b = _raised(host, "ux_lab"), _raised(host, "scrolls"), _raised(host, "scrolls")
    act = lambda name, **x: host.command("act", {"id": bench, "act": name, "args": x})
    act("pick", type="scrolls")
    w = host.detail(bench)["data"]["window"]
    assert w["standing"] and set(w["panes"]) >= {"head", "tree", "page"}
    doc = {"version": 1, "type": "scrolls", "split": "row", "panes": [
        {"id": "head", "component": "status", "size": "auto"}, {"id": "tree", "component": "tree", "size": 1},
        {"id": "page", "component": "markdown", "size": 4}]}
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: (json.dumps(
        {"proposals": [{"type": "ui", "ui": doc, "why": "the page wider"}]}), 0.01))
    act("layout", words="the page wider")
    assert _until(lambda: (host.town.worker(bench).layout or {}).get("doc") == doc)
    act("layout_apply")
    assert all(host.town.scroll.building(x).ui == doc for x in (a, b))


def test_a_card_document_shows_roles_only_and_is_kept_on_this_machine(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.realm import card_docs
    doc = card_docs.default("barracks")
    assert card_docs.problems(doc, "barracks") == []
    bad = json.loads(json.dumps(doc))
    bad["sizes"]["s"]["parts"] = [{"id": "big", "tone": "#ff0000"}, {"id": "big"}, {"id": "logo"}]
    wrong = card_docs.problems(bad, "barracks")
    assert any("tone is a role" in p for p in wrong) and any("twice" in p for p in wrong)
    assert any("a part is one of" in p for p in wrong)
    host = _host(fake_repo)
    bench, pool = _raised(host, "ux_lab"), _raised(host, "barracks")
    act = lambda name, **x: host.command("act", {"id": bench, "act": name, "args": x})
    act("pick", type="barracks")
    assert host.detail(bench)["data"]["cards"]["building"] == pool
    small = {**doc, "sizes": {**doc["sizes"], "s": {"parts": [{"id": "big", "font": "number", "tone": "accent"}]}}}
    answers = iter([json.dumps({**small, "sizes": {"s": {"parts": [{"id": "big", "color": "red"}]}}}), json.dumps(small)])
    prompts = []
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: (prompts.append(prompt) or next(answers), 0.01))
    act("card", words="the small card says only the number", size="s", part="big")
    assert _until(lambda: (host.town.worker(bench).card or {}).get("doc") == small)
    assert "its `big` part only" in prompts[0] and "REJECTED" in prompts[1]               # a wrong answer went back once
    act("card_apply")
    assert card_docs.load("barracks") == small
    hut = next(x for x in host.snapshot()["buildings"] if x["id"] == pool)
    assert hut["card_doc"] == small                                                        # every hut of the type wears it
    act("card_reset")
    act("card_apply")
    assert card_docs.load("barracks") is None
