"""📦 Loot shows the files a Barracks task committed on its branch, and opens one in the system viewer."""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.realm import gate, generated, masonry, pipes
from orkcraft.screens.typed.generator_view import GeneratorView

SIZE = (200, 46)
PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 64, 32) + b"\x08\x02\x00\x00\x00" \
    + b"\x00" * 40


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def task_branch(repo: Path) -> tuple[Path, str, str]:
    """A worktree like an ork's, with a picture and a note committed on `pool/camp/t1`."""
    base = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    wt = repo / ".orkcraft" / "worktrees" / "pool-camp-grub"
    git(repo, "worktree", "add", "-q", "-b", "pool/camp/t1", str(wt), "HEAD")
    (wt / "art").mkdir()
    (wt / "art" / "logo.png").write_bytes(PNG)
    (wt / "art" / "notes.md").write_text("# The logo\n\nred on black\n")
    (wt / "README.md").unlink()
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "a logo")
    return wt, "pool/camp/t1", base


def test_image_info_reads_the_picture_not_the_name():
    assert generated.image_info(PNG) == f"PNG image · 64×32 · {len(PNG)} bytes"
    assert generated.image_info(b"GIF89a" + struct.pack("<HH", 10, 20) + b"\0" * 2000).startswith("GIF image · 10×20 · 2.0 KB")
    jpeg = b"\xff\xd8\xff\xe0" + struct.pack(">H", 4) + b"JF" + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 48, 96) + b"\0" * 12
    assert generated.image_info(jpeg).startswith("JPEG image · 96×48")
    assert generated.image_info(b"just text") == ""
    assert generated.binary_note(b"\0\1\2") == "(binary, 3 bytes · o opens it)"


def test_a_picture_in_the_working_tree_says_what_it_is(fake_repo: Path):
    (fake_repo / "src" / "shot.png").write_bytes(PNG)
    rv = generated.Review(fake_repo, fake_repo / ".orkcraft" / "generator" / "g")
    assert rv.preview("src/shot.png") == f"(PNG image · 64×32 · {len(PNG)} bytes · o opens it)"


def test_the_branch_lists_what_the_task_committed(fake_repo: Path, tmp_path: Path):
    wt, branch, base = task_branch(fake_repo)
    br = generated.Branch(wt, branch, base)
    assert [(g.change, g.path) for g in br.files()] == [("D", "README.md"), ("A", "art/logo.png"),
                                                        ("A", "art/notes.md")]
    assert "+red on black" in br.preview("art/notes.md")
    assert br.preview("art/logo.png").startswith("(PNG image · 64×32")
    assert "-# Demo project" in br.preview("README.md")
    copy = br.export("art/logo.png", tmp_path / "out")
    assert copy.name == "logo.png" and copy.read_bytes() == PNG
    with pytest.raises(ValueError):
        generated.Branch(wt, "--output=x", base)
    with pytest.raises(RuntimeError):
        generated.Branch(wt, branch, "no-such-base").files()


