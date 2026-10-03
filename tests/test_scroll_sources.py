"""🗑️ Scroll Dump sources (folders, code, git, Confluence) and its retrievers (BM25, the code graph)."""
from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, codegraph, masonry, shelves
from orkcraft.screens.typed.knowledge_view import KnowledgeView
from orkcraft.sources import lore

UPLOAD = '''"""Uploads to the bucket."""
from shop.net import retry_request


def upload_file(path):
    """Send one file to the bucket, retrying on a timeout."""
    return retry_request("PUT", path)


class Uploader:
    def run(self, paths):
        return [upload_file(p) for p in paths]
'''
NET = '''def retry_request(method, url, tries=3):
    """Repeat a request until it succeeds."""
    for _ in range(tries):
        pass
'''
JS = '''// Formats a price with its currency.
export function formatPrice(amount, currency) {
  return currency + roundCents(amount);
}

const roundCents = (x) => Math.round(x * 100) / 100;
'''


def commit(repo: Path, msg: str = "more") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def shop(fake_repo: Path, tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("ORKCRAFT_SCROLLS_CACHE_DIR", str(tmp_path / "scroll-cache"))
    pkg = fake_repo / "src" / "shop"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "upload.py").write_text(UPLOAD)
    (pkg / "net.py").write_text(NET)
    (fake_repo / "src" / "price.js").write_text(JS)
    (fake_repo / "docs" / "handbook.md").write_text("# Handbook\n\n## Release\nTag it and publish the release.\n")
    commit(fake_repo)
    return fake_repo


def test_config_strings_make_sources(shop: Path):
    kinds = [(type(s).__name__, s.kind) for s in lore.from_config(
        {"paths": ["docs"], "sources": ["code:src", "git:main:docs", "confluence:ENG@https://x.atlassian.net/wiki", "docs"]},
        shop)]
    assert kinds == [("FolderSource", "code"), ("GitSource", "git"), ("ConfluenceSource", "confluence"),
                     ("FolderSource", "fs")]                  # `sources` first, duplicates once
    assert [s.spec for s in lore.from_config({}, shop)] == ["docs"]
    assert catalog.validate({"id": "kb", "type": "scrolls", "config": {"sources": ["code:src", "git:HEAD"]}}) == []


def test_code_folder_and_git_revision(shop: Path):
    code = lore.parse("code:src", shop).scan()
    assert {n.path for n in code.notes} == {"src/app.py", "src/price.js", "src/shop/__init__.py",
                                           "src/shop/upload.py", "src/shop/net.py"}
    assert {n.kind for n in code.notes} == {"code"}

    git = lore.parse("git:HEAD:docs", shop)
    (shop / "docs" / "handbook.md").write_text("# Handbook\n\n## Draft\nnot committed\n")
    base = git.scan()
    by = {n.path: n for n in base.notes}
    assert set(by) == {"git:HEAD:docs/handbook.md", "git:HEAD:docs/notes.md"}
    assert by["git:HEAD:docs/handbook.md"].headings == ["Release"]          # the revision, not the working copy
    assert "Tag it" in git.read("git:HEAD:docs/handbook.md")
    stamp = by["git:HEAD:docs/handbook.md"].stamp
    commit(shop)
    after = {n.path: n.stamp for n in git.scan().notes}
    assert after["git:HEAD:docs/handbook.md"] != stamp
    assert shelves.note_changes({p: n.stamp for p, n in by.items()}, [git.scan()]) == ["git:HEAD:docs/handbook.md"]
    whole = {n.path: n.kind for n in lore.parse("git:HEAD", shop).scan().notes}
    assert whole["git:HEAD:src/shop/net.py"] == "code" and whole["git:HEAD:README.md"] == "doc"
    assert lore.parse("git:nope", shop).scan().error
    assert lore.parse("git:--output=x", shop).scan().error


def test_code_graph(shop: Path):
    texts = {p: (shop / p).read_text() for p in ("src/shop/upload.py", "src/shop/net.py", "src/price.js")}
    g = codegraph.build(texts)
    up = "src/shop/upload.py::upload_file"
    assert g.calls[up] == {"src/shop/net.py::retry_request"}
    assert g.callers[up] == {"src/shop/upload.py::Uploader.run"}
    assert g.imports["src/shop/upload.py"] == {"src/shop/net.py"}
    js = {s.name: s for s in g.symbols.values() if s.path == "src/price.js" and s.kind != "module"}
    assert set(js) == {"formatPrice", "roundCents"} and "currency" in js["formatPrice"].doc
    assert g.calls[js["formatPrice"].id] == {js["roundCents"].id}
    assert codegraph.words("retryUpload_now") == "retry upload now"

    found = codegraph.search(g, "how is a file uploaded with retries?")
    assert found[0].heading.startswith("upload_file (function")
    assert "calls: retry_request (net.py:1)" in found[0].text and "called by: Uploader.run" in found[0].text
    assert "retry_request" in [c.heading.split(" ")[0] for c in found]       # the neighbour came along
    assert codegraph.search(g, "zebra") == []
    broken = codegraph.build({"bad.py": "def oops(:\n  pass\n"})
    assert "bad.py" in broken.errors and any(s.name == "oops" for s in broken.symbols.values())


