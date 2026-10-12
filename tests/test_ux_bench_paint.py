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


def test_a_moving_house_is_painted_as_two_layers_from_the_house_itself(fake_repo, isolated_layout_file, monkeypatch):
    """docs/design/building-motion.md: the mill's still layer and its sails, each painted again from the shipped layer
    with its brief and the motion prompt, a draft until Apply; the bench says how they move and which it has."""
    from orkcraft.realm import motion
    host = _host(fake_repo)
    bench = _raised(host, "ux_lab")
    act = lambda name, **a: host.command("act", {"id": bench, "act": name, "args": a})
    act("pick", type="mill")
    still, part = motion.paths("mill")
    m = host.detail(bench)["data"]["motion"]
    assert m["move"] == "turn" and m["still"] == still and m["part"] == part and "sails" in m["brief"][part]
    assert set(m["have"]) == {still, part}                                       # both shipped
    assert painter.kind_of(part) == "motion" and painter.kind_of("sprites/buildings/mill/header.png") == "sprite"
    asked = []

    def work(tool, prompt, folder, cancel, model="", *a, **kw):
        asked.append((prompt, (folder / "reference.png").read_bytes()))
        (folder / "out.png").write_bytes(PNG)
        return "", None, None, ""

    monkeypatch.setattr(jobs, "run_work", work)
    act("paint", path=part, words=m["brief"][part])
    assert _until(lambda: act("draft", path=part)["src"].startswith("data:image/png;base64,"))
    assert asked[0][1] == (tokens.SYSTEM / part).read_bytes()                    # painted again from the shipped sails
    assert "pixel for pixel" in asked[0][0] and "four sails" in asked[0][0]
    act("apply", path=part)
    assert (tokens.assets_dir() / part).read_bytes() == PNG and part in host.detail(bench)["data"]["own"]
    act("reset", path=part)
    assert act("draft", path=part)["shipped"]
    act("apply", path=part)
    assert not (tokens.assets_dir() / part).exists()
    with pytest.raises(CommandError, match="No such picture"):
        act("paint", path="sprites/buildings/barracks/work-part.png", words="x")   # the Agent pool does not move


MASCOT = "sprites/mascots/other-1.png"


def _pixels(data: bytes) -> tuple[int, int, list[bytes]]:
    """A PNG made by design/mascots.py read back: its size and its rows of RGBA (filter 0, one IDAT)."""
    import struct
    import zlib
    w, h = struct.unpack(">II", data[16:24])
    at, idat = 8, b""
    while at < len(data):
        n = struct.unpack(">I", data[at:at + 4])[0]
        if data[at + 4:at + 8] == b"IDAT":
            idat += data[at + 8:at + 8 + n]
        at += 12 + n
    raw = zlib.decompress(idat)
    return w, h, [raw[y * (4 * w + 1) + 1:(y + 1) * (4 * w + 1)] for y in range(h)]


def test_a_mascots_grid_is_checked_and_drawn_at_its_scale():
    from orkcraft.design import mascots
    g = mascots.grid(MASCOT)
    assert mascots.problems(g) == [] and len(g) == 11 and all(len(r) == 12 for r in g)
    assert any("not in the palette" in p for p in mascots.problems(["Z" * 12] * 11))
    assert mascots.problems(["." * 12] * 11) == ["the grid is empty"]
    assert "11 rows" in mascots.problems(g[:5])[0] and mascots.problems("nope")
    w, h, rows = _pixels(mascots.png(g, 2))
    assert (w, h) == (24, 22)                                                   # the sprite's 1x; its @2x at 4
    k = mascots.palette()["K"]
    y, x = next((y, x) for y, r in enumerate(g) for x, c in enumerate(r) if c == "K")
    assert rows[2 * y][8 * x:8 * x + 4] == bytes(int(k[i:i + 2], 16) for i in (1, 3, 5)) + b"\xff"
    assert rows[0][:4] == b"\x00\x00\x00\x00"                                    # "." is transparent
    assert mascots.is_mascot(MASCOT) and not mascots.is_mascot("sprites/mascots/nope-1.png")
    assert not mascots.is_mascot("sprites/mascots/other-5.png") and not mascots.is_mascot("../other-1.png")
    assert "rows 0–5 and columns 6–11" in mascots.cells({"x": 0.5, "y": 0.0, "w": 0.5, "h": 0.5})


