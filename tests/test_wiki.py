"""🗑️ Scroll Dump as an LLM wiki: the layout, what is pending, ingest and lint by the librarian orc."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, shelves, wiki
from orkcraft.screens.typed.knowledge_view import KnowledgeView


def note(path: str, stamp: str) -> shelves.Note:
    return shelves.Note(path, path, rev=stamp)


def test_layout_and_pending(tmp_path: Path):
    root = tmp_path / "llm-wiki"
    assert wiki.scaffold(root) == ["WIKI.md", "index.md", "log.md"]
    (root / "index.md").write_text("# Index\n\n- mine\n")
    assert wiki.scaffold(root) == [] and "mine" in (root / "index.md").read_text()      # never overwrites
    assert (root / "pages").is_dir()

    assert wiki.load_manifest(root) == {}
    wiki.save_manifest(root, {"docs/a.md": "1", "docs/old.md": "1", "docs/b.md": "1"})
    p = wiki.pending(wiki.load_manifest(root), [note("docs/a.md", "1"), note("docs/b.md", "2"), note("docs/c.md", "1")])
    assert (p.new, p.changed, p.gone, p.count) == (["docs/c.md"], ["docs/b.md"], ["docs/old.md"], 3)
    assert not wiki.pending({"x": "1"}, [note("x", "1")])

    assert wiki.raw_path("confluence:123") == "raw/confluence/123.md"
    assert wiki.raw_path("git:main:docs/a.md") == "raw/git/main_docs/a.md"
    assert ".." not in wiki.raw_path("confluence:../../etc/passwd")
    rel = wiki.snapshot(root, "confluence:7", "Body text", "Deploy", "https://x/7")
    text = (root / rel).read_text()
    assert text.startswith("<!-- source: confluence:7 · https://x/7 -->\n# Deploy") and "Body text" in text

    items = [wiki.Item("docs/c.md", "../docs/c.md", "new", "C"), wiki.Item("docs/old.md", "", "gone")]
    prompt = wiki.ingest_prompt(items)
    assert "- [new] docs/c.md — C (read it at `../docs/c.md`)" in prompt and "- [gone] docs/old.md\n" in prompt
    assert "Read `WIKI.md` first" in prompt and "never into `raw/`" in prompt
    assert "lint.md" in wiki.lint_prompt()

    assert wiki.lint_problems(root) is None
    (root / "lint.md").write_text("# Lint\n\n- none\n")
    assert wiki.lint_problems(root) == 0
    (root / "lint.md").write_text("# Lint\n\n- pages/a.md contradicts pages/b.md\n- pages/c.md is an orphan\n")
    assert wiki.lint_problems(root) == 2
    ctx = wiki.context(root, tmp_path, "ship the release")
    assert "`llm-wiki/`" in ctx and "**Task:** ship the release" in ctx and "- mine" in ctx


class Librarian:
    """A stand-in for `claude -p`: it writes what a librarian would, in the folder it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.fail = False

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        self.calls.append((prompt, Path(workdir)))
        if self.fail:
            raise RuntimeError("claude exited with 1: overloaded")
        if "lint.md" in prompt and "Lint " in prompt:
            (workdir / "lint.md").write_text("# Lint\n\n- pages/release.md is an orphan\n")
            return "1 problem: an orphan", 0.01, 100, ""
        (workdir / "pages" / "release.md").write_text("# Release\n\nSources: ../docs/handbook.md\n")
        (workdir / "index.md").write_text("# Index\n\n- [Release](pages/release.md)\n")
        return "Added pages/release.md", 0.02, 200, "s1"


async def settle(pilot, view: KnowledgeView) -> None:
    for _ in range(50):
        await pilot.pause()
        if not view.running:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the librarian never finished")


@pytest.mark.asyncio
async def test_ingest_and_lint(fake_repo: Path, monkeypatch):
    (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag it.\n")
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "handbook"], cwd=fake_repo, check=True, capture_output=True)
    spec = {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls",
            "config": {"sources": [".", "git:HEAD:docs"], "model": "sonnet"}}
    assert masonry.save_spec(fake_repo, spec) == []
    librarian = Librarian()
    monkeypatch.setattr(KnowledgeView, "work_runner", librarian)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("wiki.updated", "wiki.linted"):
        ts.subscribe(app.scroll, "town_hall", "dump", ev)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        root = fake_repo / "llm-wiki"
        assert not root.exists() and dump.status() == "NO WIKI"           # nothing is written before an ingest
        assert set(dump.pending.new) == {"README.md", "docs/notes.md", "docs/handbook.md", "loot/report.md",
                                         "git:HEAD:docs/notes.md", "git:HEAD:docs/handbook.md"}

        assert dump.quick_action("wiki.ingest")
        await settle(pilot, dump)
        prompt, workdir = librarian.calls[0]
        assert workdir == root and (root / "WIKI.md").is_file()
        assert "(read it at `../docs/handbook.md`)" in prompt                # project files are read in place
        assert "(read it at `raw/git/HEAD_docs/handbook.md`)" in prompt      # the rest is snapshotted
        assert "Tag it." in (root / "raw/git/HEAD_docs/handbook.md").read_text()
        assert [p.mode for p in sent if p.mode.startswith("wiki.")] == ["wiki.updated"]
        assert not dump.pending and dump.status() == "FRESH" and wiki.page_count(dump.pages) == 1
        assert all(not n.path.startswith("llm-wiki/") for n in dump.source_notes())   # its own pages are no source
        assert dump.hut_lines([16]) == ["pages: 1", "sources: 2 · 6", "pending: 0", "status: FRESH"]
        [job] = dump.log.read()
        assert job.ok and job.model == "sonnet" and job.cost_usd == 0.02

        (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag and sign it.\n")
        dump.refresh_data()
        assert dump.pending.changed == ["docs/handbook.md"] and dump.status() == "PENDING"
        librarian.fail = True
        manifest = json.loads((root / wiki.MANIFEST).read_text())
        dump.ingest()
        await settle(pilot, dump)
        assert "- [changed] docs/handbook.md" in librarian.calls[-1][0]
        assert json.loads((root / wiki.MANIFEST).read_text()) == manifest      # a failed ingest takes nothing in
        assert dump.status() == "ERROR" and dump.pending.changed == ["docs/handbook.md"]

        librarian.fail = False
        assert dump.quick_action("wiki.lint")
        await settle(pilot, dump)
        assert sent[-1].mode == "wiki.linted" and "lint: 1" in dump.hut_lines([16])
        dump.ingest()
        await settle(pilot, dump)
        assert not dump.pending and dump.status() == "FRESH"


@pytest.mark.asyncio
async def test_auto_ingest(fake_repo: Path, monkeypatch):
    spec = {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls",
            "config": {"wiki": "kb", "auto_ingest": True}}
    assert masonry.save_spec(fake_repo, spec) == []
    librarian = Librarian()
    monkeypatch.setattr(KnowledgeView, "work_runner", librarian)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        await settle(pilot, dump)
        assert len(librarian.calls) == 1 and librarian.calls[0][1] == fake_repo / "kb"
        dump.refresh_data()
        await settle(pilot, dump)
        assert len(librarian.calls) == 1                                    # nothing new: no second run
    for bad in ("../outside", "/tmp/x", ""):
        assert masonry.save_spec(fake_repo, {**spec, "id": "dump2", "config": {"wiki": bad}})
