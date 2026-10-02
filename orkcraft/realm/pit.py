"""🕳️ The Pit: intake without dialogs.

Whatever lands here — a file dragged onto the terminal, a pasted path, a link, a block of text,
the clipboard — the Scavenger sorts by kind and keeps a raw copy in `.orkcraft/pit/`:

    file   inside the project: noted by its path; outside: copied into the pit (≤ MAX_COPY)
    link   http(s) URLs, one item each
    text   anything else, kept as a Markdown note

Each item is one line of `pit.jsonl` and one cart down the road (`drop.file`, `pit.link`,
`pit.text`). Files carry a kind guessed from the name: image, log, doc, code, data, archive.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from orkcraft.realm import shelves

PIT_DIR = Path(".orkcraft") / "pit"
MAX_COPY = 20 * 1024 * 1024
KEEP = 200
URL = re.compile(r"https?://[^\s<>\"']+")
KINDS = {
    "image": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic", ".bmp"),
    "log": (".log", ".out", ".err", ".trace"),
    "doc": (".md", ".markdown", ".txt", ".pdf", ".rst", ".docx", ".html"),
    "code": (".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".sh", ".c", ".cpp", ".h"),
    "data": (".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".xml", ".sql"),
    "archive": (".zip", ".tar", ".gz", ".tgz", ".7z", ".har"),
}
ICON = {"image": "🖼", "log": "📜", "doc": "📄", "code": "⌨", "data": "🗃", "archive": "🗜", "file": "📎",
        "link": "🔗", "text": "✎"}
EVENT = {"link": "pit.link", "text": "pit.text"}


@dataclass
class Item:
    at: str
    kind: str              # image | log | doc | code | data | archive | file | link | text
    value: str             # repo-relative path (files, text notes) or the URL
    title: str
    copied: bool = False   # a file from outside the project, copied into the pit

    @property
    def event(self) -> str:
        return EVENT.get(self.kind, "drop.file")

    @property
    def is_file(self) -> bool:
        return self.event == "drop.file"


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    return next((k for k, exts in KINDS.items() if ext in exts), "file")


def _stamp(now: dt.datetime) -> str:
    return now.strftime("%Y%m%d-%H%M%S")


def _free(path: Path) -> Path:
    n, out = 2, path
    while out.exists():
        out, n = path.with_name(f"{path.stem}-{n}{path.suffix}"), n + 1
    return out


def sort(repo_root: Path, text: str, now: dt.datetime | None = None) -> list[Item]:
    """What a paste or a drop brought, sorted and kept. Writes the pit; returns the items."""
    now = now or dt.datetime.now()
    at, folder = now.isoformat(timespec="seconds"), repo_root / PIT_DIR
    items: list[Item] = []
    paths = shelves.dropped_paths(text)
    if paths:
        for p in paths:
            rel = shelves.rel_to(repo_root, p)
            if rel != str(p):                                   # inside the project: point at it
                items.append(Item(at, kind_of(p), rel, p.name))
                continue
            if p.stat().st_size > MAX_COPY:
                items.append(Item(at, kind_of(p), str(p), p.name))
                continue
            folder.mkdir(parents=True, exist_ok=True)
            dst = _free(folder / f"{_stamp(now)}-{p.name}")
            shutil.copy2(p, dst)
            items.append(Item(at, kind_of(p), shelves.rel_to(repo_root, dst), p.name, copied=True))
        return items
    stripped = text.strip()
    if not stripped:
        return []
    urls = URL.findall(stripped)
    if urls and not URL.sub("", stripped).strip(" \n\t,;"):  # only links: one item each
        return [Item(at, "link", u.rstrip(".,);"), u.rstrip(".,);")[:80]) for u in urls]
    folder.mkdir(parents=True, exist_ok=True)
    note = _free(folder / f"{_stamp(now)}-note.md")
    note.write_text(stripped + "\n", encoding="utf-8")
    first = stripped.splitlines()[0][:60]
    return [Item(at, "text", shelves.rel_to(repo_root, note), first)]


def log(repo_root: Path, items: list[Item]) -> None:
    path = repo_root / PIT_DIR / "pit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def history(repo_root: Path, limit: int = KEEP) -> list[Item]:
    try:
        lines = (repo_root / PIT_DIR / "pit.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(Item(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out


def clipboard(runner=subprocess.run) -> str:
    """The system clipboard as text (pbpaste, wl-paste, xclip, xsel), '' when none can be read."""
    cmds = [["pbpaste"]] if sys.platform == "darwin" else \
        [["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]
    for cmd in cmds:
        if runner is subprocess.run and shutil.which(cmd[0]) is None:
            continue
        try:
            out = runner(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0:
            return out.stdout
    return ""
