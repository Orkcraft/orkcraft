"""Any folder as a source of the Wiki (docs/design/wiki-folders-rules.md §1): what a `dir:` source reads and
skips, a folder outside the project read where it is, and the librarian told where each file is."""
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.scrolls import ScrollsWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, extract
from orkcraft.sources import lore

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def docx(*paragraphs: tuple[str, str]) -> bytes:
    """A minimal Word file: (style, text) per paragraph; style "" a plain one, "list" a list item."""
    body = ""
    for style, words in paragraphs:
        props = ('<w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr>' if style == "list"
                 else f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else "")
        body += f"<w:p>{props}<w:r><w:t>{words}</w:t></w:r></w:p>"
    body += "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>a</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>b</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def test_what_a_file_is_to_the_wiki():
    assert extract.kind_of("a/b.MD") == "doc" and extract.kind_of("x.txt") == "doc"
    assert extract.kind_of("app.py") == "code" and extract.kind_of("spec.docx") == "docx"
    assert extract.kind_of("paper.pdf") == "pdf" and extract.kind_of("photo.png") is None
    assert extract.secret(".env") and extract.secret("prod.env") and extract.secret("keys/server.pem")
    assert extract.secret("id_rsa") and not extract.secret("environment.md")


def test_a_word_files_text_keeps_its_headings_lists_and_tables():
    text = extract.docx_text(docx(("Heading1", "Pricing"), ("", "Three tiers."), ("list", "Free"), ("Heading2", "Notes")))
    assert text.splitlines()[:3] == ["# Pricing", "Three tiers.", "- Free"]
    assert "## Notes" in text and "| a | b |" in text
    try:
        extract.docx_text(b"not a zip")
    except ValueError as e:
        assert "not a Word document" in str(e)
    else:
        raise AssertionError("a broken file must say so")


def _mixed(folder: Path) -> Path:
    (folder / "sub").mkdir(parents=True)
    (folder / "readme.md").write_text("# Read me\n\ntext\n")
    (folder / "spec.docx").write_bytes(docx(("Heading1", "Spec"), ("", "The spec.")))
    (folder / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
    (folder / "sub" / "tool.py").write_text("print(1)\n")
    (folder / "photo.png").write_bytes(b"\x89PNG")
    (folder / ".env").write_text("TOKEN=1\n")
    (folder / "server.pem").write_text("key\n")
    (folder / ".hidden").mkdir()
    (folder / ".hidden" / "x.md").write_text("# x\n")
    (folder / "node_modules").mkdir()
    (folder / "node_modules" / "y.md").write_text("# y\n")
    return folder


def test_a_folder_outside_the_project_is_read_whatever_it_holds(fake_repo: Path, tmp_path: Path):
    outside = _mixed(tmp_path / "Documents")
    src = lore.parse(f"dir:{outside}", fake_repo)
    base = src.scan()
    names = sorted(n.path.rsplit("/", 1)[-1] for n in base.notes)
    assert names == ["paper.pdf", "readme.md", "spec.docx", "tool.py"] and not base.error
    readme = next(n for n in base.notes if n.path.endswith("readme.md"))
    assert readme.path == f"dir:{outside.resolve().as_posix()}/readme.md" and readme.title == "Read me" and readme.rev
    assert "# Spec" in src.read(next(n.path for n in base.notes if n.path.endswith(".docx")))
    assert src.in_place(readme.path) is None                                 # text outside: a snapshot
    assert src.in_place(next(n.path for n in base.notes if n.path.endswith(".pdf"))) == outside.resolve() / "paper.pdf"
    assert not src.owns("docs/notes.md") and src.owns(readme.path)
    assert lore.parse(f"dir:{outside}", fake_repo, max_files=2).scan().error == "cut at 2 files"


def test_a_folder_in_a_git_tree_skips_what_its_gitignore_ignores(fake_repo: Path):
    folder = _mixed(fake_repo / "handbook")
    (fake_repo / ".gitignore").write_text("handbook/sub/\n")
    src = lore.parse("dir:handbook", fake_repo)
    paths = sorted(n.path for n in src.scan().notes)
    assert paths == ["handbook/paper.pdf", "handbook/readme.md", "handbook/spec.docx"]
    assert src.owns("handbook/readme.md") and src.in_place("handbook/readme.md") == folder.resolve() / "readme.md"
    assert src.in_place("handbook/spec.docx") is None                       # its text is snapshotted


def test_the_librarian_is_told_where_each_file_is(fake_repo: Path, tmp_path: Path, monkeypatch):
    outside = _mixed(tmp_path / "Documents")
    prompts = []

    def runner(harness, prompt, workdir, cancel, model, env, resume):
        prompts.append(prompt)
        return "done", 0.0, None, ""

    monkeypatch.setattr(ScrollsWorker, "work_runner", staticmethod(runner))
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "commit": False, "sources": ["docs"]}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    host.command("act", {"id": bid, "act": "add_folder", "args": {"path": str(outside)}})
    assert w.config["sources"] == ["docs", f"dir:{outside.resolve().as_posix()}"] and "rules_in" not in w.config
    assert host.town.machine.recent_folders[0] == str(outside.resolve())
    assert w.ingest()
    end = time.monotonic() + 5
    while w.running and time.monotonic() < end:
        time.sleep(0.02)
    prompt = prompts[-1]
    assert f"(read it at `{outside.resolve() / 'paper.pdf'}`)" in prompt          # a PDF where it is
    assert "raw/dir/" in prompt and "spec.docx.md" in prompt                       # a Word file's text
    assert (w.wiki_root / "raw").is_dir() and "# Spec" in next((w.wiki_root / "raw" / "dir").rglob("spec.docx.md")).read_text()
    assert "(read it at `../../docs/notes.md`)" in prompt
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add_folder", "args": {"path": str(w.wiki_root)}})
    about = host.command("act", {"id": bid, "act": "about", "args": {"path": str(outside)}})
    assert about["outside"] and about["exists"]
    assert not host.command("act", {"id": bid, "act": "about", "args": {"path": "docs"}})["outside"]


