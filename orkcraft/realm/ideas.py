"""The board's tracks and ideas as Wiki pages (spec 29 §2, spec 29a §2), and each idea's state beside them.

The Wiki joined to the board holds two sections: `pages/tracks/<slug>.md` and `pages/ideas/<slug>.md`, front matter
`owner: board` (the librarian reads them and never rewrites them: realm/wiki.py). The file is the truth: a hand edit
is read as it is, and a write keeps every section and front matter key it does not know.

    tracks(root)                          # in order, General made on demand
    ideas(root, track=None)               # in order
    add_idea(root, "a dark mode")         # its slug; state raw, no model
    set_section(root, slug, "Risks", "…")
    move(root, slug, track="ux", before="other-idea")

What runs on an idea lives beside the page, never in it: `<state_dir>/ideas/<slug>/` holds `state.json` (its
state, the keeper's session), `talk.jsonl` (every turn, the archive: never read back into a model), `plan.json` and
`questions.json` (the keeper's questions as choices, and the person's answers: spec 29c §2).

No face, no model.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import threading
import unicodedata
from pathlib import Path

SECTIONS = ("Gist", "Why", "In", "Out", "Risks", "Open questions", "Estimate", "Stages", "Decisions")
TRACK_SECTIONS = ("About", "Success criteria")
STATES = ("raw", "reading", "asks", "ready", "planning", "plan", "working", "done", "failed")
SIZES = ("S", "M", "L")
SMALL = ("Gist", "In", "Out", "Stages")   # what a size S idea shows; its other sections only when written (29c §3)
GENERAL, GENERAL_TITLE = "general", "General"
TRACKS, IDEAS = "pages/tracks", "pages/ideas"
OWNER = "board"
TALK_SHOWN = 30                  # of an idea's talk, the turns a page shows
SECTION_CHARS = 20_000           # of a section, the most a write keeps
TITLE_CHARS = 120

LOCK = threading.RLock()         # every write of a page or a state file, from the host's thread or the keeper's
_FENCE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
_HEADING = re.compile(r"^(#{1,2})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
_KEY = re.compile(r"^([A-Za-z_][\w-]*):[ \t]*(.*)$")


# -- a page: front matter, a title, sections --------------------------------------------------------

class Page:
    """A Markdown page as the board reads it: front matter (`meta`, its order and its unknown lines kept), the `#`
    title, what stands before the first `##` (`head`), and the `##` sections in the order they are written."""

    def __init__(self, meta: list[tuple[str, str]] | None = None, title: str = "", head: str = "",
                 sections: list[tuple[str, str]] | None = None) -> None:
        self.meta = list(meta or [])         # (key, value); a line that is no `key: value` is kept as ("", line)
        self.title = title
        self.head = head
        self.sections = list(sections or [])

    def get(self, key: str, default: str = "") -> str:
        return next((v for k, v in self.meta if k == key), default)

    def set(self, key: str, value: object) -> None:
        value = "" if value is None else str(value)
        for i, (k, _v) in enumerate(self.meta):
            if k == key:
                self.meta[i] = (key, value)
                return
        self.meta.append((key, value))

    def section(self, name: str) -> str:
        return next((t for n, t in self.sections if n.lower() == name.lower()), "")

    def set_section(self, name: str, text: str, order: tuple[str, ...] = SECTIONS) -> None:
        text = clean_text(text)
        for i, (n, _t) in enumerate(self.sections):
            if n.lower() == name.lower():
                self.sections[i] = (n, text)
                return
        # a missing known section goes after the last known one that comes before it
        at = len(self.sections)
        if name in order:
            before = order[:order.index(name)]
            at = max((i + 1 for i, (n, _t) in enumerate(self.sections) if n in before), default=0)
        self.sections.insert(at, (name, text))

    def text(self) -> str:
        meta = "\n".join(f"{k}: {v}".rstrip() if k else v for k, v in self.meta)
        out = f"---\n{meta}\n---\n"
        if self.title:
            out += f"# {self.title}\n"
        if self.head.strip():
            out += f"\n{self.head.strip()}\n"
        for name, text in self.sections:
            out += f"\n## {name}\n" + (f"{text.strip()}\n" if text.strip() else "")
        return out


def parse(text: str) -> Page:
    """A page as written, by hand or by the board: nothing it does not know is lost."""
    text = text.replace("\r\n", "\n")
    meta: list[tuple[str, str]] = []
    m = _FENCE.match(text)
    if m:
        for line in m.group(1).split("\n"):
            km = _KEY.match(line)
            meta.append((km.group(1), km.group(2).strip()) if km else ("", line))
        text = text[m.end():]
    title, head, sections = "", [], []
    current: list[str] | None = None
    for line in text.split("\n"):
        hm = _HEADING.match(line)
        if hm and len(hm.group(1)) == 1 and not title and current is None:
            title = hm.group(2).strip()
            continue
        if hm and len(hm.group(1)) == 2:
            current = []
            sections.append((hm.group(2).strip(), current))
            continue
        (head if current is None else current).append(line)
    return Page(meta, title, "\n".join(head).strip(), [(n, "\n".join(lines).strip()) for n, lines in sections])


def clean_text(text: str) -> str:
    """A section's text as it may be written into a page: a `#` or `##` heading inside it is made a `###` one, so a
    section never splits the page (a model's answer is untrusted, a person may paste anything)."""
    text = str(text or "").replace("\r\n", "\n")[:SECTION_CHARS]
    text = re.sub(r"^#{1,2}(?=[ \t])", "###", text, flags=re.M)
    return re.sub(r"^---[ \t]*$", "- - -", text, flags=re.M).strip()


def thesis(text: str) -> str:
    """The first line of a section, without Markdown: its bold thesis."""
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^(#+|[-*+]|\d+[.)]|>)\s+", "", line)
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[*_`~]+", "", line).strip()
        if line:
            return line[:200]
    return ""


def shown(size: str, name: str, text: str) -> bool:
    """Whether the page shows a section at once (29c §3): a size S idea its four, the others only when written."""
    return size != "S" or name in SMALL or bool((text or "").strip())


def items(text: str) -> list[str]:
    """A section's list (`- x`), or its lines when it has no list."""
    lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
    marked = [re.sub(r"^([-*+]|\d+[.)])\s+", "", ln) for ln in lines if re.match(r"^([-*+]|\d+[.)])\s+", ln)]
    return marked or lines


def slugify(text: str, limit: int = 48) -> str:
    plain = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", plain)
    out = ""
    for w in words:
        if len(out) + len(w) + 1 > limit:
            break
        out = f"{out}-{w}" if out else w
    return out or "idea"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# -- files ------------------------------------------------------------------------------------------

def _read(path: Path) -> Page | None:
    try:
        return parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _ensure_root(root: Path) -> None:
    """The Wiki the board writes into, scaffolded as the Wiki does when it is not there yet."""
    if not (root / "index.md").exists():
        from orkcraft.realm import wiki
        wiki.scaffold(root, "general")
    for rel, title, what in ((TRACKS, "Tracks", "The board's tracks, in order: what each is for and its success criteria."),
                             (IDEAS, "Ideas", "The board's ideas: each a spec under discussion, kept by the board.")):
        index = root / rel / "index.md"
        if not index.exists():
            _write(index, f"# {title}\n\n{what}\n")


def _pages(folder: Path) -> list[tuple[str, Page]]:
    out = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.md")):
            if path.name in ("index.md", "CLAUDE.md") or path.name.startswith("."):
                continue
            page = _read(path)
            if page is not None:
                out.append((path.stem, page))
    return out


def _index(root: Path, rel: str, title: str, what: str, rows: list[tuple[str, str, str]]) -> None:
    lines = [f"# {title}", "", what, ""] + [f"- [{t}]({s}.md)" + (f" — {line}" if line else "") for s, t, line in rows]
    _write(root / rel / "index.md", "\n".join(lines) + "\n")


def _reindex(root: Path) -> None:
    """Each section's `index.md`, one line a page, as every Wiki section has."""
    _index(root, TRACKS, "Tracks", "The board's tracks, in order: what each is for and its success criteria.",
           [(t["slug"], t["title"], thesis(t["about"])) for t in tracks(root, make=False)])
    _index(root, IDEAS, "Ideas", "The board's ideas: each a spec under discussion, kept by the board.",
           [(i["slug"], i["title"], i["thesis"]) for i in ideas(root)])


# -- tracks -----------------------------------------------------------------------------------------

def _track(slug: str, page: Page, count: int = 0) -> dict:
    return {"slug": slug, "title": page.title or slug, "about": page.section("About"),
            "criteria": items(page.section("Success criteria")), "deadline": page.get("deadline"),
            "order": _int(page.get("order")), "count": count}


def track_page(root: Path, slug: str) -> Page | None:
    return _read(root / TRACKS / f"{slug}.md") if re.fullmatch(r"[a-z0-9-]+", slug or "") else None


def tracks(root: Path, make: bool = True) -> list[dict]:
    """The tracks in order, each with its count of ideas; General is written the first time a track is needed."""
    if make and not (root / TRACKS / f"{GENERAL}.md").exists() and not _pages(root / TRACKS):
        add_track(root, GENERAL_TITLE)
    counts: dict[str, int] = {}
    for _slug, page in _pages(root / IDEAS):
        t = page.get("track") or GENERAL
        counts[t] = counts.get(t, 0) + 1
    out = [_track(s, p, counts.get(s, 0)) for s, p in _pages(root / TRACKS)]
    return sorted(out, key=lambda t: (t["order"], t["slug"]))


def add_track(root: Path, title: str) -> str:
    title = " ".join(str(title or "").split())[:TITLE_CHARS]
    if not title:
        raise ValueError("A track needs a title")
    with LOCK:
        _ensure_root(root)
        slug = GENERAL if title == GENERAL_TITLE and not (root / TRACKS / f"{GENERAL}.md").exists() else _free(
            root / TRACKS, slugify(title))
        order = max((_int(p.get("order")) for _s, p in _pages(root / TRACKS)), default=0) + 1
        page = Page([("owner", OWNER), ("kind", "track"), ("order", str(order))], title, "",
                    [("About", ""), ("Success criteria", "")])
        _write(root / TRACKS / f"{slug}.md", page.text())
        _reindex(root)
    return slug


def set_track(root: Path, slug: str, about: str | None = None, criteria: list | None = None,
              deadline: str | None = None) -> None:
    with LOCK:
        page = track_page(root, slug)
        if page is None:
            raise ValueError(f"No track {slug!r}")
        if about is not None:
            page.set_section("About", about, TRACK_SECTIONS)
        if criteria is not None:
            lines = [" ".join(str(c).split())[:300] for c in criteria if str(c).strip()][:20]
            page.set_section("Success criteria", "\n".join(f"- {c}" for c in lines), TRACK_SECTIONS)
        if deadline is not None:
            deadline = str(deadline).strip()
            if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
                raise ValueError("A deadline is a date: YYYY-MM-DD")
            page.set("deadline", deadline)
        _write(root / TRACKS / f"{slug}.md", page.text())
        _reindex(root)


def _free(folder: Path, slug: str, taken: set[str] = frozenset()) -> str:
    out, n = slug, 2
    while (folder / f"{out}.md").exists() or out in taken or out == "index":
        out, n = f"{slug}-{n}", n + 1
    return out


# -- ideas ------------------------------------------------------------------------------------------

def idea_page(root: Path, slug: str) -> Page | None:
    return _read(root / IDEAS / f"{slug}.md") if re.fullmatch(r"[a-z0-9-]+", slug or "") else None


def _idea(slug: str, page: Page) -> dict:
    return {"slug": slug, "title": page.title or slug, "track": page.get("track") or GENERAL,
            "order": _int(page.get("order")), "size": page.get("size") if page.get("size") in SIZES else "",
            "thesis": thesis(page.section("Gist"))}


def ideas(root: Path, track: str | None = None) -> list[dict]:
    """The ideas in order (a track's, or every track's by the tracks' order)."""
    out = [_idea(s, p) for s, p in _pages(root / IDEAS)]
    if track is not None:
        return sorted((i for i in out if i["track"] == track), key=lambda i: (i["order"], i["slug"]))
    place = {t["slug"]: n for n, t in enumerate(tracks(root, make=False))}
    return sorted(out, key=lambda i: (place.get(i["track"], len(place)), i["order"], i["slug"]))


def add_idea(root: Path, text: str, track: str = GENERAL, state_dir: Path | None = None) -> str:
    """A dropped idea: its text under Gist, the rest empty, last in its track. No model."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("An idea needs a few words")
    with LOCK:
        known = {t["slug"] for t in tracks(root)}
        track = track if track in known else GENERAL
        if track not in known:
            add_track(root, GENERAL_TITLE)
        first = thesis(text) or text.split("\n")[0]
        title = first if len(first) <= 80 else first[:77].rsplit(" ", 1)[0] + "…"
        taken = {p.name for p in (state_dir / "ideas").iterdir()} if state_dir and (state_dir / "ideas").is_dir() else set()
        slug = _free(root / IDEAS, slugify(" ".join(first.split()[:8])), taken)
        order = max((i["order"] for i in ideas(root, track)), default=0) + 1
        page = Page([("owner", OWNER), ("kind", "idea"), ("track", track), ("order", str(order)), ("size", "")],
                    title, "", [(name, text if name == "Gist" else "") for name in SECTIONS])
        page.set_section("Gist", text)
        _write(root / IDEAS / f"{slug}.md", page.text())
        _reindex(root)
    if state_dir is not None:
        save_state(state_dir, slug, state="raw")
    return slug


def set_section(root: Path, slug: str, name: str, text: str) -> None:
    if name not in SECTIONS:
        raise ValueError(f"An idea has no section {name!r}")
    with LOCK:
        page = idea_page(root, slug)
        if page is None:
            raise ValueError(f"No idea {slug!r}")
        page.set_section(name, text)
        _write(root / IDEAS / f"{slug}.md", page.text())
        if name == "Gist":
            _reindex(root)


def set_meta(root: Path, slug: str, **values: object) -> None:
    """Front matter of an idea (its size, a track the keeper proposes); only these keys."""
    with LOCK:
        page = idea_page(root, slug)
        if page is None:
            raise ValueError(f"No idea {slug!r}")
        for k, v in values.items():
            page.set(k, v)
        _write(root / IDEAS / f"{slug}.md", page.text())


def update(root: Path, slug: str, sections: dict[str, str], decisions: list[str] = ()) -> list[str]:
    """Several sections at once (the keeper's turn) and lines appended to Decisions: the sections written."""
    with LOCK:
        page = idea_page(root, slug)
        if page is None:
            raise ValueError(f"No idea {slug!r}")
        done = []
        for name, text in sections.items():
            if name in SECTIONS and name != "Decisions":
                page.set_section(name, text)
                done.append(name)
        lines = [" ".join(str(d).split())[:500] for d in decisions if str(d).strip()]
        if lines:
            day = dt.date.today().isoformat()
            old, new = page.section("Decisions"), "\n".join(f"- {day}: {d}" for d in lines)
            page.set_section("Decisions", f"{old}\n{new}" if old else new)
            done.append("Decisions")
        _write(root / IDEAS / f"{slug}.md", page.text())
        if "Gist" in done:
            _reindex(root)
    return done


def move(root: Path, slug: str, track: str | None = None, before: str | None = None) -> None:
    """An idea to another track and/or before another idea (else last); `order` renumbered only where needed."""
    with LOCK:
        page = idea_page(root, slug)
        if page is None:
            raise ValueError(f"No idea {slug!r}")
        to = track or page.get("track") or GENERAL
        if to not in {t["slug"] for t in tracks(root)}:
            raise ValueError(f"No track {to!r}")
        rest = [i["slug"] for i in ideas(root, to) if i["slug"] != slug]
        at = rest.index(before) if before in rest else len(rest)
        order = rest[:at] + [slug] + rest[at:]
        for n, s in enumerate(order, start=1):
            p = page if s == slug else idea_page(root, s)
            if p is None:
                continue
            changed = _int(p.get("order")) != n or (s == slug and p.get("track") != to)
            if s == slug:
                p.set("track", to)
            if changed:
                p.set("order", n)
                _write(root / IDEAS / f"{s}.md", p.text())
        _reindex(root)


def drop(root: Path, slug: str, state_dir: Path | None = None) -> None:
    """The page and its state go (git keeps what was committed)."""
    with LOCK:
        path = root / IDEAS / f"{slug}.md"
        if idea_page(root, slug) is None:
            raise ValueError(f"No idea {slug!r}")
        path.unlink(missing_ok=True)
        if state_dir is not None and re.fullmatch(r"[a-z0-9-]+", slug):
            shutil.rmtree(state_dir / "ideas" / slug, ignore_errors=True)
        _reindex(root)


# -- what runs on an idea: <state_dir>/ideas/<slug>/ ------------------------------------------------

STATE_DEFAULT = {"state": "raw", "session": "", "session_at": "", "context": 0, "batch_at": "", "error": ""}


def state_folder(state_dir: Path, slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", slug or ""):
        raise ValueError(f"No idea {slug!r}")
    return state_dir / "ideas" / slug


def _json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict) -> None:
    _write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def state(state_dir: Path, slug: str) -> dict:
    data = _json(state_folder(state_dir, slug) / "state.json") or {}
    out = {**STATE_DEFAULT, **{k: v for k, v in data.items() if k in STATE_DEFAULT}}
    if out["state"] not in STATES:
        out["state"] = "raw"
    return out


def save_state(state_dir: Path, slug: str, **changes: object) -> dict:
    """Only the keys given change; the rest of the file (the runner's keys too) is kept."""
    with LOCK:
        path = state_folder(state_dir, slug) / "state.json"
        data = {**STATE_DEFAULT, **(_json(path) or {}), **changes}
        _write_json(path, data)
    return data


def add_turn(state_dir: Path, slug: str, who: str, text: str, section: str = "") -> dict:
    turn = {"who": who, "text": str(text)[:SECTION_CHARS], "section": section, "at": _now()}
    with LOCK:
        path = state_folder(state_dir, slug) / "talk.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn, ensure_ascii=False) + "\n")
    return turn


def talk(state_dir: Path, slug: str, last: int = TALK_SHOWN) -> list[dict]:
    """The last turns, to show only: the archive is never read back into a model."""
    try:
        lines = (state_folder(state_dir, slug) / "talk.jsonl").read_text(encoding="utf-8").splitlines()[-last:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append({k: str(row.get(k, "")) for k in ("who", "text", "section", "at")})
    return out


def plan(state_dir: Path, slug: str) -> dict | None:
    return _json(state_folder(state_dir, slug) / "plan.json")


def save_plan(state_dir: Path, slug: str, data: dict) -> None:
    """The keeper's plan; never once it was passed (from then on the runner owns the file)."""
    with LOCK:
        old = plan(state_dir, slug)
        if old and old.get("passed_at"):
            raise ValueError("This plan is passed: the runner keeps it now")
        _write_json(state_folder(state_dir, slug) / "plan.json", data)


def edit_plan(state_dir: Path, slug: str, change) -> dict:
    """Read, change (`change(plan)` in place) and write plan.json under the lock: passing it, a to-do ticked."""
    with LOCK:
        data = plan(state_dir, slug)
        if data is None:
            raise ValueError("This idea has no plan yet")
        change(data)
        _write_json(state_folder(state_dir, slug) / "plan.json", data)
    return data


def questions(state_dir: Path, slug: str) -> list[dict]:
    """The keeper's open questions as choices: `[{"id", "text", "options", "recommended", "why", "answer"}]`."""
    try:
        data = json.loads((state_folder(state_dir, slug) / "questions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for q in data if isinstance(data, list) else []:
        if not isinstance(q, dict) or not isinstance(q.get("text"), str) or not isinstance(q.get("id"), str):
            continue
        options = [o for o in q.get("options") or [] if isinstance(o, str)] if isinstance(q.get("options"), list) else []
        rec = q.get("recommended")
        out.append({"id": q["id"], "text": q["text"], "options": options,
                    "recommended": rec if isinstance(rec, int) and not isinstance(rec, bool)
                    and 0 <= rec < len(options) else None,
                    "why": str(q.get("why") or ""),
                    "answer": q["answer"] if isinstance(q.get("answer"), str) else None})
    return out


def save_questions(state_dir: Path, slug: str, asked: list[dict]) -> list[dict]:
    """The questions anew (ids q1…, no answers yet): from the keeper's parsed answer, or [] to clear them."""
    rows = [{"id": f"q{n}", "text": q["text"], "options": list(q.get("options") or []),
             "recommended": q.get("recommended"), "why": q.get("why") or "", "answer": None}
            for n, q in enumerate(asked, start=1)]
    with LOCK:
        _write(state_folder(state_dir, slug) / "questions.json", json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    return rows


def answer(state_dir: Path, slug: str, qid: str, choice: object = None, text: object = None) -> list[dict]:
    """The person's answer to one question: one of its options (`choice`, an index) or their own words (`text`).
    The questions as they are now."""
    with LOCK:
        asked = questions(state_dir, slug)
        q = next((q for q in asked if q["id"] == qid), None)
        if q is None:
            raise ValueError("That question is gone")
        if isinstance(choice, int) and not isinstance(choice, bool):
            if not 0 <= choice < len(q["options"]):
                raise ValueError("Pick one of its answers")
            q["answer"] = q["options"][choice]
        elif isinstance(text, str) and text.strip():
            q["answer"] = " ".join(text.split())[:500]
        else:
            raise ValueError("An answer needs a choice or a few words")
        _write(state_folder(state_dir, slug) / "questions.json", json.dumps(asked, indent=2, ensure_ascii=False) + "\n")
    return asked


def touched_at(root: Path, state_dir: Path, slug: str) -> str:
    """When the idea last changed: its page or its state, whichever is newer."""
    paths = [root / IDEAS / f"{slug}.md"]
    folder = state_dir / "ideas" / slug
    paths += [folder / n for n in ("state.json", "talk.jsonl", "plan.json", "questions.json")]
    times = [p.stat().st_mtime for p in paths if p.exists()]
    return dt.datetime.fromtimestamp(max(times)).isoformat(timespec="seconds") if times else ""

