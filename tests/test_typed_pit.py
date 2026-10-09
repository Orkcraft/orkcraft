"""🕳️ The Pit (T1107 stage 2): files, links, text and the clipboard, sorted and sent on."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace


from orkcraft.realm import pit

NOW = dt.datetime(2026, 10, 2, 5, 30, 0)


def test_sort_files_links_and_text(fake_repo: Path, tmp_path: Path):
    shot = tmp_path / "bug.png"
    shot.write_bytes(b"\x89PNG")
    [img] = pit.sort(fake_repo, f"'{shot}'", NOW)
    assert (img.kind, img.copied, img.event) == ("image", True, "drop.file")
    assert img.value == ".orkcraft/pit/20261002-053000-bug.png" and (fake_repo / img.value).exists()
    [inside] = pit.sort(fake_repo, str(fake_repo / "src" / "app.py"), NOW)
    assert (inside.kind, inside.value, inside.copied) == ("code", "src/app.py", False)
    links = pit.sort(fake_repo, "https://github.com/x/y/pull/7 https://example.com/a.", NOW)
    assert [(i.kind, i.value) for i in links] == [("link", "https://github.com/x/y/pull/7"),
                                                  ("link", "https://example.com/a")]
    [note] = pit.sort(fake_repo, "Traceback: boom\nsee https://example.com", NOW)
    assert note.kind == "text" and note.title == "Traceback: boom" and note.event == "pit.text"
    assert (fake_repo / note.value).read_text().startswith("Traceback")
    assert pit.sort(fake_repo, "   ", NOW) == []
    pit.log(fake_repo, [img, inside, *links, note])
    assert [i.kind for i in pit.history(fake_repo)] == ["text", "link", "link", "code", "image"]
    ok = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="copied text")
    assert pit.clipboard(ok) == "copied text"
    assert pit.clipboard(lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="")) == ""
