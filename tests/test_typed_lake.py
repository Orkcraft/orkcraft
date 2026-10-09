"""🌊 The Lake of Insight (T1107 stage 6): diffs side by side, Markdown, URLs as text, branches."""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from orkcraft.realm import lake

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


def test_a_file_is_saved_with_its_line_endings_never_over_a_change_on_disk(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_bytes(b"# Notes\r\nfirst\r\n")
    f.chmod(0o640)
    assert lake.look(tmp_path, "file", "notes.md").path == str(f)
    draft = lake.read_for_edit(str(f))
    assert draft.text == "# Notes\nfirst\n" and draft.newline == "\r\n"
    assert lake.save(draft, draft.text) == "unchanged"
    assert lake.save(draft, "# Notes\nfirst\nsecond\n") == "saved"
    assert f.read_bytes() == b"# Notes\r\nfirst\r\nsecond\r\n" and f.stat().st_mode & 0o777 == 0o640
    f.write_bytes(b"# Notes\r\nchanged elsewhere\r\n")                    # someone else wrote it
    assert lake.save(draft, "mine\n") == "conflict" and b"elsewhere" in f.read_bytes()
    assert lake.save(draft, "mine\n", force=True) == "saved" and f.read_bytes() == b"mine\r\n"
    assert not list(tmp_path.glob(".notes.md.*"))                        # no temporary file is left
    (tmp_path / "blob.bin").write_bytes(b"\0\1\2")
    with pytest.raises(ValueError, match="binary"):
        lake.read_for_edit(str(tmp_path / "blob.bin"))
    assert lake.look(tmp_path, "text", "plain words").path == ""        # only a file is edited
