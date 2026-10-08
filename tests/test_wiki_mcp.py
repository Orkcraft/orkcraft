"""The Wiki as an MCP server (docs/design/wiki-mcp.md): what it answers over stdio, the entry each AI tool
reads it from, kept beside a person's own servers, and written with the rules for AI tools."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from orkcraft import wiki_mcp
from orkcraft.core import buildings
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, wikimcp
from orkcraft.settings import ToolChoice


def _wiki(project: Path) -> Path:
    root = project / "llm-wiki" / "general"
    (root / "pages" / "people").mkdir(parents=True)
    (root / "raw").mkdir()
    (root / "index.md").write_text("# Index\n\n- people: who is who\n")
    (root / "RULES.md").write_text("# Rules for AI tools\n")
    (root / "pages" / "people" / "sergey.md").write_text("---\naliases: [Серёжа]\n---\n# Sergey\n\nOwns pricing tiers.\n")
    (root / "raw" / "secret.md").write_text("snapshot\n")
    return root


def _talk(w: wiki_mcp.Wiki, *messages: dict) -> list[dict]:
    out = io.StringIO()
    wiki_mcp.serve(w, io.StringIO("".join(json.dumps(m) + "\n" for m in messages) + "nonsense\n"), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_the_server_maps_searches_and_reads_the_wiki(tmp_path: Path):
    root = _wiki(tmp_path)
    w = wiki_mcp.Wiki(tmp_path, root)
    call = lambda i, name, **a: {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": a}}  # noqa: E731
    got = _talk(w, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                call(3, "wiki_map"), call(4, "wiki_search", query="pricing"),
                call(5, "wiki_read", path="llm-wiki/general/pages/people/sergey.md"),
                call(6, "wiki_read", path="pages/people/sergey.md"),
                call(7, "wiki_read", path="../../README.md"), call(8, "wiki_read", path="raw/secret.md"),
                call(9, "wiki_search", query="quantum"), call(10, "nope"))
    by = {r.get("id"): r for r in got}
    assert by[1]["result"]["serverInfo"]["name"] == "orkcraft-wiki" and "wiki_map first" in by[1]["result"]["instructions"]
    assert [t["name"] for t in by[2]["result"]["tools"]] == ["wiki_map", "wiki_search", "wiki_read"]
    text = lambda i: by[i]["result"]["content"][0]["text"]  # noqa: E731
    assert "# Index" in text(3) and "# Rules for AI tools" in text(3)
    assert "`llm-wiki/general/pages/people/sergey.md` — Sergey" in text(4)
    assert "Owns pricing tiers." in text(5) and text(5) == text(6)
    assert by[7]["result"]["isError"] and by[8]["result"]["isError"]
    assert "Nothing in the wiki matches" in text(9)
    assert by[10]["error"]["code"] == -32602 and by[None]["error"]["code"] == -32700
    assert len(got) == 11                                                   # the notification has no answer


def test_the_server_runs_as_a_module(tmp_path: Path):
    root = _wiki(tmp_path)
    msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    out = subprocess.run([sys.executable, "-m", "orkcraft.wiki_mcp", "--project", str(tmp_path), "--wiki", str(root)],
                         input=msg, capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout)["result"]["tools"][0]["name"] == "wiki_map"


def test_each_tools_entry_kept_beside_a_persons_own(tmp_path: Path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}}))
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text('model = "gpt"\n')
    cmd = ["/py", "-m", "orkcraft.wiki_mcp", "--project", "/p", "--wiki", "/p/llm-wiki/general"]
    changed = wikimcp.write(tmp_path, "s1", ["claude", "codex", "cursor"], cmd)
    assert {p.name for p in changed} == {".mcp.json", "mcp.json", "config.toml"}
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert servers["mine"] == {"command": "x"} and servers["orkcraft-wiki-s1"] == {"command": "/py", "args": cmd[1:]}
    toml = (tmp_path / ".codex" / "config.toml").read_text()
    assert toml.startswith('model = "gpt"\n') and '[mcp_servers.orkcraft-wiki-s1]\ncommand = "/py"' in toml
    assert wikimcp.write(tmp_path, "s1", ["claude", "codex", "cursor"], cmd) == []
    assert wikimcp.written(tmp_path, "s1") == [".mcp.json", ".cursor/mcp.json", ".codex/config.toml"]
    wikimcp.write(tmp_path, "s1", ["claude"], cmd)                          # Codex and Cursor turned off
    assert not (tmp_path / ".cursor" / "mcp.json").exists()
    assert (tmp_path / ".codex" / "config.toml").read_text() == 'model = "gpt"\n'
    wikimcp.remove(tmp_path, "s1")
    assert json.loads((tmp_path / ".mcp.json").read_text()) == {"mcpServers": {"mine": {"command": "x"}}}
    (tmp_path / ".mcp.json").write_text("{broken")
    assert wikimcp.write(tmp_path, "s1", ["claude"], cmd) == [] and (tmp_path / ".mcp.json").read_text() == "{broken"


def test_the_server_is_written_with_the_rules_and_never_committed(fake_repo: Path):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    host.town.machine.tools = {t: ToolChoice(enabled=t in ("claude", "cursor")) for t in host.town.machine.tools}
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "sources": ["docs"]}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    written = w.write_rules()
    assert ".mcp.json" in written and ".cursor/mcp.json" in written
    entry = json.loads((fake_repo / ".mcp.json").read_text())["mcpServers"][wikimcp.name_of(bid)]
    assert entry["command"] == sys.executable and entry["args"][-1] == str(w.wiki_root.resolve())
    status = subprocess.run(["git", "status", "--porcelain"], cwd=fake_repo, capture_output=True, text=True).stdout
    assert "?? .mcp.json" in status                                         # this machine's paths stay local
    assert ".mcp.json" in host.detail(bid)["data"]["rules"]["files"]
    w.save_config({"wiki_mcp": False})
    w.write_rules()
    assert not (fake_repo / ".mcp.json").exists()
    w.save_config({"wiki_mcp": True})
    w.write_rules()
    w.remove_rules()
    assert not (fake_repo / ".mcp.json").exists() and not (fake_repo / ".cursor" / "mcp.json").exists()