def test_open_file_uses_the_system_viewer(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(generated.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(generated.sys, "platform", "darwin")
    generated.open_file(tmp_path / "a.png")
    monkeypatch.setattr(generated.sys, "platform", "linux")
    monkeypatch.setattr(generated.shutil, "which", lambda name: "/usr/bin/xdg-open" if name == "xdg-open" else None)
    generated.open_file(tmp_path / "a.png")
    assert calls == [["open", str(tmp_path / "a.png")], ["xdg-open", str(tmp_path / "a.png")]]
    monkeypatch.setattr(generated.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError):
        generated.open_file(tmp_path / "a.png")


@pytest.mark.asyncio
async def test_a_held_cart_shows_its_branch_files_and_opens_the_picture(fake_repo: Path, monkeypatch):
    wt, branch, base = task_branch(fake_repo)
    spec = {"id": "gate", "title": "Art Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
            "config": {"sources": ["camp"], "paths": ["art/*.png"]}}
    assert masonry.save_spec(fake_repo, spec) == []
    opened = []
    monkeypatch.setattr(generated, "open_file", lambda p: opened.append((p.name, p.read_bytes())))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: [])
        view = app.desktop.get_window("gate").query_one(GeneratorView)
        hop = pipes.hop("camp", "Grub", "agent", 900, 0.04, str(wt), branch, "done", base=base)
        cart = pipes.Payload(pipes.TEXT, "## A logo\n\ndone", "camp", "pool.done", "Logo", (hop,), "T-1")
        view.receive(cart, "Logo", cart.value)
        [item] = view.queue.open()
        assert "touches art/logo.png" in item.why                    # the rules read the branch's files too
        lst = view.query_one("#gen-files")
        ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        rows = [i for i in ids if i and i.startswith("bf:")]
        assert len(rows) == 3 and ids.index(rows[0]) == ids.index(f"q:{item.id}") + 1   # right under the cart
        assert "3 files on pool/camp/t1" in str(view.query_one("#gen-preview").render())

        lst.highlighted = ids.index(rows[1])                         # art/logo.png
        await pilot.pause()
        assert "PNG image · 64×32" in str(view.query_one("#gen-preview").render())
        view.action_open()
        assert opened == [("logo.png", PNG)]                         # copied out of the branch, then opened

        (fake_repo / "src" / "app.py").write_text("print('changed')\n")   # a file of the working tree opens in place
        view.refresh_data()
        ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        lst.highlighted = ids.index("src/app.py")
        view.action_open()
        assert opened[-1] == ("app.py", b"print('changed')\n")

        view.accept_item(item)                                       # passed: its branch rows go
        ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        assert not any(i and i.startswith("bf:") for i in ids) and view.branches == {}


def test_one_file_of_the_branch_is_rejected_and_brought_back(fake_repo: Path, tmp_path: Path):
    wt, branch, base = task_branch(fake_repo)
    git(wt, "checkout", "-q", "--detach")                    # the ork moved on: the branch is checked out nowhere
    br = generated.Branch(wt, branch, base)
    before = git(fake_repo, "rev-parse", branch)
    added = br.reject("art/notes.md", tmp_path / "keep")
    assert added["change"] == "A" and Path(added["kept"]).read_text() == "# The logo\n\nred on black\n"
    assert [g.path for g in br.files()] == ["README.md", "art/logo.png"]          # the rest goes on
    assert git(fake_repo, "rev-parse", f"{branch}~1") == before                   # one commit on top, nothing rewritten
    deleted = br.reject("README.md", tmp_path / "keep")                            # a deletion: the file comes back
    assert deleted["kept"] == "" and git(fake_repo, "show", f"{branch}:README.md").startswith("# Demo project")
    assert [g.path for g in br.files()] == ["art/logo.png"]
    br.restore(added)
    br.restore(deleted)
    assert [(g.change, g.path) for g in br.files()] == [("D", "README.md"), ("A", "art/logo.png"), ("A", "art/notes.md")]
    with pytest.raises(ValueError):
        br.reject("src/app.py", tmp_path / "keep")                                 # not the branch's


def test_a_worktree_that_has_the_branch_follows_it(fake_repo: Path, tmp_path: Path):
    wt, branch, base = task_branch(fake_repo)
    br = generated.Branch(wt, branch, base)
    entry = br.reject("art/logo.png", tmp_path / "keep")
    assert not (wt / "art" / "logo.png").exists() and git(wt, "status", "--porcelain") == ""
    br.restore(entry)
    assert (wt / "art" / "logo.png").read_bytes() == PNG and git(wt, "status", "--porcelain") == ""
    (wt / "art" / "notes.md").write_text("half done\n")                            # someone's uncommitted change
    with pytest.raises(RuntimeError, match="uncommitted"):
        br.reject("art/notes.md", tmp_path / "keep")
    assert (wt / "art" / "notes.md").read_text() == "half done\n"
