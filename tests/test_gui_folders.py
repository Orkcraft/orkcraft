"""Choosing a folder for the Wiki (docs/design/wiki-folders-rules.md §2): the system's dialog per platform,
a dialog on a thread of its own, browsing, recent folders and a dropped folder's path."""
from __future__ import annotations

import time
from pathlib import Path

from orkcraft import settings
from orkcraft.gui import folders


def test_the_systems_dialog_per_platform():
    has = lambda *names: (lambda n: f"/usr/bin/{n}" if n in names else None)      # noqa: E731
    assert folders.command("/x", "darwin", has("osascript"))[0] == "osascript"
    assert folders.command("/x", "linux", has("zenity"))[:3] == ["zenity", "--file-selection", "--directory"]
    assert folders.command("/x", "linux", has("kdialog"))[:2] == ["kdialog", "--getexistingdirectory"]
    assert folders.command("/x", "win32", has("powershell"))[0] == "/usr/bin/powershell"
    assert folders.command("/x", "linux", has()) is None


def _wait(token: str) -> dict:
    end = time.monotonic() + 3
    while time.monotonic() < end:
        got = folders.result(token)
        if got["state"] != "open":
            return got
        time.sleep(0.01)
    raise AssertionError("the dialog never answered")


def test_a_dialog_answers_on_its_own_thread():
    assert _wait(folders.start("/a", ask=lambda start: start + "/b")) == {"state": "done", "path": "/a/b", "error": ""}
    assert _wait(folders.start("", ask=lambda start: None))["state"] == "none"

    def none_here(start):
        raise folders.Unavailable("no folder dialog on this machine")
    got = _wait(folders.start("", ask=none_here))
    assert got["state"] == "error" and got["browse"]
    assert folders.result("nope")["state"] == "error"


def test_browse_lists_folders_only(tmp_path: Path):
    (tmp_path / "b").mkdir()
    (tmp_path / "A").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "file.md").write_text("x")
    got = folders.browse(str(tmp_path))
    assert [d["name"] for d in got["dirs"]] == ["A", "b"] and got["parent"] == str(tmp_path.parent)
    try:
        folders.browse(str(tmp_path / "file.md"))
    except ValueError:
        pass
    else:
        raise AssertionError("a file is not a folder")


def test_recent_folders_newest_first_and_kept(tmp_path: Path):
    machine = settings.MachineSettings()
    for name in ("a", "b", "a"):
        (tmp_path / name).mkdir(exist_ok=True)
        folders.remember(machine, str(tmp_path / name))
    assert machine.recent_folders == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert settings.load().recent_folders == machine.recent_folders
    (tmp_path / "b").rmdir()
    assert folders.recent(machine) == [str(tmp_path / "a")]


def test_a_drop_on_the_window_gives_the_full_path(tmp_path: Path):
    folders.on_drop({"dataTransfer": {"files": [{"name": "specs", "pywebviewFullPath": str(tmp_path / "specs")}]}})
    assert folders.dropped(["specs"]) == [str(tmp_path / "specs")]
    assert folders.dropped(["other"]) == []
