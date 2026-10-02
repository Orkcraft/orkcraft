"""🛠 File Generator (T1105 stage 5): review generated files, accept keeps, reject rolls back."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import generated, masonry
from orkcraft.screens.typed.generator_view import GeneratorView

SIZE = (200, 46)
SPEC = {"id": "outputs", "title": "Generated", "icon": "🛠", "orc": {"name": "Artisan"}, "type": "generator"}


def _status(repo: Path) -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout


def test_review_lists_accepts_and_rolls_back(fake_repo: Path):
    (fake_repo / "src" / "app.py").write_text("print('changed by an agent')\n")
    (fake_repo / "src" / "new.py").write_text("NEW = 1\n")
    (fake_repo / "docs" / "notes.md").unlink()
    (fake_repo / ".orkcraft").mkdir()
    (fake_repo / ".orkcraft" / "x.json").write_text("{}")
    rv = generated.Review(fake_repo, fake_repo / ".orkcraft" / "generator" / "g")
    rows = {g.path: g.change for g in rv.files()}
    assert rows == {"src/app.py": "M", "src/new.py": "A", "docs/notes.md": "D"}      # .orkcraft is its own
    assert "+print('changed by an agent')" in rv.preview("src/app.py")
    assert rv.preview("src/new.py") == "NEW = 1"

    rv.accept("src/new.py")
    assert [g.path for g in rv.pending()] == ["docs/notes.md", "src/app.py"]
    (fake_repo / "src" / "new.py").write_text("NEW = 2\n")                       # changed again: back for review
    assert "src/new.py" in [g.path for g in rv.pending()]

    kept = rv.reject("src/app.py")
    assert (fake_repo / "src" / "app.py").read_text() == "print('hello')\n"         # restored from HEAD
    assert kept is not None and kept.read_text() == "print('changed by an agent')\n"
    kept_new = rv.reject("src/new.py")
    assert not (fake_repo / "src" / "new.py").exists() and kept_new.read_text() == "NEW = 2\n"
    assert rv.reject("docs/notes.md") is None and (fake_repo / "docs" / "notes.md").exists()
    assert rv.files() == []
    with pytest.raises(ValueError):
        rv.accept("../outside.txt")


def test_scope_limits_the_review(fake_repo: Path):
    (fake_repo / "src" / "a.py").write_text("a\n")
    (fake_repo / "docs" / "b.md").write_text("b\n")
    rv = generated.Review(fake_repo, fake_repo / ".orkcraft" / "generator" / "g", "docs")
    assert [g.path for g in rv.files()] == ["docs/b.md"]


@pytest.mark.asyncio
async def test_the_generator_building_accepts_rejects_and_sends(fake_repo: Path, monkeypatch):
    assert masonry.save_spec(fake_repo, SPEC) == []
    (fake_repo / "src" / "gen1.py").write_text("one\n")
    (fake_repo / "src" / "gen2.py").write_text("two\n")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "outputs", "generator.accepted")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        view = app.desktop.get_window("outputs").query_one(GeneratorView)
        assert view.mini_status()[0] == "2 to review" and "* gen1.py" in view.mini_status()
        app.desktop.focus_window(app.desktop.get_window("outputs"))
        await pilot.pause()
        assert view.selected_path() == "src/gen1.py"
        await pilot.press("r")                                         # reject gen1: gone, kept aside
        await pilot.pause()
        assert not (fake_repo / "src" / "gen1.py").exists()
        assert view.selected_path() == "src/gen2.py"
        assert view.quick_action("generator.accept_all")
        assert view.mini_status()[0] == "all reviewed ✓"
        assert [(p.kind, p.mode, p.value) for p in sent] == [("file", "generator.accepted", "src/gen2.py")]
