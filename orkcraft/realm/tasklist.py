"""The Tasks building's list: three columns kept in plain files.

`path` (default `TASKS.md`) is either

    a Markdown file   `## To Do` / `## In Progress` / `## Done` sections of `- [ ] task` lines
    a folder          with `todo/`, `in-progress/` and `done/` holding one `.md` file per task
                      (a project's `tasks/` folder works as it is: moving a task moves its file and
                      updates its `status:` line)

A task's id is its file name in a folder, a slug of its title in a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ("todo", "in_progress", "done")
LABELS = {"todo": "To Do", "in_progress": "In Progress", "done": "Done"}
FOLDERS = {"todo": "todo", "in_progress": "in-progress", "done": "done"}
_HEAD = re.compile(r"^#{2,3}\s+(.+?)\s*$")
_ITEM = re.compile(r"^\s*[-*]\s+(?:\[( |x|X)\]\s+)?(.+?)\s*$")
_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
_STATUS = re.compile(r"^status:\s*.*$", re.M)


def column_of(heading: str) -> str | None:
    h = heading.lower().replace("-", " ").strip()
    if h in ("to do", "todo", "backlog", "next"):
        return "todo"
    if h in ("in progress", "doing", "wip", "in work"):
        return "in_progress"
    if h in ("done", "finished", "completed"):
        return "done"
    return None


def slug(title: str) -> str:
    s = re.sub(r"[^\w]+", "-", title.lower(), flags=re.U).strip("-")
    return s[:48] or "task"


@dataclass
class Task:
    id: str
    title: str
    column: str


class TaskList:
    def __init__(self, repo_root: Path, path: str = "") -> None:
        self.repo = repo_root
        rel = (path or "TASKS.md").strip()
        self.path = (repo_root / rel).resolve()
        if repo_root.resolve() not in self.path.parents and self.path != repo_root.resolve():
            raise ValueError(f"{rel} is outside the repository")

    @property
    def is_folder(self) -> bool:
        return self.path.is_dir()

    # -- reading ------------------------------------------------------------------------------------

    def load(self) -> list[Task]:
        return self._load_folder() if self.is_folder else self._load_file()

    def _load_file(self) -> list[Task]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        col, tasks, ids = None, [], set()
        for line in lines:
            m = _HEAD.match(line)
            if m:
                col = column_of(m.group(1))
                continue
            m = _ITEM.match(line)
            if m and col:
                title = m.group(2)
                tid, n = slug(title), 2
                while tid in ids:
                    tid, n = f"{slug(title)}-{n}", n + 1
                ids.add(tid)
                tasks.append(Task(tid, title, col))
        return tasks

    def _load_folder(self) -> list[Task]:
        tasks = []
        for col in COLUMNS:
            folder = self.path / FOLDERS[col]
            for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
                try:
                    text = f.read_text(encoding="utf-8")[:4000]
                except OSError:
                    continue
                m = _TITLE.search(text) or _H1.search(text)
                tasks.append(Task(f.stem, m.group(1) if m else f.stem, col))
        return tasks

    # -- writing ------------------------------------------------------------------------------------

    def _write_file(self, tasks: list[Task]) -> None:
        try:
            old = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            old = []
        head = [ln for ln in old[:3] if ln.startswith("# ")] or ["# Tasks"]
        out = head[:1] + [""]
        for col in COLUMNS:
            out.append(f"## {LABELS[col]}")
            out += [f"- [{'x' if col == 'done' else ' '}] {t.title}" for t in tasks if t.column == col]
            out.append("")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

    def add(self, title: str) -> Task:
        title = " ".join(title.split())
        if not title:
            raise ValueError("a task needs a title")
        if self.is_folder:
            folder = self.path / FOLDERS["todo"]
            folder.mkdir(parents=True, exist_ok=True)
            stem, n = slug(title), 2
            while any((self.path / FOLDERS[c] / f"{stem}.md").exists() for c in COLUMNS):
                stem, n = f"{slug(title)}-{n}", n + 1
            (folder / f"{stem}.md").write_text(f"---\ntitle: \"{title}\"\nstatus: todo\n---\n\n# {title}\n",
                                               encoding="utf-8")
            return Task(stem, title, "todo")
        tasks = self._load_file()
        tasks.append(Task(slug(title), title, "todo"))
        self._write_file(tasks)
        return next(t for t in reversed(self._load_file()) if t.title == title)

    def move(self, task_id: str, column: str) -> tuple[str, str]:
        if column not in COLUMNS:
            raise ValueError(f"no column {column!r}")
        tasks = self.load()
        task = next((t for t in tasks if t.id == task_id), None)
        if task is None:
            raise KeyError(task_id)
        before = task.column
        if before == column:
            return before, column
        if self.is_folder:
            src = self.path / FOLDERS[before] / f"{task_id}.md"
            dst = self.path / FOLDERS[column] / f"{task_id}.md"
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_text(encoding="utf-8")
            end = text.find("\n---", 3) if text.startswith("---") else -1
            if end > 0 and _STATUS.search(text[:end]):         # the frontmatter's status follows the folder
                text = _STATUS.sub(f"status: {FOLDERS[column]}", text[:end], count=1) + text[end:]
            dst.write_text(text, encoding="utf-8")
            src.unlink()
        else:
            task.column = column
            tasks.remove(task)
            tasks.append(task)
            self._write_file(tasks)
        return before, column

    def rename(self, task_id: str, title: str) -> None:
        title = " ".join(title.split())
        if not title:
            raise ValueError("a task needs a title")
        if self.is_folder:
            task = next(t for t in self._load_folder() if t.id == task_id)
            f = self.path / FOLDERS[task.column] / f"{task_id}.md"
            text = f.read_text(encoding="utf-8")
            text = _TITLE.sub(f'title: "{title}"', text, count=1) if _TITLE.search(text) else text
            text = _H1.sub(f"# {title}", text, count=1) if _H1.search(text) else text
            f.write_text(text, encoding="utf-8")
            return
        tasks = self._load_file()
        for t in tasks:
            if t.id == task_id:
                t.title = title
        self._write_file(tasks)


def changes(before: list[Task] | None, after: list[Task]) -> list[tuple[str, Task, str]]:
    """(event id, task, detail) between two loads; the first load only sets the baseline."""
    if before is None:
        return []
    old = {t.id: t for t in before}
    out = []
    for t in after:
        prev = old.get(t.id)
        if prev is None:
            out.append(("tasks.created", t, LABELS[t.column]))
        elif prev.column != t.column:
            out.append(("tasks.status_changed", t, f"{LABELS[prev.column]} → {LABELS[t.column]}"))
    return out
