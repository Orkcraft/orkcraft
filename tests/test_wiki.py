"""🗑️ Scroll Dump as an LLM wiki: topics and hierarchy, what is pending, ingest and lint by the
librarian orc, pages people own, commits, the Council's spot-checks, the steward's wiki loop."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes, shelves, steward, wiki
from orkcraft.screens.typed.knowledge_view import KnowledgeView


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def test_topics_and_hierarchy(tmp_path: Path):
    root = tmp_path / "llm-wiki" / "codebase"
    made = wiki.scaffold(root, "codebase")
    assert {"WIKI.md", "index.md", "log.md", "raw/.gitignore", "CLAUDE.md", "AGENTS.md",
            "pages/modules/index.md", "pages/modules/CLAUDE.md", "pages/decisions/CLAUDE.md"} <= set(made)
    schema = (root / "WIKI.md").read_text()
    assert "**modules**" in schema and "aliases:" in schema and "owner is human" in schema and "~40 pages" in schema
    assert "kind: modules" in (root / "pages/modules/CLAUDE.md").read_text()
    (root / "index.md").write_text("# Index\n\n- mine\n")
    assert wiki.scaffold(root, "codebase") == [] and "mine" in (root / "index.md").read_text()   # never overwrites
    design = wiki.schema_text("design")
    assert all(f"**{s}**" in design for s in ("components", "screens", "decisions", "tokens"))
    assert wiki.topic_of({"topic": "team"}) == "team" and wiki.topic_of({"topic": "x"}) == "general"
    assert wiki.default_dir("team") == "llm-wiki/team"
    notes = wiki.pages(root, tmp_path)
    assert not any(n.path.endswith("CLAUDE.md") for n in notes)
    assert wiki.page_count(notes) == 0                                       # section maps are not pages
    (root / "pages/modules/pay.md").write_text("---\nkind: modules\n---\n# Pay\n")
    assert wiki.page_count(wiki.pages(root, tmp_path)) == 1
    assert wiki.wiki_roots([shelves.Note("llm-wiki/codebase/WIKI.md", "x"), shelves.Note("docs/a.md", "a")]) \
        == ["llm-wiki/codebase"]


def test_pending_batches_and_fingerprints(tmp_path: Path):
    p = wiki.pending({"docs/a.md": "1", "docs/old.md": "1", "docs/b.md": "1", "confluence:9": "3"},
                     {"docs/a.md": "1", "docs/b.md": "2", "docs/c.md": "1"},
                     unsure=lambda path: path.startswith("confluence:"))
    assert (p.new, p.changed, p.gone) == (["docs/c.md"], ["docs/b.md"], ["docs/old.md"])   # confluence is unsure
    big = wiki.Pending(new=[f"src/pay/{i}.py" for i in range(5)] + [f"src/auth/{i}.py" for i in range(4)] + ["README.md"])
    first = wiki.take_batch(big, limit=6)
    assert [x for _, x in first] == ["README.md", "src/auth/0.py", "src/auth/1.py", "src/auth/2.py", "src/auth/3.py"]
    assert len(wiki.take_batch(wiki.Pending(new=[f"src/x/{i}.py" for i in range(9)]), limit=6)) == 6  # a big module is cut

    (tmp_path / "a.md").write_text("one")
    prints = wiki.Fingerprints(tmp_path)
    n = shelves.read_note(tmp_path / "a.md", tmp_path)
    first_print = prints.of(n)
    (tmp_path / "a.md").write_text("one")                                      # touched, same bytes
    assert prints.of(shelves.read_note(tmp_path / "a.md", tmp_path)) == first_print
    (tmp_path / "a.md").write_text("two")
    assert prints.of(shelves.read_note(tmp_path / "a.md", tmp_path)) != first_print
    assert prints.of(shelves.Note("git:HEAD:a.md", "a", rev="abc")) == "abc"

    assert wiki.raw_path("confluence:123") == "raw/confluence/123.md"
    assert ".." not in wiki.raw_path("confluence:../../etc/passwd")


def test_people_pages_reviews_and_context(tmp_path: Path):
    root = tmp_path / "w"
    wiki.scaffold(root)
    (root / "pages/concepts/mine.md").write_text("---\nkind: concepts\nowner: human\n---\n# Mine\n")
    (root / "pages/concepts/old.md").write_text("# Old\n<!-- manual -->\n")
    (root / "pages/concepts/orcs.md").write_text("---\nowner: orc\n---\n# Orcs\n")
    before = wiki.manual_pages(root)
    assert set(before) == {"pages/concepts/mine.md", "pages/concepts/old.md"}
    (root / "pages/concepts/mine.md").write_text("# Rewritten by the orc\n")
    (root / "pages/concepts/old.md").unlink()
    assert sorted(wiki.restore(root, before)) == ["pages/concepts/mine.md", "pages/concepts/old.md"]
    assert "owner: human" in (root / "pages/concepts/mine.md").read_text()
    prompt = wiki.ingest_prompt([wiki.Item("docs/c.md", "../docs/c.md", "new", "C")], sorted(before))
    assert "- `pages/concepts/mine.md`" in prompt and "proposals.md" in prompt and "reviews.md" in prompt
    assert "- [new] docs/c.md — C (read it at `../docs/c.md`)" in prompt

    req = wiki.review_request(root, ["pages/concepts/orcs.md"], "general")
    assert "Spot-check" in req and "## pages/concepts/orcs.md" in req and "# Orcs" in req
    wiki.record_review(root, "OK", "first", dt.date(2026, 10, 1))
    wiki.record_review(root, "orcs.md: wrong owner", "second", dt.date(2026, 10, 2))
    text = (root / "reviews.md").read_text()
    assert text.index("2026-10-02 — second") < text.index("2026-10-01 — first") and text.count("# Reviews") == 1

    (root / "index.md").write_text("# Index\n" + "".join(f"- line {i}\n" for i in range(2000)))
    ctx = wiki.context(root, tmp_path, "ship it")
    assert len(ctx) < wiki.CONTEXT_CHARS + 400 and "the rest is in `w/index.md`" in ctx and "**Task:** ship it" in ctx
    assert wiki.lint_problems(root) is None
    (root / "lint.md").write_text("# Lint\n\n- none\n")
    assert wiki.lint_problems(root) == 0


class Librarian:
    """A stand-in for `claude -p`: it writes what a librarian would, in the folder it was given —
    and, when told to misbehave, a page people own and a file outside the wiki."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.fail = False
        self.misbehave = False
        self.wait = None

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        self.calls.append((prompt, Path(workdir)))
        if self.wait is not None and cancel.wait(5):
            raise InterruptedError("stopped")
        if self.fail:
            raise RuntimeError("claude exited with 1: overloaded")
        if "# Lint " in prompt:
            (workdir / "lint.md").write_text("# Lint\n\n- pages/how-to/release.md is an orphan\n")
            return "1 problem: an orphan", 0.01, 100, ""
        (workdir / "pages/how-to/release.md").write_text("---\nkind: how-to\nowner: orc\n---\n# Release\n\nTag it.\n")
        (workdir / "index.md").write_text("# Index\n\n- [How-to](pages/how-to/index.md)\n")
        if self.misbehave:
            (workdir / "pages/how-to/mine.md").write_text("# Taken over\n")
            (workdir.parent.parent / "src" / "app.py").write_text("print('orc was here')\n")
        return "Added pages/how-to/release.md", 0.02, 200, "s1"