def test_a_folder_outside_may_get_the_rules_when_asked(fake_repo: Path, tmp_path: Path):
    outside = tmp_path / "other"
    outside.mkdir()
    (outside / "a.md").write_text("# A\n")
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "commit": False}
    bid = buildings.raise_spec(host.town, spec).id
    host.command("act", {"id": bid, "act": "add_folder", "args": {"path": str(outside), "rules": True}})
    w = host.town.worker(bid)
    assert w.config["rules_in"] == [outside.resolve().as_posix()]
    assert w.config["sources"][-1] == f"dir:{outside.resolve().as_posix()}"


def test_the_ai_tool_may_read_the_folders_outside_never_write_them(fake_repo: Path, tmp_path: Path, monkeypatch):
    from orkcraft.realm import harnesses, jobs
    argv = harnesses.need("claude").work("take in", fake_repo, dirs=["/data/specs"])
    assert argv[argv.index("--add-dir") + 1] == "/data/specs"
    assert "Edit(//data/specs/**)" in argv[argv.index("--disallowedTools") + 1]
    assert harnesses.need("codex").work("x", fake_repo, dirs=["/data/specs"]) == harnesses.need("codex").work("x", fake_repo)
    outside = _mixed(tmp_path / "Documents")
    got = {}

    def run_work(harness, prompt, workdir, cancel, model, env, resume, dirs=()):
        got["dirs"] = dirs
        return "done", 0.0, None, ""

    monkeypatch.setattr(jobs, "run_work", run_work)
    monkeypatch.setattr(ScrollsWorker, "work_runner", None)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "commit": False,
                      "sources": ["docs", f"dir:{outside}"]}
    w = host.town.worker(buildings.raise_spec(host.town, spec).id)
    w.refresh()
    assert w.ingest()
    end = time.monotonic() + 5
    while w.running and time.monotonic() < end:
        time.sleep(0.02)
    assert got["dirs"] == (str(outside.resolve()),)
