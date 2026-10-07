"""🛠 The Workshop's work: its script runs on every cart (realm/workshop.py).

A cart runs the script in a thread of its own; exit 0 sends `workshop.done`, 4 `workshop.alert`,
anything else `workshop.failed`; exit 3 hands the cart to its keeper's prompt (one model call, never
in the demo, never past the budget, on the model its steward's `escalate` names: realm/steward.py `pick`). `tick()` runs it on its schedule (a `workshop.tick` cart). Run
runs the last cart again; Test runs the blueprint's mock carts in the sandbox and keeps their log.
The script is saved (checked first) as a checkpoint, so Revert takes it back.
"""
from __future__ import annotations

import datetime as dt
import threading
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.realm import pipes, roads, workshop

INPUT_LIMIT = 256 * 1024
SENT = {"done": "workshop.done", "alert": "workshop.alert", "failed": "workshop.failed"}


def mini_line(r: workshop.Run) -> str:
    mark = {"done": "✓", "alert": "!", "escalated": "?"}.get(r.outcome, "✗")
    first = (r.result or r.err).splitlines()[0][:14] if (r.result or r.err) else ""
    return f"{mark} {r.at[11:16]} {first}"


class WorkshopWorker(Worker):
    TYPE = "workshop"
    steward_runner = None                # tests put a fake model here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.runs: list[workshop.Run] = []
        self.running = False
        self.last_cart: dict | None = None
        self.tests: list[workshop.Run] = []
        self.tested_at = ""                       # when Test last ran ("" never)
        self.last_tick: dt.datetime | None = None

    def start(self) -> None:
        self.last_tick = dt.datetime.now()        # its timer fires from now on
        self.refresh()

    # -- what it is -----------------------------------------------------------------------------

    @property
    def runtime(self) -> str:
        return str(self.config.get("runtime") or "python")

    @property
    def layout(self) -> str:
        return str(self.config.get("layout") or "log")

    @property
    def schedule(self) -> str:
        return str(self.config.get("schedule") or "").strip()

    @property
    def script(self) -> Path:
        return workshop.script_path(self.repo_root, self.building_id, self.runtime)

    @property
    def keeper(self) -> str:
        """Its keeper's name: the one who writes its script and schedule from plain words (core/keeper.py)."""
        bs = self.town.scroll.building(self.building_id) if self.town.scroll is not None else None
        lead = bs.garrison.steward if bs is not None else None
        return lead.name if lead is not None else self.btype.orc

    def source(self) -> str:
        return workshop.load_script(self.repo_root, self.building_id, self.runtime)

    def refresh(self) -> None:
        self.runs = workshop.runs(self.state_dir)
        if self.runs and self.last_cart is None:
            r = self.runs[0]
            self.last_cart = workshop.cart(r.event, r.source, r.input)
        self.changed()

    # -- running --------------------------------------------------------------------------------

    def tick(self, now: dt.datetime | None = None) -> bool:
        """Its own timer: on schedule a `workshop.tick` cart runs the script."""
        from orkcraft.realm import watch
        now = now or dt.datetime.now()
        if not self.schedule or not watch.cron_due(self.schedule, self.last_tick, now):
            return False
        self.last_tick = now
        return self.run_cart(workshop.cart("workshop.tick", self.building_id, now.isoformat(timespec="seconds"),
                                           "timer"))

    def receive(self, payload: pipes.Payload, title: str, markdown: str) -> None:
        value = payload.value
        if payload.kind == pipes.FILE:
            try:
                value = (self.repo_root / payload.value).read_text(encoding="utf-8", errors="replace")
            except OSError:
                value = markdown or payload.value
        self.run_cart(workshop.cart(payload.mode, payload.source, value[:INPUT_LIMIT], title))

    def run_cart(self, the_cart: dict) -> bool:
        if self.running:
            return False
        self.running, self.last_cart = True, the_cart
        script, runtime, repo = self.script, self.runtime, self.repo_root
        prompt = str(self.config.get("steward_prompt") or "")
        may_ask = bool(prompt) and not self.simulated and self.town.budget_ok()
        from orkcraft.realm import feedback, steward
        scroll = getattr(self.town, "scroll", None)
        runner = steward.runner_for(scroll.building(self.building_id) if scroll is not None else None, "escalate",
                                    type(self).steward_runner, type_id=self.TYPE, goal=self.aim_now) if may_ask else None
        liked = [str(r.get("value", "")) for r in feedback.examples(repo, self.building_id, 3)]
        self.changed()

        def work() -> None:
            r = workshop.run(script, runtime, the_cart, repo)
            if r.code == workshop.ESCALATE and may_ask:
                try:
                    r.steward = runner(workshop.steward_prompt(prompt, the_cart, r.out, liked))[0].strip()
                except Exception as e:  # the model is out of reach: the cart stays escalated
                    r.err = (r.err + f"\nsteward: {e}").strip()[:workshop.OUT_KEEP]
            try:
                self.town.call(self.finish, r)
            except Exception:
                self.running = False

        threading.Thread(target=work, daemon=True, name=f"workshop-{self.building_id}").start()
        return True

    def finish(self, r: workshop.Run) -> None:
        self.running = False
        try:
            workshop.log(self.state_dir, r)
        except OSError:
            pass
        if r.outcome == "done":
            self.emit("workshop.done", r.result, self.title)
        elif r.outcome == "alert":
            self.emit("workshop.alert", r.result, self.title)
        elif r.outcome == "failed":
            self.emit("workshop.failed", r.err or f"exit {r.code}", self.title)
            delivery.ran(self.town, roads.HandlerRun(self.building_id, "tinker", "script", r.at, 0.0, 0.0,
                                                     outcome="error", error=r.err or f"exit {r.code}"))
        self.refresh()

    def run_again(self) -> str:
        """Run: the last cart again. "" when it started, else why not."""
        if self.last_cart is None:
            return "no cart yet — a road brings one, or Test runs the mock carts"
        if not self.run_cart(self.last_cart):
            return "already running"
        return ""

    def run_tests(self) -> list[workshop.Run]:
        """Test: the blueprint's mock carts in the sandbox; their log stays until the next Test."""
        bp = workshop.load_blueprint(self.repo_root, self.building_id)
        self.tests = workshop.sandbox(self.source(), self.runtime, bp.get("mocks") or [])
        self.tested_at = dt.datetime.now().isoformat(timespec="seconds")
        self.changed()
        return self.tests

    def save_script(self, text: str) -> str:
        """Keep a new script: "" when kept (a checkpoint), else why not."""
        if text == self.source():
            return ""
        why = workshop.check_syntax(text, self.runtime)
        if why:
            return why
        workshop.save_script(self.repo_root, self.building_id, self.runtime, text)
        self.town.checkpoint("update", self.building_id, "script edited")
        self.changed()
        return ""

    # -- the hut --------------------------------------------------------------------------------

    def status(self) -> str:
        if self.running:
            return "WORKING"
        return "ERROR" if self.runs and self.runs[0].outcome == "failed" else ""

    def mini_status(self) -> list[str]:
        if self.running:
            return ["🛠 running…"]
        if not self.runs:
            return ["waiting for a cart"]
        return [mini_line(self.runs[0]), f"{len(self.runs)} run{'s' if len(self.runs) != 1 else ''}"]

    def hut_lines(self, widths: list[int]) -> list[str]:
        if self.running:
            return ["running…"]
        n = len(self.runs)
        last = mini_line(self.runs[0]) if self.runs else "waiting for a cart"
        timer = f"⏰ {self.schedule}" if self.schedule else f"layout: {self.layout}"
        return [last, f"{n} run{'s' if n != 1 else ''}", timer, self.script.name]
