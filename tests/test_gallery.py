"""tools/gallery.py's page: one section per building with its three views and what was found (no browser)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "gallery.py"


def _gallery():
    spec = importlib.util.spec_from_file_location("gallery", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gallery"] = mod                 # its dataclasses look their module up
    spec.loader.exec_module(mod)
    return mod


def test_the_page_has_a_section_per_building_and_lists_what_was_found():
    gl = _gallery()
    g = gl.Gallery("2026-10-06 03:00", maps=[gl.Shot("shots/map-my-day.jpg", "My Day")])
    b = gl.Building("days", "Calendar", "war_drum", "My Day",
                    closed=[gl.Shot("shots/my-day-days-closed.png", "Closed: the card", 270, 114)],
                    command=[gl.Shot("shots/my-day-days-command-card.png", "Command: Command Card", 438, 438),
                             gl.Shot("shots/my-day-days-command-screen.jpg", "Command: the whole screen", 1440, 900)],
                    full=[gl.Shot("shots/my-day-days-full.png", "Full: the window", 1400, 820)],
                    problems=[{"level": "warn", "view": "closed", "text": "text cut: “<b>Standup</b>”"}])
    g.buildings.append(b)
    g.buildings.append(gl.Building("todo", "Task board", "fields", "My Day"))
    g.errors.append({"at": "Calendar · full", "kind": "pageerror", "text": "TypeError: x is undefined"})
    gl.add_notes(g, {"todo": ["command: the lanes overlap"], "days": ["looks fine apart from the hour"]})
    page = gl.render(g)
    assert page.startswith("<title>Orkcraft Building Gallery</title>")
    assert 'id="my-day-days"' in page and 'id="my-day-todo"' in page
    assert 'src="shots/my-day-days-closed.png" width="270" height="114"' in page          # each view a file of its own
    assert 'src="shots/my-day-days-command-card.png"' in page and 'src="shots/my-day-days-full.png"' in page
    assert '<figure class=screen><img src="shots/my-day-days-command-screen.jpg"' in page
    assert page.index("my-day-days-closed.png") < page.index("command-card.png") < page.index("days-full.png")
    assert "&lt;b&gt;Standup&lt;/b&gt;" in page and "<b>Standup</b>" not in page          # what it found is text
    assert "TypeError: x is undefined" in page and "the lanes overlap" in page
    assert [p["level"] for p in g.buildings[1].problems] == ["eye"]
    assert g.buildings[0].problems[-1] == {"level": "eye", "view": "seen", "text": "looks fine apart from the hour"}
    assert gl.report(g)["buildings"][0]["id"] == "days"
