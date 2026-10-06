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


def test_codex_hooks_go_into_codex_hooks_json(tmp_path: Path, monkeypatch, capsys):
    import json
    import subprocess
    import sys

    from orkcraft.cli import main
    from orkcraft.hooks import install as hooks_install

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(hooks_install.shutil, "which", lambda name: None)
    assert hooks_install.install_all(tmp_path) == [tmp_path / ".claude" / "settings.json"]   # no Codex here
    assert not (tmp_path / ".codex").exists()

    (tmp_path / ".codex").mkdir()                                     # the project configures Codex
    codex = tmp_path / ".codex" / "hooks.json"
    codex.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0  # idempotent
    assert "/hooks" in capsys.readouterr().out                       # Codex runs them once trusted
    data = json.loads(codex.read_text())
    pre = data["hooks"]["PreToolUse"]
    assert len(pre) == 1 and pre[0]["matcher"] == "Bash|apply_patch|Edit|Write"
    assert pre[0]["hooks"][0]["command"] == f"{sys.executable} -m orkcraft.hooks.warder codex"
    assert data["hooks"]["SessionStart"][0]["hooks"][0]["command"].endswith("-m orkcraft.hooks.session codex")
    assert main(["--repo", str(tmp_path), "hooks", "uninstall"]) == 0
    assert json.loads(codex.read_text())["hooks"] == {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}


def test_agy_hooks_merge_into_agents_hooks_json_and_leave_the_rest(tmp_path: Path, monkeypatch, capsys):
    import json
    import subprocess
    import sys

    from orkcraft.cli import main
    from orkcraft.hooks import install as hooks_install

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(hooks_install.shutil, "which", lambda name: None)
    assert hooks_install.install_all(tmp_path) == [tmp_path / ".claude" / "settings.json"]   # no agy here
    assert not (tmp_path / ".agents").exists()

    monkeypatch.setattr(hooks_install.tools, "agy_version", lambda: "1.1.11")
    assert not hooks_install.wants_agy()                                  # too old to be guarded
    monkeypatch.setattr(hooks_install.tools, "agy_version", lambda: "1.2.17")
    agents = tmp_path / ".agents" / "hooks.json"
    agents.parent.mkdir()
    theirs = {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo mine"}]}]}
    agents.write_text(json.dumps({"mine": theirs}))
    assert main(["--repo", str(tmp_path), "hooks", "install", "--no-agy-global"]) == 0
    assert main(["--repo", str(tmp_path), "hooks", "install", "--no-agy-global"]) == 0    # idempotent
    assert "trusted" in capsys.readouterr().out
    data = json.loads(agents.read_text())
    assert set(data) == {"mine", "orkcraft"} and data["mine"] == theirs
    pre = data["orkcraft"]["PreToolUse"]
    assert len(pre) == 1 and "run_command" in pre[0]["matcher"] and "view_file" in pre[0]["matcher"]
    assert pre[0]["hooks"][0]["command"] == f"{sys.executable} -m orkcraft.hooks.warder agy"
    assert data["orkcraft"]["Stop"][0]["command"].endswith("-m orkcraft.hooks.session agy")
    assert not hooks_install.agy_global_file().exists()                 # never without a yes

    assert main(["--repo", str(tmp_path), "hooks", "uninstall"]) == 0
    assert json.loads(agents.read_text()) == {"mine": theirs}


def test_agy_global_hooks_only_after_a_yes(tmp_path: Path, monkeypatch):
    import io
    import json
    import subprocess

    import orkcraft.cli as cli
    from orkcraft.cli import main
    from orkcraft.hooks import install as hooks_install

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(hooks_install.shutil, "which", lambda name: None)
    monkeypatch.setattr(hooks_install.tools, "agy_version", lambda: "1.2.17")
    glob = hooks_install.agy_global_file()
    glob.parent.mkdir(parents=True)
    glob.write_text(json.dumps({"someone": {"Stop": []}}))

    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("y\n"))          # piped: never asked, never written
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0
    assert json.loads(glob.read_text()) == {"someone": {"Stop": []}}

    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True
    asked: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or "n")
    monkeypatch.setattr(cli.sys, "stdin", Tty())
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0
    assert "temp folder" in asked[0] and "orkcraft" not in json.loads(glob.read_text())
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert main(["--repo", str(tmp_path), "hooks", "install"]) == 0
    data = json.loads(glob.read_text())
    assert set(data) == {"someone", "orkcraft"}

    assert main(["--repo", str(tmp_path), "hooks", "uninstall", "--no-agy-global"]) == 0
    assert "orkcraft" in json.loads(glob.read_text())                   # left alone when told to
    assert main(["--repo", str(tmp_path), "hooks", "uninstall"]) == 0
    assert json.loads(glob.read_text()) == {"someone": {"Stop": []}}


def test_agy_hooks_file_that_is_not_json_is_left_alone(tmp_path: Path):
    import pytest as _pytest

    from orkcraft.hooks import install as hooks_install

    broken = tmp_path / "hooks.json"
    broken.write_text("{nope")
    with _pytest.raises(ValueError):
        hooks_install.install_agy(broken)
    assert broken.read_text() == "{nope"


def test_the_demo_flag_never_swallows_the_gui_subcommand(monkeypatch, tmp_path: Path):
    """`orkcraft --demo gui` and `orkcraft gui --demo` both open the sandbox in the GUI, not the TUI."""
    import orkcraft.cli as cli
    import orkcraft.demo as demo
    opened = []

    class Launch:
        @staticmethod
        def run(root, auto_commit, layout, demo=False, browser=False, port=0, look="office"):
            opened.append((root, demo, browser))
            return 0

    monkeypatch.setattr(cli, "_gui", lambda: Launch)
    monkeypatch.setattr(demo, "build", lambda path, reset=False, set_name="main": tmp_path)
    monkeypatch.setattr(cli, "OrkcraftApp", lambda *a, **kw: pytest.fail("the TUI opened"))
    assert main(["--demo", "gui"]) == 0
    assert main(["gui", "--demo", "--browser"]) == 0
    assert main(["--demo", "gui", "--browser"]) == 0
    assert opened == [(tmp_path, True, False), (tmp_path, True, True), (tmp_path, True, True)]
