"""Mason & Artisan: spec checks, safe data fetchers and the build pipeline (no real Claude calls)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from orkcraft.realm import builders, masonry


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "loot").mkdir(parents=True, exist_ok=True)
    (repo / "loot" / "notes.md").write_text("# Notes\nline 2\n", encoding="utf-8")
    (repo / "logs").mkdir(exist_ok=True)
    (repo / "logs" / "build.log").write_text("\n".join(f"line {i}" for i in range(1, 101)), encoding="utf-8")
    return repo


GOOD = {
    "id": "ci_watch", "title": "CI Watch", "icon": "🛠", "summary": "failing builds",
    "orc": {"name": "Tinker", "role": "watches the build log"},
    "data": [
        {"name": "high", "source": "graph_nodes", "params": {"type": "task", "priority": "high", "limit": 20}},
        {"name": "log", "source": "file_tail", "params": {"path": "logs/build.log", "lines": 10}},
    ],
    "layout": {"direction": "horizontal", "panes": [
        {"widget": "table", "data": "high", "title": "High", "ratio": 2, "columns": ["id", "title", "status"]},
        {"widget": "log", "data": "log"},
    ]},
    "actions": [{"key": "O", "label": "Open card", "action": "node:open"}],
}


def _with(**changes) -> dict:
    spec = json.loads(json.dumps(GOOD))
    for path, value in changes.items():
        obj = spec
        keys = path.split("__")
        for k in keys[:-1]:
            obj = obj[int(k)] if k.isdigit() else obj[k]
        last = keys[-1]
        obj[int(last) if last.isdigit() else last] = value
    return spec


def test_a_good_spec_validates_saves_and_loads(tmp_path: Path):
    repo = _repo(tmp_path)
    assert masonry.validate_spec(GOOD, repo) == []
    assert masonry.save_spec(repo, GOOD) == []
    specs, problems = masonry.load_specs(repo)
    assert [s["id"] for s in specs] == ["ci_watch"] and problems == []
    assert masonry.validate_spec(GOOD, repo, existing_ids={"ci_watch"})   # taken now
    (repo / ".orkcraft" / "buildings" / "broken.json").write_text("{", encoding="utf-8")
    specs, problems = masonry.load_specs(repo)
    assert len(specs) == 1 and problems and problems[0].startswith("broken.json")


@pytest.mark.parametrize("changes, needle", [
    ({"data__1__params": {"path": "../outside.txt"}}, "outside the repository"),
    ({"data__1__params": {"path": "/etc/passwd"}}, "outside the repository"),
    ({"data__1__params": {"path": ".git/config"}}, "outside the repository"),
    ({"data__0__params": {"type": "task", "shell": "rm -rf /"}}, "unknown param 'shell'"),
    ({"data__0__params": {"limit": 5000}}, "between 1 and 200"),
    ({"data__0__params": {"status": "exploded"}}, "must be one of"),
    ({"data__0__source": "http_get"}, "is not one of"),
    ({"layout__panes__1__widget": "table"}, "shows list data, but 'log' is text"),
    ({"layout__panes__0__data": "nope"}, "no data named 'nope'"),
    ({"actions": [{"key": "X", "label": "boom", "action": "node:open"}]}, "taken by orkcraft"),
    ({"actions": [{"key": "O", "label": "run", "action": "shell:run"}]}, "is not one of"),
    ({"id": "forge"}, "is taken"),
    ({"extra": "field"}, "Additional properties"),
])
def test_bad_specs_are_refused_with_a_readable_reason(tmp_path: Path, changes, needle):
    errors = masonry.validate_spec(_with(**changes), _repo(tmp_path))
    assert any(needle in e for e in errors), errors


def test_symlink_out_of_the_repo_is_refused(tmp_path: Path):
    repo = _repo(tmp_path)
    secret = tmp_path / "secret.env"
    secret.write_text("TOKEN=1", encoding="utf-8")
    os.symlink(secret, repo / "loot" / "link.env")
    assert masonry.safe_path(repo, "loot/link.env") is None
    data = masonry.fetch("file", {"path": "loot/link.env"}, repo)
    assert data.error and "TOKEN" not in data.text


def test_fetchers(tmp_path: Path):
    repo = _repo(tmp_path)
    tail = masonry.fetch("file_tail", {"path": "logs/build.log", "lines": 3}, repo)
    assert tail.text.splitlines() == ["line 98", "line 99", "line 100"]
    assert masonry.fetch("file", {"path": "loot/notes.md"}, repo).text.startswith("# Notes")
    assert masonry.fetch("directory", {"path": "loot"}, repo).path == (repo / "loot").resolve()

    class E:
        def __init__(self, id, type, status, priority="-", tags=()):
            self.id, self.title, self.type, self.status, self.priority = id, f"Title {id}", type, status, priority
            self.subtype, self.assignee, self.tags, self.deadline, self.summary, self.is_personal = None, "", list(tags), None, "", False

    class G:
        entities = {e.id: e for e in (E("T2", "task", "todo", "high"), E("T1", "task", "done"), E("C1", "context", "active"))}

        def processes(self):
            return []

    rows = masonry.fetch("graph_nodes", {"type": "task", "priority": "high"}, repo, graph=G()).rows
    assert [(r.id, r.title) for r in rows] == [("T2", "Title T2")]
    assert masonry.fetch("sql", {}, repo).error


def test_git_log_uses_fixed_arguments(tmp_path: Path):
    repo = _repo(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "first; $(rm -rf /)"], cwd=repo, check=True)
    data = masonry.fetch("git_log", {"limit": 5, "path": "loot"}, repo)
    assert [r.title for r in data.rows] == ["first; $(rm -rf /)"] and data.rows[0].id == ""
    assert masonry.fetch("git_log", {"path": "../x"}, repo).error


def test_catalog_lists_exactly_what_validation_allows():
    text = masonry.catalog()
    for name in (*masonry.SOURCES, *masonry.WIDGETS, *masonry.ACTIONS):
        assert name in text
    assert "X" not in text.split("Free action keys:")[1].split(".")[0]


def test_extract_json():
    assert builders.extract_json('Sure!\n```json\n{"a": {"b": 1}}\n```\nthanks') == {"a": {"b": 1}}
    assert builders.extract_json("[1, 2] then {\"x\": 1}") == {"x": 1}
    assert builders.extract_json("no json here") is None


def _mason_answer(spec: dict) -> str:
    return json.dumps({k: v for k, v in spec.items() if k not in ("layout", "actions")})


def test_build_succeeds_first_time(tmp_path: Path):
    calls = []

    def runner(prompt):
        calls.append(prompt)
        return (_mason_answer(GOOD), 0.01) if prompt.startswith("You are Mason") else (json.dumps(GOOD), 0.02)

    result = builders.build("watch CI failures", _repo(tmp_path), runner=runner)
    assert result.ok and result.spec["id"] == "ci_watch" and len(result.attempts) == 1
    assert result.cost_usd == pytest.approx(0.03)
    assert "watch CI failures" in calls[0] and "DATA SOURCES" in calls[0]
    assert "REJECTED" not in calls[0]


def test_invalid_spec_goes_back_to_mason_with_the_errors(tmp_path: Path):
    bad = _with(**{"data__1__params": {"path": "../../etc/passwd"}})
    seen = []

    def runner(prompt):
        seen.append(prompt)
        first_round = len(seen) <= 2
        spec = bad if first_round else GOOD
        return (_mason_answer(spec), None) if prompt.startswith("You are Mason") else (json.dumps(spec), None)

    result = builders.build("watch CI", _repo(tmp_path), runner=runner)
    assert result.ok and len(result.attempts) == 2
    assert result.attempts[0].errors and "outside the repository" in result.attempts[0].errors[0]
    assert "REJECTED" in seen[2] and "outside the repository" in seen[2]   # round 2 starts at Mason


def test_build_gives_up_and_reports(tmp_path: Path):
    result = builders.build("x", _repo(tmp_path), runner=lambda p: ("no idea", None))
    assert not result.ok and len(result.attempts) == builders.MAX_ATTEMPTS
    assert result.attempts[-1].errors == ["Mason's answer had no JSON object"]

    def broken(prompt):
        raise RuntimeError("Claude Code CLI not found")

    result = builders.build("x", _repo(tmp_path), runner=broken)
    assert not result.ok and "not found" in result.error


def test_claude_runner_calls_the_cli_in_an_empty_folder(tmp_path: Path, monkeypatch):
    fake = tmp_path / "fake-claude"
    record = tmp_path / "record.json"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'cwd': os.getcwd(), 'files': os.listdir('.'),"
        f" 'orkcraft_env': [k for k in os.environ if k.startswith('ORKCRAFT_')]}}, open({str(record)!r}, 'w'))\n"
        "print(json.dumps({'type': 'result', 'result': '{\"ok\": 1}', 'total_cost_usd': 0.05}))\n",
        encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(fake))
    monkeypatch.setenv("ORKCRAFT_TICKET", "T1093")
    text, cost = builders.claude_runner("design it")
    assert (text, cost) == ('{"ok": 1}', 0.05)
    rec = json.loads(record.read_text())
    assert rec["argv"] == ["-p", "design it", "--output-format", "json"]
    assert rec["files"] == [] and "orkcraft-mason-" in rec["cwd"]
    assert rec["orkcraft_env"] == []                      # no ORKCRAFT_* leaks into the builders
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="not found"):
        builders.claude_runner("x")
