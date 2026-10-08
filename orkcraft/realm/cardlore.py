"""What a Task Fields board knows of its cards beyond the board file: which are personal, the wiki pages that
are a card's context (📜), a to-do's plan (🧭) and what the night round found for it (🌙). It lives in the building's state folder
(`.orkcraft/fields/<id>/cards.json`), never in `TASKS.md`: the file stays the person's to edit by hand.

    lore = cardlore.Lore(state_dir)
    lore.set_context("call-the-bank", [Page("llm-wiki/general/pages/bank.md", "Bank", 1700000000.0)])
    lore.keep_plan("call-the-bank", ["Find the card number", "Call before 12"], "haiku")
    lore.rename("call-the-bank", "call-the-bank-today")     # a card's id follows its title
    lore.set_news("call-the-bank", {"commits": [["ab12", "Bank card form"]], "words": "…"})   # 🌙 the night round

What went to a model is logged as a fact, never as its text (`sent.jsonl`): when, which card, how many
characters, which model and pages, what was taken out first.

Pure module, no face.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

FILE, SENT, TRUST = "cards.json", "sent.jsonl", "plan_ok"
PAGE_CHARS = 2500                 # of each page a plan gets
TODO_CHARS = 4000
STEPS = 7


@dataclass(frozen=True)
class Page:
    path: str                     # repo-relative
    title: str
    mtime: float = 0.0            # when it was looked up: a page changed since makes the context stale


class Lore:
    def __init__(self, state_dir: Path) -> None:
        self.dir = state_dir
        self._data: dict | None = None

    # -- the file -------------------------------------------------------------------------------

    @property
    def data(self) -> dict:
        if self._data is None:
            try:
                got = json.loads((self.dir / FILE).read_text(encoding="utf-8"))
                self._data = got if isinstance(got, dict) else {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def _save(self) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / FILE).write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def of(self, card_id: str) -> dict:
        got = self.data.get(card_id)
        return got if isinstance(got, dict) else {}

    def _put(self, card_id: str, **fields) -> None:
        entry = {**self.of(card_id), **fields}
        entry = {k: v for k, v in entry.items() if v is not None and v != [] and v != ""}
        if entry:
            self.data[card_id] = entry
        else:
            self.data.pop(card_id, None)
        self._save()

    def rename(self, old: str, new: str) -> None:
        """A card's id follows its title: what is kept of it, and the cards that name it (joined to it), follow."""
        if old == new:
            return
        moved = old in self.data
        if moved:
            self.data[new] = self.data.pop(old)
        for entry in self.data.values():
            for key in ("into", "hint"):
                if isinstance(entry, dict) and entry.get(key) == old:
                    entry[key] = new
                    moved = True
        if moved:
            self._save()

    def drop(self, card_id: str) -> None:
        if self.data.pop(card_id, None) is not None:
            self._save()

    def keep_only(self, ids: set[str]) -> None:
        """Forget the cards gone from the board (a hand edit of the file removed them)."""
        gone = [k for k in self.data if k not in ids]
        for k in gone:
            del self.data[k]
        if gone:
            self._save()

    # -- personal -------------------------------------------------------------------------------

    def private(self, card_id: str) -> bool | None:
        """True or False when the person said so for this card, None when they did not."""
        v = self.of(card_id).get("private")
        return v if isinstance(v, bool) else None

    def set_private(self, card_id: str, private: bool) -> None:
        entry = {**self.of(card_id), "private": bool(private)}
        self.data[card_id] = entry
        self._save()

    # -- context --------------------------------------------------------------------------------

    def context(self, card_id: str) -> list[Page]:
        out = []
        for p in self.of(card_id).get("context") or []:
            if isinstance(p, dict) and p.get("path"):
                out.append(Page(str(p["path"]), str(p.get("title") or p["path"]), float(p.get("mtime") or 0)))
        return out

    def set_context(self, card_id: str, pages: list[Page]) -> None:
        self._put(card_id, context=[asdict(p) for p in pages], context_at=time.time() if pages else None)

    def stale(self, card_id: str, repo_root: Path) -> bool:
        """A page of the card's context changed or went since it was looked up."""
        for p in self.context(card_id):
            try:
                if (repo_root / p.path).stat().st_mtime > p.mtime + 1e-6:
                    return True
            except OSError:
                return True
        return False

    # -- plan -----------------------------------------------------------------------------------

    def plan(self, card_id: str) -> list[str]:
        return [str(s) for s in self.of(card_id).get("plan") or [] if str(s).strip()]

    def keep_plan(self, card_id: str, steps: list[str], model: str) -> None:
        self._put(card_id, plan=steps, plan_model=model, plan_at=time.time())

    # -- the night round (realm/nightround.py): 🌙 what is new for a card, and the ideas it gave ---------

    def news(self, card_id: str) -> dict:
        """What the night round found for the card: `at`, `commits` [[sha, subject]], `pages` [[path, title]],
        `words` (a model's, "" without); {} when there is nothing new or it was seen."""
        got = self.of(card_id).get("news")
        return got if isinstance(got, dict) else {}

    def set_news(self, card_id: str, news: dict | None) -> None:
        self._put(card_id, news=news or None)

    def idea(self, card_id: str) -> str:
        """The night round's key for a card it added as an idea ("" for any other card): it follows a rename."""
        return str(self.of(card_id).get("idea") or "")

    def set_idea(self, card_id: str, key: str) -> None:
        self._put(card_id, idea=key or None)

    def ideas(self) -> dict[str, str]:
        """Every card the night round added as an idea: idea key → card id."""
        return {str(v["idea"]): k for k, v in self.data.items() if isinstance(v, dict) and v.get("idea")}

    # -- settling: a task waits before it goes, related ones go together (realm/settle.py) -------------

    def _num(self, card_id: str, key: str) -> float | None:
        v = self.of(card_id).get(key)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def hold(self, card_id: str) -> float | None:
        """When the held task goes (epoch seconds); None when it is not held."""
        return self._num(card_id, "hold")

    def came(self, card_id: str) -> float | None:
        """When the held task was first held."""
        return self._num(card_id, "came")

    def set_hold(self, card_id: str, at: float | None, came: float | None = None) -> None:
        """Hold the task till `at` (None: not held any more; its Not urgent goes with it)."""
        if at is None:
            self._put(card_id, hold=None, came=None, later=None)
        else:
            self._put(card_id, hold=at, came=came if came is not None else (self.came(card_id) or at))

    def later(self, card_id: str) -> bool:
        return self.of(card_id).get("later") is True

    def set_later(self, card_id: str, later: bool) -> None:
        self._put(card_id, later=True if later else None)

    def into(self, card_id: str) -> str:
        """The task this card is joined to ("" when it is its own)."""
        return str(self.of(card_id).get("into") or "")

    def set_into(self, card_id: str, first: str) -> None:
        self._put(card_id, into=first or None)

    def joined(self, first: str) -> list[str]:
        """The cards joined to `first`."""
        return [k for k, v in self.data.items() if isinstance(v, dict) and v.get("into") == first]

    def hint(self, card_id: str) -> str:
        """A held task it looks like (near, not close): the card asks whether to join it."""
        return str(self.of(card_id).get("hint") or "")

    def set_hint(self, card_id: str, other: str) -> None:
        self._put(card_id, hint=other or None)

    def sent(self, card_id: str) -> bool:
        """The task went down the roads (by itself, Send now, or as a part of the task it is joined to)."""
        return self.of(card_id).get("sent") is not None

    def set_sent(self, card_id: str) -> None:
        self._put(card_id, sent=time.time(), hold=None, came=None, later=None, hint=None)

    # -- what left the machine ------------------------------------------------------------------

    def log_sent(self, card_id: str, chars: int, model: str, pages: list[str], found: dict[str, int]) -> None:
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "card": card_id, "chars": chars, "model": model,
                "pages": pages, "taken_out": found}
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with (self.dir / SENT).open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            pass

    @property
    def plan_ok(self) -> bool:
        """The person said once that a plan may go without showing what leaves (Don't ask again)."""
        return (self.dir / TRUST).exists()

    def trust_plans(self) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / TRUST).write_text("1", encoding="utf-8")
        except OSError:
            pass


