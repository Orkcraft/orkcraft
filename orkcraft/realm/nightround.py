"""🌙 The Night round (docs/design/night-round.md): once a night the boards' stewards look over the work —
the cards that lie, the code that changed — not over the town. This module is its rules and its memory;
the boards do their part (core/workers/fields_round.py) and core/retros.py runs the night.

    nightround.commits(root, since)            the project's commits since then: subject and files
    nightround.lying(cards)                    the cards that lie: To Do tasks, open to-dos
    nightround.theirs(text, commits)           the commits that share a card's words, best first
    nightround.news_prompt(…) / parse_news     a light model's words on what is new for a card, or nothing
    nightround.ideas_prompt(…) / parse_ideas   at most `IDEAS_MAX` cleanup ideas from the day's diff
    nightround.ideas_cap(root)                 how many ideas tonight: fewer when they are deleted
    nightround.work_text(root, specs)          THE WORK for the Weekly retro: what lies, how long, what came of it

Kept in `.orkcraft/round/`: `last.json` (when it last looked), `seen.json` (when a card was first seen
lying), `ideas.json` (the ideas it gave and what became of them), `nights.jsonl` (one line a night).

Pure module, no face.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import cardlore, catalog, tasklist, wiki

DIR = Path(".orkcraft") / "round"
LAST, SEEN, IDEAS, NIGHTS = "last.json", "seen.json", "ideas.json", "nights.jsonl"
LOOK_BACK = dt.timedelta(hours=24)       # the first round looks back a day
COMMITS_MAX = 200
CARDS_MAX = 8                            # cards with news a board marks a night
TOLD_MAX = 5                             # of them, the ones a model puts in words
IDEAS_MAX = 3
DIFF_CHARS = 12_000
PAGE_CHARS = 1200
NEWS_CHARS = 300
IDEA_LANE = "Ideas"
NOTHING = "NOTHING"


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    files: tuple[str, ...] = ()

    @property
    def words(self) -> str:
        """What it is matched by: its subject and its files' names (`gui/views/fields.py` → gui views fields)."""
        return " ".join([self.subject, *(re.sub(r"[/._-]+", " ", f) for f in self.files)])


@dataclass
class Night:
    """One night, as `nights.jsonl` keeps it."""
    at: str
    boards: list[str] = field(default_factory=list)
    commits: int = 0
    news: int = 0                        # cards marked 🌙
    told: int = 0                        # of them, put in words by a model
    ideas: int = 0
    calls: int = 0                       # model calls
    skipped: str = ""                    # why nothing was looked at
    errors: list[str] = field(default_factory=list)


# -- when -----------------------------------------------------------------------------------------------

def _read(root: Path, name: str, default):
    try:
        got = json.loads((Path(root) / DIR / name).read_text(encoding="utf-8"))
        return got if isinstance(got, type(default)) else default
    except (OSError, ValueError):
        return default


def _write(root: Path, name: str, data) -> None:
    path = Path(root) / DIR / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def off_by_env() -> bool:
    """`ORKCRAFT_NIGHT_ROUND=0`: never on its clock (the tests; Look now still looks)."""
    return os.environ.get("ORKCRAFT_NIGHT_ROUND", "").strip().lower() in ("0", "false", "no", "off")


def last_run(root: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(_read(root, LAST, {}).get("at") or ""))
    except ValueError:
        return None


def mark_run(root: Path, now: dt.datetime) -> None:
    _write(root, LAST, {"at": now.isoformat(timespec="seconds")})


def since(root: Path, now: dt.datetime) -> dt.datetime:
    """What tonight looks back to: the last round, else a day."""
    last = last_run(root)
    return last if last is not None and last < now else now - LOOK_BACK


# -- the code that changed ------------------------------------------------------------------------------

