"""Tests for CLI and root detection."""
from pathlib import Path
import pytest

from orkcraft.cli import main
from orkcraft.config import find_project_root


def test_find_project_root(fake_repo: Path, tmp_path: Path):
    # From root
    assert find_project_root(fake_repo) == fake_repo
    assert find_project_root(fake_repo) == fake_repo

    # From deep subdirectory
    sub = fake_repo / "tasks" / "todo"
    assert find_project_root(sub) == fake_repo

    # Outside project
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(FileNotFoundError):
        find_project_root(outside)


def test_hooks_install_merges_and_uninstall_removes(tmp_path: Path):
    import json
    import subprocess
    import sys

    from orkcraft.cli import main

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    old = {"command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/session_hook.py\" claude", "type": "command"}
    mine = {"type": "command", "command": "echo mine"}
    settings.write_text(json.dumps({"model": "x", "hooks": {"SessionStart": [{"hooks": [old]}, {"hooks": [mine]}]}}))
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0          # idempotent
    data = json.loads(settings.read_text())
    assert data["model"] == "x"
    start = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert start == ["echo mine", f"{sys.executable} -m orkcraft.hooks.session claude"]   # the old copy replaced
    assert data["hooks"]["PreToolUse"][0]["hooks"][0]["command"].endswith("-m orkcraft.hooks.warder")
    assert main(["--repo", str(tmp_path), "hooks", "uninstall"]) == 0
    data = json.loads(settings.read_text())
    assert data["hooks"] == {"SessionStart": [{"hooks": [mine]}]}


def test_packaged_hooks_run_as_modules(tmp_path: Path):
    import os
    import subprocess
    import sys

    for module, stdin, expect in (("orkcraft.hooks.session", "not json", ""), ("orkcraft.hooks.warder", "{}", "")):
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}   # as installed
        out = subprocess.run([sys.executable, "-m", module, "claude"], input=stdin, capture_output=True, text=True,
                             cwd=tmp_path, env=env)
        assert out.returncode == 0 and out.stdout.strip() == expect, out.stderr