def test_library_merges_notes_and_code(shop: Path):
    lib = lore.Library(lore.from_config({"sources": ["docs", "code:src"]}, shop))
    lib.scan()
    found = lib.search(shop, "upload file to the bucket")
    assert found and found[0].path == "src/shop/upload.py"
    assert lib.search(shop, "publish the release")[0].heading == "Release"
    assert "retry_request" in lib.read("src/shop/net.py")
    with pytest.raises(ValueError):
        lib.read("confluence:1")


# -- Confluence -----------------------------------------------------------------------------------------

def page(i: int, body: str) -> dict:
    return {"id": str(i), "title": f"Page {i}", "version": {"number": 2},
            "body": {"storage": {"value": body}}, "_links": {"webui": f"/spaces/ENG/pages/{i}"}}


def test_confluence(shop: Path, monkeypatch):
    src = lore.parse("confluence:ENG@https://acme.atlassian.net/wiki", shop)
    with pytest.raises(ValueError, match="no token"):
        src.fetch()
    monkeypatch.setenv("ORKCRAFT_CONFLUENCE_EMAIL", "me@acme.io")
    monkeypatch.setenv("ORKCRAFT_CONFLUENCE_TOKEN", "t0k")
    calls = []
    first = [page(i, "<p>x</p>") for i in range(lore.ConfluenceSource.PAGE - 1)]
    first.append(page(99, "<h1>Deploy</h1><h2>Rollback</h2><p>Revert &amp; redeploy.</p><ul><li>one</li></ul>"))
    answers = [{"results": first, "_links": {"next": "/rest/api/content?start=50",
                                             "base": "https://acme.atlassian.net/wiki"}},
               {"results": [page(100, "<p>last</p>")], "_links": {}}]

    def fake(url, headers):
        calls.append((url, headers))
        return answers[len(calls) - 1]

    monkeypatch.setattr(lore, "http_json", fake)
    started = []
    monkeypatch.setattr(lore.RemoteSource, "refresh_in_background", lambda self: started.append(self.spec))
    assert src.scan().error == lore.FETCHING and started == [src.spec]       # never blocks: fetches aside
    src.refresh()
    assert "spaceKey=ENG" in calls[0][0] and "start=50" in calls[1][0]
    assert calls[0][1]["Authorization"].startswith("Basic ")
    base = src.scan()
    assert len(base.notes) == 51 and not base.error and started == [src.spec]   # fresh cache: no refetch
    n99 = next(n for n in base.notes if n.path == "confluence:99")
    assert n99.headings == ["Rollback"] and n99.url.endswith("/pages/99") and n99.stamp == "2"
    text = src.read("confluence:99")
    assert "# Deploy" in text and "## Rollback" in text and "Revert & redeploy." in text and "- one" in text
    assert "[open ↗](https://acme.atlassian.net/wiki/spaces/ENG/pages/99)" in text

    def denied(url, headers):
        raise urllib.error.HTTPError(url, 401, "no", {}, io.BytesIO(b""))
    monkeypatch.setattr(lore, "http_json", denied)
    src.refresh()
    stale = src.scan()
    assert stale.error == "HTTP 401 — check the token" and len(stale.notes) == 51      # the cache stays
    lib = lore.Library([src])
    lib.scan()
    assert lib.search(shop, "rollback")[0].heading == "Rollback"
    monkeypatch.setenv("ORKCRAFT_CONFLUENCE_PAT", "pat")
    assert src.headers() == {"Authorization": "Bearer pat"}
    assert json.loads(src.cache_file.read_text())["spec"] == src.spec


# -- the building --------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_dump_reads_many_sources(shop: Path, monkeypatch):
    spec = {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls",
            "config": {"sources": ["docs", "code:src", "git:HEAD:docs"]}}
    assert masonry.save_spec(shop, spec) == []
    app = OrkcraftApp(repo_root=shop, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "dump", "knowledge.chunks")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        assert [b.kind for b in dump.bases] == ["fs", "code", "git"]
        assert dump.hut_lines([16])[:3] == ["sources: 3", "notes: 4", "code: 5"]
        dump.find("upload a file")
        assert "upload_file" in sent[-1].value and "called by" in sent[-1].value
        dump.read("git:HEAD:docs/handbook.md")
        dump.read("src/shop/net.py")
        await pilot.pause()
        dump.save_config({"sources": ["docs"]})
        dump.refresh_data()
        assert [b.kind for b in dump.bases] == ["fs"]
