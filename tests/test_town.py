"""Town view (T1102): every building a hut on the map, one expanded at a time over it."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import buildings, huts, masonry
from orkcraft.realm.masonry import Data, Row

SIZE = (200, 50)


@pytest.fixture
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


# -- the art library and the `mini` block ----------------------------------------------------------

def test_art_library_fits_the_hut():
    assert len(huts.ART) >= 10
    for name, (lines, use) in huts.ART.items():
        assert len(lines) == huts.ART_H and use, name
        assert all(len(ln) <= huts.ART_W and ln.isascii() for ln in lines), name
    assert set(huts.BUILTIN_ART.values()) <= set(huts.ART)
    assert huts.art("nope") == huts.art(huts.DEFAULT_ART)


def test_mini_templates_render_from_fetched_data(tmp_path: Path):
    rows = Data("list", rows=[Row("Fix login", id="T1", status="in-progress"), Row("Docs", id="T2", status="todo"),
                              Row("Tests", id="T3", status="todo")])
    assert huts.render_line("{count} open · {title}", rows) == "3 open · Fix login"
    assert huts.render_line("{count} todo · next {id}", rows, {"status": "todo"}) == "2 todo · next T2"
    assert huts.render_line("{title}", rows, {"status": "done"}) == huts.EMPTY
    log = Data("text", text="collected 12\n\n12 passed in 3s\n")
    assert huts.render_line("{last}", log) == "12 passed in 3s"
    assert huts.render_line("{count} lines", log) == "2 lines"
    md = Data("text", text="```diff\n+x\n```\n## PR · `auth` **fix**\nbody line\n")
    assert huts.render_line("{heading}", md) == "PR · auth fix" and huts.render_line("{last}", md) == "body line"
    (tmp_path / "a").write_text("x")
    assert huts.render_line("{count} files", Data("tree", path=tmp_path)) == "1 files"
    assert huts.render_line("{last}", Data("text", error="no file")).startswith("⚠")

    spec = {"mini": {"art": "forge", "lines": [{"data": "tasks", "template": "⚙ {count}", "where": {"status": "todo"}},
                                               {"data": "log", "template": "{last}"}]}}
    assert huts.custom_status(spec, {"tasks": rows, "log": log}) == ["⚙ 2", "12 passed in 3s"]
    # no `mini`: what the first data entry holds
    assert huts.custom_status({}, {"tasks": rows}) == ["3 rows · Fix login"]
    assert huts.custom_status({}, {"log": log}) == ["12 passed in 3s"]


def _spec(**mini) -> dict:
    return {"id": "ci_watch", "title": "CI Watch", "icon": "🛠", "orc": {"name": "Tinker"},
            "data": [{"name": "open", "source": "graph_nodes", "params": {"status": "todo"}},
                     {"name": "log", "source": "file_tail", "params": {"path": "README.md", "lines": 5}}],
            "layout": {"direction": "vertical", "panes": [{"widget": "list", "data": "open"},
                                                          {"widget": "log", "data": "log"}]},
            **({"mini": mini} if mini else {})}


def test_mini_is_checked_with_the_spec(fake_repo: Path):
    ok = _spec(art="workshop", lines=[{"data": "open", "template": "{count} open · {title}", "where": {"status": "todo"}},
                                      {"data": "log", "template": "{last}"}])
    assert masonry.validate_spec(ok, fake_repo) == []
    assert masonry.validate_spec(_spec(), fake_repo) == []          # optional
    bad = masonry.validate_spec(_spec(art="castle"), fake_repo)
    assert bad and "art" in bad[0]
    errors = masonry.validate_spec(_spec(lines=[{"data": "nope", "template": "{count}"},
                                                {"data": "log", "template": "{title}"}]), fake_repo)
    assert any("no data named 'nope'" in e for e in errors)
    assert any("{title} is not available for text data" in e for e in errors)
    errors = masonry.validate_spec(_spec(lines=[{"data": "log", "template": "{last}", "where": {"status": "x"}}]), fake_repo)
    assert any("where only applies to list data" in e for e in errors)
    errors = masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}", "where": {"colour": "x"}}]), fake_repo)
    assert any("unknown field 'colour'" in e for e in errors)
    assert masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}"}] * 3), fake_repo) == []
    assert masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}"}] * 4), fake_repo)  # at most three


# -- geometry and the scroll -------------------------------------------------------------------------

HUT_W, HUT_H = 18, 12


def test_scroll_keeps_view_and_hut_spots(tmp_path: Path, town):
    presets = buildings.presets(buildings.registry())
    s = ts.load(tmp_path / "s.json", presets)[0]
    assert s.preferences["view"] == "town"
    s.buildings[0].hut = [0.25, 0.5]
    s.preferences["view"] = "tiles"
    assert ts.save(tmp_path / "s.json", s) == []
    back = ts.load(tmp_path / "s.json", presets)[0]
    assert back.buildings[0].hut == [0.25, 0.5] and back.preferences["view"] == "tiles"
    data = json.loads((tmp_path / "s.json").read_text())
    data["buildings"][0]["hut"] = [2, 0]
    (tmp_path / "s.json").write_text(json.dumps(data))
    assert ts.load(tmp_path / "s.json", presets)[1]                 # out of range: refused


# -- the town on the canvas ------------------------------------------------------------------------


# -- the calm console (T1103) ---------------------------------------------------------------------


BUILD_BUTTON_QUERY = "BuildButton"
