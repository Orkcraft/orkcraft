"""Projects (docs/design/projects.md, stage 1): the folder an orkspace works in. The Town Scroll keeps the list
and each orkspace's choice (old scrolls load as they were); an orkspace works in its project's folder, else the
town's; the folders no project should be are refused in plain words; git starts in a folder only with a yes, and
never leaves a half-made repository behind; a new orkspace picks its project as it is made."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.gui.host import Host
from orkcraft.gui.host import CommandError
from orkcraft.realm import projects, worktrees


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# shop\n", encoding="utf-8")
    _git(path, "init", "-q")
    return path


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """A home folder of the test's own: `~/Orkcraft` (new projects) is in it."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    return h


def _scroll() -> ts.TownScroll:
    return ts.default_scroll({})


# -- the Town Scroll ----------------------------------------------------------------------------------------

def test_an_old_scroll_loads_with_no_projects_and_writes_none(tmp_path):
    s = _scroll()
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, s) == []
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "projects" not in data and all("project" not in o for o in data["orkspaces"])
    back, problems = ts.load(path, {})
    assert problems == [] and back.projects == [] and all(o.project is None for o in back.orkspaces)


def test_projects_are_kept_and_two_orkspaces_may_share_one(tmp_path):
    s = _scroll()
    shop = projects.add(s, "Shop", _repo(tmp_path / "shop"))
    other = ts.new_orkspace(s, "QA")
    projects.link(s, s.orkspaces[0].id, shop.id)
    projects.link(s, other.id, shop.id)
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, s) == []
    back, problems = ts.load(path, {})
    assert problems == []
    assert [p.id for p in back.projects] == ["shop"] and back.projects[0].path == str((tmp_path / "shop").resolve())
    assert {o.project for o in back.orkspaces} == {"shop"}
    assert projects.add(back, "Shop again", tmp_path / "shop").id == "shop"        # one folder, one project


def test_an_orkspace_naming_an_unknown_project_is_refused():
    data = _scroll().to_dict()
    data["orkspaces"][0]["project"] = "nowhere"
    assert any("unknown project 'nowhere'" in p for p in ts.validate(data))
    with pytest.raises(projects.ProjectError):
        projects.link(_scroll(), "main_camp", "nowhere")


# -- where an orkspace works ----------------------------------------------------------------------------------

def test_an_orkspace_works_in_its_projects_folder_while_it_is_there(tmp_path):
    town = _repo(tmp_path / "town")
    s = _scroll()
    oid = s.orkspaces[0].id
    assert projects.root_of(s, oid, town) == town                                   # no project: the town's
    shop = projects.add(s, "Shop", _repo(tmp_path / "shop"))
    projects.link(s, oid, shop.id)
    assert projects.root_of(s, oid, town) == (tmp_path / "shop").resolve()
    assert worktrees.cwd_for(s, oid, town) == (tmp_path / "shop").resolve()          # sessions start there
    (tmp_path / "shop" / "README.md").unlink()
    (tmp_path / "shop" / ".git").rename(tmp_path / "git-aside")
    (tmp_path / "shop").rmdir()
    assert projects.root_of(s, oid, town) == town                                   # gone: back to the town's
    projects.link(s, oid, None)
    assert s.orkspaces[0].project is None


def test_a_worktree_link_is_dropped_when_the_orkspace_changes_project(tmp_path):
    s = _scroll()
    ork = s.orkspaces[0]
    ork.git = ts.GitLink(True, "worktree", ".orkcraft/worktrees/main_camp", "feat")
    shop = projects.add(s, "Shop", _repo(tmp_path / "shop"))
    projects.link(s, ork.id, shop.id)
    assert ork.git.enabled is False and ork.project == "shop"


# -- which folders may be projects ---------------------------------------------------------------------------

def test_the_disk_the_home_folder_and_a_folder_inside_a_repository_are_refused(tmp_path, home):
    assert "whole disk" in projects.refusal(Path("/"))
    assert "home folder" in projects.refusal(home)
    assert "no folder" in projects.refusal(tmp_path / "nowhere").lower()
    shop = _repo(tmp_path / "shop")
    (shop / "src").mkdir()
    assert f"inside the repository {shop.resolve()}" in projects.refusal(shop / "src")
    assert projects.refusal(shop) == ""
    plain = tmp_path / "notes"
    plain.mkdir()
    assert projects.refusal(plain) == ""


