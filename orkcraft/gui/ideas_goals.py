"""A goal by dialog (spec 34 §1, §4), as `gui/ideas.py`'s `Ideas` has it: `ideas.goal_save`, `ideas.goal`, `ideas.read_now`.

Saving a goal sends it to the keeper at once (core/idea_goals.py); a goal's state (`reading` → `asks` | `ready`) lives
beside its page (`<state_dir>/goals/<slug>/`). Split from ideas.py to keep it under ~600 lines.
"""
from __future__ import annotations

from typing import Any

from orkcraft.core import idea_keeper
from orkcraft.gui.ideas_args import IdeasError, _device, _opt, _text
from orkcraft.realm import event_log, ideas


class GoalsMixin:
    def goal_state(self, slug: str) -> dict:
        st = ideas.goal_state(self.state_dir, slug)
        if st["state"] == "reading" and not self.keeper.busy_goal(slug):
            st["state"] = "raw"                        # a reading the host lost (it closed)
        return st

    def _goal_row(self, g: dict) -> dict:
        """A goal as the board lists it: its fields, its state in the keeper's words."""
        st = self.goal_state(g["slug"])
        return {**g, "state": st["state"], "error": st["error"], "ideas": g["count"]}

    def goal(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        g = next((t for t in ideas.tracks(self.root(), make=False) if t["slug"] == slug), None)
        if g is None:
            raise IdeasError("That goal is gone")
        st = self.goal_state(slug)
        page = ideas.track_page(self.root(), slug)
        return {**self._goal_row(g), "description": g["about"],
                "sections": [{"name": n, "text": page.section(n)} for n in ideas.TRACK_SECTIONS],
                "talk": ideas.talk(self.state_dir, slug, goal=True),
                "busy": bool(self.keeper.busy_goal(slug)) or st["state"] == "reading"}

    def goal_save(self, args: dict) -> dict:
        slug = _opt(args, "slug") or None
        about = args.get("about", "")
        if not isinstance(about, str):
            raise IdeasError("about is not text")
        metrics, links = args.get("metrics") or [], args.get("links") or []
        if not isinstance(metrics, list) or not isinstance(links, list):
            raise IdeasError("Metrics and links are lists")
        got, new = ideas.save_goal(self.root(), slug, _text(args, "title", ideas.TITLE_CHARS), about[:ideas.SECTION_CHARS],
                                   metrics, _opt(args, "priority") or "normal", links, _opt(args, "deadline"))
        g = next(t for t in ideas.tracks(self.root(), make=False) if t["slug"] == got)
        self._ev(event_log.GOAL_SAVED, args, goal=got, new=new, metrics=[m["name"] for m in g["metrics"]], links=g["links"],
                 priority=g["priority"])
        self._read_goal(got)
        self.changed(f"goal:{got}")
        return {"slug": got}

    def _read_goal(self, slug: str, said: str = "") -> None:
        """The keeper reads the goal at once, in the background; a keeper that may not run (the demo, the spend limit)
        leaves it `raw` with the reason on it."""
        try:
            self.keeper.read_goal(slug, said)
        except idea_keeper.KeeperError as e:
            if said:
                raise IdeasError(str(e)) from None

    def read_now(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        try:
            self.keeper.read_now(slug)
        except idea_keeper.KeeperError as e:
            raise IdeasError(str(e)) from None
        self.changed(slug)
        return {"ok": True}

    def goal_event(self, slug: str) -> None:
        """`goal_read` when a goal's reading ends (asks, ready, or raw: it could not)."""
        import time
        st = ideas.goal_state(self.state_dir, slug)["state"]
        now = time.monotonic()
        was, since = self._seen.get(f"goal:{slug}", ("", None))
        if st == was:
            return
        self._seen[f"goal:{slug}"] = (st, now)
        if st in ("asks", "ready", "raw") and was == "reading":
            self._ev(event_log.GOAL_READ, goal=slug, state=st, seconds=round(now - since, 1) if since else None)

    def goal_needs(self, goals: list[dict]) -> list[dict[str, Any]]:
        """A goal that asks is in Needs you."""
        out = []
        for g in goals:
            if g["state"] == "asks":
                out.append({"idea": "", "goal": g["slug"], "kind": "goal", "title": g["title"],
                            "text": g["questions"][0] if g["questions"] else "The keeper asks you about this goal"})
        return out
