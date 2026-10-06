"""Checkpoints (T1108 stage 1): the camp's own git in `.orkcraft/`, one building's revert."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orkcraft.realm import checkpoint as cpt


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root / ".orkcraft"), "ls-files"], capture_output=True, text=True)
    return sorted(out.stdout.split())


def _spec(root: Path, bid: str, **extra) -> None:
    p = root / ".orkcraft" / "buildings" / f"{bid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"id": bid, **extra}), encoding="utf-8")


def test_commits_track_only_what_defines_the_camp(tmp_path: Path):
    _spec(tmp_path, "a", n=1)
    (tmp_path / ".orkcraft" / "ledger.jsonl").write_text("{}\n")
    (tmp_path / ".orkcraft" / "scripts" / "a").mkdir(parents=True)
    (tmp_path / ".orkcraft" / "scripts" / "a" / "run.sh").write_text("echo hi\n")
    scroll_file = tmp_path / ".orkcraft.json"
    scroll_file.write_text(json.dumps({"buildings": [{"id": "a"}]}))
    sha = cpt.commit(tmp_path, "create", "a", "raised", scroll_file)
    assert sha and _tracked(tmp_path) == [".gitignore", "buildings/a.json", "scripts/a/run.sh", "town/scroll.json"]
    assert cpt.commit(tmp_path, "update", "a", "nothing", scroll_file) is None       # nothing changed
    log = subprocess.run(["git", "-C", str(tmp_path / ".orkcraft"), "log", "-1", "--format=%B"],
                         capture_output=True, text=True).stdout
    assert log.startswith("create(a): raised") and "Orkcraft-Building: a" in log


def test_history_and_building_before_see_one_building(tmp_path: Path):
    _spec(tmp_path, "a", n=1)
    cpt.commit(tmp_path, "create", "a", "raised")
    _spec(tmp_path, "b", n=1)
    cpt.commit(tmp_path, "create", "b", "raised")
    _spec(tmp_path, "a", n=2)
    cpt.commit(tmp_path, "update", "a", "n=2")
    _spec(tmp_path, "b", n=2)
    cpt.commit(tmp_path, "update", "b", "n=2")
    assert [c.message for c in cpt.history(tmp_path, "a")] == ["update(a): n=2", "create(a): raised"]
    assert {c.building for c in cpt.history(tmp_path)} == {"a", "b"}
    parent, spec, entry, files = cpt.building_before(tmp_path, "a")
    assert spec == {"id": "a", "n": 1} and entry is None and files == {}
    cpt.restore_files(tmp_path, "a", spec, files)
    assert json.loads((tmp_path / ".orkcraft/buildings/b.json").read_text())["n"] == 2   # b is untouched
    assert json.loads((tmp_path / ".orkcraft/buildings/a.json").read_text())["n"] == 1
    assert cpt.building_before(tmp_path / "nowhere", "a") is None



def test_can_revert_only_with_an_earlier_checkpoint_that_had_the_building(tmp_path: Path):
    assert not cpt.can_revert(tmp_path / "nowhere", "a")
    _spec(tmp_path, "a", n=1)
    cpt.commit(tmp_path, "create", "a", "raised")
    assert not cpt.can_revert(tmp_path, "a")                   # its first checkpoint: nothing before it
    _spec(tmp_path, "b", n=1)
    cpt.commit(tmp_path, "create", "b", "raised")
    assert not cpt.can_revert(tmp_path, "b")                   # the checkpoint before did not have it
    _spec(tmp_path, "a", n=2)
    cpt.commit(tmp_path, "update", "a", "n=2")
    assert cpt.can_revert(tmp_path, "a")


@pytest.mark.asyncio
async def test_revert_puts_one_building_back_and_leaves_the_others(fake_repo: Path):
    from orkcraft.app import OrkcraftApp

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        assert app.build_from_type("catapult") and app.build_from_type("crag")
        await pilot.pause()
        app._custom_view("catapult").save_config({"url": "https://example.test/one"})
        app._custom_view("crag").save_config({"orientation": "horizontal"})
        app._custom_view("catapult").save_config({"url": "https://example.test/two"})
        await pilot.pause()
        msgs = [c.message for c in cpt.history(fake_repo, "catapult")]
        assert msgs[0] == "update(catapult): settings: url" and msgs[-1].startswith("create(catapult)")
        assert app.revert_building("catapult")
        await pilot.pause()
        assert app.custom_specs["catapult"]["config"]["url"] == "https://example.test/one"
        saved = json.loads((fake_repo / ".orkcraft/buildings/catapult.json").read_text())
        assert saved["config"]["url"] == "https://example.test/one"
        assert app.custom_specs["crag"]["config"]["orientation"] == "horizontal"                      # the later change elsewhere stays
        assert cpt.history(fake_repo, "catapult")[0].message.startswith("revert(catapult)")
        assert not app.revert_building("nowhere")