def _git(root: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout if out.returncode == 0 else ""


def commits(root: Path, after: dt.datetime, limit: int = COMMITS_MAX) -> list[Commit]:
    """The project's commits since `after`, newest first, merges left out: each one's subject and files."""
    text = _git(root, "log", f"--since={after.isoformat(timespec='seconds')}", "--no-merges", f"-n{limit}",
                "--format=%x1e%h%x1f%ct%x1f%s", "--name-only")
    out = []
    for chunk in text.split("\x1e"):
        head, _, rest = chunk.partition("\n")
        sha, _, tail = head.partition("\x1f")
        stamp, _, subject = tail.partition("\x1f")
        if not sha.strip() or not stamp.strip().isdigit() or int(stamp) <= int(after.timestamp()):
            continue                              # --since counts its own second: last night's last commit
        out.append(Commit(sha.strip(), subject.strip(), tuple(f for f in rest.split("\n") if f.strip())))
    return out


def diff(root: Path, found: list[Commit], limit: int = DIFF_CHARS) -> str:
    """The changes of these commits, oldest first, cut at `limit` characters (lock files left out)."""
    if not found:
        return ""
    text = _git(root, "show", "--no-color", "--format=%x1e%h %s", "--stat", "--patch", *[c.sha for c in reversed(found)],
                "--", ".", ":(exclude)*.lock", ":(exclude)*lock.json", ":(exclude)uv.lock")
    return text.replace("\x1e", "\n### ")[:limit]


# -- the cards that lie, and what is theirs -------------------------------------------------------------

def lying(cards: list[tasklist.Task]) -> list[tasklist.Task]:
    """The cards that wait for someone: tasks in To Do and the person's to-dos not ticked off."""
    return [c for c in cards if (c.kind == tasklist.TASK and c.column == "todo")
            or (c.kind == tasklist.MINE and not c.checked)]


def theirs(text: str, found: list[Commit], best: int = 3) -> list[Commit]:
    """The commits that share the card's words: at least two (one, when the card has one word that counts)."""
    want = wiki.wanted(text)
    if not want:
        return []
    need = min(2, len(want))
    scored = []
    for i, c in enumerate(found):
        hits = wiki.shared(want, c.words)
        if hits >= need:
            scored.append((-hits, i, c))
    return [c for *_, c in sorted(scored)[:best]]


def first_seen(root: Path, board: str, ids: list[str], now: dt.datetime) -> dict[str, str]:
    """When each card was first seen lying (now for a new one); the cards gone are forgotten."""
    data = _read(root, SEEN, {})
    mine = {k: v for k, v in (data.get(board) or {}).items() if k in ids}
    stamp = now.isoformat(timespec="seconds")
    for cid in ids:
        mine.setdefault(cid, stamp)
    data[board] = mine
    _write(root, SEEN, data)
    return mine


def days_lain(seen: dict[str, str], card_id: str, now: dt.datetime) -> int:
    try:
        return max(0, (now - dt.datetime.fromisoformat(seen[card_id])).days)
    except (KeyError, ValueError):
        return 0


# -- the model: what is new for a card ------------------------------------------------------------------

def news_prompt(card: str, found: list[Commit], pages: list[tuple[str, str]]) -> str:
    out = ["A person's card has lain on their board. Below is what changed in their project since it was last "
           "looked at: commits and notes that share its words. In one or two short sentences, in the language "
           "the card is written in, say what is new for this card — and whether it may be done already. "
           f"When none of it matters to the card, answer {NOTHING} and nothing else. Marks like [email-1] stand "
           "for what was taken out: keep them as they are.",
           "", "## The card", card[:cardlore.TODO_CHARS]]
    if found:
        out += ["", "## Commits"] + [f"- {c.sha} {c.subject}" + (f" ({', '.join(c.files[:4])})" if c.files else "")
                                     for c in found]
    for title, text in pages:
        out += ["", f"## Note: {title}", text[:PAGE_CHARS]]
    return "\n".join(out)


def parse_news(answer: str) -> str:
    """The model's words, "" when it said nothing matters."""
    text = " ".join((answer or "").split()).strip("*_ ")
    if not text or text.upper().strip(".!") == NOTHING or text.upper().startswith(NOTHING + " "):
        return ""
    return text[:NEWS_CHARS]


# -- the model: cleanup ideas from the day's code -------------------------------------------------------

def ideas_prompt(found: list[Commit], changes: str, cap: int, have: list[str]) -> str:
    out = [f"You look at what changed in a project's code since yesterday. Propose at most {cap} small cleanup "
           "ideas that these changes call for: dead code left behind, a duplicate, a test missing for what "
           "changed, a TODO left, a name that no longer says what a thing does. Only what the changes below "
           "show; nothing about style; none of these already on the board. Fewer is better than weak ones.",
           'Answer with ONE JSON object and nothing else: {"ideas": [{"title": "<at most 80 characters>", '
           '"why": "<one sentence>", "file": "<path>"}]} — {"ideas": []} when nothing is worth it.',
           "", "## Already on the board"] + [f"- {t}" for t in have[:40]] + ["", "## Commits"]
    out += [f"- {c.sha} {c.subject}" for c in found[:60]]
    out += ["", "## The changes", changes]
    return "\n".join(out)


def parse_ideas(data: dict | None, cap: int, have: list[str]) -> list[dict]:
    """The ideas worth a note: a title, not one the board has, at most `cap`."""
    taken = {" ".join(t.lower().split()) for t in have}
    out = []
    for item in (data or {}).get("ideas") or []:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split())[:80].strip()
        if not title or title.lower() in taken:
            continue
        taken.add(title.lower())
        why = " ".join(str(item.get("why") or "").split())[:240]
        where = str(item.get("file") or "").strip()[:160]
        out.append({"title": title, "why": why, "file": where})
        if len(out) >= cap:
            break
    return out


