"""The Task Fields board: cards in lanes, kept in plain files — tasks and sticky notes on one board.

A **lane** is a column of cards. The three status lanes — To Do, In Progress, Done — hold **tasks**:
moving one between them is a change of status (`tasks.status_changed`). Every other lane (Ideas,
Notes, Questions…) holds **notes**, stickers with no status. A card is a task or a note by the lane
it is in: a note moved into a status lane becomes a task, a task moved out becomes a note.
One more lane is the person's own: **My to-dos** (`mine`) holds what the person has to do, a checklist —
its cards are ticked off (`- [x]`) rather than moved, and they are neither tasks for the orks nor notes.

`path` (default `TASKS.md`) is either

    a Markdown file   one `##` section per lane: `## To Do` / `## In Progress` / `## Done` and any
                      other heading (`## Ideas`); a card is a `- [ ] title` (or `- title`) line, its
                      text the indented lines under it; what comes before the first `##` is kept;
                      `## My to-dos` (or `For me`, `Mine`…) is the person's checklist
    a folder          `todo/`, `in-progress/`, `done/` and any other subfolder (`ideas/`) holding one
                      `.md` file per card (a project's `tasks/` folder works as it is: moving a task
                      moves its file and updates its `status:` line; the text after the title is the
                      card's text); `mine/` is the person's checklist, a ticked card's front matter
                      says `done: true`

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
MINE = "mine"                                            # the person's own to-dos: a checklist
MINE_LABEL = "My to-dos"
TASK, NOTE = "task", "note"                              # a card's kind; the person's to-do is MINE
_MINE_HEADS = ("my to dos", "my todos", "my to do", "to dos", "todos", "for me", "mine", "my chores", "chores",
               "personal", "my checklist", "checklist")
_HEAD = re.compile(r"^##\s+(.+?)\s*$")
_ITEM = re.compile(r"^[-*]\s+(?:\[( |x|X)\]\s+)?(.+?)\s*$")
_BODY = re.compile(r"^(?: {2,}|\t)(.*)$")
_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
_STATUS = re.compile(r"^status:\s*.*$", re.M)
_COLOR = re.compile("^(" + "|".join(c for c in COLORS if c) + r")\s*")
_DONE = re.compile(r"^done:[ \t]*(.*?)[ \t]*$", re.M)


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


def is_mine(heading: str) -> bool:
    """A heading that names the person's own checklist (`## My to-dos`, `## For me`)."""
    return heading.lower().replace("-", " ").strip() in _MINE_HEADS


def lane_of(heading: str) -> str:
    """The lane id a `##` heading stands for."""
    return column_of(heading) or (MINE if is_mine(heading) else slug(heading))


def slug(title: str) -> str:
    s = re.sub(r"[^\w]+", "-", title.lower(), flags=re.U).strip("-")
    return s[:48] or "task"


TITLE_WORDS = 4               # a card is written as one text; its title is a few words of it


def short_title(text: str) -> str:
    """The title a text names itself without a model: the whole text when it is one short line, else its
    first few words (no trailing punctuation)."""
    line = next((ln.strip(" #*-") for ln in text.splitlines() if ln.strip(" #*-")), "")
    title = " ".join(line.split()[:TITLE_WORDS]).rstrip(".,:;!?—-")[:60]
    return title[:1].upper() + title[1:]


def needs_title(text: str) -> bool:
    """More than a short line: its title is worth asking a light model for."""
    words = text.split()
    return len(words) > TITLE_WORDS or len([ln for ln in text.splitlines() if ln.strip()]) > 1


def title_prompt(text: str) -> str:
    return ("Name this task or note in 2 to 4 words, in the language it is written in. "
            "Answer with the title only: no quotes, no full stop.\n\n" + text[:4000])


def parse_title(answer: str) -> str:
    """The model's title: its first line, quotes and a full stop aside, at most a few words; "" when it said none."""
    line = next((ln for ln in answer.splitlines() if ln.strip()), "")
    line = line.strip().strip("\"'`*«»“”").rstrip(".")
    return " ".join(line.split()[:TITLE_WORDS + 1])[:60]


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
    """`task` in a status lane, `mine` in the person's checklist, else `note`."""
    return TASK if lane in COLUMNS else MINE if lane == MINE else NOTE


