"""🎯 The Catapult's work: it waits for its roads, checks, and sends out — one shot at a time.

Carts are loaded under their source buildings, in groups (realm/catapult.py); a group that has
everything `wait_for` names becomes a shot and joins the queue; shots fire one at a time. Each is
checked against `schema` and sent to `url` — or, in browser mode (realm/catapult_web/), fills
the intent's forms in turn, a screenshot of each kept (`screens`). With `confirm` on, a shot
waits for the person's yes (`asking`: the faces show the question, `answer` takes it); put off,
it waits at the front of the queue and holds it (`held`) until Resume or Drop.
`catapult.sent` carries the answer, `catapult.failed` the reason. The sandbox never sends.

In `mode: mcp` a shot goes to an MCP server: a learned direct path, a local server, or the AI tool
that has the server (core/workers/catapult_mcp.py).

The overseer (the building's ork) scouts the forms, maps fields with a model and repairs a script
the site broke; a site that wants a login holds the queue (`login_needed`) until `login()`.
🛑 Stop all kills the browser and pauses the queue until Resume (or the next Fire).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.core.workers.catapult_mcp import McpShots
from orkcraft.realm import catapult as cp, catapult_web as cw, halt, roads

GLOBE = "🌐"
SCREENS = 120                    # screenshots kept, newest last


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class CatapultWorker(McpShots, Worker):
    TYPE = "catapult"
    opener = None                      # tests put a fake network here
    repair_runner = None               # … a fake overseer for repairs
    scout_runner = None                # … and for scouting

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.shots: list[cp.Shot] = []
        self.firing = False
        self.busy = ""                 # "scouting…", "mapping…", "repairing…"
        self.progress = ""             # "2/3" while the forms of a shot are filled
        self.step = ""                 # the form being filled now
        self.login_needed = ""         # why the site wants a login again (the hut burns)
        self.paused = False            # 🛑 Stop all: the queue waits for Resume
        self.held = False              # the first queued shot was put off: the queue waits for Resume or Drop
        self.waiting = ""              # mode mcp: why the queue waits (no carrier, no budget) until Resume
        self.failed: dict | None = None
        self.proc = None               # the running fill.py
        self.asking: dict | None = None        # a shot waiting for the person's yes: {title, text}
        self._go: Callable[[], None] | None = None
        self._asked: dict | None = None        # the body and first form of the shot `asking` is about

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
        return (self.repo_root / str(rel)) if rel else None

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
        return cw.form_dir(self.repo_root, self.building_id, form if isinstance(form, str) else form.name)

    # -- its life -----------------------------------------------------------------------------------

    def start(self) -> None:
        self._migrate_single_page()
        self.refresh()

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

    def refresh(self) -> None:
        self.shots = cp.shots(self.state_dir)
        self.changed()

    def status(self) -> str:
        return "WORKING" if self.firing or self.busy else ""

    def halt(self) -> int:
        """🛑 Stop all: the running browser stops, the queue waits for Resume."""
        self.paused = True
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            proc.kill()
            return 1
        return 0

    def _later(self, fn, *a) -> None:
        """From a thread: `fn` where the face wants it (a town that is gone drops it)."""
        try:
            self.town.call(fn, *a)
        except Exception:
            pass

    # -- the person's yes -----------------------------------------------------------------------------

    def _ask(self, title: str, text: str, go: Callable[[], None], body, start: int = 0) -> None:
        """`confirm` is on: the shot waits for the person (the faces show `asking`)."""
        self.firing = True
        self.asking, self._go = {"title": title, "text": text}, go
        self._asked = {"body": body, "start": start}
        self.changed()

    def answer(self, yes: bool, drop: bool = False) -> None:
        """Yes fires the shot; no puts it off — it goes back to the front of the queue, which holds
        until Resume (it asks again) or Drop; `drop` lets it go."""
        go, self._go, self.asking = self._go, None, None
        asked, self._asked = self._asked, None
        if yes and go is not None:
            go()
            return
        self.firing = False
        if asked is not None and not drop:
            self.queue.push(asked["body"], asked["start"], front=True)
            self.held = True
            self.changed()
            return
        self.pump()

    def resume(self) -> bool:
        """The queue goes on after 🛑 Stop all or a shot put off; nothing loaded is fired."""
        mcp_login = self.mcp_mode and self.login_needed      # a refused token: fixed outside, then Resume
        if not (self.paused or self.held or self.waiting or mcp_login):
            return False
        self.paused = self.held = False
        self.waiting = ""
        if mcp_login:
            self.login_needed = ""
        self.pump()
        return True

    def drop(self, what: str) -> bool:
        """Let something go: `next` the first queued shot (the one put off), `failed` the shot Fire
        would send again, `load` what is loaded and not yet a shot."""
        if what == "next":
            if self.queue.pop() is None:
                return False
            self.held = False
            self.pump()
            return True
        if what == "failed":
            if self.failed is None:
                return False
            self.failed = None
            self.changed()
            return True
        if what == "load":
            load = self.load
            if not load.groups:
                return False
            load.clear()
            self.changed()
            return True
        raise ValueError(f"drop {what!r}: next, failed or load")

    # -- loading and the queue ----------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        load = self.load
        load.put(payload.source, payload.value, str(self.config.get("key") or ""))
        dropped = load.expire(int(self.config.get("ttl") or 0))
        if dropped:
            self.toast("older than ttl, dropped: " + ", ".join(dropped), title="🎯 Catapult")
        queue = self.queue
        while (body := load.take(self.wait_for)) is not None:
            queue.push(body)
        self.pump()

    def pump(self) -> None:
        """Fire the next queued shot, unless one is flying, the ork is busy, the site wants a login,
        🛑 Stop all paused the queue or a shot was put off."""
        if self.firing or self.busy or self.login_needed or self.paused or self.held or self.waiting:
            self.changed()
            return
        item = self.queue.pop()
        if item is None:
            self.changed()
            return
        self._shoot(item["body"], int(item.get("start") or 0))

    def loaded_body(self):
        """What a 🧪 would show: the loaded body, else the first queued one, else the failed one."""
        body = self.load.body(self.wait_for)
        if body is None and len(self.queue):
            body = self.queue.items[0]["body"]
        if body is None and self.failed:
            body = self.failed["body"]
        return body

    def fire(self, auto: bool = False, dry: bool = False) -> bool:
        """🎯: what is loaded now joins the queue (ready or not) — or the last failed shot again; the
        queue goes on (as Resume). 🧪 (`dry`): show it, take nothing."""
        if dry:
            body = self.loaded_body()
            if body is None and self.mcp_mode:
                body = self.sample().get("cart")                # the cart the path was learned on
            if body is None:
                self.toast("nothing is loaded yet", title="🎯 Catapult")
                return False
            return self._dry(body)
        self.paused = self.held = False
        self.waiting = ""
        body = self.load.take(self.wait_for, force=True)
        if body is not None:
            self.queue.push(body)
        elif self.failed:
            self.queue.push(self.failed["body"], self.failed.get("start", 0), front=True)
            self.failed = None
        elif not len(self.queue):
            self.toast("nothing is loaded yet", title="🎯 Catapult")
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
        if self.mcp_mode:
            return self._shoot_mcp(body, start)
        url = str(self.config.get("url") or "")
        if self.simulated or not url:
            self._done(cp.dry_run(url or "(no url set)", str(self.config.get("method") or "POST"), body))
            return True
        if self.config.get("confirm"):
            self._ask(f"🎯 Send to {url}?", json.dumps(body, ensure_ascii=False)[:600], lambda: self._send(url, body), body)
            return True
        self._send(url, body)
        return True

    def _send(self, url: str, body) -> None:
        self.firing = True
        self.changed()
        method = str(self.config.get("method") or "POST")
        token = os.environ.get(str(self.config.get("token_env") or ""), "")
        opener = type(self).opener

        def work() -> None:
            shot = cp.fire(url, method, body, token, *([opener] if opener else []))
            self._later(self._done, shot, body)

        threading.Thread(target=work, daemon=True, name=f"catapult-{self.building_id}").start()

    def _dry(self, body) -> bool:
        problems = cp.check(body, self.schema_path)
        if problems:
            # a dry run that fails the check is still a dry run: nothing failed downstream, Fire is unchanged
            self._done(cp.Shot(_now(), False, 0, "", str(body)[:2000], error="; ".join(problems), dry=True), body=None)
            return False
        if self.browser:
            parts = []
            for form in self.forms:
                p = self.form_plan(form, body)
                parts.append(f"[{form.name}] " + (cw.describe(p, body) if p else "not scouted yet — Scout finds it"))
            self._done(cp.dry_run_form(", ".join(f.name for f in self.forms) or "(no forms)", "\n\n".join(parts), body))
            return True
        if self.mcp_mode:
            where, what = self.dry_text(body)
            shot = cp.Shot(_now(), not what.startswith("✗"), 0, where, json.dumps(body, ensure_ascii=False, indent=2)[:2000],
                           what[:cp.ANSWER_KEEP], what[2:200] if what.startswith("✗") else "", dry=True, track="dry")
            self._done(shot)
            return True
        url = str(self.config.get("url") or "")
        self._done(cp.dry_run(url or "(no url set)", str(self.config.get("method") or "POST"), body))
        return True

    def check_now(self) -> tuple[object, list[str]]:
        """The loaded body and what the schema says of it now (no shot)."""
        body = self.loaded_body()
        return body, (cp.check(body, self.schema_path) if body is not None else [])

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
        root, out = self.repo_root, set()
        for bid, spec in (self.town.custom_specs or {}).items():
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
                return self._problem(body, form.url, f"{form.name}: not scouted yet — Scout finds it", start)
            if not p.steps:
                return self._problem(body, form.url, f"{form.name}: no field matches the cart — set fields or Map fields", start)
            if press and not self._submit(form):
                return self._problem(body, form.url, f"{form.name}: no submit button known — scout again or name it in forms", start)
            filled, problems = cw.resolve_files(body, p.steps, self.repo_root, pending, self.state_dir / "downloads")
            if problems:
                return self._problem(body, form.url, f"{form.name}: " + "; ".join(problems), start)
            script = self.write_script(form, body)
            if script is not None and script.name != "fill.py":
                script = script.parent / "fill.py"        # edited by hand: the operator's version runs
            url = str((cw.load_map(self.fdir(form)) or {}).get("url") or form.url)
            runs.append((i, form, script, url, filled, cw.describe(p, body)))
        if self.config.get("confirm"):
            self._ask(f"🎯 Fill {label}?", "\n\n".join(f"[{f.name}] {d}" for _, f, _, _, _, d in runs)[:900],
                      lambda: self._run_forms(runs, body, press, retried_at), body, start)
            return True
        self._run_forms(runs, body, press, retried_at)
        return True

    def _run_forms(self, runs: list, body, press: bool, retried_at: int | None) -> None:
        self.firing = True
        total = len(self.forms)
        profile, headless = self.profile, self.headless
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

        def started(proc) -> None:
            self.proc = proc

        def work() -> None:
            answers, pictures = [], []
            for i, form, script, url, filled, _ in runs:
                self.progress, self.step = f"{i + 1}/{total}", form.name
                self.changed()
                picture = self.state_dir / "screens" / f"{stamp}-{i + 1}-{form.name}.png"
                res = cw.run_script(script, profile, filled, press, headless=headless, on_start=started, screen=picture)
                self.proc = None
                shot = cp.form_shot(url, filled, res, press)
                shot.url = f"[{form.name}] {shot.url}"
                if picture.is_file():
                    pictures.append((form.name, picture))
                if not (shot.ok and not res.summary.get("login") and not res.summary.get("broken")):
                    self._later(self._screens, shot.at, pictures)        # the run ends on this shot
                if res.summary.get("login"):
                    self._later(self._login_lost, form, str(res.summary["login"]), shot, body, i)
                elif res.summary.get("broken") and retried_at != i:
                    self._later(self._broken, form, i, shot, res.summary, body)
                elif not shot.ok:
                    self._later(self._done, shot, body, i)
                else:
                    cp.log(self.state_dir, shot)
                    answers.append(f"[{form.name}] {shot.answer}")
                    continue
                return
            final = cp.Shot(_now(), True, 0, ", ".join(f.name for _, f, *_ in runs), json.dumps(body, ensure_ascii=False)[:2000],
                            "\n\n".join(answers))
            self._later(self._screens, final.at, pictures)
            self._later(self._done, final, body)

        threading.Thread(target=work, daemon=True, name=f"catapult-form-{self.building_id}").start()

    # -- the screenshots ------------------------------------------------------------------------------

    def _screens(self, at: str, pictures: list[tuple[str, Path]]) -> None:
        """Keep the pictures of a run's forms with the shot it ended on (`screens.jsonl`, the newest last)."""
        if not pictures:
            return
        path = self.state_dir / "screens.jsonl"
        rows = self.screens() + [{"at": at, "form": form, "path": str(picture.relative_to(self.repo_root))}
                                 for form, picture in pictures]
        keep = rows[-SCREENS:]
        for old in rows[:-SCREENS]:
            if not any(r["path"] == old["path"] for r in keep):
                (self.repo_root / old["path"]).unlink(missing_ok=True)
        try:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        except OSError:
            pass

    def screens(self, at: str | None = None) -> list[dict]:
        """The pictures kept: [{at, form, path}], the newest last (only those of the shot `at`)."""
        try:
            lines = (self.state_dir / "screens.jsonl").read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("path") and (at is None or row.get("at") == at):
                out.append(row)
        return out

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

    # -- mapping and settings -----------------------------------------------------------------------

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

    def toggle_finish(self) -> bool:
        if not self.browser:
            return False
        finish = "leave" if self.config.get("finish") == "press" else "press"
        if not self.save_config({"finish": finish}):
            return False
        for form in self.forms:
            self.write_script(form)
        self.changed()
        return True

    def toggle_confirm(self) -> bool:
        if not self.save_config({"confirm": not self.config.get("confirm")}):
            return False
        self.changed()
        return True

    # -- after a shot -------------------------------------------------------------------------------

    def _done(self, shot: cp.Shot, body=None, start: int = 0) -> None:
        self.firing, self.progress, self.step = False, "", ""
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
        self.changed()
        self.pump()

    # -- the hut ----------------------------------------------------------------------------------

    def state_text(self) -> str:
        bits = []
        if self.firing:
            bits.append(f"filling {self.progress}" if self.browser and self.progress else
                        "waits for your yes" if self.asking else "firing…")
        if self.busy:
            bits.append(self.busy)
        if self.login_needed:
            bits.append(f"🔥 {self.login_needed}" if self.mcp_mode else f"🔥 log in again — {self.login_needed}")
        if self.paused:
            bits.append("stopped by Stop all — Resume goes on")
        if self.held:
            bits.append("a shot put off waits — Resume asks again, Drop lets it go")
        if self.waiting:
            bits.append(f"waits: {self.waiting} — Resume tries again")
        queued = len(self.queue)
        if queued:
            bits.append(f"{queued} queued")
        return " · ".join(bits)

    def _mark(self, line: str) -> str:
        return f"{GLOBE} {line}" if self.browser else line

    def mini_status(self) -> list[str]:
        load = self.load
        missing = load.missing(self.wait_for)
        lines = [self._mark("🔥 log in" if self.login_needed else
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
