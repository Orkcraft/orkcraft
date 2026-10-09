"""Tool detection for onboarding and the HUD corner that follows each tool's billing."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orkcraft import tools


def _run(cmd, **_):
    return subprocess.CompletedProcess(cmd, 0, stdout={"claude": "2.1.4 (Claude Code)\n", "agy": "agy v1.3.0\n",
                                                       "codex": "codex-cli 0.160.0\n"}
                                       .get(Path(cmd[0]).name, ""), stderr="")


def _which(found: set[str]):
    return lambda name: f"/usr/bin/{name}" if name in found else None


def test_found_tools_with_versions_and_logins(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    got = {t.id: t for t in tools.detect(_which({"claude", "agy"}), _run, env={}, home=tmp_path)}
    assert got["claude"].found and got["claude"].version == "2.1.4"
    assert got["claude"].logged_in and got["claude"].billing == "subscription"
    assert got["agy"].found and got["agy"].version == "1.3.0" and got["agy"].logged_in is None
    assert not got["codex"].found and got["codex"].summary() == "not found — npm i -g @openai/codex"


def test_an_api_key_means_api_billing(tmp_path: Path):
    got = {t.id: t for t in tools.detect(_which({"claude", "agy"}), _run,
                                         env={"ANTHROPIC_API_KEY": "x", "GEMINI_API_KEY": "y"}, home=tmp_path)}
    assert got["claude"].billing == "api" and got["agy"].billing == "api"
    assert "API key" in got["claude"].summary()


def test_oauth_account_in_claude_json(tmp_path: Path):
    (tmp_path / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "a@b"}}), encoding="utf-8")
    claude = tools.detect(_which({"claude"}), _run, env={}, home=tmp_path)[0]
    assert claude.logged_in and claude.billing == "subscription"


FIXTURES = Path(__file__).parent / "fixtures"


def _codex(tmp_path: Path, env: dict | None = None, run=_run) -> tools.ToolStatus:
    return {t.id: t for t in tools.detect(_which({"codex"}), run, env=env or {}, home=tmp_path)}["codex"]


def _auth(tmp_path: Path, text: str) -> None:
    (tmp_path / ".codex").mkdir(exist_ok=True)
    (tmp_path / ".codex" / "auth.json").write_text(text, encoding="utf-8")


def _login_status(line: str, code: int = 0):
    def run(cmd, **kw):
        if cmd[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(cmd, code, stdout="", stderr=line + "\n")
        return _run(cmd, **kw)
    return run


def test_codex_billing_is_what_its_auth_json_holds(tmp_path: Path):
    codex = _codex(tmp_path)
    assert codex.found and codex.version == "0.160.0" and codex.logged_in is None
    _auth(tmp_path, (FIXTURES / "codex_auth_chatgpt.json").read_text(encoding="utf-8"))
    codex = _codex(tmp_path)
    assert codex.logged_in and codex.billing == "subscription" and codex.summary() == "found · v0.160.0 · logged in"
    for fixture in ("codex_auth_apikey.json", "codex_auth_legacy_apikey.json"):    # `login --with-api-key`: same file
        _auth(tmp_path, (FIXTURES / fixture).read_text(encoding="utf-8"))
        codex = _codex(tmp_path)
        assert codex.logged_in and codex.billing == "api" and "API key" in codex.summary(), fixture
        assert "sk-" not in codex.summary()


def test_only_codex_api_key_makes_codex_api_billed(tmp_path: Path):
    _auth(tmp_path, (FIXTURES / "codex_auth_chatgpt.json").read_text(encoding="utf-8"))
    assert _codex(tmp_path, {"OPENAI_API_KEY": "x"}).billing == "subscription"     # `codex exec` ignores it
    assert _codex(tmp_path, {"CODEX_API_KEY": "x"}).billing == "api"


def test_codex_login_status_tells_when_auth_json_cannot(tmp_path: Path):
    _auth(tmp_path, "not even json")
    codex = _codex(tmp_path, run=_login_status("Logged in using an API key - sk-proj-***ABCDE"))
    assert codex.logged_in and codex.billing == "api"
    codex = _codex(tmp_path, run=_login_status("Logged in using ChatGPT"))
    assert codex.logged_in and codex.billing == "subscription"
    (tmp_path / ".codex" / "auth.json").unlink()                                   # a keyring login: no file
    assert _codex(tmp_path, run=_login_status("Not logged in", 1)).logged_in is False
    assert _codex(tmp_path, run=_login_status("Logged in using ChatGPT")).billing == "subscription"
    assert _codex(tmp_path).logged_in is None                                      # it says nothing: unknown


def test_codex_is_only_led():
    assert "codex" not in {o.id for o in tools.OTHERS}            # led now, not only asked about


def test_missing_tools_say_how_to_get_them(tmp_path: Path):
    got = tools.detect(_which(set()), _run, env={}, home=tmp_path)
    assert all(not t.found for t in got)
    assert "npm i -g @anthropic-ai/claude-code" in got[0].summary()


def test_a_cli_that_cannot_say_its_version(tmp_path: Path):
    def boom(cmd, **_):
        raise subprocess.TimeoutExpired(cmd, 5)
    claude = tools.detect(_which({"claude"}), boom, env={}, home=tmp_path)[0]
    assert claude.found and claude.version == ""


def test_the_warder_guards_agy_from_1_1_12():
    assert tools.agy_guardable("1.1.12") and tools.agy_guardable("v1.2.17") and tools.agy_guardable("1.10.0")
    assert not tools.agy_guardable("1.1.11") and not tools.agy_guardable("1.0.16")
    assert not tools.agy_guardable("") and not tools.agy_guardable("unknown")     # cannot tell: not guarded
    assert tools.version_tuple("agy") is None and tools.version_tuple("1.2.3-beta") == (1, 2, 3)


def test_agy_version_is_none_when_agy_is_missing():
    assert tools.agy_version(_which(set()), _run) is None
    assert tools.agy_version(_which({"agy"}), _run) == "1.3.0"
