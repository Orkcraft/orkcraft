"""🗑️ Scroll Dump as an LLM wiki: topics and hierarchy, what is pending, ingest and lint by the
librarian orc, pages people own, commits, the Council's spot-checks, the steward's wiki loop."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


from orkcraft import scroll as ts
from orkcraft.realm import masonry, shelves, steward, wiki


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


def spec(**config) -> dict:
    return {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls",
            "config": config}


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
