"""Updates (core/updates.py, gui/updates.py, docs/updates.md): the list of releases, what is offered,
what installs by itself when the town opens, and how each kind of install upgrades."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import __version__, cli, settings
from orkcraft.core import updates

ROOT = Path(__file__).resolve().parents[1]


def manifest(*rels: tuple[str, bool]) -> dict:
    return {"releases": [{"version": v, "critical": c, "notes": f"notes of {v}"} for v, c in rels]}


@pytest.fixture
def on(monkeypatch):
    """Updates are read here (conftest turns them off for every other test)."""
    monkeypatch.delenv("ORKCRAFT_NO_UPDATE", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv(updates.UPDATED_ENV, raising=False)


class Runs:
    """subprocess.run as a script: each command answered from `answers` (by its first words), all kept."""

    def __init__(self, version: str = "9.0.0", fail: str = "", status: str = "", branch: str = "main"):
        self.calls: list[list[str]] = []
        self.version, self.fail, self.status, self.branch = version, fail, status, branch

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        line = " ".join(cmd)
        if "import orkcraft" in line:
            return SimpleNamespace(returncode=0, stdout=self.version + "\n", stderr="")
        if " status " in f" {line} ":
            return SimpleNamespace(returncode=0, stdout=self.status, stderr="")
        if "symbolic-ref" in line:
            return SimpleNamespace(returncode=0 if self.branch else 1, stdout=self.branch + "\n", stderr="")
        if self.fail and self.fail in line:
            return SimpleNamespace(returncode=1, stdout="", stderr="no network")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")


# -- versions and the list ----------------------------------------------------------------------

def test_versions_compare_as_numbers():
    assert updates.newer("0.1.10", "0.1.9")
    assert not updates.newer("0.2", "0.2.0") and not updates.newer("0.2.0", "0.2")
    assert updates.newer("v1.0.0", "0.9.9")
    assert updates.version_key("1.2.0rc1") == (1, 2)


def test_nothing_is_offered_when_nothing_is_newer():
    assert updates.offer(manifest(("0.1.0", True), (__version__, False))) is None
    assert updates.offer({}) is None and updates.offer("broken") is None


def test_an_offer_is_critical_when_any_release_on_the_way_is():
    found = updates.offer(manifest(("0.4.0", False), ("0.3.0", True), ("0.1.0", True)), current="0.2.0")
    assert found.version == "0.4.0" and found.critical
    assert found.notes == ["0.4.0: notes of 0.4.0", "0.3.0: notes of 0.3.0"]
    assert found.critical_notes == ["0.3.0: notes of 0.3.0"]
    calm = updates.offer(manifest(("0.4.0", False), ("0.1.0", True)), current="0.2.0")
    assert calm.version == "0.4.0" and not calm.critical


def test_malformed_releases_are_left_out():
    found = updates.offer({"releases": [{"version": 3}, "x", {"notes": "no version"}, {"version": "0.9.0"}]},
                          current="0.1.0")
    assert found.version == "0.9.0" and not found.critical


def test_what_installs_by_itself_follows_the_policy():
    critical = updates.offer(manifest(("9.0.0", True)))
    calm = updates.offer(manifest(("9.0.0", False)))
    assert updates.due(critical, "critical") and updates.due(critical, "auto") and not updates.due(critical, "ask")
    assert not updates.due(calm, "critical") and updates.due(calm, "auto") and not updates.due(calm, "ask")
    assert not updates.due(None, "auto")


def test_the_repositorys_list_names_this_version_last():
    data = json.loads((ROOT / "updates.json").read_text(encoding="utf-8"))
    rels = updates.releases(data)
    assert rels and len(rels) == len(data["releases"]), "every release in updates.json is well formed"
    assert rels[0].version == __version__, "a release raises orkcraft.__version__ and lists it in updates.json"


# -- reading the list ---------------------------------------------------------------------------

def test_the_list_is_read_again_only_when_old(on, tmp_path):
    file = tmp_path / "state.json"
    reads = []
    read = lambda: reads.append(1) or manifest(("9.0.0", False))   # noqa: E731
    s = updates.check(now=1000.0, file=file, read=read)
    assert s.manifest["releases"][0]["version"] == "9.0.0" and len(reads) == 1
    updates.check(now=1000.0 + updates.CHECK_EVERY_S - 1, file=file, read=read)
    assert len(reads) == 1
    updates.check(now=1000.0 + updates.CHECK_EVERY_S + 1, file=file, read=read)
    assert len(reads) == 2


def test_a_list_that_cannot_be_read_keeps_the_last(on, tmp_path):
    file = tmp_path / "state.json"
    updates.check(now=0.0, file=file, read=lambda: manifest(("9.0.0", True)))

    def broken():
        raise OSError("offline")
    s = updates.check(now=updates.CHECK_EVERY_S * 2, file=file, read=broken)
    assert updates.offer(s.manifest).critical
    with pytest.raises(OSError):
        updates.check(force=True, file=file, read=broken)


def test_the_list_reads_from_a_file_url(on, tmp_path, monkeypatch):
    where = tmp_path / "updates.json"
    where.write_text(json.dumps(manifest(("9.0.0", True))), encoding="utf-8")
    monkeypatch.setenv("ORKCRAFT_UPDATE_URL", where.as_uri())
    assert updates.fetch()["releases"][0]["version"] == "9.0.0"


def test_nothing_is_read_when_turned_off(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_NO_UPDATE", "1")
    assert updates.blocked()
    s = updates.check(force=True, file=tmp_path / "s.json", read=lambda: pytest.fail("read while off"))
    assert s.manifest == {}
    monkeypatch.delenv("ORKCRAFT_NO_UPDATE")
    monkeypatch.setenv("CI", "true")
    assert updates.blocked() == "running under CI"


# -- how this copy upgrades ---------------------------------------------------------------------

def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "orkcraft-src"
    (root / ".git").mkdir(parents=True)
    (root / "orkcraft").mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "orkcraft"\n', encoding="utf-8")
    return root


def test_a_git_checkout_pulls(tmp_path):
    root = checkout(tmp_path)
    way = updates.method(root / "orkcraft", prefix=str(root / ".venv"), which=lambda name: "/bin/" + name)
    assert way.kind == "git" and way.steps[0] == ("git", "-C", str(root), "pull", "--ff-only")
    assert way.steps[1][:3] == ("uv", "pip", "install")
    assert updates.method(root / "orkcraft", prefix="/x", which=lambda name: None).steps == way.steps[:1]


def test_pipx_and_uv_upgrade_with_their_own_tool(tmp_path):
    pkg = tmp_path / "site" / "orkcraft"
    has = lambda name: "/bin/" + name   # noqa: E731
    pipx = updates.method(pkg, prefix="/home/a/.local/share/pipx/venvs/orkcraft", which=has)
    assert pipx.kind == "pipx" and pipx.steps == (("pipx", "upgrade", "orkcraft"),)
    uv = updates.method(pkg, prefix="/home/a/.local/share/uv/tools/orkcraft", which=has)
    assert uv.kind == "uv" and uv.steps == (("uv", "tool", "upgrade", "orkcraft"),)
    missing = updates.method(pkg, prefix="/home/a/.local/share/pipx/venvs/orkcraft", which=lambda n: None)
    assert not missing.can and "pipx install --force" in missing.why


def test_homebrew_upgrades_with_brew_and_restarts_under_opt(tmp_path, monkeypatch):
    pkg = tmp_path / "site" / "orkcraft"
    monkeypatch.delenv("HOMEBREW_PREFIX", raising=False)
    has = lambda name: "/opt/homebrew/bin/" + name   # noqa: E731
    brew = updates.method(pkg, prefix="/opt/homebrew/Cellar/orkcraft/0.2.1/libexec", which=has)
    assert brew.kind == "brew" and brew.steps == (("/opt/homebrew/bin/brew", "update", "--quiet"),
                                                  ("/opt/homebrew/bin/brew", "upgrade", "orkcraft/orkcraft/orkcraft"))
    assert brew.python == "/opt/homebrew/opt/orkcraft/libexec/bin/python"
    monkeypatch.setenv("HOMEBREW_PREFIX", "/home/linuxbrew/.linuxbrew")
    opt = updates.method(pkg, prefix="/home/linuxbrew/.linuxbrew/opt/orkcraft/libexec", which=has)
    assert opt.kind == "brew" and opt.python == "/home/linuxbrew/.linuxbrew/opt/orkcraft/libexec/bin/python"
    missing = updates.method(pkg, prefix="/opt/homebrew/Cellar/orkcraft/0.2.1/libexec", which=lambda n: None)
    assert not missing.can and "brew upgrade orkcraft/orkcraft/orkcraft" in missing.why
    runs = Runs(version="9.0.0")
    assert updates.install(brew, runs).ok and runs.calls[-1][0] == brew.python   # the new version, read under opt/
    seen = []
    monkeypatch.delenv(updates.UPDATED_ENV, raising=False)
    updates.restart(["gui"], "9.0.0", execv=lambda exe, args: seen.append(exe), python=brew.python)
    assert seen == [brew.python]


def test_a_copy_from_elsewhere_says_what_to_run(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "_direct_url", lambda: "")
    way = updates.method(tmp_path / "site" / "orkcraft", prefix="/usr", which=lambda n: None)
    assert not way.can and updates.SOURCE in way.why
    monkeypatch.setattr(updates, "_direct_url", lambda: "https://github.com/Orkcraft/orkcraft")
    pip = updates.method(tmp_path / "site" / "orkcraft", prefix="/usr", which=lambda n: None)
    assert pip.kind == "pip" and pip.steps[0][-1] == "orkcraft @ git+https://github.com/Orkcraft/orkcraft"


def test_an_install_runs_each_step_and_reads_the_new_version():
    way = updates.Method("pipx", (("pipx", "upgrade", "orkcraft"),))
    runs = Runs(version="9.0.0")
    result = updates.install(way, runs)
    assert result.ok and result.version == "9.0.0" and runs.calls[0] == ["pipx", "upgrade", "orkcraft"]


def test_an_install_that_fails_or_changes_nothing_is_not_ok():
    way = updates.Method("pipx", (("pipx", "upgrade", "orkcraft"),))
    failed = updates.install(way, Runs(fail="pipx"))
    assert not failed.ok and "no network" in failed.output
    same = updates.install(way, Runs(version=__version__))
    assert not same.ok and f"still {__version__}" in same.output


def test_a_checkout_with_changes_or_off_main_is_left_alone(tmp_path):
    way = updates.Method("git", (("git", "pull", "--ff-only"),), cwd=str(tmp_path))
    dirty = Runs(status=" M orkcraft/cli.py\n")
    assert not updates.install(way, dirty).ok and ["git", "pull", "--ff-only"] not in dirty.calls
    branch = Runs(branch="my-feature")
    result = updates.install(way, branch)
    assert not result.ok and "my-feature" in result.output and ["git", "pull", "--ff-only"] not in branch.calls
    assert updates.install(way, Runs()).ok


# -- when the town opens ------------------------------------------------------------------------

def launch(tmp_path, policy, rels, runs=None, monkeypatch=None, can=True):
    said, execs = [], []
    way = updates.Method("pipx", (("pipx", "upgrade", "orkcraft"),)) if can else updates.Method("none", why="no way")
    monkeypatch.setattr(updates, "method", lambda: way)
    found = updates.at_launch(["gui"], policy, say=said.append, now=10.0, file=tmp_path / "s.json",
                              read=lambda: manifest(*rels), run=runs or Runs(), execv=lambda *a: execs.append(a))
    return found, said, execs


def test_a_critical_update_installs_and_restarts_before_the_town_loads(on, tmp_path, monkeypatch):
    runs = Runs(version="9.0.0")
    found, said, execs = launch(tmp_path, "critical", [("9.0.0", True)], runs, monkeypatch)
    assert found is None and ["pipx", "upgrade", "orkcraft"] in runs.calls
    assert execs and execs[0][1][-1] == "gui" and execs[0][1][1:3] == ["-m", "orkcraft.cli"]
    assert any("critical update 9.0.0" in line for line in said)
    import os
    assert os.environ.get(updates.UPDATED_ENV) == "9.0.0"


def test_an_ordinary_update_waits_unless_the_policy_is_auto(on, tmp_path, monkeypatch):
    found, said, execs = launch(tmp_path, "critical", [("9.0.0", False)], monkeypatch=monkeypatch)
    assert found.version == "9.0.0" and not execs and not said
    found, _, execs = launch(tmp_path / "b", "auto", [("9.0.0", False)], monkeypatch=monkeypatch)
    assert found is None and execs


def test_ask_installs_nothing_even_critical(on, tmp_path, monkeypatch):
    found, said, execs = launch(tmp_path, "ask", [("9.0.0", True)], monkeypatch=monkeypatch)
    assert found.critical and not execs and not said


def test_a_failed_install_lets_the_town_open_and_waits_a_day(on, tmp_path, monkeypatch):
    found, said, execs = launch(tmp_path, "critical", [("9.0.0", True)], Runs(fail="pipx"), monkeypatch)
    assert found.version == "9.0.0" and not execs and any("did not install" in line for line in said)
    assert updates.load_state(tmp_path / "s.json").failed_version == "9.0.0"
    runs = Runs()
    again = updates.at_launch(["gui"], "critical", say=said.append, now=20.0, file=tmp_path / "s.json",
                              read=lambda: manifest(("9.0.0", True)), run=runs, execv=lambda *a: None)
    assert again.version == "9.0.0" and runs.calls == []


def test_a_critical_update_that_cannot_install_itself_is_said(on, tmp_path, monkeypatch):
    found, said, execs = launch(tmp_path, "critical", [("9.0.0", True)], monkeypatch=monkeypatch, can=False)
    assert found.critical and not execs and "no way" in said[0]


def test_the_restarted_process_never_installs_again(on, tmp_path, monkeypatch):
    monkeypatch.setenv(updates.UPDATED_ENV, "9.0.0")
    found, said, execs = launch(tmp_path, "auto", [("9.0.0", True)], monkeypatch=monkeypatch)
    assert found is None and not execs and not said


# -- the command line ---------------------------------------------------------------------------

def test_update_check_says_what_is_out(on, tmp_path, monkeypatch, capsys):
    where = tmp_path / "updates.json"
    where.write_text(json.dumps(manifest(("9.0.0", True))), encoding="utf-8")
    monkeypatch.setenv("ORKCRAFT_UPDATE_URL", where.as_uri())
    assert cli.main(["update", "check"]) == 0
    out = capsys.readouterr().out
    assert "9.0.0 is out — a critical update" in out and "notes of 9.0.0" in out


def test_update_sets_the_policy(capsys):
    assert cli.main(["update", "ask"]) == 0
    assert settings.load().updates == "ask" and "nothing installs by itself" in capsys.readouterr().out
    assert cli.main(["update", "critical"]) == 0 and settings.load().updates == "critical"


def test_the_policy_is_kept_and_a_broken_one_is_the_default():
    s = settings.MachineSettings.from_dict({"updates": "auto"})
    assert s.updates == "auto" and s.to_dict()["updates"] == "auto"
    assert settings.MachineSettings.from_dict({"updates": "yolo"}).updates == "critical"
    assert settings.MachineSettings().updates == "critical"


# -- the window ---------------------------------------------------------------------------------

def test_the_window_installs_on_a_click_and_restarts(fake_repo, monkeypatch):
    from orkcraft.gui import updates as gui_updates
    from orkcraft.gui.host import CommandError, Host
    host = Host(fake_repo, auto_commit=False)
    up = host.updates
    assert host.snapshot()["update"] is None
    with pytest.raises(CommandError):
        host.command("update.install")
    up._method = lambda: updates.Method("pipx", (("pipx", "upgrade", "orkcraft"),))
    up._read(updates.State(manifest=manifest(("9.0.0", True))))
    snap = host.snapshot()["update"]
    assert snap["version"] == "9.0.0" and snap["critical"] and snap["can"] and snap["state"] == "idle"
    started = []                               # the install's thread runs at once
    monkeypatch.setattr(gui_updates.threading, "Thread",
                        lambda target, **kw: SimpleNamespace(start=lambda: started.append(target) or target()))
    monkeypatch.setattr(updates, "install", lambda way: updates.Result(True, "ok", "9.0.0"))
    monkeypatch.setattr(updates, "remember", lambda result, version: None)
    quits = []
    up.quit = lambda: quits.append(1)
    host.command("update.install")
    assert started and up.state == "installed" and up.restart_wanted and quits == [1]
    host.close()


def test_the_window_says_a_failed_install_and_keeps_running(fake_repo, monkeypatch):
    from orkcraft.gui import updates as gui_updates
    from orkcraft.gui.host import Host
    host = Host(fake_repo, auto_commit=False)
    up = host.updates
    up._method = lambda: updates.Method("pipx", (("pipx", "upgrade", "orkcraft"),))
    up._read(updates.State(manifest=manifest(("9.0.0", False))))
    monkeypatch.setattr(gui_updates.threading, "Thread",
                        lambda target, **kw: SimpleNamespace(start=target))
    monkeypatch.setattr(updates, "install", lambda way: updates.Result(False, "no network"))
    monkeypatch.setattr(updates, "remember", lambda result, version: None)
    up.quit = lambda: pytest.fail("restarted after a failed install")
    host.command("update.install")
    snap = host.snapshot()["update"]
    assert snap["state"] == "failed" and snap["error"] == "no network" and not up.restart_wanted
    host.command("update.policy", {"policy": "ask"})
    assert host.town.machine.updates == "ask" and settings.load().updates == "ask"
    host.close()


def test_the_window_never_reads_the_list_in_the_demo_or_when_off(fake_repo, monkeypatch):
    from orkcraft.gui.host import Host
    host = Host(fake_repo, auto_commit=False)
    monkeypatch.setattr(updates, "check_later", lambda on_done=None: pytest.fail("read while off"))
    host.updates.tick(0.0)                     # conftest: ORKCRAFT_NO_UPDATE
    host.close()


def test_the_restart_runs_the_same_command(monkeypatch):
    seen = []
    monkeypatch.delenv(updates.UPDATED_ENV, raising=False)
    updates.restart(["gui", "--browser"], "9.0.0", execv=lambda exe, args: seen.append((exe, args)))
    assert seen == [(sys.executable, [sys.executable, "-m", "orkcraft.cli", "gui", "--browser"])]
