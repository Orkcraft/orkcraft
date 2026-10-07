"""The MCP servers the AI tools here know: names only, never what could hold a token (realm/mcp.py)."""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft.realm import mcp


def _home(tmp_path: Path) -> tuple[Path, Path]:
    home, repo = tmp_path / "home", tmp_path / "project"
    (home / ".codex").mkdir(parents=True)
    (home / ".gemini").mkdir()
    repo.mkdir()
    (home / ".claude.json").write_text(json.dumps({
        "mcpServers": {"github": {"command": "gh-mcp", "env": {"GITHUB_TOKEN": "ghp_secret"}}},
        "projects": {str(repo): {"mcpServers": {"amplitude": {"url": "https://mcp.amplitude.com", "headers":
                                                               {"Authorization": "Bearer amp_secret"}}}},
                     "/elsewhere": {"mcpServers": {"not-mine": {}}}}}))
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"figma-dev": {"command": "figma"}}}))
    (home / ".codex" / "config.toml").write_text('[mcp_servers.github]\ncommand = "gh-mcp"\n'
                                                 'args = ["--token", "ghp_other"]\n')
    (home / ".gemini" / "settings.json").write_text(json.dumps({"mcpServers": {"Slack": {"command": "slack"}}}))
    return home, repo


def test_every_server_once_with_the_tools_that_have_it(tmp_path: Path):
    home, repo = _home(tmp_path)
    found = {s.id: s for s in mcp.found(home, repo)}
    assert set(found) == {"github", "amplitude", "figma-dev", "slack"}            # another project's stays out
    assert found["github"].tools == ("claude", "codex") and found["github"].glyph == "github"
    assert found["figma-dev"].title == "Figma" and found["figma-dev"].glyph == "figma"
    assert found["amplitude"].title == "Amplitude" and found["amplitude"].glyph == ""
    assert found["slack"].tools == ("agy",)


def test_no_secret_leaves_the_files(tmp_path: Path):
    home, repo = _home(tmp_path)
    said = json.dumps([s.to_dict() for s in mcp.found(home, repo)])
    for secret in ("ghp_secret", "amp_secret", "ghp_other", "mcp.amplitude.com", "gh-mcp", "--token"):
        assert secret not in said


def test_missing_or_broken_files_are_no_servers(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text("{not json")
    assert mcp.found(home, None) == []
    assert mcp.found(tmp_path / "nobody", tmp_path / "nowhere") == []
