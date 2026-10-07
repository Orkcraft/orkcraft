"""What a Task Fields board knows of its cards beyond the board file: which are personal, the wiki pages that
are a card's context (📜) and a to-do's plan (🧭). It lives in the building's state folder
(`.orkcraft/fields/<id>/cards.json`), never in `TASKS.md`: the file stays the person's to edit by hand.

    lore = cardlore.Lore(state_dir)
    lore.set_context("call-the-bank", [Page("llm-wiki/general/pages/bank.md", "Bank", 1700000000.0)])
    lore.keep_plan("call-the-bank", ["Find the card number", "Call before 12"], "haiku")
    lore.rename("call-the-bank", "call-the-bank-today")     # a card's id follows its title

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
        if old != new and old in self.data:
            self.data[new] = self.data.pop(old)
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
