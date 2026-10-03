"""🗑️ Scroll Dump sources: folders, code, git revisions, Confluence (read-only)."""
from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest

from orkcraft.realm import catalog, shelves
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
    monkeypatch.setenv("ORKCRAFT_CONFLUENCE_PAT", "pat")
    assert src.headers() == {"Authorization": "Bearer pat"}
    assert json.loads(src.cache_file.read_text())["spec"] == src.spec
