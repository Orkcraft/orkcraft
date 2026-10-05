"""The Task Fields board: cards in lanes, kept in plain files — tasks and sticky notes on one board.

A **lane** is a column of cards. The three status lanes — To Do, In Progress, Done — hold **tasks**:
moving one between them is a change of status (`tasks.status_changed`). Every other lane (Ideas,
Notes, Questions…) holds **notes**, stickers with no status. A card is a task or a note by the lane
it is in: a note moved into a status lane becomes a task, a task moved out becomes a note.

`path` (default `TASKS.md`) is either

    a Markdown file   one `##` section per lane: `## To Do` / `## In Progress` / `## Done` and any
                      other heading (`## Ideas`); a card is a `- [ ] title` (or `- title`) line, its
                      text the indented lines under it; what comes before the first `##` is kept
    a folder          `todo/`, `in-progress/`, `done/` and any other subfolder (`ideas/`) holding one
                      `.md` file per card (a project's `tasks/` folder works as it is: moving a task
                      moves its file and updates its `status:` line; the text after the title is the
                      card's text)

A card's colour is the coloured square its title starts with (🟨 🟩 🟦 🟥 🟪): it reads the same in
the file, on GitHub and on the board. A card's id is its file name in a folder, a slug of its title
(the colour aside) in a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ("todo", "in_progress", "done")               # the status lanes, in order
LABELS = {"todo": "To Do", "in_progress": "In Progress", "done": "Done"}
FOLDERS = {"todo": "todo", "in_progress": "in-progress", "done": "done"}
COLORS = ("", "🟨", "🟩", "🟦", "🟥", "🟪")
NOTES = "notes"                                          # the lane a task goes to when it becomes a note
TASK, NOTE = "task", "note"
_HEAD = re.compile(r"^##\s+(.+?)\s*$")
_ITEM = re.compile(r"^[-*]\s+(?:\[( |x|X)\]\s+)?(.+?)\s*$")
_BODY = re.compile(r"^(?: {2,}|\t)(.*)$")
_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
_STATUS = re.compile(r"^status:\s*.*$", re.M)
_COLOR = re.compile("^(" + "|".join(c for c in COLORS if c) + r")\s*")


def column_of(heading: str) -> str | None:
    """The status lane a heading names; None — a lane of notes."""
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


def color_of(title: str) -> str:
    m = _COLOR.match(title)
    return m.group(1) if m else ""


def plain(title: str) -> str:
    """The title without its colour."""
    return _COLOR.sub("", title, count=1)


def next_color(title: str) -> str:
    """The title with the next colour (none → 🟨 → … → 🟪 → none)."""
    c = COLORS[(COLORS.index(color_of(title)) + 1) % len(COLORS)]
    return f"{c} {plain(title)}" if c else plain(title)


def kind_of(lane: str) -> str:
    return TASK if lane in COLUMNS else NOTE


@dataclass
class Task:
    """A card. `column` is its lane's id: a status (`todo`…) for a task, else a notes lane."""
    id: str
    title: str
    column: str
    body: str = ""

    @property
    def kind(self) -> str:
        return kind_of(self.column)

    @property
    def color(self) -> str:
        return color_of(self.title)


Card = Task