@dataclass
class Task:
    """A card. `column` is its lane's id: a status (`todo`…) for a task, `mine` for the person's to-do,
    else a notes lane. `checked`: a to-do of the person's that is done (ticked off)."""
    id: str
    title: str
    column: str
    body: str = ""
    checked: bool = False

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
        """The status lanes first, the person's to-dos when the board has them, then the lanes of notes
        in the order the file keeps them."""
        found = self._read()[0]
        mine = [ln for ln in found if ln.kind == MINE][:1]
        notes = [ln for ln in found if ln.kind == NOTE]
        return [Lane(c, LABELS[c]) for c in COLUMNS] + mine + notes

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
                lid = lane_of(m.group(1))
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
                last = Task(tid, title, lane.id, checked=lane.id == MINE and (m.group(1) or " ") in "xX")
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
            if d.name == MINE:
                out.append((Lane(MINE, MINE_LABEL), d))
            elif d.name not in status and not d.name.startswith((".", "_")):
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
                done = _DONE.search(_front(text))
                cards.append(Task(f.stem, m.group(1) if m else f.stem, lane.id, _folder_body(text),
                                  checked=lane.id == MINE and bool(done) and done.group(1).lower() in ("true", "yes", "x")))
        return lanes, cards

    # -- writing ------------------------------------------------------------------------------------

    def _write_file(self, head: list[str], lanes: list[Lane], cards: list[Task]) -> None:
        out = list(head) or ["# Tasks", ""]
        if out and out[-1].strip():
            out.append("")
        order = [ln for ln in lanes if ln.kind == TASK] + [ln for ln in lanes if ln.kind == MINE][:1] \
            + [ln for ln in lanes if ln.kind == NOTE]
        for c in COLUMNS:                                    # the status lanes are always there
            if not any(ln.id == c for ln in order):
                order.insert(COLUMNS.index(c), Lane(c, LABELS[c]))
        for lane in order:
            out.append(f"## {lane.label}")
            for t in cards:
                if t.column != lane.id:
                    continue
                if lane.kind == MINE:
                    box = "[x] " if t.checked else "[ ] "
                else:
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
        if column_of(name) or is_mine(name) or not re.search(r"[^\W_]", name) or not lid:
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
        lane = lane if lane in COLUMNS or lane == MINE else (slug(lane) if lane else NOTES)
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
            lanes.append(_new_lane(lane))
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
            end = text.find("\n---", 3) if text.startswith("---") else -1
            if end > 0 and _DONE.search(text[:end]):           # a to-do starts unticked wherever it goes
                text = _DONE.sub("done: false", text[:end], count=1) + text[end:]
            dst.write_text(text, encoding="utf-8")
            src.unlink()
        else:
            head, lanes, cards = self._read_file()
            if not any(ln.id == column for ln in lanes) and column not in COLUMNS:
                lanes.append(_new_lane(column))
            moved = next(t for t in cards if t.id == task_id)
            cards.remove(moved)
            moved.column, moved.checked = column, False
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

    def check(self, task_id: str, done: bool | None = None) -> Task:
        """Tick one of the person's to-dos off, or back on (`done` None: the other way round from how it is)."""
        card = self._find(task_id)
        if card.column != MINE:
            raise ValueError("only a to-do of yours is ticked off")
        done = (not card.checked) if done is None else bool(done)
        if self.is_folder:
            f = self._card_file(card)
            text = f.read_text(encoding="utf-8")
            line = f"done: {'true' if done else 'false'}"
            front = _front(text)
            if front:
                head = _DONE.sub(line, front, count=1) if _DONE.search(front) else f"{front}\n{line}"
                text = head + text[len(front):]
            else:
                text = f"---\n{line}\n---\n\n{text.lstrip()}"
            f.write_text(text, encoding="utf-8")
        else:
            head, lanes, cards = self._read_file()
            for t in cards:
                if t.id == task_id:
                    t.checked = done
            self._write_file(head, lanes, cards)
        return Task(card.id, card.title, card.column, card.body, done)

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


def _new_lane(lane: str) -> Lane:
    return Lane(MINE, MINE_LABEL) if lane == MINE else Lane(lane, lane.replace("-", " ").capitalize())


def _front(text: str) -> str:
    """A card file's front matter up to its closing `---` ("" when it has none)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[:end]
    return ""


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
    A task added or moved between statuses → tasks.*; a note added → notes.created; the person's own
    to-dos send nothing (they are no work for the orks until one is moved into a status lane)."""
    if before is None:
        return []
    old = {t.id: t for t in before}
    out = []
    for t in after:
        prev = old.get(t.id)
        if t.kind == MINE:
            continue
        if t.kind == NOTE:
            if prev is None:
                out.append(("notes.created", t, t.column))
            continue
        if prev is None or prev.kind != TASK:
            out.append(("tasks.created", t, LABELS[t.column]))
        elif prev.column != t.column:
            out.append(("tasks.status_changed", t, f"{LABELS[prev.column]} → {LABELS[t.column]}"))
    return out