async def settle(pilot, view: KnowledgeView) -> None:
    for _ in range(100):
        await pilot.pause()
        if not view.running:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the librarian never finished")


def spec(**config) -> dict:
    return {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls",
            "config": config}


@pytest.mark.asyncio
async def test_ingest_commit_people_and_review(fake_repo: Path, monkeypatch):
    (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag it.\n")
    git(fake_repo, "add", "-A")
    git(fake_repo, "commit", "-qm", "handbook")
    assert masonry.save_spec(fake_repo, spec(sources=[".", "git:HEAD:docs"], model="sonnet", review_sample=5)) == []
    librarian = Librarian()
    monkeypatch.setattr(KnowledgeView, "work_runner", librarian)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("wiki.updated", "wiki.linted", "wiki.review"):
        ts.subscribe(app.scroll, "town_hall", "dump", ev)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        root = fake_repo / "llm-wiki" / "general"
        assert not root.exists() and dump.status() == "NO WIKI"            # nothing is written before an ingest
        assert set(dump.pending.new) == {"README.md", "docs/notes.md", "docs/handbook.md", "loot/report.md",
                                         "git:HEAD:docs/notes.md", "git:HEAD:docs/handbook.md"}

        assert dump.quick_action("wiki.ingest")
        await settle(pilot, dump)
        prompt, workdir = librarian.calls[0]
        assert workdir == root and (root / "WIKI.md").is_file()
        assert "(read it at `../../docs/handbook.md`)" in prompt                # project files are read in place
        assert "(read it at `raw/git/HEAD_docs/handbook.md`)" in prompt         # the rest is snapshotted
        assert not dump.pending and dump.status() == "FRESH" and wiki.page_count(dump.pages) == 1
        log = git(fake_repo, "log", "-1", "--format=%an|%s", "--name-only")
        assert log.startswith("Scroll Scrapper (orkcraft)|wiki(general): take in 6 source(s)")
        assert "llm-wiki/general/raw/manifest.json" in log and "raw/git" not in log   # snapshots stay out of git
        assert "llm-wiki/general/pages/how-to/release.md" in log and "src/" not in log
        assert [p.mode for p in sent if p.mode.startswith("wiki.")] == ["wiki.updated", "wiki.review"]
        assert "## pages/how-to/release.md" in sent[-1].value
        [job] = dump.log.read()
        assert job.ok and job.model == "sonnet" and job.cost_usd == 0.02 and job.meta["commit"]

        app.deliver_payload("dump", pipes.Payload(pipes.TEXT, "release.md: OK", "council", "team.artifact_ready",
                                                  "verdict"), "verdict", "release.md: OK")
        assert "release.md: OK" in (root / "reviews.md").read_text()
        assert git(fake_repo, "log", "-1", "--format=%s").strip() == "wiki(general): the Council's review"

        (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag it.\n")    # touched only
        dump.refresh_data()
        assert not dump.pending
        (root / "pages/how-to/mine.md").write_text("---\nowner: human\n---\n# Mine\n")
        (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag and sign it.\n")
        dump.refresh_data()
        assert dump.pending.changed == ["docs/handbook.md"] and dump.status() == "PENDING"
        assert "🔒 people's: 1" in dump.hut_lines([16])

        librarian.fail = True
        manifest = json.loads((root / wiki.MANIFEST).read_text())
        dump.ingest()
        await settle(pilot, dump)
        assert json.loads((root / wiki.MANIFEST).read_text()) == manifest      # a failed ingest takes nothing in
        assert dump.status() == "ERROR" and dump.pending.changed == ["docs/handbook.md"]

        librarian.fail, librarian.misbehave, dump.last_error = False, True, ""
        dump.ingest()
        await settle(pilot, dump)
        assert "- `pages/how-to/mine.md`" in librarian.calls[-1][0]
        assert "owner: human" in (root / "pages/how-to/mine.md").read_text()     # put back
        assert "put back 1 page" in dump.last_note and "outside the wiki changed while it worked: src/app.py" in dump.last_note
        assert "src/app.py" not in git(fake_repo, "log", "-1", "--name-only")

        librarian.misbehave = False
        assert dump.quick_action("wiki.lint")
        await settle(pilot, dump)
        assert [p.mode for p in sent][-1] == "wiki.linted" and "lint: 1" in dump.hut_lines([16])

        (fake_repo / "docs" / "notes.md").write_text("# Notes\n\nchanged\n")
        dump.refresh_data()
        librarian.wait = True
        dump.ingest()
        await pilot.pause()
        await pilot.press("x")
        dump.action_stop()
        await settle(pilot, dump)
        assert dump.log.read()[0].outcome == "interrupted" and dump.status() == "PENDING"


@pytest.mark.asyncio
async def test_a_failing_source_is_not_gone(fake_repo: Path, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ORKCRAFT_SCROLLS_CACHE_DIR", str(tmp_path / "cache"))
    assert masonry.save_spec(fake_repo, spec(sources=["docs", "confluence:ENG@https://x.atlassian.net/wiki"])) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        root = dump.wiki_root
        wiki.save_manifest(root, {"docs/notes.md": dump._fingerprints["docs/notes.md"], "confluence:1": "4"})
        dump.refresh_data()
        assert dump.bases[1].error and not dump.pending                     # Confluence down: its pages stay


@pytest.mark.asyncio
async def test_auto_ingest_waits_for_the_sources_to_settle(fake_repo: Path, monkeypatch):
    from orkcraft.screens.typed import knowledge_view
    monkeypatch.setenv("ORKCRAFT_WIKI_AUTO", "1")
    monkeypatch.setattr(knowledge_view, "SETTLE_S", 3600)
    assert masonry.save_spec(fake_repo, spec(wiki="kb", topic="codebase", commit=False)) == []
    for bad in ("../outside", "/tmp/x", ""):
        assert masonry.save_spec(fake_repo, {**spec(wiki=bad), "id": "dump2"})
    librarian = Librarian()
    monkeypatch.setattr(KnowledgeView, "work_runner", librarian)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        dump.refresh_data()
        assert dump.pending and not librarian.calls                        # not settled yet
        (fake_repo / "kb" / "pages" / "how-to").mkdir(parents=True)
        monkeypatch.setattr(knowledge_view, "SETTLE_S", 0)
        dump.refresh_data()
        await settle(pilot, dump)
        assert len(librarian.calls) == 1 and librarian.calls[0][1] == fake_repo / "kb"
        assert (fake_repo / "kb" / "pages" / "modules" / "CLAUDE.md").is_file()
        dump.refresh_data()
        dump.refresh_data()
        await settle(pilot, dump)
        assert len(librarian.calls) == 1                                    # nothing new: no second run
        assert "Scroll Scrapper" not in git(fake_repo, "log", "--format=%an")   # commit: false


# -- the steward's wiki loop -----------------------------------------------------------------------------

@dataclass
class FakeSession:
    transcript: str
    orcs: set[str] = field(default_factory=set)
    last: dt.datetime | None = None


def test_the_steward_proposes_a_wiki_loop(tmp_path: Path):
    presets = {"fields": {"title": "Task Fields", "icon": "🌾", "orc": "Taskmaster", "role": "kanban", "category": "core"},
               "pool": {"title": "Barracks", "icon": "🏕️", "orc": "Grunts", "role": "preview", "category": "core"},
               "kb": {"title": "Scrolls", "icon": "🗑️", "orc": "Scroll Scrapper", "role": "files", "category": "core"}}
    scroll = ts.default_scroll(presets)
    ts.subscribe(scroll, "pool", "fields", "tasks.created")
    assert masonry.save_spec(tmp_path, {**spec(topic="codebase"), "id": "kb"}) == []
    transcript = tmp_path / "t.jsonl"
    rows = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": f"t{i}", "name": "Read",
         "input": {"file_path": f"{tmp_path}/llm-wiki/codebase/pages/modules/pay{i}.md"}}]}} for i in range(4)]
    transcript.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    now = dt.datetime(2026, 10, 4, 12, 0)
    sessions = [FakeSession(str(transcript), {"pool/grunt-1"}, now), FakeSession(str(transcript), {"other/x"}, now)]

    def no_model(prompt):
        raise AssertionError("the wiki loop needs no model")

    report = steward.watch(tmp_path, scroll, "pool", sessions=sessions, runner=no_model, now=now)
    assert report.metrics.wiki_reads == {"kb": 4}
    assert [f.kind for f in report.findings] == ["wiki_bypass"]
    assert [(p.type, p.data.get("to"), p.data["from"], p.data["event"]) for p in report.proposals] == [
        ("new_road", None, "kb", "knowledge.chunks"), ("new_road", "kb", "fields", "tasks.created")]
    for p in report.proposals:
        steward.apply_proposal(scroll, "pool", p)
    assert any(r.source == "kb" for r in scroll.building("pool").roads)
    assert any(r.source == "fields" for r in scroll.building("kb").roads)
    again = steward.watch(tmp_path, scroll, "pool", sessions=sessions, runner=no_model, now=now)
    assert "wiki_bypass" not in [f.kind for f in again.findings]           # the road is there now