def idea_body(idea: dict) -> str:
    lines = [idea["why"]] if idea.get("why") else []
    if idea.get("file"):
        lines.append(f"`{idea['file']}`")
    lines.append("🌙 from the night round")
    return "\n".join(lines)


# -- what became of the ideas ---------------------------------------------------------------------------

def ideas(root: Path) -> list[dict]:
    return [i for i in _read(root, IDEAS, {}).get("ideas", []) if isinstance(i, dict)]


def keep_ideas(root: Path, board: str, keys: list[str], lane: str, now: dt.datetime) -> None:
    data = _read(root, IDEAS, {})
    got = [i for i in data.get("ideas", []) if isinstance(i, dict)]
    stamp = now.isoformat(timespec="seconds")
    got += [{"board": board, "key": k, "lane": lane, "at": stamp, "status": "open"} for k in keys]
    data["ideas"] = got[-300:]
    _write(root, IDEAS, data)


def settle_ideas(root: Path, where: dict[str, dict[str, str]], now: dt.datetime | None = None) -> None:
    """What became of the open ideas. `where`: board → {idea key → the lane its card is in now}; a key
    missing from a board that was looked at is a card that was deleted."""
    data = _read(root, IDEAS, {})
    changed = False
    stamp = (now or dt.datetime.now()).isoformat(timespec="seconds")
    for i in data.get("ideas", []):
        if not isinstance(i, dict) or i.get("status") != "open" or i.get("board") not in where:
            continue
        lane = where[i["board"]].get(i.get("key", ""))
        if lane is None:
            i["status"], i["done"] = "dropped", stamp
        elif lane != i.get("lane"):
            i["status"], i["done"] = "taken", stamp
        else:
            continue
        changed = True
    if changed:
        _write(root, IDEAS, data)


