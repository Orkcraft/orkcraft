"""Two modes: immersion (orcs, fire, rocks, gold) and hidden (people, ❓, squares, words)."""
from __future__ import annotations

from pathlib import Path

import pytest
from rich.cells import cell_len

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, modes, silhouettes as sil
from orkcraft.widgets import carts
from orkcraft.widgets.hud import Hud
from orkcraft.widgets.hut import ALERT_RED, FIRE, FIRE_GROUND, Hut

SIZE = (200, 56)
ASKING = "🧌 Peon 🔨 🔥"


@pytest.fixture(autouse=True)
def immersion():
    modes.set_current(modes.IMMERSION)
    yield
    modes.set_current(modes.IMMERSION)


def test_the_old_plain_reads_as_hidden_and_badges_speak_the_mode():
    assert modes.normalize("plain") == modes.normalize("hidden") == modes.HIDDEN
    assert modes.normalize(None) == modes.normalize("anything") == modes.IMMERSION
    assert modes.skin(ASKING) == ASKING
    assert modes.skin("🗿🧌 Smith+1 C 🔨 🔥", modes.HIDDEN) == "Smith+1 C ?"
    assert modes.skin("🗿 Bot 🕒 ⚙", modes.HIDDEN) == "Bot busy"
    assert modes.skin("🧌 Peon 🔨 💤", modes.HIDDEN) == "Peon"
    assert (modes.cart_glyph(), modes.cart_glyph(modes.HIDDEN)) == ("🪨", "■")
    assert [modes.resource(r, modes.HIDDEN) for r in ("gold", "lumber", "supply")] == ["Spend", "Context", "Agents"]


def test_the_fire_goes_orange_then_red_then_takes_the_roof():
    assert modes.fire_stage(0) == ("orange", 0.0)
    assert modes.fire_stage(modes.FIRE_RED_S) == ("red", 0.0)
    stage, half = modes.fire_stage((modes.FIRE_ROOF_S + modes.FIRE_ROOF_FULL_S) / 2)
    assert stage == "red" and half == pytest.approx(0.5)
    assert modes.fire_stage(modes.FIRE_ROOF_FULL_S * 10) == ("red", 1.0)

    roof = ["    /\\    ", "   /  \\   ", " _/____\\_ "]
    assert modes.burn(roof, 0) == roof
    some, more, all_ = modes.burn(roof, 0.3), modes.burn(roof, 0.7), modes.burn(roof, 1.0)
    count = lambda lines: sum(ln.count("🔥") for ln in lines)                      # noqa: E731
    assert 0 < count(some) < count(more) < count(all_)
    assert all(cell_len(ln) == len(r) for ln, r in zip(all_, roof))               # the width stays
    assert not any(set(ln) - set("🔥 ") for ln in all_)                           # nothing left unburnt
    lit = {(r, c) for r, ln in enumerate(some) for c, ch in enumerate(ln) if ch == "🔥"}
    assert lit and modes.burn(roof, 0.3) == some                                  # the same every redraw


def _roof(hut: Hut) -> str:
    return "\n".join(str(hut.render()).splitlines()[len(hut.label.lines):len(hut.label.lines) + 3])


def _styles(hut: Hut) -> set[str]:
    return {str(span.style) for span in hut.render().spans}


def test_a_hut_left_waiting_burns_and_the_whole_card_takes_the_colour():
    hut = Hut("w", sil.WATCHTOWER, [])
    hut.set_title(1, "🗼 Tower")
    hut.set_badge(ASKING, now=0.0)
    assert hut.on_fire and hut.has_class("-alert") and not hut.has_class("-burning")
    name = hut.render().spans[0]
    assert str(name.style) == FIRE[0]                                            # the name: orange letters only
    assert _styles(hut) == {FIRE[0], f"{FIRE[0]} on {FIRE_GROUND[0]}"}            # the building: on an orange ground
    hut.update_fire(now=modes.FIRE_RED_S + 1)
    assert hut.has_class("-burning") and "🔥" not in _roof(hut)
    assert _styles(hut) == {f"bold {FIRE[1]}", f"bold {FIRE[1]} on {FIRE_GROUND[1]}"}
    hut.update_fire(now=(modes.FIRE_ROOF_S + modes.FIRE_ROOF_FULL_S) / 2)
    half = _roof(hut).count("🔥")
    hut.update_fire(now=modes.FIRE_ROOF_FULL_S)
    assert 0 < half < _roof(hut).count("🔥")
    assert "/" not in _roof(hut)                                                 # the roof is all fire
    assert "│" in str(hut.render())                                             # the walls still stand

    hut.set_badge("🧌 Peon 🔨 💤")                                               # answered: the fire is out
    assert not hut.on_fire and not hut.has_class("-burning") and "🔥" not in str(hut.render())