@pytest.mark.asyncio
async def test_the_council_spot_checks(fake_repo: Path, monkeypatch):
    council = {"id": "elders", "title": "Clan Fire", "icon": "🪔", "orc": {"name": "Chieftains"}, "type": "council",
               "config": {"members": ["Reviewer:claude", "Critic:claude"], "max_cycles": 4, "budget_usd": 5.0}}
    assert masonry.save_spec(fake_repo, council) == []
    assert masonry.save_spec(fake_repo, spec(sources=["docs"], council="elders", review_sample=1)) == []
    asked = []

    def members(harness, prompt, model):
        asked.append(prompt)
        if prompt.startswith("You are the steward"):
            return "DECISION: approve\n\nrelease.md: OK", 0.02
        return "APPROVE — release.md: OK", 0.01

    monkeypatch.setattr(KnowledgeView, "work_runner", Librarian())
    monkeypatch.setattr(KnowledgeView, "review_runner", staticmethod(members))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        dump.ingest()
        await settle(pilot, dump)
        for _ in range(100):
            await pilot.pause()
            if not dump.reviewing:
                break
        assert len(asked) == 3 and all("pages/how-to/release.md" in p for p in asked[:2])   # two reviews, a decision
        assert "Never ask the operator" in asked[2]
        reviews = (dump.wiki_root / "reviews.md").read_text()
        assert "release.md: OK" in reviews and "Reviewer" in reviews
        saved = list((fake_repo / ".orkcraft" / "council" / "elders" / "discussions").glob("*.json"))
        assert len(saved) == 1 and json.loads(saved[0].read_text())["outcome"] == "approved"
        assert git(fake_repo, "log", "-1", "--format=%s").strip() == "wiki(general): the Council's review"