@dataclass
class Lane:
    id: str
    label: str

    @property
    def kind(self) -> str:
        return kind_of(self.id)


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
        """Every card, tasks and notes, lane by lane."""
        return self._read()[1]

    def tasks(self) -> list[Task]:
        return [t for t in self.load() if t.kind == TASK]

    def lanes(self) -> list[Lane]:
        """The status lanes first, then the lanes of notes in the order the file keeps them."""
        found = self._read()[0]
        notes = [ln for ln in found if ln.kind == NOTE]
        return [Lane(c, LABELS[c]) for c in COLUMNS] + notes

    def _read(self) -> tuple[list[Lane], list[Task]]:
        return self._read_folder() if self.is_folder else self._read_file()[1:]

    def _read_file(self) -> tuple[list[str], list[Lane], list[Task]]:
        """(the lines before the first lane, the lanes in file order, the cards)."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return [], [], []
        head: list[str] = []
        lanes: list[Lane] = []
        lane: Lane | None = None
        cards: list[Task] = []
        ids: set[str] = set()
        last: Task | None = None
        for line in lines:
            m = _HEAD.match(line)
            if m:
                lid = column_of(m.group(1)) or slug(m.group(1))
                lane = next((ln for ln in lanes if ln.id == lid), None)
                if lane is None:
                    lane = Lane(lid, LABELS.get(lid, m.group(1)))
                    lanes.append(lane)
                last = None
                continue
            if lane is None:
                head.append(line)
                continue
            m = _ITEM.match(line)
            if m:
                title = m.group(2)
                base = slug(plain(title))
                tid, n = base, 2
                while tid in ids:
                    tid, n = f"{base}-{n}", n + 1
                ids.add(tid)
                last = Task(tid, title, lane.id)
                cards.append(last)
                continue
            b = _BODY.match(line)
            if b and last is not None:
                last.body = f"{last.body}\n{b.group(1)}" if last.body else b.group(1)
            elif line.strip():
                last = None                         # free text between cards ends the card above
        return head, lanes, cards

    def _folder_lanes(self) -> list[tuple[Lane, Path]]:
        out = [(Lane(c, LABELS[c]), self.path / FOLDERS[c]) for c in COLUMNS]
        status = set(FOLDERS.values())
        for d in sorted(p for p in self.path.iterdir() if p.is_dir()) if self.path.is_dir() else []:
            if d.name not in status and not d.name.startswith((".", "_")):
                out.append((Lane(d.name, d.name.replace("-", " ").replace("_", " ").capitalize()), d))
        return out

    def _read_folder(self) -> tuple[list[Lane], list[Task]]:
        lanes, cards = [], []
        for lane, folder in self._folder_lanes():
            lanes.append(lane)
            for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
                try:
                    text = f.read_text(encoding="utf-8")[:8000]
                except OSError:
                    continue
                m = _TITLE.search(text) or _H1.search(text)
                cards.append(Task(f.stem, m.group(1) if m else f.stem, lane.id, _folder_body(text)))
        return lanes, cards

    # -- writing ------------------------------------------------------------------------------------

    def _write_file(self, head: list[str], lanes: list[Lane], cards: list[Task]) -> None:
        out = list(head) or ["# Tasks", ""]
        if out and out[-1].strip():
            out.append("")
        order = [ln for ln in lanes if ln.kind == TASK] + [ln for ln in lanes if ln.kind == NOTE]
        for c in COLUMNS:                                    # the status lanes are always there
            if not any(ln.id == c for ln in order):
                order.insert(COLUMNS.index(c), Lane(c, LABELS[c]))
        for lane in order:
            out.append(f"## {lane.label}")
            for t in cards:
                if t.column != lane.id:
                    continue
                box = ("[x] " if lane.id == "done" else "[ ] ") if lane.kind == TASK else ""
                out.append(f"- {box}{t.title}")
                out += [f"  {ln}" if ln.strip() else "" for ln in t.body.splitlines()]
            out.append("")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

    def _lane_folder(self, lane: str) -> Path:
        return self.path / FOLDERS.get(lane, lane)

    def _card_file(self, card: Task) -> Path:
        return self._lane_folder(card.column) / f"{card.id}.md"

    def _find(self, card_id: str) -> Task:
        card = next((t for t in self.load() if t.id == card_id), None)
        if card is None:
            raise KeyError(card_id)
        return card

    def add_lane(self, name: str) -> Lane:
        """A new, empty lane of notes: a `## <name>` in the file, a folder in a tasks folder. A lane
        that is there already is returned as it is; a status lane's name is refused."""
        name = " ".join(name.split())
        lid = slug(name).lstrip("_-")
        if column_of(name) or not re.search(r"[^\W_]", name) or not lid:
            raise ValueError(f"“{name}” is not a name for a lane of notes")
        if self.is_folder:
            folder = self._lane_folder(lid)
            folder.mkdir(parents=True, exist_ok=True)
            return next(ln for ln in self.lanes() if ln.id == lid)
        head, lanes, cards = self._read_file()
        have = next((ln for ln in lanes if ln.id == lid), None)
        if have is not None:
            return have
        lanes.append(Lane(lid, name))
        self._write_file(head, lanes, cards)
        return lanes[-1]

    def add(self, title: str, lane: str = "todo", body: str = "") -> Task:
        """A new card at the end of `lane` (a status for a task; any other name — a lane of notes)."""
        title = " ".join(title.split())
        if not plain(title).strip():
            raise ValueError("a card needs a title")
        lane = lane if lane in COLUMNS else (slug(lane) if lane else NOTES)
        if self.is_folder:
            folder = self._lane_folder(lane)
            folder.mkdir(parents=True, exist_ok=True)
            stem, n = slug(plain(title)), 2
            while any((d / f"{stem}.md").exists() for _, d in self._folder_lanes()):
                stem, n = f"{slug(plain(title))}-{n}", n + 1
            status = f"status: {FOLDERS[lane]}\n" if lane in COLUMNS else ""
            (folder / f"{stem}.md").write_text(f"---\ntitle: \"{title}\"\n{status}---\n\n# {title}\n"
                                               + (f"\n{body.strip()}\n" if body.strip() else ""),
                                               encoding="utf-8")
            return Task(stem, title, lane, body.strip())
        head, lanes, cards = self._read_file()
        if not any(ln.id == lane for ln in lanes) and lane not in COLUMNS:
            lanes.append(Lane(lane, lane.replace("-", " ").capitalize()))
        cards.append(Task("", title, lane, body.strip()))
        self._write_file(head, lanes, cards)
        return next(t for t in reversed(self.load()) if t.title == title and t.column == lane)

    def move(self, task_id: str, column: str) -> tuple[str, str]:
        """To another lane (its id); (from, to). A new lane of notes is made when it is not there."""
        if not column:
            raise ValueError("no lane")
        card = self._find(task_id)
        before = card.column
        if before == column:
            return before, column
        if self.is_folder:
            src, dst = self._card_file(card), self._lane_folder(column) / f"{task_id}.md"
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_text(encoding="utf-8")
            end = text.find("\n---", 3) if text.startswith("---") else -1
            if end > 0 and _STATUS.search(text[:end]):         # the frontmatter's status follows the folder
                status = FOLDERS.get(column, "note")
                text = _STATUS.sub(f"status: {status}", text[:end], count=1) + text[end:]
            dst.write_text(text, encoding="utf-8")
            src.unlink()
        else:
            head, lanes, cards = self._read_file()
            if not any(ln.id == column for ln in lanes) and column not in COLUMNS:
                lanes.append(Lane(column, column.replace("-", " ").capitalize()))
            moved = next(t for t in cards if t.id == task_id)
            cards.remove(moved)
            moved.column = column
            cards.append(moved)
            self._write_file(head, lanes, cards)
        return before, column

    def edit(self, task_id: str, title: str | None = None, body: str | None = None) -> Task:
        """A new title and / or text; what is None stays."""
        card = self._find(task_id)
        new_title = card.title if title is None else " ".join(title.split())
        if not plain(new_title).strip():
            raise ValueError("a card needs a title")
        new_body = card.body if body is None else body.strip()
        if self.is_folder:
            f = self._card_file(card)
            text = f.read_text(encoding="utf-8")
            if title is not None:
                text = _TITLE.sub(f'title: "{new_title}"', text, count=1) if _TITLE.search(text) else text
                text = _H1.sub(f"# {new_title}", text, count=1) if _H1.search(text) else text
            if body is not None:
                text = _folder_head(text) + (f"\n{new_body}\n" if new_body else "")
            f.write_text(text, encoding="utf-8")
        else:
            head, lanes, cards = self._read_file()
            for t in cards:
                if t.id == task_id:
                    t.title, t.body = new_title, new_body
            self._write_file(head, lanes, cards)
        return Task(task_id, new_title, card.column, new_body)

    def rename(self, task_id: str, title: str) -> None:
        self.edit(task_id, title=title)

    def remove(self, task_id: str) -> Task:
        card = self._find(task_id)
        if self.is_folder:
            self._card_file(card).unlink()
        else:
            head, lanes, cards = self._read_file()
            self._write_file(head, lanes, [t for t in cards if t.id != task_id])
        return card


def _folder_head(text: str) -> str:
    """A card file up to its title line (front matter and `# title`), with one newline after."""
    m = _H1.search(text)
    if m:
        return text[:m.end()].rstrip() + "\n"
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[:end + 4] + "\n"
    return ""


def _folder_body(text: str) -> str:
    return text[len(_folder_head(text)):].strip() if _folder_head(text) else text.strip()


def changes(before: list[Task] | None, after: list[Task]) -> list[tuple[str, Task, str]]:
    """(event id, card, detail) between two loads; the first load only sets the baseline.
    A task added or moved between statuses → tasks.*; a note added → notes.created."""
    if before is None:
        return []
    old = {t.id: t for t in before}
    out = []
    for t in after:
        prev = old.get(t.id)
        if t.kind == NOTE:
            if prev is None:
                out.append(("notes.created", t, t.column))
            continue
        if prev is None or prev.kind == NOTE:
            out.append(("tasks.created", t, LABELS[t.column]))
        elif prev.column != t.column:
            out.append(("tasks.status_changed", t, f"{LABELS[prev.column]} → {LABELS[t.column]}"))
    return out
