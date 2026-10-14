"""Mission 1 in the town (docs/design/first-mission.md §3): each quest raises its building on a plot lit for it, lays
its road, and is done when its goal holds — looked at on every tick, so it notices what the person did anywhere.

    m = Mission(town)
    m.begin()        # quest 1 now (the onboarding's "Raise the camp yourself")
    m.raise_it()     # the quest's one press: its building on its plot, its road, its drill
    m.tick()         # True when the mission moved on (a quest done)
    m.leave()        # skipped: the quest under way counted as skipped, the town stays as it stands
    m.view()         # what the quest log draws, None when no mission is under way

Quests 1 to 3½ call no model: the Agent pool runs the drill by a script while its `drill.json` is there
(core/workers/barracks.py DRILL), and the drill is called a drill on its card and in the Warchief's words.
Before quest 4 the hooks are asked for once (`hooks`), showing what is written where. Quest 4 reads only (realm/
mission_work.py: GitHub with the person's `gh`, else the TODO and FIXME lines) and calls no model; quest 5 is real
work, its price said before the press, on branches, the Security reviewer on, nothing merged without the person.
Each quest's start, end and skip go to the local event log (realm/event_log.py). No face here.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from typing import Any

from orkcraft import settings
from orkcraft.core import buildings, roads
from orkcraft.hooks import install as hooks_install
from orkcraft.realm import builders, event_log, harnesses, mission, mission_work, quickadd

PLOTS = {"board": [0.0, 0.0], "pool": [0.333, 0.0], "gate": [0.667, 0.0], "listen": [1.0, 0.0]}   # each quest's
LABELS = {"board": "1", "pool": "2", "gate": "3", "office": "3½", "listen": "4", "two": "5"}     # building's plot


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


class Mission:
    def __init__(self, town) -> None:
        self.town = town
        self.root = town.repo_root

    # -- where it stands ------------------------------------------------------------------------------

    @property
    def state(self) -> dict:
        return mission.load(self.root)

    def on(self) -> bool:
        s = self.state
        return bool(s.get("on")) and s.get("quest") in mission.IDS and not self.town.demo

    def _save(self, s: dict) -> None:
        mission.save(self.root, s)

    def _record(self, event: str, **fields: Any) -> None:
        if not self.town.demo:
            event_log.record(self.root, event, **fields)

    def _start(self, s: dict, quest_id: str) -> None:
        s["quest"] = quest_id
        s.setdefault("started", {})[quest_id] = _now().isoformat(timespec="seconds")
        self._record(event_log.QUEST_STARTED, quest=quest_id)

    # -- what the person does -------------------------------------------------------------------------

    def begin(self) -> dict:
        """The mission from quest 1 (again from the start, if it was left)."""
        s = {"on": True, "done": [], "skipped": [], "built": {}}
        self._start(s, mission.IDS[0])
        self._save(s)
        return s

    def leave(self) -> None:
        """Skipped: the quest under way counts as skipped; what was raised stays, the drill's script goes."""
        s = self.state
        if not s.get("on"):
            return
        q = s.get("quest", "")
        s["on"], s["quest"] = False, ""
        s.setdefault("skipped", []).append(q)
        self._save(s)
        self._record(event_log.QUEST_SKIPPED, quest=q)
        self._end_drill(s, keep=True)
        self._save(s)

    def raise_it(self) -> str:
        """The quest's one press: its building on the plot lit for it (and its road, its drill). The building's id,
        "" when the quest raises nothing or raised it already."""
        s = self.state
        q = mission.quest(s.get("quest", "")) if s.get("on") else None
        if q is not None and q.id == "two":
            return self._send_two(s)
        if q is None or not q.raises or (s.get("built") or {}).get(q.id) or self._asks_hooks(s, q.id):
            return ""
        spec = buildings.type_spec(self.town, q.raises)
        if spec is None:
            return ""
        spec["config"] = {**(spec.get("config") or {}), **self._config(q.id)}
        b = buildings.raise_spec(self.town, spec, PLOTS.get(q.id), folded=False)
        if b is None:
            return ""
        s.setdefault("built", {})[q.id] = b.id
        self._save(s)
        getattr(self, f"_after_{q.id}")(s, b.id)
        return b.id

    @staticmethod
    def _config(quest_id: str) -> dict:
        if quest_id == "board":
            return {"send_new": True}
        if quest_id == "pool":                  # the drill needs no branch and no plan; one ork is enough
            return {"worktrees": False, "plan": False, "max_orcs": 1}
        if quest_id == "gate":                  # the first gate: every cart waits for the person
            return {"review": "always"}
        return {}

    # -- the hooks, asked once before quest 4 (open-questions.md Q16) ---------------------------------

    def _agy(self) -> bool | None:
        return None if getattr(self.town.machine, "agy_warder_checked", False) else False

    def _asks_hooks(self, s: dict, quest_id: str) -> bool:
        """Quest 4 waits on the answer; quest 5 needs the Security reviewer on."""
        if quest_id not in ("listen", "two") or hooks_install.installed(self.root):
            return False
        return quest_id == "two" or s.get("hooks") not in ("yes", "no")

    def hooks(self, yes: bool) -> list[str]:
        """The person's answer: the hooks written into the project's settings (the files written), or not now."""
        s = self.state
        paths = []
        if yes:
            paths = [str(p.relative_to(self.root)) if p.is_relative_to(self.root) else str(p)
                     for p in hooks_install.install_all(self.root, agy=self._agy())]
        s["hooks"] = "yes" if yes else "no"
        self._save(s)
        return paths

    def _hooks_view(self) -> dict:
        return {"says": mission.HOOKS_SAYS, "files": hooks_install.preview(self.root, agy=self._agy()),
                "take_back": hooks_install.TAKE_BACK, "fail_open": hooks_install.FAIL_OPEN}

    # -- quest 4: what waits outside, read only -------------------------------------------------------

    def _after_listen(self, s: dict, tower: str) -> None:
        board = (s.get("built") or {}).get("board", "")
        if board and self.town.scroll.building(board) is not None:
            self.town.worker(board).save_config({"send_new": None})      # cards wait on the board until sent
            roads.lay(self.town, board, tower, "watch.github", None, quiet=True)
        host, repo = quickadd.origin(self.root)
        if host == "github.com" and repo:
            self.town.worker(tower).save_config({"github": repo})
        s["looking"] = True
        self._save(s)
        threading.Thread(target=self._look, args=(board,), daemon=True, name="mission-look").start()

    def _look(self, board: str) -> None:
        try:
            source, items = mission_work.found(self.root)
        except Exception:                                   # a look that fails leaves the board as it is
            source, items = "", []
        self.town.call(self._found, board, source, items)

    def _found(self, board: str, source: str, items: list) -> None:
        s = self.state
        w = self.town.worker(board) if board and self.town.scroll.building(board) is not None else None
        cards = []
        for it in items if w is not None else []:
            card = w.add(it.title, "todo", it.body, seen=False)
            if card is not None:
                cards.append(card.id)
        s.pop("looking", None)
        s["listen"] = {"source": source, "cards": cards}
        self._save(s)

    # -- quest 5: two at once, real work ---------------------------------------------------------------

    def _pool(self, s: dict):
        pool = (s.get("built") or {}).get("pool", "")
        return self.town.worker(pool) if pool and self.town.scroll.building(pool) is not None else None

    def _two_cards(self, s: dict) -> list[str]:
        board = (s.get("built") or {}).get("board", "")
        w = self.town.worker(board) if board and self.town.scroll.building(board) is not None else None
        if w is None:
            return []
        return [c.id for c in w.cards if c.column == "todo" and c.id != s.get("card")][:2]

    def two_cost(self, s: dict | None = None) -> str:
        s = self.state if s is None else s
        w = self._pool(s)
        spent = w.state.spent if w is not None else 0.0
        return mission.TWO_COST.format(tool=harnesses.title(builders.main_tool(self.town.machine)),
                                       budget=spent + mission.TWO_BUDGET_USD)

    def _send_two(self, s: dict) -> str:
        """The press of quest 5: two cards from the board to the pool, on branches, under a budget."""
        board = (s.get("built") or {}).get("board", "")
        w = self._pool(s)
        cards = self._two_cards(s)
        if s.get("two") or w is None or len(cards) < 2 or self._asks_hooks(s, "two"):
            return ""
        (w.state_dir / "drill.json").unlink(missing_ok=True)
        w.save_config({"worktrees": True, "max_orcs": 2,
                       "budget_usd": round(w.state.spent + mission.TWO_BUDGET_USD, 2)})
        s["two"] = [f"{board}:{c}" for c in cards]
        s["two_seen"] = []
        self._save(s)
        b = self.town.worker(board)
        for c in cards:
            b.send(c)
        return w.building_id

    def _after_board(self, s: dict, board: str) -> None:
        card = self.town.worker(board).add(mission.DRILL_TITLE, "todo", mission.DRILL_BODY)
        if card is not None:
            s["card"] = card.id
            s["ref"] = f"{board}:{card.id}"
            self._save(s)

    def _after_pool(self, s: dict, pool: str) -> None:
        w = self.town.worker(pool)
        (w.state_dir).mkdir(parents=True, exist_ok=True)
        (w.state_dir / "drill.json").write_text(json.dumps(mission.drill_script()), encoding="utf-8")
        board = (s.get("built") or {}).get("board", "")
        if board and self.town.scroll.building(board) is not None:
            roads.lay(self.town, pool, board, "tasks.sent", None, quiet=True)
            roads.lay(self.town, board, pool, "pool.assigned", None, quiet=True, returns=True)
            roads.lay(self.town, board, pool, "pool.done", None, quiet=True, returns=True)
            if s.get("card"):
                self.town.worker(board).send(s["card"])

    def _after_gate(self, s: dict, gate: str) -> None:
        pool = (s.get("built") or {}).get("pool", "")
        if not pool or self.town.scroll.building(pool) is None:
            return
        roads.lay(self.town, gate, pool, "pool.done", None, quiet=True)
        task = self._drill_task(s)
        if task is not None and task.status == "done":       # it ended before the gate stood: sent again, now
            self.town.worker(pool).emit("pool.done", mission.DRILL_DONE, mission.DRILL_TITLE, ref=s.get("ref", ""))

    # -- the goals ------------------------------------------------------------------------------------

    def _drill_task(self, s: dict):
        pool = (s.get("built") or {}).get("pool", "")
        w = self.town.worker(pool) if pool and self.town.scroll.building(pool) is not None else None
        if w is None or not s.get("ref"):
            return None
        return next((t for t in w.state.queue + w.state.tasks if t.ref == s["ref"]), None)

    def _reached(self, s: dict, quest_id: str) -> bool:
        built = s.get("built") or {}
        if quest_id == "board":
            return bool(built.get("board")) and bool(s.get("card"))
        if quest_id == "pool":                                   # the person answered the ork's question
            task = self._drill_task(s)              # the drill's steward never answers: each answer is the person's
            return task is not None and bool(task.qa) and task.status != "asked"
        if quest_id == "gate":                                   # the drill came to the gate, then was passed
            gate = built.get("gate", "")
            w = self.town.worker(gate) if gate and self.town.scroll.building(gate) is not None else None
            if w is None:
                return False
            held = w.queue.by_ref(s.get("ref", "")) is not None
            if held:
                s["held"] = True
            return bool(s.get("held")) and not held
        if quest_id == "office":                                  # Office seen, then Camp again
            look = settings.look_now(self.town.machine)
            if look == "office":
                s["office_seen"] = True
            return bool(s.get("office_seen")) and look != "office"
        if quest_id == "listen":                                  # what it found is on the board
            return "listen" in s
        if quest_id == "two":                                     # both results came to the gate
            gate = built.get("gate", "")
            w = self.town.worker(gate) if gate and self.town.scroll.building(gate) is not None else None
            if w is None or not s.get("two"):
                return False
            seen = set(s.get("two_seen") or [])
            seen |= {ref for ref in s["two"] if w.queue.by_ref(ref) is not None}
            s["two_seen"] = sorted(seen)
            if len(seen) < len(s["two"]):
                return False
            pool = self._pool(s)
            if pool is not None:
                pool.save_config({"budget_usd": None})           # the mission's budget ends with it
            return True
        return False

    def tick(self) -> bool:
        """The quest under way is done when its goal holds: the next one starts (or the mission ends)."""
        self._tidy(self.state)
        if not self.on():
            return False
        s = self.state
        before = dict(s)
        q = s["quest"]
        if not self._reached(s, q):
            if s != before:
                self._save(s)
            return False
        started = s.get("started", {}).get(q)
        try:
            seconds = round((_now() - dt.datetime.fromisoformat(started)).total_seconds(), 1) if started else None
        except ValueError:
            seconds = None
        s.setdefault("done", []).append(q)
        self._record(event_log.QUEST_DONE, quest=q, seconds=seconds)
        nxt = mission.after(q)
        if q == "pool" or not nxt:
            self._end_drill(s, keep=q == "pool")
        if nxt:
            self._start(s, nxt)
        else:
            s["on"], s["quest"] = False, ""
            s["finished"] = True
        self._save(s)
        return True

    def _end_drill(self, s: dict, keep: bool = False) -> None:
        """The pool runs real work again once its drill was answered (`keep`: the drill's own run may still end
        on the script it read)."""
        pool = (s.get("built") or {}).get("pool", "")
        w = self.town.worker(pool) if pool and self.town.scroll.building(pool) is not None else None
        if w is None:
            return
        task = self._drill_task(s)
        if keep and task is not None and task.status != "done":
            s["drill_left"] = True                    # taken away once the drill's run is over (`view`'s tick)
            return
        (w.state_dir / "drill.json").unlink(missing_ok=True)

    def _tidy(self, s: dict) -> None:
        if s.get("drill_left"):
            task = self._drill_task(s)
            if task is None or task.status in ("done", "failed"):
                s.pop("drill_left")
                self._end_drill(s)
                self._save(s)

    def view(self) -> dict | None:
        s = self.state
        self._tidy(s)
        if not self.on():
            return {"finished": True, "says": mission.DONE_SAYS} if s.get("finished") and not s.get("seen_end") else None
        q = mission.quest(s["quest"])
        built = (s.get("built") or {}).get(q.id, "")
        out = {"quest": q.id, "n": LABELS.get(q.id, ""), "of": LABELS[mission.IDS[-1]], "says": q.says,
               "goal": q.goal, "cost": q.cost, "press": "" if built else q.press, "built": built,
               "done": list(s.get("done") or []), "hooks": None, "needs": ""}
        if self._asks_hooks(s, q.id):
            out["hooks"], out["press"] = self._hooks_view(), ""
        if q.id == "listen" and s.get("looking"):
            out["needs"] = "Looking at what waits for you…"
        if q.id == "two":
            out["cost"] = self.two_cost(s)
            if s.get("two"):
                out["press"] = ""
                out["needs"] = f"At the Review gate: {len(s.get('two_seen') or [])} of {len(s['two'])}"
            elif len(self._two_cards(s)) < 2:
                out["press"], out["needs"] = "", "Write two cards on the Task board first, or skip the mission"
        return out

    def seen_end(self) -> None:
        s = self.state
        s["seen_end"] = True
        self._save(s)
