"""🔧 The Catapult's overseer (the building's ork): it scouts the forms, maps their fields with a model,
repairs a script the site broke, and holds the queue while the site wants a login.

A mixin of CatapultWorker (core/workers/catapult.py): the browser and the model run in threads,
what they come to is applied on the town's thread (`_later`).
"""
from __future__ import annotations

import threading
import time

from orkcraft.core import delivery
from orkcraft.realm import catapult as cp, catapult_web as cw, halt, roads


class OverseerMixin:
    # -- the overseer: repairs ----------------------------------------------------------------------

    def _broken(self, form: cw.Form, index: int, shot: cp.Shot, summary: dict, body) -> None:
        """The script broke on the site (not on the cart): the ork repairs it, the shot resumes here."""
        d = self.fdir(form)
        page_map = cw.load_map(d)
        may = (self.config.get("repair", True) and page_map is not None and not self.simulated
               and self.town.budget_ok())
        if not may:
            self._done(shot, body, index)
            return
        self.firing, self.progress, self.step = False, "", ""
        cp.log(self.state_dir, shot)                 # no catapult.failed yet: the ork may fix it
        self.busy = f"🔧 {self.overseer} is repairing {form.name}…"
        self.refresh()
        profile, orc = self.profile, self.overseer
        submit, finish = self._submit(form), str(self.config.get("finish") or "leave")
        rules, mapping, keys = self._rules(form), cw.load_mapping(d), list(self._keys(body))
        runner = type(self).repair_runner

        def work() -> None:
            started = time.time()
            try:
                r = cw.repair(d, page_map, lambda m: cw.plan(m, keys, rules, mapping), submit, finish,
                              list(summary.get("broken") or []), summary.get("page") or {}, profile, orc, runner=runner)
            except halt.Halted:
                r = cw.Repair(False, errors=["stopped by Halt All"])
            self._later(self._repaired, form, index, r, body, started)

        threading.Thread(target=work, daemon=True, name=f"catapult-repair-{self.building_id}").start()

    def _record(self, what: str, started: float, ok: bool, cost: float, error: str = "") -> None:
        delivery.ran(self.town, roads.HandlerRun(self.building_id, self.overseer.lower(), "agent", f"{what}-{int(started)}",
                                                 started, time.time(), outcome="done" if ok else "error",
                                                 error=error[:300], cost_usd=cost or None))

    def _commit(self, reason: str) -> None:
        try:
            self.town.checkpoint("update", self.building_id, f"catapult: {reason}")
        except Exception:
            pass

    def _repaired(self, form: cw.Form, index: int, r: cw.Repair, body, started: float) -> None:
        self.busy = ""
        if r.attempts:
            self._record("repair", started, r.ok, r.cost, "; ".join(r.errors))
        if r.login:
            self._login_lost(form, r.errors[0] if r.errors else "a login page", None, body, index)
            return
        if not r.ok:
            why = "; ".join(r.errors)[:400] or "no repair"
            self.failed = {"body": body, "start": index}
            self.emit("catapult.failed", f"{self.overseer} could not repair {form.name}: {why}", "repair failed")
            self.toast(f"{self.overseer} could not repair {form.name}: {why}", title="🔧 Repair", severity="error")
            self.pump()
            return
        note = r.note or "the script was rewritten"
        self._commit(f"{self.overseer} repaired {form.name} — {note}")
        self.emit("catapult.repaired", f"{self.overseer} ({form.name}): {note}", "repaired")
        self.toast(f"{self.overseer}: {note} — firing again from {form.name}", title="🔧 Repaired")
        self._shoot_forms(body, index, retried_at=index)

    # -- the overseer: scouting ---------------------------------------------------------------------

    def scout(self) -> bool:
        forms = self.forms
        if not self.browser or not forms:
            self.toast("set mode: browser and forms first", title="🎯 Catapult")
            return False
        if self.simulated:
            self.toast("the sandbox opens no browsers", title="🎯 Catapult")
            return False
        if self.out_of_gold("scouting"):
            return False
        if self.busy or self.firing:
            return False
        todo = [f for f in forms if cw.load_map(self.fdir(f)) is None] or forms
        self.busy = f"🔭 {self.overseer} is looking for {', '.join(f.name for f in todo)}…"
        self.changed()
        profile, orc, runner = self.profile, self.overseer, type(self).scout_runner

        def work() -> None:
            for form in todo:
                started = time.time()
                try:
                    page_map, cost = cw.agent_scout(form, profile, orc, runner=runner, headless=True)
                    error, login = "", False
                except cw.LoginNeeded as e:
                    page_map, cost, error, login = None, 0.0, str(e), True
                except Exception as e:
                    page_map, cost, error, login = None, 0.0, str(e)[:300], False
                self._later(self._scouted, form, page_map, cost, error, login, started)
                if page_map is None:
                    break
            self._later(self._scouting_over)

        threading.Thread(target=work, daemon=True, name=f"catapult-scout-{self.building_id}").start()
        return True

    def _scouted(self, form: cw.Form, page_map: dict | None, cost: float, error: str, login: bool,
                 started: float) -> None:
        self._record("scout", started, page_map is not None, cost, error)
        if login:
            self.login_needed = error
            self.changed()
            return
        if page_map is None:
            self.toast(error, title=f"🔭 {form.name}", severity="error")
            return
        self._save_map(form, page_map, f"{self.overseer} scouted {form.name}")

    def _save_map(self, form: cw.Form, page_map: dict, reason: str) -> None:
        cw.save_map(self.fdir(form), page_map)
        script = self.write_script(form)
        p = self.form_plan(form)
        path = cw.path_text(page_map)
        self._commit(reason)
        self.toast(f"{len(page_map['fields'])} fields; {len(p.steps) if p else 0} matched → "
                   f"{script.name if script else 'no script'}" + (f"\nreached by: {path}" if path else "")
                   + (f"\nsubmit: {page_map['submit']!r}" if page_map.get("submit") else ""),
                   title=f"🔭 {form.name}")

    def _scouting_over(self) -> None:
        self.busy = ""
        self.pump()

    # -- logging in -----------------------------------------------------------------------------------

    def _login_lost(self, form: cw.Form, why: str, shot: cp.Shot | None, body, index: int) -> None:
        """The site wants a login: the shot goes back to the front of the queue, the hut burns."""
        self.firing, self.progress, self.step = False, "", ""
        if shot is not None:
            shot.ok, shot.error = False, f"log in again ({form.name})"
            cp.log(self.state_dir, shot)
        if body is not None:
            self.queue.push(body, index, front=True)
        first = not self.login_needed
        self.login_needed = f"{form.name}: {why}"
        if first:
            self.emit("catapult.failed", f"{self.overseer}: the site wants a login again — {why}", "log in again")
        self.refresh()

    def login(self) -> bool:
        """A visible browser on the site with the building's profile: log in, and — if you like —
        open a form that has no map yet; closing the window keeps the login (and that form's map)."""
        forms = self.forms
        if not self.browser or not forms:
            self.toast("set mode: browser and forms first", title="🎯 Catapult")
            return False
        if self.simulated or self.busy:
            return False
        name = self.login_needed.split(":", 1)[0] if self.login_needed else ""
        form = next((f for f in forms if f.name == name), None) \
            or next((f for f in forms if cw.load_map(self.fdir(f)) is None), forms[0])
        self.busy = "🔑 log in in the browser window, then close it"
        self.changed()
        profile, headless = self.profile, self.headless

        def work() -> None:
            try:
                snap, error = cw.scout(form.url, profile, watch=True, headless=headless, need_fields=False), ""
            except Exception as e:
                snap, error = None, str(e)[:300]
            self._later(self.logged_in, form, snap, error)

        threading.Thread(target=work, daemon=True, name=f"catapult-login-{self.building_id}").start()
        return True

    def logged_in(self, form: cw.Form, snap: dict | None, error: str) -> None:
        self.busy = ""
        if snap is None:
            self.toast(error, title="🔑 Login", severity="error")
            self.changed()
            return
        if snap.get("fields") and not snap.get("login") and cw.load_map(self.fdir(form)) is None:
            self._save_map(form, snap, f"the operator showed the way to {form.name}")
        self.login_needed = ""
        self.changed()
        self.pump()

    # -- the overseer: mapping ----------------------------------------------------------------------

    def map_fields(self) -> bool:
        forms = [f for f in self.forms if cw.load_map(self.fdir(f)) is not None]
        keys = self._keys()
        if not self.browser or not forms:
            self.toast("Scout the forms first", title="🎯 Catapult")
            return False
        if not self.simulated and self.out_of_gold("the mapping"):
            return False
        if not keys:
            self.toast("load a cart or set schema — the model needs the keys", title="🎯 Catapult")
            return False
        if self.simulated or self.busy:
            return False
        self.busy = "🧠 mapping fields…"
        self.changed()
        dirs = {f.name: self.fdir(f) for f in forms}

        def work() -> None:
            started, out, cost, error = time.time(), {}, 0.0, ""
            for name, d in dirs.items():
                try:
                    mapping, c = cw.map_with_model(cw.load_map(d), keys)
                    out[name], cost = mapping, cost + (c or 0.0)
                except Exception as e:
                    error = str(e)[:300]
                    break
            self._later(self._mapped, out, cost, error, started)

        threading.Thread(target=work, daemon=True, name=f"catapult-map-{self.building_id}").start()
        return True

    def _mapped(self, mappings: dict, cost: float, error: str, started: float) -> None:
        self.busy = ""
        self._record("map", started, not error, cost, error)
        if error:
            self.toast(error, title="🧠 Map", severity="error")
        for form in self.forms:
            if form.name in mappings:
                cw.save_mapping(self.fdir(form), mappings[form.name])
                self.write_script(form)
        if mappings:
            self._commit(f"{self.overseer} mapped " + ", ".join(mappings))
            self.toast(", ".join(f"{n}: {len(m)} fields" for n, m in mappings.items()), title="🧠 Map")
        self.pump()
