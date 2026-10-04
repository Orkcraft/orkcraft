"""🎯 The Catapult: waits for its roads, checks, and sends out — one shot at a time.

Carts are loaded under their source buildings, in groups (realm/catapult.py): with `key` (a body
path such as `version.tag`) carts naming the same value share a group, so two releases never mix;
carts older than `ttl` minutes are dropped. A group that has everything `wait_for` names (any cart,
without `wait_for`) becomes a shot and joins the queue; shots fire one at a time, the rest wait.
Each is checked against `schema` and sent to `url`. `c` asks before each shot (`confirm`).
🎯 fires what is loaded now (or retries the last failed shot), 🧪 shows it without sending.
`catapult.sent` carries the answer, `catapult.failed` the reason. The sandbox never sends.

Browser mode (`mode: browser`, realm/catapult_web.py) closes a whole intent on a site with no API:
`forms` lists its forms in order (`event = https://… | the new-event form`). `s`: the building's
orc walks the site to each form itself, marks its fields and writes its `fill.py` (kept in the
camp's git). `l`: a visible browser to log in (and, if you like, show the way to a form). `m`: a
model maps the cart's keys to the fields. A shot fills the forms in turn and presses each one's
submit (`finish: press`) or hands each to you (`finish: leave`, `f`). A site sending the browser
to a login page sets the hut on fire 🔥 and holds the queue until you log in. A script that breaks
because the site changed is repaired by the orc and the shot resumes at that form
(`catapult.repaired`; `repair: false` turns it off). File fields take a project file, `loot:<path>`
(not while it waits for your review in a Loot Vault) or an http(s) URL. 🛑 Halt All stops the browser.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import threading
import time
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import catapult as cp, catapult_web as cw, halt, roads
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView

GLOBE = "🌐"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class CatapultView(TypedView):
    TYPE = "catapult"
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm shots on/off"),
                Binding("s", "scout", "The ork finds the forms (browser mode)"),
                Binding("l", "login", "Log in to the site (browser mode)"),
                Binding("m", "map_fields", "Map fields with a model (browser mode)"),
                Binding("f", "toggle_finish", "Hand over / press submit (browser mode)")]
    opener = None                      # tests put a fake network here
    repair_runner = None               # … a fake overseer for repairs
    scout_runner = None                # … and for scouting

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.shots: list[cp.Shot] = []
        self.firing = False
        self.busy = ""                 # "scouting…", "mapping…", "repairing…"
        self.progress = ""             # "2/3" while the forms of a shot are filled
        self.login_needed = ""         # why the site wants a login again (the hut burns)
        self.paused = False            # 🛑 Halt All: the queue waits for 🎯
        self.failed: dict | None = None
        self.proc = None               # the running fill.py

    # -- what it is ---------------------------------------------------------------------------------

    @property
    def load(self) -> cp.Load:
        return cp.Load(self.state_dir)

    @property
    def queue(self) -> cp.Queue:
        return cp.Queue(self.state_dir)

    @property
    def wait_for(self) -> list[str]:
        return [str(x) for x in (self.config.get("wait_for") or [])]

    @property
    def schema_path(self) -> Path | None:
        rel = self.config.get("schema")
        return (self._get_repo_root() / str(rel)) if rel else None

    @property
    def browser(self) -> bool:
        return self.config.get("mode") == "browser"

    @property
    def forms(self) -> list[cw.Form]:
        return cw.parse_forms([str(x) for x in self.config.get("forms") or []])[0]

    @property
    def profile(self) -> Path:
        return self.state_dir / "profile"

    @property
    def overseer(self) -> str:
        orc = self.spec.get("orc")
        return str(orc.get("name") if isinstance(orc, dict) and orc.get("name") else self.btype.orc)

    @property
    def headless(self) -> bool:
        return bool(os.environ.get("ORKCRAFT_HEADLESS"))

    def fdir(self, form: cw.Form | str) -> Path:
        return cw.form_dir(self._get_repo_root(), self.building_id, form if isinstance(form, str) else form.name)

    def compose_body(self) -> ComposeResult:
        yield Static("", id="cat-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="cat-shots", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="cat-detail", markup=False)

    def on_mount(self) -> None:
        self._migrate_single_page()
        super().on_mount()

    def _migrate_single_page(self) -> None:
        """A Catapult of one page kept its map beside its shots; it moves to the first form's folder."""
        forms, old = self.forms, self.state_dir
        if not self.browser or not forms or not (old / "map.json").exists():
            return
        target = self.fdir(forms[0])
        if (target / "map.json").exists():
            return
        target.mkdir(parents=True, exist_ok=True)
        for name in ("map.json", "mapping.json", "fill.py", "fill.sha", "fill.new.py"):
            if (old / name).exists():
                shutil.move(str(old / name), str(target / name))

    def refresh_data(self) -> None:
        self.shots = cp.shots(self.state_dir)
        self._render_list()

    # -- loading and the queue ----------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        load = self.load
        load.put(payload.source, payload.value, str(self.config.get("key") or ""))
        dropped = load.expire(int(self.config.get("ttl") or 0))
        if dropped:
            self.app.notify("older than ttl, dropped: " + ", ".join(dropped), title="🎯 Catapult")
        queue = self.queue
        while (body := load.take(self.wait_for)) is not None:
            queue.push(body)
        self.pump()

    def pump(self) -> None:
        """Fire the next queued shot, unless one is flying, the orc is busy, the site wants a login
        or 🛑 Halt All paused the queue."""
        if self.firing or self.busy or self.login_needed or self.paused:
            self._render_list()
            return
        item = self.queue.pop()
        if item is None:
            self._render_list()
            return
        self._shoot(item["body"], int(item.get("start") or 0))

    def fire(self, auto: bool = False, dry: bool = False) -> bool:
        """🎯: what is loaded now joins the queue (ready or not) — or the last failed shot again.
        🧪 (`dry`): show it, take nothing."""
        load = self.load
        if dry:
            body = load.body(self.wait_for)
            if body is None and len(self.queue):
                body = self.queue.items[0]["body"]
            if body is None and self.failed:
                body = self.failed["body"]
            if body is None:
                self.app.notify("nothing is loaded yet", title="🎯 Catapult")
                return False
            return self._dry(body)
        self.paused = False
        body = load.take(self.wait_for, force=True)
        if body is not None:
            self.queue.push(body)
        elif self.failed:
            self.queue.push(self.failed["body"], self.failed.get("start", 0), front=True)
            self.failed = None
        elif not len(self.queue):
            self.app.notify("nothing is loaded yet", title="🎯 Catapult")
            return False
        self.pump()
        return True

    def _problem(self, body, url: str, error: str, start: int = 0) -> bool:
        self._done(cp.Shot(_now(), False, 0, url, str(body)[:2000], error=error), body=body, start=start)
        return False

    def _shoot(self, body, start: int = 0) -> bool:
        problems = cp.check(body, self.schema_path)
        if problems:
            return self._problem(body, str(self.config.get("url", "")), "; ".join(problems))
        if self.browser:
            return self._shoot_forms(body, start)
        url = str(self.config.get("url") or "")
        if self.simulated or not url:
            self._done(cp.dry_run(url or "(no url set)", str(self.config.get("method") or "POST"), body))
            return True
        if self.config.get("confirm"):
            self.app.push_screen(Confirm(f"🎯 Send to {url}?", json.dumps(body, ensure_ascii=False)[:600]),
                                 lambda yes: self._send(url, body) if yes else self._declined())
            self.firing = True
            return True
        self._send(url, body)
        return True

    def _declined(self) -> None:
        self.firing = False
        self.pump()

    def _send(self, url: str, body) -> None:
        self.firing = True
        self._render_list()
        method = str(self.config.get("method") or "POST")
        token = os.environ.get(str(self.config.get("token_env") or ""), "")
        opener, app = type(self).opener, self.app

        def work() -> None:
            shot = cp.fire(url, method, body, token, *([opener] if opener else []))
            try:
                app.call_from_thread(self._done, shot, body)
            except Exception:
                self.firing = False

        threading.Thread(target=work, daemon=True, name=f"catapult-{self.building_id}").start()

    def _dry(self, body) -> bool:
        problems = cp.check(body, self.schema_path)
        if problems:
            self._done(cp.Shot(_now(), False, 0, "", str(body)[:2000], error="; ".join(problems)), body=None)
            return False
        if self.browser:
            parts = []
            for form in self.forms:
                p = self.form_plan(form, body)
                parts.append(f"[{form.name}] " + (cw.describe(p, body) if p else "not scouted yet (s)"))
            self._done(cp.dry_run_form(", ".join(f.name for f in self.forms) or "(no forms)", "\n\n".join(parts), body))
            return True
        url = str(self.config.get("url") or "")
        self._done(cp.dry_run(url or "(no url set)", str(self.config.get("method") or "POST"), body))
        return True

    # -- browser mode: the forms --------------------------------------------------------------------

    def _keys(self, body=None) -> dict[str, object]:
        """The cart's keys with sample values: the given body, the loaded one, else the schema's."""
        if body is None:
            body = self.load.body(self.wait_for)
        if body is not None:
            return cw.leaves(body)
        try:
            schema = json.loads(self.schema_path.read_text(encoding="utf-8")) if self.schema_path else {}
        except (OSError, ValueError):
            schema = {}
        return {k: "" for k in cw.schema_paths(schema)}

    def _rules(self, form: cw.Form) -> list[str]:
        return cw.rules_for([str(x) for x in self.config.get("fields") or []], form.name, [f.name for f in self.forms])

    def _submit(self, form: cw.Form) -> str:
        return form.submit or str((cw.load_map(self.fdir(form)) or {}).get("submit") or "")

    def form_plan(self, form: cw.Form, body=None) -> cw.Plan | None:
        page_map = cw.load_map(self.fdir(form))
        if page_map is None:
            return None
        return cw.plan(page_map, list(self._keys(body)), self._rules(form), cw.load_mapping(self.fdir(form)))

    def write_script(self, form: cw.Form, body=None) -> Path | None:
        d = self.fdir(form)
        page_map, p = cw.load_map(d), self.form_plan(form, body)
        if page_map is None or p is None:
            return None
        return cw.write_script(d, cw.script_text(page_map, p, self._submit(form), str(self.config.get("finish") or "leave")))

    def _pending_review(self) -> set[str]:
        """Files a Loot Vault still waits for you to review: the Catapult will not upload them."""
        from orkcraft.realm import generated
        root, out = self._get_repo_root(), set()
        for bid, spec in (getattr(self.app, "custom_specs", {}) or {}).items():
            if spec.get("type") not in ("loot", "generator"):
                continue
            try:
                review = generated.Review(root, root / ".orkcraft" / "loot" / bid, str((spec.get("config") or {}).get("path", "")))
                out |= {g.path for g in review.pending()}
            except Exception:
                continue
        return out

    def _shoot_forms(self, body, start: int = 0, retried_at: int | None = None) -> bool:
        forms = self.forms
        label = ", ".join(f.name for f in forms) or "(no forms)"
        if not forms:
            return self._problem(body, label, "no forms set — `name = https://… | what to open`")
        if self.simulated:
            return self._dry(body)
        press = self.config.get("finish") == "press"
        runs, pending = [], self._pending_review()
        for i, form in enumerate(forms):
            if i < start:
                continue
            p = self.form_plan(form, body)
            if p is None:
                return self._problem(body, form.url, f"{form.name}: not scouted yet — press s", start)
            if not p.steps:
                return self._problem(body, form.url, f"{form.name}: no field matches the cart — set fields or press m", start)
            if press and not self._submit(form):
                return self._problem(body, form.url, f"{form.name}: no submit button known — scout again or name it in forms", start)
            filled, problems = cw.resolve_files(body, p.steps, self._get_repo_root(), pending,
                                                self.state_dir / "downloads")
            if problems:
                return self._problem(body, form.url, f"{form.name}: " + "; ".join(problems), start)
            script = self.write_script(form, body)
            if script is not None and script.name != "fill.py":
                script = script.parent / "fill.py"        # edited by hand: the operator's version runs
            url = str((cw.load_map(self.fdir(form)) or {}).get("url") or form.url)
            runs.append((i, form, script, url, filled, cw.describe(p, body)))
        if self.config.get("confirm"):
            self.firing = True
            self.app.push_screen(Confirm(f"🎯 Fill {label}?", "\n\n".join(f"[{f.name}] {d}" for _, f, _, _, _, d in runs)[:900]),
                                 lambda yes: self._run_forms(runs, body, press, retried_at) if yes else self._declined())
            return True
        self._run_forms(runs, body, press, retried_at)
        return True

    def _run_forms(self, runs: list, body, press: bool, retried_at: int | None) -> None:
        self.firing = True
        total = len(self.forms)
        app, profile, headless = self.app, self.profile, self.headless

        def started(proc) -> None:
            self.proc = proc

        def work() -> None:
            answers = []
            for i, form, script, url, filled, _ in runs:
                self.progress = f"{i + 1}/{total}"
                try:
                    app.call_from_thread(self._render_list)
                except Exception:
                    pass
                res = cw.run_script(script, profile, filled, press, headless=headless, on_start=started)
                self.proc = None
                shot = cp.form_shot(url, filled, res, press)
                shot.url = f"[{form.name}] {shot.url}"
                try:
                    if res.summary.get("login"):
                        app.call_from_thread(self._login_lost, form, str(res.summary["login"]), shot, body, i)
                    elif res.summary.get("broken") and retried_at != i:
                        app.call_from_thread(self._broken, form, i, shot, res.summary, body)
                    elif not shot.ok:
                        app.call_from_thread(self._done, shot, body, i)
                    else:
                        cp.log(self.state_dir, shot)
                        answers.append(f"[{form.name}] {shot.answer}")
                        continue
                except Exception:
                    self.firing = False
                return
            final = cp.Shot(_now(), True, 0, ", ".join(f.name for _, f, *_ in runs), json.dumps(body, ensure_ascii=False)[:2000],
                            "\n\n".join(answers))
            try:
                app.call_from_thread(self._done, final, body)
            except Exception:
                self.firing = False

        threading.Thread(target=work, daemon=True, name=f"catapult-form-{self.building_id}").start()

    # -- the overseer: repairs ----------------------------------------------------------------------

    def _broken(self, form: cw.Form, index: int, shot: cp.Shot, summary: dict, body) -> None:
        """The script broke on the site (not on the cart): the orc repairs it, the shot resumes here."""
        d = self.fdir(form)
        page_map, app = cw.load_map(d), self.app
        may = (self.config.get("repair", True) and page_map is not None and not self.simulated
               and not getattr(app, "gold_exhausted", lambda: False)())
        if not may:
            self._done(shot, body, index)
            return
        self.firing, self.progress = False, ""
        cp.log(self.state_dir, shot)                 # no catapult.failed yet: the orc may fix it
        self.busy = f"🔧 {self.overseer} is repairing {form.name}…"
        self.refresh_data()
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
            try:
                app.call_from_thread(self._repaired, form, index, r, body, started)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-repair-{self.building_id}").start()

    def _record(self, what: str, started: float, ok: bool, cost: float, error: str = "") -> None:
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None:
            on_run(roads.HandlerRun(self.building_id, self.overseer.lower(), "agent", f"{what}-{int(started)}",
                                    started, time.time(), outcome="done" if ok else "error",
                                    error=error[:300], cost_usd=cost or None))

    def _commit(self, reason: str) -> None:
        mark = getattr(self.app, "checkpoint", None)
        if callable(mark):
            try:
                mark("update", self.building_id, f"catapult: {reason}")
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
            self.app.notify(f"{self.overseer} could not repair {form.name}: {why}", title="🔧 Repair", severity="error")
            self.pump()
            return
        note = r.note or "the script was rewritten"
        self._commit(f"{self.overseer} repaired {form.name} — {note}")
        self.emit("catapult.repaired", f"{self.overseer} ({form.name}): {note}", "repaired")
        self.app.notify(f"{self.overseer}: {note} — firing again from {form.name}", title="🔧 Repaired")
        self._shoot_forms(body, index, retried_at=index)

    # -- the overseer: scouting ---------------------------------------------------------------------

    def action_scout(self) -> None:
        forms = self.forms
        if not self.browser or not forms:
            self.app.notify("set mode: browser and forms first", title="🎯 Catapult")
            return
        if self.simulated:
            self.app.notify("the sandbox opens no browsers", title="🎯 Catapult")
            return
        if self.out_of_gold("scouting"):
            return
        if self.busy or self.firing:
            return
        todo = [f for f in forms if cw.load_map(self.fdir(f)) is None] or forms
        self.busy = f"🔭 {self.overseer} is looking for {', '.join(f.name for f in todo)}…"
        self._render_list()
        app, profile, orc, runner = self.app, self.profile, self.overseer, type(self).scout_runner

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
                try:
                    app.call_from_thread(self._scouted, form, page_map, cost, error, login, started)
                except Exception:
                    self.busy = ""
                    return
                if page_map is None:
                    break
            try:
                app.call_from_thread(self._scouting_over)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-scout-{self.building_id}").start()

    def _scouted(self, form: cw.Form, page_map: dict | None, cost: float, error: str, login: bool,
                 started: float) -> None:
        self._record("scout", started, page_map is not None, cost, error)
        if login:
            self.login_needed = error
            self._fire_alert()
            return
        if page_map is None:
            self.app.notify(error, title=f"🔭 {form.name}", severity="error")
            return
        self._save_map(form, page_map, f"{self.overseer} scouted {form.name}")

    def _save_map(self, form: cw.Form, page_map: dict, reason: str) -> None:
        cw.save_map(self.fdir(form), page_map)
        script = self.write_script(form)
        p = self.form_plan(form)
        path = cw.path_text(page_map)
        self._commit(reason)
        self.app.notify(f"{len(page_map['fields'])} fields; {len(p.steps) if p else 0} matched → "
                        f"{script.name if script else 'no script'}" + (f"\nreached by: {path}" if path else "")
                        + (f"\nsubmit: {page_map['submit']!r}" if page_map.get("submit") else ""),
                        title=f"🔭 {form.name}")

    def _scouting_over(self) -> None:
        self.busy = ""
        self.pump()

    # -- logging in -----------------------------------------------------------------------------------

    def _login_lost(self, form: cw.Form, why: str, shot: cp.Shot | None, body, index: int) -> None:
        """The site wants a login: the shot goes back to the front of the queue, the hut burns."""
        self.firing, self.progress = False, ""
        if shot is not None:
            shot.ok, shot.error = False, f"log in again ({form.name})"
            cp.log(self.state_dir, shot)
        if body is not None:
            self.queue.push(body, index, front=True)
        first = not self.login_needed
        self.login_needed = f"{form.name}: {why}"
        if first:
            self.emit("catapult.failed", f"{self.overseer}: the site wants a login again — {why}", "log in again")
        self._fire_alert()
        self.refresh_data()

    def _fire_alert(self) -> None:
        refresh = getattr(self.app, "refresh_roster", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        self._render_list()

    def orders_alert(self):
        """The hut's 🔥: the site wants a login (the app shows it as the lead orc's alert)."""
        if not self.login_needed:
            return None
        waiting = len(self.queue)
        return ("login", f"🎯 {self.overseer}: log in to the site again",
                [self.login_needed, f"{waiting} shot{'s' if waiting != 1 else ''} wait in the queue"],
                [("1", "Log in now (opens a browser)"), ("2", "Later")])

    def answer_alert(self, key: str):
        if key == "1":
            self.action_login()
        return None

    def action_login(self) -> None:
        """A visible browser on the site with the building's profile: log in, and — if you like —
        open a form that has no map yet; closing the window keeps the login (and that form's map)."""
        forms = self.forms
        if not self.browser or not forms:
            self.app.notify("set mode: browser and forms first", title="🎯 Catapult")
            return
        if self.simulated or self.busy:
            return
        name = self.login_needed.split(":", 1)[0] if self.login_needed else ""
        form = next((f for f in forms if f.name == name), None) \
            or next((f for f in forms if cw.load_map(self.fdir(f)) is None), forms[0])
        self.busy = "🔑 log in in the browser window, then close it"
        self._render_list()
        app, profile = self.app, self.profile

        def work() -> None:
            try:
                snap, error = cw.scout(form.url, profile, watch=True, headless=self.headless, need_fields=False), ""
            except Exception as e:
                snap, error = None, str(e)[:300]
            try:
                app.call_from_thread(self._logged_in, form, snap, error)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-login-{self.building_id}").start()

    def _logged_in(self, form: cw.Form, snap: dict | None, error: str) -> None:
        self.busy = ""
        if snap is None:
            self.app.notify(error, title="🔑 Login", severity="error")
            self._render_list()
            return
        if snap.get("fields") and not snap.get("login") and cw.load_map(self.fdir(form)) is None:
            self._save_map(form, snap, f"the operator showed the way to {form.name}")
        self.login_needed = ""
        self._fire_alert()
        self.pump()

    # -- mapping and settings -----------------------------------------------------------------------

    def action_map_fields(self) -> None:
        forms = [f for f in self.forms if cw.load_map(self.fdir(f)) is not None]
        keys = self._keys()
        if not self.browser or not forms:
            self.app.notify("scout the forms first (s)", title="🎯 Catapult")
            return
        if not self.simulated and self.out_of_gold("the mapping"):
            return
        if not keys:
            self.app.notify("load a cart or set schema — the model needs the keys", title="🎯 Catapult")
            return
        if self.simulated or self.busy:
            return
        self.busy = "🧠 mapping fields…"
        self._render_list()
        app, dirs = self.app, {f.name: self.fdir(f) for f in forms}

        def work() -> None:
            started, out, cost, error = time.time(), {}, 0.0, ""
            for name, d in dirs.items():
                try:
                    mapping, c = cw.map_with_model(cw.load_map(d), keys)
                    out[name], cost = mapping, cost + (c or 0.0)
                except Exception as e:
                    error = str(e)[:300]
                    break
            try:
                app.call_from_thread(self._mapped, out, cost, error, started)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-map-{self.building_id}").start()

    def _mapped(self, mappings: dict, cost: float, error: str, started: float) -> None:
        self.busy = ""
        self._record("map", started, not error, cost, error)
        if error:
            self.app.notify(error, title="🧠 Map", severity="error")
        for form in self.forms:
            if form.name in mappings:
                cw.save_mapping(self.fdir(form), mappings[form.name])
                self.write_script(form)
        if mappings:
            self._commit(f"{self.overseer} mapped " + ", ".join(mappings))
            self.app.notify(", ".join(f"{n}: {len(m)} fields" for n, m in mappings.items()), title="🧠 Map")
        self.pump()

    def action_toggle_finish(self) -> None:
        if not self.browser:
            return
        finish = "leave" if self.config.get("finish") == "press" else "press"
        if self.save_config({"finish": finish}):
            for form in self.forms:
                self.write_script(form)
            self._render_list()

    def action_toggle_confirm(self) -> None:
        if self.save_config({"confirm": not self.config.get("confirm")}):
            self._render_list()

    def halt(self) -> int:
        """🛑 Halt All: the running browser stops, the queue waits for 🎯."""
        self.paused = True
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            proc.kill()
            return 1
        return 0

    # -- after a shot -------------------------------------------------------------------------------

    def _done(self, shot: cp.Shot, body=None, start: int = 0) -> None:
        self.firing, self.progress = False, ""
        cp.log(self.state_dir, shot)
        if not shot.dry:
            if shot.ok:
                self.emit("catapult.sent", f"{shot.status} {shot.url}\n\n{shot.answer}", f"{shot.status} {shot.url}")
                self.failed = None
            else:
                if body is not None:
                    self.failed = {"body": body, "start": start}
                self.emit("catapult.failed", f"{shot.error or shot.status} {shot.url}\n\n{shot.answer}".strip(),
                          shot.error or str(shot.status))
        self.shots = cp.shots(self.state_dir)
        self.pump()

    # -- the view -----------------------------------------------------------------------------------

    def _state_text(self) -> str:
        bits = []
        if self.firing:
            bits.append(f"filling {self.progress}" if self.browser and self.progress else "firing…")
        if self.busy:
            bits.append(self.busy)
        if self.login_needed:
            bits.append(f"🔥 log in again (l) — {self.login_needed}")
        if self.paused:
            bits.append("halted — 🎯 resumes")
        queued = len(self.queue)
        if queued:
            bits.append(f"{queued} queued")
        return " · ".join(bits)

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#cat-head", Static), self.query_one("#cat-shots", OptionList)
        except Exception:
            return
        load = self.load
        if self.browser:
            forms = self.forms
            finish = "press submit" if self.config.get("finish") == "press" else "hand over"
            marks = " → ".join(f"{f.name}{'' if cw.load_map(self.fdir(f)) else ' (not scouted)'}" for f in forms)
            target = f"{GLOBE} {marks or 'no forms set'} · then {finish} (f)"
        else:
            target = f"→ {self.config.get('method') or 'POST'} {self.config.get('url') or 'no url set — 🧪 dry runs only'}"
        waits = self.wait_for
        loaded = ", ".join(f"{'✓' if s in load.items else '·'} {s}" for s in waits) if waits else \
            (f"{len(load.items)} loaded" if load.items else "fires on every cart")
        extra = [f"key {self.config['key']}"] if self.config.get("key") else []
        extra += [f"ttl {self.config['ttl']}m"] if self.config.get("ttl") else []
        state = self._state_text()
        head.update(Text(f"{target} · {loaded} · schema {self.config.get('schema') or '—'} · "
                         + "".join(f"{x} · " for x in extra)
                         + f"confirm: {'on' if self.config.get('confirm') else 'off'} (c)"
                         + (f" · {state}" if state else ""), style="dim"))
        lst.clear_options()
        for i, s in enumerate(self.shots):
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("🧪 " if s.dry else "✓ " if s.ok else "✗ ", style="cyan" if s.dry else "green" if s.ok else "red")
            row.append(f"{s.at[5:16].replace('T', ' ')} ")
            row.append("dry run" if s.dry else (s.error or str(s.status)), style="dim")
            lst.add_option(Option(row, id=f"s{i}"))
        if self.shots:
            lst.highlighted = 0
            self._show(self.shots[0])
        elif self.browser:
            parts = []
            for form in self.forms:
                p, page_map = self.form_plan(form), cw.load_map(self.fdir(form)) or {}
                path = cw.path_text(page_map)
                parts.append(f"[{form.name}] " + ((cw.describe(p) + (f"\nreached by: {path}" if path else ""))
                                                  if p else f"not scouted yet — s sends {self.overseer} to find it"))
            try:
                self.query_one("#cat-detail", Static).update("\n\n".join(parts) or "Set forms: `name = https://… | what to open`.")
            except Exception:
                pass

    def _show(self, s: cp.Shot) -> None:
        try:
            self.query_one("#cat-detail", Static).update(
                (s.answer if s.dry else f"→ {s.url}\n{s.body}\n\n← {s.status} {s.error}\n{s.answer}").strip())
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "cat-shots" and event.option.id:
            event.stop()
            self._show(self.shots[int(event.option.id[1:])])

    # -- the hut ----------------------------------------------------------------------------------

    def _mark(self, line: str) -> str:
        return f"{GLOBE} {line}" if self.browser else line

    def mini_status(self) -> list[str]:
        load = self.load
        missing = load.missing(self.wait_for)
        lines = [self._mark("🔥 log in (l)" if self.login_needed else
                            f"waits for {', '.join(missing)}" if missing and self.wait_for else
                            f"{len(load.items)} loaded" if load.items else "empty")]
        queued = len(self.queue)
        if queued:
            lines.append(f"{queued} queued")
        if self.shots:
            s = self.shots[0]
            lines.append("🧪 dry run" if s.dry else f"✓ {s.status}" if s.ok else f"✗ {(s.error or str(s.status))[:30]}")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """One short line: filling, burning, waiting for how many roads, or how the last shot went."""
        load, waits, queued = self.load, self.wait_for, len(self.queue)
        more = f" +{queued}" if queued else ""
        if self.login_needed:
            return [self._mark("🔥 log in")]
        if self.firing:
            return [self._mark((f"fill {self.progress}" if self.browser and self.progress else "firing…") + more)]
        if self.busy:
            return [self._mark(self.busy.split(" ")[0] + "…")]
        if waits and load.missing(waits):
            return [self._mark(f"wait {len(waits) - len(load.missing(waits))}/{len(waits)}{more}")]
        if self.shots:
            s = self.shots[0]
            return [self._mark(("🧪 dry" if s.dry else f"✓ {s.status}" if s.ok else f"✗ {s.status or 'err'}") + more)]
        return [self._mark("idle")]

    def quick_action(self, action_id: str) -> bool:
        if action_id == "catapult.fire":
            self.fire()
            return True
        if action_id == "catapult.dry_run":
            self.fire(dry=True)
            return True
        if action_id == "catapult.scout":
            self.action_scout()
            return True
        return False
