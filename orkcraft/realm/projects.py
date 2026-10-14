"""Projects: the folder an orkspace works in (docs/design/projects.md).

An orkspace points to a project; many orkspaces may point to the same one; one without a project works in the
town's own folder. The Town Scroll keeps the list (`scroll.projects`, `Orkspace.project`); this module says where
an orkspace works, links a folder, refuses the folders no project should be, and starts git in one:

    root_of(scroll, "feat_oauth", town_root)     # the project's folder, else the town's
    refusal(Path("~/code/shop").expanduser())    # "" when it may be a project, else why not, in plain words
    start_git(folder)                            # git and a first commit, unless it would be too large
    link(scroll, "feat_oauth", add(scroll, "Shop", folder).id)

Every git call uses fixed arguments (no shell). Pure module: it never shows anything.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.config import default_town_root

PROJECTS_DIR = "projects"            # a new project's folder: ~/Orkcraft/projects/<name>
FIRST_COMMIT_MAX_MB = 200
GIT_TIMEOUT_S = 60


class ProjectError(Exception):
    """Why a folder cannot be a project, or why its git could not start: said to the person as it is."""


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)


def folder_of(project: ts.Project) -> Path:
    return Path(project.path).expanduser()


# -- where an orkspace works ----------------------------------------------------------------------------------

def project_of(scroll: ts.TownScroll, orkspace_id: str | None) -> ts.Project | None:
    ork = scroll.orkspace(orkspace_id) if orkspace_id else None
    return scroll.project(ork.project) if ork is not None else None


def root_of(scroll: ts.TownScroll, orkspace_id: str | None, town_root: Path) -> Path:
    """The folder the orkspace works in: its project's, while that folder is there; else the town's."""
    project = project_of(scroll, orkspace_id)
    if project is not None:
        folder = folder_of(project)
        if folder.is_dir():
            return folder
    return town_root


def root_for_building(scroll: ts.TownScroll, building_id: str, town_root: Path) -> Path:
    ork = scroll.orkspace_of(building_id)
    return root_of(scroll, ork.id if ork else None, town_root)


# -- the list in the Town Scroll ------------------------------------------------------------------------------

def add(scroll: ts.TownScroll, name: str, folder: Path, managed: bool = False) -> ts.Project:
    """The project of this folder: the one the town has already, else a new one named `name`."""
    folder = folder.expanduser().resolve()
    for p in scroll.projects:
        if folder_of(p).resolve() == folder:
            return p
    name = (name.strip() or folder.name or "project")[:60]
    base = ts._slug(name)
    ids = {p.id for p in scroll.projects}
    pid, n = base, 2
    while pid in ids:
        suffix = f"_{n}"
        pid, n = base[: 64 - len(suffix)] + suffix, n + 1
    project = ts.Project(pid, name, str(folder), managed)
    scroll.projects.append(project)
    return project


def link(scroll: ts.TownScroll, orkspace_id: str, project_id: str | None) -> None:
    """The orkspace works in this project from now on (None: the town's folder). Its worktree link is dropped
    when the project changes: a worktree belongs to the repository it was made of."""
    ork = scroll.orkspace(orkspace_id)
    if ork is None:
        raise ProjectError(f"No orkspace {orkspace_id!r}")
    if project_id is not None and scroll.project(project_id) is None:
        raise ProjectError(f"No project {project_id!r}")
    if ork.project != project_id and ork.git.mode == "worktree":
        ork.git = ts.GitLink()
    ork.project = project_id


# -- which folders may be projects -------------------------------------------------------------------------

def has_git(folder: Path) -> bool:
    """The folder is a repository of its own (a worktree's `.git` file counts)."""
    return (folder / ".git").exists()


def _toplevel(folder: Path) -> Path | None:
    try:
        out = _git(folder, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(out.stdout.strip()).resolve() if out.returncode == 0 and out.stdout.strip() else None


def refusal(folder: Path, town_home: Path | None = None) -> str:
    """"" when the folder may be a project; else why not. Never the whole disk, the home folder or a folder
    inside another repository (Orkline's own `~/Orkcraft` aside: its projects live there)."""
    folder = folder.expanduser()
    if not folder.is_dir():
        return f"There is no folder at {folder}"
    folder = folder.resolve()
    if folder.parent == folder:
        return "Not the whole disk: choose the folder of one project"
    if folder == Path.home().resolve():
        return "Not your home folder: choose the folder of one project"
    if has_git(folder):
        return ""
    top = _toplevel(folder)
    home = (town_home or default_town_root()).expanduser().resolve()
    if top is not None and top != folder and top != home:
        return f"{folder} is inside the repository {top}: choose {top} itself, or a folder outside it"
    return ""


def _keep_out_of(top: Path, folder: Path) -> None:
    """A project inside Orkline's own `~/Orkcraft` repository: that repository never takes it in (its local
    exclude, nothing committed)."""
    try:
        rel = folder.resolve().relative_to(top)
    except ValueError:
        return
    exclude = top / ".git" / "info" / "exclude"
    line = f"/{rel.as_posix()}/"
    try:
        have = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
        if line not in have:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


def new_folder(name: str, town_home: Path | None = None) -> Path:
    """A new, empty folder for a new project: `~/Orkcraft/projects/<name>` (`<name>_2`… when taken)."""
    home = (town_home or default_town_root()).expanduser()
    base = ts._slug(name)
    folder, n = home / PROJECTS_DIR / base, 2
    while folder.exists():
        folder, n = home / PROJECTS_DIR / f"{base}_{n}", n + 1
    folder.mkdir(parents=True)
    top = _toplevel(home) if home.is_dir() else None
    if top is not None:
        _keep_out_of(top, folder)
    return folder


# -- git ------------------------------------------------------------------------------------------------

def _largest(folder: Path, names: list[str], top: int = 3) -> list[tuple[str, int]]:
    sizes: dict[str, int] = {}
    for rel in names:
        first = rel.split("/", 1)[0]
        try:
            sizes[first] = sizes.get(first, 0) + (folder / rel).stat().st_size
        except OSError:
            continue
    return sorted(sizes.items(), key=lambda kv: -kv[1])[:top]


def start_git(folder: Path, max_mb: int = FIRST_COMMIT_MAX_MB) -> str:
    """Git in the folder and a first commit of its files as they are (secrets and caches left out, realm/jobs.py
    `ensure_repo`): "" when it had git already, else what was done. Refused, and nothing left behind, when the
    first commit would be over `max_mb`: the message names the largest folders, to leave out first."""
    from orkcraft.realm import jobs
    folder = folder.expanduser().resolve()
    if has_git(folder):
        return ""
    problem = refusal(folder)
    if problem:
        raise ProjectError(problem)
    ignore = folder / ".gitignore"
    wrote_ignore = not ignore.exists()
    try:
        if wrote_ignore:
            ignore.write_text(jobs.FIRST_IGNORE, encoding="utf-8")
        init = _git(folder, "init", "-q")
        if init.returncode != 0:
            raise ProjectError((init.stderr or init.stdout).strip()[:300] or "git init failed")
        listed = _git(folder, "ls-files", "--others", "--exclude-standard", "-z").stdout
        names = [n for n in listed.split("\0") if n]
        total = sum((folder / n).stat().st_size for n in names if (folder / n).is_file())
        if total > max_mb * 1024 * 1024:
            big = ", ".join(f"{n} ({s // (1024 * 1024)} MB)" for n, s in _largest(folder, names))
            raise ProjectError(f"The first commit would be {total // (1024 * 1024)} MB, over {max_mb} MB. "
                               f"Leave the largest folders out in a .gitignore first: {big}")
        jobs.ensure_repo(folder)
    except (ProjectError, RuntimeError, OSError, subprocess.SubprocessError) as e:
        shutil.rmtree(folder / ".git", ignore_errors=True)
        if wrote_ignore:
            try:
                os.remove(ignore)
            except OSError:
                pass
        if isinstance(e, ProjectError):
            raise
        raise ProjectError(str(e)) from e
    done = "started git here"
    if wrote_ignore:
        done += "; wrote a .gitignore (.env, keys, caches and .orkcraft/ left out)"
    return done + "; made a first commit of the files as they are"