def ideas_cap(root: Path) -> int:
    """Tonight's ideas: three; one after three deleted in a row; none after six — until one is taken."""
    done = sorted((i for i in ideas(root) if i.get("status") in ("taken", "dropped")), key=lambda i: str(i.get("done")))
    streak = 0
    for i in reversed(done):
        if i.get("status") != "dropped":
            break
        streak += 1
    return 0 if streak >= 6 else 1 if streak >= 3 else IDEAS_MAX


# -- the nights ----------------------------------------------------------------------------------------

def record(root: Path, night: Night) -> None:
    path = Path(root) / DIR / NIGHTS
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(night), ensure_ascii=False) + "\n")
    except OSError:
        pass


def nights(root: Path, limit: int = 30) -> list[Night]:
    try:
        lines = (Path(root) / DIR / NIGHTS).read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(Night(**json.loads(ln)))
        except (ValueError, TypeError):
            continue
    return out


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def summary(night: Night, paused: bool = False) -> str:
    """The night in one plain line ("" when it found nothing to say)."""
    parts = []
    if night.news:
        parts.append(_n(night.news, "card has news", "cards have news"))
    if night.ideas:
        parts.append(_n(night.ideas, "cleanup idea", "cleanup ideas"))
    if paused and night.commits:
        parts.append("no ideas: the last six were deleted")
    return ", ".join(parts)


def said(night: Night | None) -> str:
    """The last night as Settings shows it."""
    if night is None:
        return "It has not looked yet."
    when = night.at[:16].replace("T", " ")
    if night.skipped:
        return f"{when}: {night.skipped}."
    words = summary(night) or "nothing new for the cards"
    return f"{when}: {words} · {_n(night.calls, 'model call', 'model calls')}."


# -- THE WORK, for the Weekly retro ---------------------------------------------------------------------

def work_text(root: Path, specs: dict[str, dict], now: dt.datetime | None = None, limit: int = 4000) -> str:
    """The boards' open cards with how long each has lain (a personal one by its first word only), and what
    the week's rounds found and what became of their ideas. "" when there are no boards."""
    now = now or dt.datetime.now()
    seen = _read(root, SEEN, {})
    lines = []
    for bid, spec in sorted(specs.items()):
        if catalog.type_of(spec).id != "fields" or spec.get("demolished"):
            continue
        cfg = spec.get("config") or {}
        try:
            cards = tasklist.TaskList(Path(root), str(cfg.get("path", ""))).load()
        except (OSError, ValueError):
            continue
        lore = cardlore.Lore(Path(root) / ".orkcraft" / "fields" / bid)
        open_ = lying(cards)
        mine = seen.get(bid) or {}
        lines.append(f"## board {bid}: {len(open_)} open, {sum(1 for c in cards if c.kind == tasklist.NOTE)} notes")
        rows = sorted(open_, key=lambda c: -days_lain(mine, c.id, now))
        for c in rows[:25]:
            private = lore.private(c.id)
            if private is None:
                private = c.kind == tasklist.MINE and bool(cfg.get("private_todos"))
            title = tasklist.plain(c.title)
            shown = (title.split()[0] + " … (personal)") if private and title.split() else title
            kind = "to-do" if c.kind == tasklist.MINE else "task"
            lines.append(f"- {kind}, {days_lain(mine, c.id, now)} days: {shown[:100]}")
    if not lines:
        return ""
    week = [n for n in nights(root, 14) if n.at >= (now - dt.timedelta(days=7)).isoformat()]
    if week:
        lines.append(f"## the night rounds this week: {len(week)} nights, {sum(n.news for n in week)} cards with news, "
                     f"{sum(n.ideas for n in week)} ideas")
    recent = [i for i in ideas(root) if str(i.get("at")) >= (now - dt.timedelta(days=30)).isoformat()]
    if recent:
        count = {s: sum(1 for i in recent if i.get("status") == s) for s in ("taken", "dropped", "open")}
        lines.append(f"## their ideas in 30 days: {count['taken']} taken, {count['dropped']} deleted, {count['open']} open")
    return "\n".join(lines)[:limit]