def test_in_the_hidden_mode_a_waiting_hut_only_gets_a_red_frame():
    modes.set_current(modes.HIDDEN)
    hut = Hut("w", sil.WATCHTOWER, [])
    hut.set_plain(True)
    hut.set_title(1, "🗼 Tower")
    hut.set_status(["all quiet"])
    hut.set_badge(ASKING, now=0.0)
    hut.update_fire(now=modes.FIRE_ROOF_FULL_S * 2)
    drawn = hut.render()
    out = drawn.plain
    assert "🔥" not in out and "🧌" not in out and "🗼" not in out and " ? " in out and "Tower" in out
    assert not hut.has_class("-burning") and hut.fire_ground() is None
    assert not any(" on " in str(sp.style) for sp in drawn.spans)                  # no red ground
    red = "".join(out[sp.start:sp.end] for sp in drawn.spans if str(sp.style) == f"bold {ALERT_RED}")
    assert "┌" in red and "│" in red and "Tower" in red                             # the frame and the name
    assert "all quiet" not in red                                                  # not the text inside


def test_carts_are_rocks_or_squares():
    assert carts.cart_look("sent").plain == "🪨"
    modes.set_current(modes.HIDDEN)
    assert carts.cart_look("error").plain == "■" and "#ef4444" in str(carts.cart_look("error").style)


@pytest.mark.asyncio
async def test_the_hud_speaks_gold_and_lumber_or_words(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hud = app.query_one(Hud)
        hud.resources.alerts = 2
        hud.update_hud()
        text = str(hud.render())
        assert "🪙" in text and "🪵" in text and "🥩" in text and "🔥 2" in text and "🧌" in text
        app.desktop.set_mode(True)
        await pilot.pause()
        text = str(hud.render())
        assert "Spend $" in text and "Context" in text and "Agents" in text and "? 2" in text
        assert not modes._EMOJI.search(text)                                       # no emoji at all
        assert app.desktop.has_class("-hidden") and modes.hidden()
        app.desktop.set_mode(False)
        await pilot.pause()
        assert "🪙" in str(hud.render()) and not app.desktop.has_class("-hidden")


@pytest.mark.asyncio
async def test_a_scroll_with_the_old_plain_opens_hidden(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")
    assert masonry.save_spec(fake_repo, {"id": "mill", "title": "Mill", "icon": "🏗", "orc": {"name": "Peon"},
                                         "type": "mill"}) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.desktop.scroll.preferences["mode"] = "plain"
        app.desktop._wear_mode()
        assert app.desktop.plain and modes.hidden()


@pytest.mark.asyncio
async def test_the_hidden_mode_has_no_biome_black_ground_grey_frames(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from orkcraft import theme
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")
    assert masonry.save_spec(fake_repo, {"id": "mill", "title": "Mill", "icon": "🏗", "orc": {"name": "Peon"},
                                         "type": "mill"}) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        d = app.desktop
        biome = d.biome
        assert d.look.name == biome and d.has_class(f"biome-{biome}")
        d.set_mode(True)
        await pilot.pause()
        assert d.look is theme.OFFICE and d.has_class("biome-office") and not d.has_class(f"biome-{biome}")
        assert d.terrain.biome is theme.OFFICE and not theme.OFFICE.glyphs
        hut = d.huts["mill"]
        assert hut.styles.color.hex.lower() == theme.OFFICE.border and hut.styles.background.hex == "#000000"
        assert d.biome == biome                                   # the orkspace keeps its biome …
        d.set_mode(False)
        await pilot.pause()
        assert d.look.name == biome and d.has_class(f"biome-{biome}")   # … and wears it again


def test_emoji_go_and_the_text_stays():
    from rich.text import Text
    assert modes.strip_emoji("🌾 Task fields") == "Task fields"
    assert modes.strip_emoji("[🪙 $1 / $5]") == "[$1 / $5]"
    assert modes.strip_emoji("✓ all reviewed · 02:15 → done") == "✓ all reviewed · 02:15 → done"
    assert modes.strip_emoji(" 👍 ") == "+1"
    t = Text("▶ [F1] ")
    t.append("🏡 My Day", style="bold red")
    out = modes.strip_rich(t)
    assert out.plain == "▶ [F1] My Day" and any("red" in str(sp.style) for sp in out.spans)
    assert modes.text("🌾 Fields") == "🌾 Fields" and modes.text("🌾 Fields", modes.HIDDEN) == "Fields"


def test_a_hidden_hut_has_no_emoji_at_all():
    from orkcraft.realm.catalog import ActionDef
    modes.set_current(modes.HIDDEN)
    hut = Hut("t", sil.TOWN_HALL, [ActionDef("a", "Preset", "📜", "")])
    hut.set_plain(True)
    hut.set_title(9, "🏰 Town hall")
    hut.set_status(["🛡 all quiet", "🪙 $0.00 / $5"])
    hut.set_badge("🧌 Peon 🔨 💤")
    out = hut.render().plain
    assert not modes._EMOJI.search(out)
    assert "Town Hall" in out and "all quiet" in out and "$0.00 / $5" in out and "[Preset]" in out
