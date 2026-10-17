"""The keeper's reading of a goal (spec 34 §1): a goal saved is sent to the keeper at once, on the warrior tier,
read-only — its Summary, how each metric is counted, 0–3 questions. Split from `idea_keeper.py` (the module's size).

    keeper.read_goal(slug)             # in the background; the goal is `reading`, then `asks` or `ready`
    keeper.read_goal(slug, "answer")   # the person answers its questions: the talk of an idea's, on a goal

A mixin of `IdeaKeeper`; `self` has its `call`, `wiki_root`, `state_dir`, `_start`, `_busy`, `_may_run`, `publish`.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from orkcraft.realm import ideas

GOAL_TIER = "warrior"
LINK_CHARS, LINKS_READ = 6000, 6
INDEX_CHARS, REPLY_CHARS, MAX_QUESTIONS = 6000, 4000, 3


def _kw():
    from orkcraft.core import idea_keeper
    return idea_keeper


class GoalMixin:
    def _linked(self, root: Path, links: list[str]) -> str:
        """The goal's linked documents: a path in the repository or a page of the Wiki is read (cut), a URL is only
        named — never fetched."""
        out = []
        for link in links[:LINKS_READ]:
            if re.match(r"^[a-z][a-z0-9+.-]*://", link, re.I):
                out.append(f"- {link} (a web link: not fetched)")
                continue
            body = ""
            for base in (self.repo_root, root):
                path = (Path(base) / link.split("#")[0].lstrip("/")).resolve()
                if path.is_file() and Path(base).resolve() in path.parents:
                    try:
                        body = path.read_text(encoding="utf-8")[:LINK_CHARS]
                    except (OSError, UnicodeDecodeError):
                        body = ""
                    break
            out.append(f"- {link}:\n{body}" if body else f"- {link} (not found in the repository or the Wiki)")
        return "\n".join(out) or "(no links)"

    def goal_prompt(self, root: Path, slug: str, said: str = "") -> str:
        g = next(t for t in ideas.tracks(root) if t["slug"] == slug)
        try:
            index = (root / "index.md").read_text(encoding="utf-8")[:INDEX_CHARS]
        except OSError:
            index = "(no index yet)"
        metrics = "\n".join(f"- {m['name']} → target {m['target'] or 'not set'}" for m in g["metrics"]) or "(none)"
        talk = "\n".join(f"{t['who']}: {t['text']}" for t in ideas.talk(self.state_dir, slug, 6, goal=True))
        return f"""You are the keeper of this project's Task board. A person saved a goal; read it and make it clear. You
may read the repository (read only). Web links are named, never fetched.

The project's Wiki, its map (index.md):
{index}

The goal: {g['title']} (priority {g['priority']}{', deadline ' + g['deadline'] if g['deadline'] else ''})
{g['about'][:3000]}

Its metrics:
{metrics}

Its linked documents:
{self._linked(root, g['links'])}
""" + (f"\nThe talk so far:\n{talk}\n" if talk else "") + (f"\nThe person says:\n{said}\n" if said else "") + """
Answer with one JSON object and nothing else:
{"summary": "what the goal means for this repository, 3 to 5 lines",
 "metrics": [{"name": "the metric's name as listed", "how": "how it is counted, and where"}],
 "questions": ["zero to three questions the person must answer to make the goal clear"],
 "reply": "one short line to the person (only when they said something)"}
"""

    def read_goal(self, slug: str, said: str = "") -> None:
        """Send a goal to the keeper at once (warrior, read-only), or its answer to the person's words."""
        if not any(t["slug"] == slug for t in ideas.tracks(self.wiki_root())):
            raise _kw().KeeperError("That goal is gone")
        said = str(said or "").strip()[:ideas.SECTION_CHARS]
        if why := self._may_run():
            ideas.save_goal_state(self.state_dir, slug, state="raw", error=why)
            raise _kw().KeeperError(why)
        key = f"goal:{slug}"
        if said:
            ideas.add_turn(self.state_dir, slug, "you", said, goal=True)
        if self.busy(key):                         # saved again while it reads: it reads once more after this
            self._again.add(key)
            return
        ideas.save_goal_state(self.state_dir, slug, state="reading", error="")
        self._start(slug, "goal", lambda: self._goal_loop(slug, said), key)

    def _goal_loop(self, slug: str, said: str) -> None:
        key = f"goal:{slug}"
        self.read_goal_one(slug, said)
        while key in self._again:
            self._again.discard(key)
            self.read_goal_one(slug, "")

    def read_goal_one(self, slug: str, said: str = "") -> None:
        root = self.wiki_root()
        ideas.save_goal_state(self.state_dir, slug, state="reading", error="")
        self.publish(f"goal:{slug}")
        try:
            self._tls.slug = f"goal-{slug}"
            text, _cost, _tokens, _s = self.call(GOAL_TIER, self.goal_prompt(root, slug, said), "")
            answer = _kw().first_json(text)
            if answer is None:
                raise _kw().KeeperError("the keeper's answer was not the JSON it was asked for")
        except Exception as e:
            ideas.save_goal_state(self.state_dir, slug, state="raw", error=_kw()._why(e))
            return
        how: dict[str, str] = {}
        for i, m in enumerate(answer.get("metrics") if isinstance(answer.get("metrics"), list) else []):
            if isinstance(m, dict) and _kw()._words(m.get("how"), 300):
                how[_kw()._words(m.get("name"), 300) or str(i)] = _kw()._words(m.get("how"), 300)
        questions = _kw()._strings(answer.get("questions"), MAX_QUESTIONS)
        ideas.write_goal_reading(root, slug, _kw()._words(answer.get("summary"), 3000), how, questions)
        if said and (reply := _kw()._words(answer.get("reply"), REPLY_CHARS)):
            ideas.add_turn(self.state_dir, slug, "keeper", reply, goal=True)
        ideas.save_goal_state(self.state_dir, slug, state="asks" if questions else "ready", error="",
                              read_at=dt.datetime.now().isoformat(timespec="seconds"))