def plan_prompt(todo: str, pages: list[tuple[str, str]]) -> str:
    """A light model's ask for a to-do's plan: the to-do, then the wiki pages that are its context."""
    out = ["Make a short plan for this to-do of a person's own: 3 to "
           f"{STEPS} concrete steps, in the order they are done, each one line, in the language the to-do is "
           "written in. Use the project notes below only where they help. Marks like [email-1] or [phone-1] "
           "stand for what was taken out: keep them as they are. Answer with the numbered steps only.",
           "", "## The to-do", todo[:TODO_CHARS]]
    for title, text in pages:
        out += ["", f"## Project note: {title}", text[:PAGE_CHARS]]
    return "\n".join(out)


_STEP = re.compile(r"^\s*(?:\d+[.)]|[-*•]|\[ \])\s+(.+?)\s*$")


def parse_plan(answer: str) -> list[str]:
    """The model's steps: its numbered or bulleted lines (else its non-empty lines), at most `STEPS`."""
    lines = [ln for ln in (answer or "").splitlines() if ln.strip()]
    steps = [m.group(1) for m in map(_STEP.match, lines) if m]
    if not steps:
        steps = [ln.strip() for ln in lines if not ln.lstrip().startswith("#")]
    return [" ".join(s.strip("*_ ").split())[:200] for s in steps if s.strip("*_ ")][:STEPS]
