"""The window's side of projects (docs/design/projects.md §4): which folder an orkspace works in.

    project.link    {orkspace, path, git?}   link a folder; one with no git asks first ({state: "ask_git"})
    project.use     {orkspace, project}      an existing project, or "" for the town's folder
    project.pick    {start?}                 the system's folder dialog (gui/folders.py): a token
    project.picked  {token}                  what came of it

A new orkspace picks its project as it is made (`for_new`, called by `orkspace.new`). Every change is saved
and redrawn; refusals come back as the command's error, in the words of realm/projects.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from orkcraft.gui import folders
from orkcraft.realm import projects


class ProjectCommandError(Exception):
    """A refusal said to the person."""


class Projects:
    def __init__(self, host) -> None:
        self.host = host

    @property
    def scroll(self):
        return self.host.town.scroll

    def _orkspace(self, args: dict):
        ork = self.scroll.orkspace(str(args.get("orkspace", "")))
        if ork is None:
            raise ProjectCommandError(f"No orkspace {args.get('orkspace')!r}")
        return ork

    def _done(self, orkspace_id: str) -> None:
        ork = self.scroll.orkspace(orkspace_id)
        project = self.scroll.project(ork.project) if ork is not None else None
        self.host.town.save()
        self.host.town.checkpoint("orkspace", "", f"works in {project.name if project else 'the town folder'}",
                                  orkspace=orkspace_id)
        self.host.on_change()

    # -- a new orkspace -------------------------------------------------------------------------------

    def for_new(self, orkspace_id: str, choice: str, opened: str | None, name: str) -> str:
        """The project a new orkspace works in: "" the open orkspace's, "town" the town's folder, "new" a new
        project of its own (a folder and git, no question: the folder is Orkcraft's), or a project's id.
        What was done, in a sentence ("" when nothing needs saying)."""
        if choice == "town":
            return ""
        if choice == "new":
            try:
                folder = projects.new_folder(name)
                projects.start_git(folder)
            except (projects.ProjectError, OSError) as e:
                raise ProjectCommandError(str(e)) from None
            project = projects.add(self.scroll, name, folder, managed=True)
            projects.link(self.scroll, orkspace_id, project.id)
            return f"A new project in {folder}, with git"
        pid = choice or (projects.project_of(self.scroll, opened).id if projects.project_of(self.scroll, opened) else None)
        if pid is not None and self.scroll.project(pid) is not None:
            projects.link(self.scroll, orkspace_id, pid)
        return ""

    # -- commands -------------------------------------------------------------------------------------

    def _link(self, args: dict) -> dict:
        ork = self._orkspace(args)
        raw = str(args.get("path") or "").strip()[:2000]
        if not raw:
            raise ProjectCommandError("Choose a folder")
        folder = Path(raw).expanduser()
        problem = projects.refusal(folder)
        if problem:
            raise ProjectCommandError(problem)
        folder = folder.resolve()
        did = ""
        if not projects.has_git(folder):
            wants = args.get("git")
            if wants is None:
                return {"state": "ask_git", "path": str(folder)}
            if wants:
                try:
                    did = projects.start_git(folder)
                except projects.ProjectError as e:
                    raise ProjectCommandError(str(e)) from None
        project = projects.add(self.scroll, folder.name, folder, managed=bool(did))
        projects.link(self.scroll, ork.id, project.id)
        if getattr(self.host.town, "machine", None) is not None:
            folders.remember(self.host.town.machine, str(folder))
        self._done(ork.id)
        return {"state": "linked", "project": project.id, "git": projects.has_git(folder), "did": did}

    def _use(self, args: dict) -> None:
        ork = self._orkspace(args)
        pid = str(args.get("project") or "") or None
        try:
            projects.link(self.scroll, ork.id, pid)
        except projects.ProjectError as e:
            raise ProjectCommandError(str(e)) from None
        self._done(ork.id)

    def _pick(self, args: dict) -> str:
        return folders.start(str(args.get("start") or "").strip()[:2000] or str(self.host.town.repo_root))

    def _picked(self, args: dict) -> dict:
        return folders.result(str(args.get("token") or "")[:40])

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"project.link": self._link, "project.use": self._use, "project.pick": self._pick,
                "project.picked": self._picked}


def snapshot(town) -> list[dict[str, Any]]:
    """The town's projects, for the War Map and the Project dialog."""
    out = []
    for p in town.scroll.projects:
        folder = projects.folder_of(p)
        out.append({"id": p.id, "name": p.name, "path": str(folder), "there": folder.is_dir(),
                    "git": projects.has_git(folder), "used": sum(1 for o in town.scroll.orkspaces if o.project == p.id)})
    return out
