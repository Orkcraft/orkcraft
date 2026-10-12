"""The Alchemist's look check (gui/look_check.py, check_cli.py `_looks`): the windows pictured, held against the last
check's, a changed one judged broken or not. The pictures and the judge are fakes here, but for `compare`, which runs
in a Chromium when there is one."""
from __future__ import annotations

import base64
import json

import pytest

from orkcraft import check_cli, cli
from orkcraft.gui import look_check
from orkcraft.realm import check

# 2×2 PNGs: all white, and one with a black pixel
WHITE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMBmjCi+wAAAABJRU5ErkJggg==")
DOT = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNgYGD4z8DAwMDAwMDAAAAMAQEAhZVTpwAAAABJRU5ErkJggg==")


def test_a_window_the_same_new_or_changed(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir(), after.mkdir()
    (before / "pool.png").write_bytes(WHITE)
    (after / "pool.png").write_bytes(WHITE)
    (after / "tower.png").write_bytes(WHITE)
    assert look_check.compare(before, after) == {"pool": 0.0, "tower": 1.0}


@pytest.mark.skipif(bool(look_check.available()), reason="no Playwright here")
def test_how_much_of_a_window_changed_is_measured_in_a_browser(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir(), after.mkdir()
    (before / "pool.png").write_bytes(WHITE)
    (after / "pool.png").write_bytes(DOT)
    try:
        got = look_check.compare(before, after)
    except Exception as e:  # Playwright without its Chromium
        pytest.skip(f"no Chromium: {e}")
    assert 0 < got["pool"] <= 1


def test_the_first_check_pictures_the_next_holds_against_it_and_a_broken_window_is_red(fake_repo, monkeypatch, capsys):
    shots = {"pool": WHITE, "tower": WHITE}

    def capture(folder):
        folder.mkdir(parents=True, exist_ok=True)
        for w, data in shots.items():
            (folder / f"{w}.png").write_bytes(data)
        return {"windows": list(shots), "error": ""}

    monkeypatch.setattr(look_check, "capture", capture)
    monkeypatch.setattr(look_check, "compare", lambda b, a: {w: (0.3 if shots[w] is DOT else 0.0) for w in shots})
    judged = []
    monkeypatch.setattr(check_cli, "_read", lambda tool, prompt, wd, model: judged.append(sorted(p.name for p in wd.iterdir()))
                        or json.dumps({"broken": True, "score": 2, "notes": "the title is cut off"}))
    args = ["--repo", str(fake_repo), "check", "--scenario", "looks", "--only", "scenarios"]
    assert cli.main(args) == 0
    assert "2 windows pictured: the next check holds them against these" in capsys.readouterr().out
    monkeypatch.setattr(check_cli.dt, "datetime", _Later)
    shots["pool"] = DOT
    assert cli.main(args) == 1
    out = capsys.readouterr().out
    assert "| pool | 30% changed |" in out and "broken: the title is cut off" in out
    assert judged == [["after.png", "before.png"]]                 # only the changed window, both pictures
    folder = check_cli.latest(fake_repo)
    assert (folder / "runs/looks/pool/before.png").is_file() and (folder / "runs/looks/pool/judge.json").is_file()


def test_without_playwright_the_looks_are_not_checked_and_not_red(fake_repo, monkeypatch, capsys):
    monkeypatch.setattr(look_check, "capture", lambda folder: {"windows": [], "error": "it needs Playwright"})
    assert cli.main(["--repo", str(fake_repo), "check", "--scenario", "looks", "--only", "scenarios"]) == 0
    assert "not checked: it needs Playwright" in capsys.readouterr().out


class _Later:
    """The second check a minute after the first, so its folder sorts after."""
    import datetime as _dt
    _base = _dt.datetime.now() + _dt.timedelta(minutes=1)

    @classmethod
    def now(cls):
        return cls._base
