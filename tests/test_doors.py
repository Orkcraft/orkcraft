"""The doors (docs/design/distribution.md, docs/distribution-howto.md): Orkline on PyPI as `orkline`, and
Orkline's Claude Code plugin with its own marketplace (`.claude-plugin/marketplace.json`,
`plugins/claude-code/`). The formats checked here are Claude Code's documented ones
(code.claude.com/docs/en/plugins/manifest-reference, …/marketplace-reference, …/en/hooks), read 2026-10-14;
`claude plugin validate` checks the same when Claude Code is installed."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from orkcraft import __version__, cli
from orkcraft.core import updates
from orkcraft.hooks import install, session

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN = ROOT / "plugins" / "claude-code"
SHIM = PLUGIN / "scripts" / "session-hook.sh"
sys.path.insert(0, str(ROOT / "tools"))
import pypi  # noqa: E402

REAL_PATH = os.environ.get("PATH", "")          # read at import, before conftest takes the real tools off PATH
CLAUDE = shutil.which("claude")

# Claude Code's documented formats
NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*$")                 # kebab-case; no spaces, @, :, slashes
MARKETPLACE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RESERVED = {"claude-code-marketplace", "claude-code-plugins", "claude-plugins-official", "anthropic-marketplace",
            "anthropic-plugins", "agent-skills", "anthropic-agent-skills", "claude-community",
            "claude-plugins-community", "inline", "builtin", "skills-dir", "synced", "npm", "pip", "uv", "cargo",
            "github", "gh", "claude", "anthropic", "anthropics", "claude-code", "claude-mods"}
PLUGIN_FIELDS = {"$schema", "name", "displayName", "version", "description", "author", "homepage", "repository",
                 "license", "keywords", "metadata", "icon", "documentationUrl", "supportUrl", "privacyPolicyUrl",
                 "termsOfServiceUrl", "defaultEnabled", "dependencies", "settings", "userConfig", "skills",
                 "commands", "agents", "hooks", "mcpServers", "lspServers", "outputStyles"}
MARKETPLACE_FIELDS = {"$schema", "name", "owner", "plugins", "description", "version", "metadata",
                      "forceRemoveDeletedPlugins", "allowCrossMarketplaceDependenciesOn", "renames"}
ENTRY_FIELDS = {"name", "source", "description", "version", "category", "tags", "strict", "dependencies",
                "defaultEnabled", "displayName", "metadata", "author", "homepage", "repository", "license",
                "keywords", "commands", "agents", "skills", "hooks", "outputStyles"}
HOOK_EVENTS = {"SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion", "PreToolUse", "PermissionRequest",
               "PermissionDenied", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "Notification",
               "SubagentStart", "SubagentStop", "Stop", "StopFailure", "PreCompact", "PostCompact", "SessionEnd"}
SKILL_FIELDS = {"name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
                "user-invocable", "allowed-tools", "model", "effort", "context", "agent", "paths", "shell"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    head = text[4:text.index("\n---\n", 4)]
    return dict(line.split(":", 1) for line in head.splitlines() if line.strip())


# -- the plugin and its marketplace, as Claude Code documents them ----------------------------------------

def test_the_marketplace_file_has_claude_codes_fields():
    m = _json(MARKETPLACE)
    assert set(m) <= MARKETPLACE_FIELDS and {"name", "owner", "plugins"} <= set(m)
    assert MARKETPLACE_NAME.match(m["name"]) and m["name"] not in RESERVED and not m["name"].startswith("claudeai-")
    assert isinstance(m["owner"], dict) and m["owner"].get("name")
    assert m["description"]
    [entry] = m["plugins"]
    assert set(entry) <= ENTRY_FIELDS and {"name", "source"} <= set(entry)
    assert entry["source"].startswith("./") and ".." not in entry["source"]
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()
    assert install.PLUGIN_ID == f"{entry['name']}@{m['name']}"     # what plugin_in looks for in enabledPlugins


def test_the_plugin_manifest_has_claude_codes_fields():
    p = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    entry = _json(MARKETPLACE)["plugins"][0]
    assert set(p) <= PLUGIN_FIELDS
    assert NAME.match(p["name"]) and p["name"] not in RESERVED and p["name"] == entry["name"]
    assert not re.match(r"^(claude|anthropic|anthropics|cc-plugin)-", p["name"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", p["version"])
    assert isinstance(p["author"], dict) and p["author"]["name"]
    assert p["homepage"].startswith("https://") and p["license"] == "Apache-2.0"
    assert sorted(x.name for x in (PLUGIN / ".claude-plugin").iterdir()) == ["plugin.json"]  # the rest at its root


def test_the_plugins_hooks_have_claude_codes_shape_and_point_at_the_shim():
    data = _json(PLUGIN / "hooks" / "hooks.json")
    assert set(data) == {"hooks"}
    assert set(data["hooks"]) <= HOOK_EVENTS
    assert set(data["hooks"]) == set(install.SESSION_EVENTS)   # the session log only: the Warder stays an opt-in
    for groups in data["hooks"].values():
        for group in groups:
            for handler in group["hooks"]:
                assert handler["type"] == "command" and 0 < handler["timeout"] <= 30
                assert "${CLAUDE_PLUGIN_ROOT}/scripts/session-hook.sh" in handler["command"]
    assert SHIM.is_file()


def test_the_plugins_commands_are_skills_with_frontmatter():
    names = {}
    for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        front = _frontmatter(skill)
        assert set(front) <= SKILL_FIELDS and front["description"].strip()
        assert front["name"].strip() == skill.parent.name
        names[skill.parent.name] = skill.read_text(encoding="utf-8")
    assert set(names) == {"orkline", "orkcraft"}
    for script in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?)[\"`]", names["orkline"]):
        assert (PLUGIN / script).is_file(), script
    # it asks before installing, and says what it would put where
    assert "ask" in names["orkline"] and "uv tool install \"orkline[gui]\"" in names["orkline"]
    assert "astral.sh/uv" in names["orkline"]


def test_the_plugins_words_say_ork_never_orc():
    for path in [*PLUGIN.rglob("*.md"), *PLUGIN.rglob("*.json"), MARKETPLACE]:
        text = path.read_text(encoding="utf-8").lower()
        assert not re.search(r"\borcs?\b|orchestrat", text), path


@pytest.mark.skipif(CLAUDE is None, reason="Claude Code is not installed")
def test_claude_code_validates_the_marketplace_and_the_plugin(tmp_path):
    for target in (["."], ["plugins/claude-code", "--strict"]):
        done = subprocess.run([CLAUDE, "plugin", "validate", *target], cwd=ROOT, capture_output=True, text=True,
                              timeout=120, env={**os.environ, "PATH": REAL_PATH, "HOME": str(tmp_path)})
        assert done.returncode == 0, done.stdout + done.stderr


# -- the hook shim fails open ---------------------------------------------------------------------------

def _run_shim(tmp_path: Path, bin_dir: Path | None, payload: dict) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    path = os.pathsep.join([str(bin_dir)] if bin_dir else []) + os.pathsep + "/usr/bin:/bin"
    return subprocess.run(["sh", str(SHIM)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=30, env={"PATH": path, "HOME": str(home)})


def _fake(bin_dir: Path, name: str, body: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / name
    exe.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


needs_sh = pytest.mark.skipif(shutil.which("sh", path="/usr/bin:/bin") is None, reason="no POSIX sh")


@needs_sh
def test_the_shim_says_nothing_and_exits_0_without_orkline(tmp_path):
    done = _run_shim(tmp_path, None, {"session_id": "s1", "cwd": str(tmp_path)})
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


@needs_sh
def test_the_shim_says_nothing_and_exits_0_when_orkline_fails(tmp_path):
    # an Orkline too old for `hooks session` (argparse says so on stderr and exits 2), or one that crashes
    for body in ('echo "usage: orkline hooks {install,uninstall}" >&2; exit 2', "echo boom; kill -9 $$"):
        _fake(tmp_path / "bin", "orkline", body)
        done = _run_shim(tmp_path, tmp_path / "bin", {"session_id": "s1", "cwd": str(tmp_path)})
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


@needs_sh
def test_the_shim_hands_the_payload_to_orkline_or_the_older_orkcraft(tmp_path):
    for name in ("orkline", "orkcraft"):
        bin_dir = tmp_path / name
        seen = tmp_path / f"{name}.seen"
        _fake(bin_dir, name, f'echo "$@" > "{seen}"; cat >> "{seen}"')
        done = _run_shim(tmp_path, bin_dir, {"session_id": "s1"})
        assert done.returncode == 0 and done.stdout == ""
        args, payload = seen.read_text(encoding="utf-8").split("\n", 1)
        assert args == "hooks session" and json.loads(payload) == {"session_id": "s1"}


@needs_sh
def test_the_shim_finds_orkline_in_local_bin_when_path_is_short(tmp_path):
    seen = tmp_path / "seen"
    _fake(tmp_path / "home" / ".local" / "bin", "orkline", f'cat > "{seen}"')
    assert _run_shim(tmp_path, None, {"session_id": "s2"}).returncode == 0
    assert json.loads(seen.read_text(encoding="utf-8")) == {"session_id": "s2"}


# -- `orkline hooks session`: what the shim runs -----------------------------------------------------------

def _project(tmp_path: Path, kept: bool = True) -> Path:
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    if kept:
        (project / ".orkcraft").mkdir()
    return project


def _hooks_session(monkeypatch, capsys, payload: dict) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert cli.main(["hooks", "session"]) == 0
    return capsys.readouterr().out


def test_hooks_session_records_in_a_project_orkline_keeps(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    out = _hooks_session(monkeypatch, capsys, {"session_id": "s1", "cwd": str(project),
                                               "hook_event_name": "SessionStart"})
    assert out == ""                                     # Claude Code adds a SessionStart's stdout to the context
    [line] = (project / ".orkcraft" / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["session"] == "s1" and json.loads(line)["harness"] == "claude"


def test_hooks_session_leaves_other_projects_and_bad_payloads_alone(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path, kept=False)
    assert _hooks_session(monkeypatch, capsys, {"session_id": "s1", "cwd": str(project)}) == ""
    assert not (project / ".orkcraft").exists()
    assert _hooks_session(monkeypatch, capsys, {"session_id": "s1", "cwd": str(tmp_path / "nowhere")}) == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert cli.main(["hooks", "session"]) == 0


def test_hooks_session_stays_quiet_where_the_settings_log_already(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    install.install(project)                             # written before the plugin came in
    _hooks_session(monkeypatch, capsys, {"session_id": "s1", "cwd": str(project)})
    assert not (project / ".orkcraft" / "sessions.jsonl").exists()
    assert session.plugin_records({"cwd": str(project)}) is False


# -- no double install --------------------------------------------------------------------------------------

def _enable(path: Path, on: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _json(path) if path.exists() else {}
    data.setdefault("enabledPlugins", {})[install.PLUGIN_ID] = on
    path.write_text(json.dumps(data), encoding="utf-8")


def test_plugin_in_reads_enabled_plugins_the_later_scope_winning(tmp_path, monkeypatch):
    home = Path(os.environ["CLAUDE_CONFIG_DIR"])
    project = _project(tmp_path)
    assert not install.plugin_in(project)
    _enable(home / "settings.json")
    assert install.plugin_in(project) and install.plugin_in()
    _enable(project / ".claude" / "settings.local.json", on=False)
    assert not install.plugin_in(project) and install.plugin_in()
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert not install.plugin_in()                      # never raises
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    _enable(tmp_path / "h" / ".claude" / "settings.json")
    assert install.plugin_in()


def test_hooks_install_writes_only_the_warder_while_the_plugin_is_in(tmp_path):
    project = _project(tmp_path)
    settings = project / ".claude" / "settings.json"
    install.install(project)
    assert set(_json(settings)["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreToolUse"}
    _enable(Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json")
    install.install(project)                             # the session hooks from before go: the plugin's run
    hooks = _json(settings)["hooks"]
    assert set(hooks) == {"PreToolUse"} and install.installed(project)
    assert "orkcraft.hooks.warder" in json.dumps(hooks)
    other = {"hooks": [{"type": "command", "command": "echo mine"}]}
    hooks["SessionStart"] = [other]
    settings.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    install.install(project)
    assert _json(settings)["hooks"]["SessionStart"] == [other]     # someone else's hook stays


def test_hooks_install_from_the_cli_does_not_double_the_plugin(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    _enable(project / ".claude" / "settings.json")
    assert cli.main(["--repo", str(project), "hooks", "install", "--no-agy-global", "--no-hermes-global"]) == 0
    data = _json(project / ".claude" / "settings.json")
    assert data["enabledPlugins"] == {install.PLUGIN_ID: True} and set(data["hooks"]) == {"PreToolUse"}


# -- PyPI -----------------------------------------------------------------------------------------------

def test_the_wheel_leaves_out_what_is_meant_for_readers():
    toml = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert toml["project"]["name"] == "orkcraft"         # from git; tools/pypi.py names the PyPI build orkline
    assert set(toml["project"]["scripts"]) == set(pypi.COMMANDS)
    left_out = toml["tool"]["setuptools"]["exclude-package-data"]["orkcraft"]
    assert "design/system/previews/*" in left_out and "design/system/**/*.md" in left_out


def test_rename_names_the_pypi_build_orkline_once(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    shutil.copy(ROOT / "pyproject.toml", pyproject)
    pypi.rename(pyproject)
    assert tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["name"] == "orkline"
    with pytest.raises(ValueError):
        pypi.rename(pyproject)


def _dist(tmp_path: Path, extra: tuple[str, ...] = (), commands=pypi.COMMANDS, version=__version__) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir(parents=True)
    info = f"orkline-{version}.dist-info"
    with zipfile.ZipFile(dist / f"orkline-{version}-py3-none-any.whl", "w") as z:
        z.writestr(f"{info}/METADATA", f"Metadata-Version: 2.4\nName: orkline\nVersion: {version}\n\n")
        z.writestr(f"{info}/entry_points.txt",
                   "[console_scripts]\n" + "".join(f"{c} = orkcraft.cli:main\n" for c in commands))
        for name in ("orkcraft/__init__.py", "orkcraft/gui/static/index.html", *extra):
            z.writestr(name, "")
    with tarfile.open(dist / f"orkline-{version}.tar.gz", "w:gz") as t:
        member = tarfile.TarInfo(f"orkline-{version}/pyproject.toml")
        t.addfile(member, io.BytesIO(b""))
    return dist


def test_check_passes_a_clean_build_and_names_what_is_wrong(tmp_path):
    assert pypi.check(_dist(tmp_path), tag=f"v{__version__}") == []
    problems = pypi.check(_dist(tmp_path / "a", extra=("orkcraft/design/system/previews/Town.html",
                                                       "orkcraft/design/system/sprites/README.md",
                                                       "docs/design/img/references/0.3/a.png")),
                          tag="v0.0.1")
    text = "\n".join(problems)
    assert "tag v0.0.1" in text and "previews/Town.html" in text and "README.md" in text and "references" in text
    assert any("`orkcraft` command" in p for p in pypi.check(_dist(tmp_path / "b", commands=("orkline",))))
    assert any("expected orkline" in p for p in pypi.check(_dist(tmp_path / "c", version="0.0.0")))


def test_the_workflow_publishes_only_on_a_tag_through_trusted_publishing():
    text = (ROOT / ".github" / "workflows" / "pypi.yml").read_text(encoding="utf-8")
    publish = text[text.index("\n  publish:"):]
    assert "if: startsWith(github.ref, 'refs/tags/v')" in publish
    assert "id-token: write" in publish and "pypa/gh-action-pypi-publish" in publish
    assert "id-token" not in text[:text.index("\n  publish:")]       # only the publishing job may mint one
    assert "secrets." not in text and "password" not in text and "TWINE_" not in text
    assert "tools/pypi.py rename" in text and "twine check --strict" in text and "tools/pypi.py check dist" in text


def test_a_copy_from_pypi_upgrades_by_its_pypi_name(tmp_path, monkeypatch):
    pkg = tmp_path / "site" / "orkcraft"
    has = lambda name: "/bin/" + name   # noqa: E731
    pipx = updates.method(pkg, prefix="/home/a/.local/share/pipx/venvs/orkline", which=has)
    assert pipx.steps == (("pipx", "upgrade", "orkline"),)
    uv = updates.method(pkg, prefix="/home/a/.local/share/uv/tools/orkline", which=has)
    assert uv.steps == (("uv", "tool", "upgrade", "orkline"),)
    assert "uv tool upgrade orkline" in updates.method(pkg, prefix="/x/uv/tools/orkline", which=lambda n: None).why
    monkeypatch.setattr(updates, "_direct_url", lambda: "")
    monkeypatch.setattr(updates, "_from_pypi", lambda: True)
    pip = updates.method(pkg, prefix="/usr", which=lambda n: None)
    assert pip.kind == "pip" and pip.steps[0][-3:] == ("install", "--upgrade", "orkline")
