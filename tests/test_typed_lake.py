"""🌊 The Lake of Insight (T1107 stage 6): diffs side by side, Markdown, URLs as text, branches."""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import lake, masonry, pipes
from orkcraft.screens.typed.lake_view import LakeView

DIFF = """diff --git a/src/app.py b/src/app.py
index 1..2 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@ def main
 import sys
-print('hello')
+print('hello, camp')
+print('bye')
 sys.exit(0)
"""


class Page(io.BytesIO):
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def page(html: str):
    return lambda req, timeout=None: Page(html.encode())


def test_side_by_side_and_kinds(fake_repo: Path):
    rows = lake.side_by_side(DIFF)
    assert rows[0] == ("── src/app.py", "", "@")
    assert ("print('hello')", "print('hello, camp')", "~") in rows and ("", "print('bye')", "+") in rows
    assert ("import sys", "import sys", " ") in rows
    assert lake.look(fake_repo, "text", DIFF).kind == "diff"
    assert lake.look(fake_repo, "file", "README.md").kind == "markdown"
    assert lake.look(fake_repo, "file", "src/app.py").kind == "code"
    assert lake.look(fake_repo, "text", "**bold** and\n- a list").kind == "markdown"
    assert lake.look(fake_repo, "text", "plain words").kind == "text"
    v = lake.look(fake_repo, "text", "http://127.0.0.1:3000/", opener=page(
        "<html><head><style>x{}</style></head><body><h1>Shop</h1><p>Cart is <b>empty</b></p><script>1</script></body></html>"))
    assert v.kind == "url" and v.text.startswith("# Shop") and "Cart is empty" in v.text and "x{}" not in v.text
    def boom(req, timeout=None):
        raise OSError("refused")
    assert "could not fetch" in lake.look(fake_repo, "text", "http://localhost:9/", opener=boom).text
    subprocess.run(["git", "checkout", "-q", "-b", "feat"], cwd=fake_repo, check=True)
    (fake_repo / "src" / "app.py").write_text("print('feat')\n")
    subprocess.run(["git", "commit", "-qam", "feat"], cwd=fake_repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-"], cwd=fake_repo, check=True)
    b = lake.look(fake_repo, "text", "feat")
    assert b.kind == "diff" and b.title == "⎇ feat" and any(r[2] == "~" for r in b.rows)


@pytest.mark.asyncio
async def test_the_lake_shows_what_arrives_and_opens_it(fake_repo: Path, monkeypatch):
    spec = {"id": "insight", "title": "Lake", "icon": "🌊", "orc": {"name": "Seer"}, "type": "lake"}
    assert masonry.save_spec(fake_repo, spec) == []
    opened = []
    monkeypatch.setattr(LakeView, "opener", staticmethod(opened.append))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "insight", "lake.viewed")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("insight").query_one(LakeView)
        assert view.mini_status() == ["nothing shown"]
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("insight", pipes.Payload(pipes.TEXT, DIFF, "loot", "pit.text", "patch"), "patch", DIFF)
        for _ in range(40):
            await pilot.pause(0.05)
            if view.view is not None:
                break
        assert view.mini_status() == ["diff: patch", "+2 −1"] and sent[-1].mode == "lake.viewed"
        app.deliver_payload("insight", pipes.Payload(pipes.FILE, "README.md", "loot", "files.selected", "README.md"))
        for _ in range(40):
            await pilot.pause(0.05)
            if view.view.kind == "markdown":
                break
        assert view.query_one("#lake-md").display and "Demo project" in view.query_one("#lake-md").source
        assert view.quick_action("lake.open") and opened[-1] == (fake_repo / "README.md").resolve().as_uri()