def test_a_mascot_is_drawn_again_as_its_grid_and_kept_on_this_machine(fake_repo, isolated_layout_file, monkeypatch):
    """§6.4: the mascots are a target of their own; a head is drawn again by a text model as its grid (a wrong answer
    goes back once), never by the image tool; Apply keeps its picture, its @2x and its grid; Reset brings it back."""
    from orkcraft.design import mascots
    host = _host(fake_repo)
    bench = _raised(host, "ux_lab")
    act = lambda name, **a: host.command("act", {"id": bench, "act": name, "args": a})
    act("pick", type="mascots")
    d = host.detail(bench)["data"]
    ghost = next(m for m in d["mascots"] if m["role"] == "other")
    assert d["target"] == "mascots" and ghost["nick"] == "Wandering Ghost" and ghost["biome"] == "void"
    assert ghost["paths"] == [f"sprites/mascots/other-{n}.png" for n in (1, 2, 3, 4)] and "window" not in d
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bench)["card"]
    assert card["title"] == "Mascots" and card["pictures"] == 4 * len(d["mascots"])

    hooded = mascots.grid(MASCOT)
    hooded[1] = "....llll...."
    answers = iter([json.dumps({"grid": ["Z" * 12] * 11}), json.dumps({"grid": hooded, "why": "a green hood"})])
    prompts = []
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: (prompts.append(prompt) or next(answers), 0.01))
    monkeypatch.setattr(jobs, "run_work", lambda *a, **k: pytest.fail("a mascot is never painted by the image tool"))
    act("paint", path=MASCOT, words="a green hood", region={"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.2})
    got = {}
    assert _until(lambda: got.update(act("draft", path=MASCOT)) or got["src"].startswith("data:image/png;base64,"))
    assert got["why"] == "a green hood" and "Wandering Ghost" in prompts[0] and "Change ONLY rows 0–2" in prompts[0]
    assert "REJECTED" in prompts[1] and "not in the palette" in prompts[1]          # the wrong grid went back once

    act("apply", path=MASCOT)
    own = tokens.assets_dir() / MASCOT
    assert _pixels(own.read_bytes())[:2] == (24, 22)
    assert _pixels((tokens.assets_dir() / "sprites/mascots/other-1@2x.png").read_bytes())[:2] == (48, 44)
    assert mascots.grid(MASCOT) == hooded and server.resolve(f"/ds/{MASCOT}") == own.resolve()
    assert MASCOT in host.detail(bench)["data"]["own"]

    answers = iter([json.dumps({"grid": hooded[:1] + ["K" * 12] + hooded[2:]})])
    act("paint", path=MASCOT, words="a black band")                              # from this machine's own grid
    assert _until(lambda: act("draft", path=MASCOT)["src"])
    assert prompts[-1].count("....llll....") == 1

    act("reset", path=MASCOT)
    assert act("draft", path=MASCOT)["shipped"]
    act("apply", path=MASCOT)
    assert not own.exists() and not mascots.own_grid(MASCOT).exists() and mascots.grid(MASCOT) != hooded
    with pytest.raises(CommandError, match="No such picture"):
        act("paint", path="sprites/mascots/nope-1.png", words="x")


def test_the_town_is_told_which_houses_move_and_a_layer_not_painted_is_painted_from_the_house(fake_repo, isolated_layout_file, monkeypatch, tmp_path):
    """docs/design/building-motion.md: the snapshot's `motions` names a house whose two layers this machine has (its own
    before the design system's); a house missing one does not move, and its layer is painted from the house."""
    from orkcraft.realm import motion
    host = _host(fake_repo)
    got = host.snapshot()["motions"]
    assert set(got) == {"mill", "catapult"} and got["mill"]["move"] == "turn" and got["catapult"]["move"] == "swing"
    assert got["mill"]["v"] > 0 and 0 < got["mill"]["pivot"][0] < 1
    system = tmp_path / "system"
    monkeypatch.setattr(tokens, "SYSTEM", system)
    head = system / "sprites/buildings/mill/header.png"
    head.parent.mkdir(parents=True)
    head.write_bytes(PNG)
    (system / motion.paths("mill")[0]).write_bytes(PNG)                             # the still layer, no sails yet
    assert motion.ready() == {}
    bench = _raised(host, "ux_lab")
    worker = host.town.worker(bench)
    assert worker.picture(motion.paths("mill")[1]) == PNG                          # the house itself