def test_a_folder_inside_orkcrafts_own_home_may_be_a_project(tmp_path, home):
    own = _repo(home / "Orkcraft")
    folder = projects.new_folder("Shop")
    assert folder == own / "projects" / "shop" and folder.is_dir()
    assert projects.refusal(folder) == ""
    assert "/projects/shop/" in (own / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert projects.new_folder("Shop") == own / "projects" / "shop_2"                # taken: the next one


# -- git ------------------------------------------------------------------------------------------------

def test_git_starts_with_a_first_commit_and_secrets_left_out(tmp_path):
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "plan.md").write_text("# plan\n", encoding="utf-8")
    (folder / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    did = projects.start_git(folder)
    assert "started git here" in did and "first commit" in did
    assert projects.has_git(folder)
    tracked = _git(folder, "ls-files").splitlines()
    assert "plan.md" in tracked and ".gitignore" in tracked and ".env" not in tracked
    assert projects.start_git(folder) == ""                                        # had git: nothing to do


def test_a_first_commit_too_large_is_refused_and_leaves_nothing_behind(tmp_path):
    folder = tmp_path / "media"
    (folder / "clips").mkdir(parents=True)
    (folder / "clips" / "a.mov").write_bytes(b"x" * 2048)
    with pytest.raises(projects.ProjectError) as e:
        projects.start_git(folder, max_mb=0)
    assert "clips" in str(e.value) and "over 0 MB" in str(e.value)
    assert not (folder / ".git").exists() and not (folder / ".gitignore").exists()
    assert (folder / "clips" / "a.mov").exists()                                   # the files stay as they were


# -- the window -------------------------------------------------------------------------------------------

def test_a_new_orkspace_works_where_it_is_told(fake_repo, isolated_layout_file, home):
    host = Host(fake_repo, auto_commit=False)
    try:
        new = host.command("orkspace.new", {"name": "Shop", "project": "new"})
        ork = host.town.scroll.orkspace(new)
        project = host.town.scroll.project(ork.project)
        assert project is not None and project.managed
        assert Path(project.path) == (home / "Orkcraft" / "projects" / "shop").resolve()
        assert projects.has_git(Path(project.path))
        same = host.command("orkspace.new", {"name": "Shop QA"})                    # "": where the open one works
        assert host.town.scroll.orkspace(same).project == project.id
        plain = host.command("orkspace.new", {"name": "Notes", "project": "town"})
        assert host.town.scroll.orkspace(plain).project is None
        picked = host.command("orkspace.new", {"name": "Shop docs", "project": project.id})
        assert host.town.scroll.orkspace(picked).project == project.id
        snap = host.snapshot()
        assert snap["projects"][0]["id"] == project.id and snap["projects"][0]["used"] == 3
        assert next(o for o in snap["orkspaces"] if o["id"] == new)["project"] == project.id
    finally:
        host.close()


def test_a_folder_with_no_git_asks_first(fake_repo, isolated_layout_file, tmp_path, home):
    host = Host(fake_repo, auto_commit=False)
    try:
        oid = host.town.scroll.active_orkspace_id
        folder = tmp_path / "notes"
        folder.mkdir()
        assert host.command("project.link", {"orkspace": oid, "path": str(folder)}) == {"state": "ask_git", "path": str(folder.resolve())}
        assert host.town.scroll.orkspace(oid).project is None                        # nothing done before the answer
        r = host.command("project.link", {"orkspace": oid, "path": str(folder), "git": False})
        assert r["state"] == "linked" and r["git"] is False and not projects.has_git(folder)
        r = host.command("project.link", {"orkspace": oid, "path": str(folder), "git": True})
        assert r["git"] is True and "started git here" in r["did"]
        assert len(host.town.scroll.projects) == 1                                  # the same folder, the same project
        with pytest.raises(CommandError, match="home folder"):
            host.command("project.link", {"orkspace": oid, "path": str(home)})
        host.command("project.use", {"orkspace": oid, "project": ""})
        assert host.town.scroll.orkspace(oid).project is None
    finally:
        host.close()


def test_the_agent_pool_works_in_its_orkspaces_project_unless_it_has_a_folder_of_its_own(fake_repo, tmp_path,
                                                                                          isolated_layout_file):
    host = Host(fake_repo, False, fake_repo / ".orkcraft.json")
    try:
        bid = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
        w = host.town.worker(bid)
        assert w.code_root == fake_repo
        shop = _repo(tmp_path / "shop")
        ork = host.town.scroll.orkspace_of(bid)
        projects.link(host.town.scroll, ork.id, projects.add(host.town.scroll, "Shop", shop).id)
        assert w.code_root == shop.resolve() and w.repo_root == fake_repo
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        host.command("act", {"id": bid, "act": "repo", "args": {"path": str(elsewhere)}})
        assert w.code_root == elsewhere.resolve()                                   # its own folder wins
    finally:
        host.close()
