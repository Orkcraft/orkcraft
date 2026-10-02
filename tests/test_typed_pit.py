"""🕳️ The Pit (T1107 stage 2): files, links, text and the clipboard, sorted and sent on."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pit
from orkcraft.screens.typed.pit_view import PitView

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


@pytest.mark.asyncio
async def test_the_pit_sends_each_kind_down_its_road(fake_repo: Path, monkeypatch):
    spec = {"id": "intake", "title": "The Pit", "icon": "🕳️", "orc": {"name": "Scavenger"}, "type": "pit"}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("drop.file", "pit.link", "pit.text"):
        ts.subscribe(app.scroll, "town_hall", "intake", ev)
    monkeypatch.setattr(PitView, "clipboard_reader", staticmethod(lambda: "https://example.com/spec"))
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        view = app.desktop.get_window("intake").query_one(PitView)
        assert view.mini_status() == ["drop or paste"]
        assert view.drop("remember: ship on Friday") == 1
        assert view.quick_action("pit.paste")                          # 📋 the clipboard
        assert view.drop(str(fake_repo / "README.md")) == 1
        assert [(p.kind, p.mode, p.value) for p in sent] == [
            ("text", "pit.text", "remember: ship on Friday\n"), ("text", "pit.link", "https://example.com/spec"),
            ("file", "drop.file", "README.md")]
        assert view.mini_status() == ["📄 README.md", "3 in the pit"]
        assert view.query_one("#drop-list").option_count == 3
