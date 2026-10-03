"""🎯 The Catapult: waits for its roads, checks, and sends out.

Carts are loaded under their source buildings; when everything `wait_for` names has arrived (or
on every cart, without `wait_for`) the body is checked against `schema` and sent to `url`
(realm/catapult.py) — at once by default; `c` turns a confirmation on (the `confirm` setting).
🎯 fires what is loaded now, 🧪 shows the request without sending it. `catapult.sent` carries the
answer, `catapult.failed` the reason. The sandbox (`--demo`) never sends: it dry-runs.

Browser mode (`mode: browser`, realm/catapult_web.py), for a site with no API: `s` scouts `page` in
a visible browser (log in, open the form, close the window) and writes `fill.py`; `m` lets a model
map the cart's keys to the form's fields (labels in any language); a shot runs `fill.py`, which
fills the form and hands it to you (`finish: leave`) or presses `submit` (`finish: press`, `f`).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import catapult as cp, catapult_web as cw
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView


class CatapultView(TypedView):
    TYPE = "catapult"
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm shots on/off"),
                Binding("s", "scout", "Scout the page (browser mode)"),
                Binding("m", "map_fields", "Map fields with a model (browser mode)"),
                Binding("f", "toggle_finish", "Hand over / press submit (browser mode)")]
    opener = None                      # tests put a fake network here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.shots: list[cp.Shot] = []
        self.firing = False
        self.busy = ""                 # "scouting…", "mapping…"

    @property
    def load(self) -> cp.Load:
        return cp.Load(self.state_dir)

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
    def profile(self) -> Path:
        return self.state_dir / "profile"

    def compose_body(self) -> ComposeResult:
        yield Static("", id="cat-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="cat-shots", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="cat-detail", markup=False)

    def refresh_data(self) -> None:
        self.shots = cp.shots(self.state_dir)
        self._render_list()

    # -- loading and firing -------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        load = self.load
        load.put(payload.source, payload.value)
        if load.ready(self.wait_for):
            self.fire(auto=True)
        else:
            self._render_list()

    def fire(self, auto: bool = False, dry: bool = False) -> bool:
        load = self.load
        if not load.items:
            self.app.notify("nothing is loaded yet", title="🎯 Catapult")
            return False
        body = load.body(self.wait_for)
        problems = cp.check(body, self.schema_path)
        if problems:
            self._done(cp.Shot(dt.datetime.now().isoformat(timespec="seconds"), False, 0,
                               str(self.config.get("url", "")), str(body)[:2000], error="; ".join(problems)),
                       clear=False)
            return False
        if self.browser:
            return self._fire_form(body, dry)
        url = str(self.config.get("url") or "")
        if dry or self.simulated or not url:
            self._done(cp.dry_run(url or "(no url set)", str(self.config.get("method") or "POST"), body), clear=False)
            return True
        if self.config.get("confirm"):
            self.app.push_screen(Confirm(f"🎯 Send to {url}?", json.dumps(body, ensure_ascii=False)[:600]),
                                 lambda yes: self._send(url, body) if yes else None)
            return True
        self._send(url, body)
        return True

    def _send(self, url: str, body) -> None:
        self.firing = True
        self._render_list()
        method = str(self.config.get("method") or "POST")
        token = os.environ.get(str(self.config.get("token_env") or ""), "")
        opener, app = type(self).opener, self.app

        def work() -> None:
            shot = cp.fire(url, method, body, token, *([opener] if opener else []))
            try:
                app.call_from_thread(self._done, shot)
            except Exception:
                self.firing = False

        threading.Thread(target=work, daemon=True, name=f"catapult-{self.building_id}").start()

    # -- browser mode -------------------------------------------------------------------------------

    def _keys(self, body=None) -> dict[str, object]:
        """The cart's keys with sample values: the loaded body, else the schema's properties."""
        if body is None and self.load.items:
            body = self.load.body(self.wait_for)
        if body is not None:
            return cw.leaves(body)
        try:
            schema = json.loads(self.schema_path.read_text(encoding="utf-8")) if self.schema_path else {}
        except (OSError, ValueError):
            schema = {}
        return {k: "" for k in cw.schema_paths(schema)}

    def form_plan(self, body=None) -> cw.Plan | None:
        page_map = cw.load_map(self.state_dir)
        if page_map is None:
            return None
        return cw.plan(page_map, list(self._keys(body)), [str(x) for x in self.config.get("fields") or []],
                       cw.load_mapping(self.state_dir))

    def write_script(self, body=None) -> Path | None:
        page_map, p = cw.load_map(self.state_dir), self.form_plan(body)
        if page_map is None or p is None:
            return None
        return cw.write_script(self.state_dir, cw.script_text(page_map, p, str(self.config.get("submit") or ""),
                                                              str(self.config.get("finish") or "leave")))

    def _form_url(self) -> str:
        page_map = cw.load_map(self.state_dir)
        return str((page_map or {}).get("url") or self.config.get("page") or "")

    def _fire_form(self, body, dry: bool) -> bool:
        p = self.form_plan(body)
        url = self._form_url() or "(no page scouted)"
        if p is None:
            self._done(cp.Shot(dt.datetime.now().isoformat(timespec="seconds"), False, 0, url, str(body)[:2000],
                               error="the page is not scouted yet — set page and press s"), clear=False)
            return False
        if dry or self.simulated:
            self._done(cp.dry_run_form(url, cw.describe(p, body), body), clear=False)
            return True
        if not p.steps:
            self._done(cp.Shot(dt.datetime.now().isoformat(timespec="seconds"), False, 0, url, str(body)[:2000],
                               error="no field matches the cart — set fields or press m"), clear=False)
            return False
        script = self.write_script(body)
        if script is not None and script.name != "fill.py":
            script = script.parent / "fill.py"          # edited by hand: the operator's version runs
        if self.config.get("confirm"):
            self.app.push_screen(Confirm(f"🎯 Fill the form at {url}?", cw.describe(p, body)[:600]),
                                 lambda yes: self._send_form(script, url, body) if yes else None)
            return True
        self._send_form(script, url, body)
        return True

    def _send_form(self, script: Path, url: str, body) -> None:
        self.firing = True
        self._render_list()
        press = self.config.get("finish") == "press"
        profile, app = self.profile, self.app

        def work() -> None:
            res = cw.run_script(script, profile, body, press, headless=bool(os.environ.get("ORKCRAFT_HEADLESS")))
            shot = cp.form_shot(url, body, res, press)
            try:
                app.call_from_thread(self._done, shot)
            except Exception:
                self.firing = False

        threading.Thread(target=work, daemon=True, name=f"catapult-form-{self.building_id}").start()

    def action_scout(self) -> None:
        page = str(self.config.get("page") or "")
        if not self.browser or not page:
            self.app.notify("set mode: browser and page first", title="🎯 Catapult")
            return
        if self.simulated:
            self.app.notify("the sandbox opens no browsers", title="🎯 Catapult")
            return
        if self.busy:
            return
        self.busy = "scouting… close the browser window when the form is open"
        self._render_list()
        app, state, profile = self.app, self.state_dir, self.profile
        headless = bool(os.environ.get("ORKCRAFT_HEADLESS"))

        def work() -> None:
            try:
                page_map, error = cw.scout(page, profile, watch=not headless, headless=headless), ""
            except Exception as e:              # no playwright, no display, no fields — all said the same way
                page_map, error = None, str(e)[:300]
            try:
                app.call_from_thread(self._scouted, page_map, error)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-scout-{self.building_id}").start()

    def _scouted(self, page_map: dict | None, error: str) -> None:
        self.busy = ""
        if page_map is None:
            self.app.notify(error, title="🔭 Scout", severity="error")
            self._render_list()
            return
        cw.save_map(self.state_dir, page_map)
        script = self.write_script()
        p = self.form_plan()
        path = cw.path_text(page_map)
        self.app.notify(f"{len(page_map['fields'])} fields, {len(page_map.get('buttons') or [])} buttons; "
                        f"{len(p.steps) if p else 0} matched → {script.name if script else 'no script'}"
                        + (f"\nreached by: {path}" if path else ""), title="🔭 Scout")
        self._render_list()

    def action_map_fields(self) -> None:
        page_map = cw.load_map(self.state_dir)
        keys = self._keys()
        if not self.browser or page_map is None:
            self.app.notify("scout the page first (s)", title="🎯 Catapult")
            return
        if not keys:
            self.app.notify("load a cart or set schema — the model needs the keys", title="🎯 Catapult")
            return
        if self.simulated or self.busy:
            return
        self.busy = "mapping fields…"
        self._render_list()
        app = self.app

        def work() -> None:
            try:
                mapping, error = cw.map_with_model(page_map, keys)[0], ""
            except Exception as e:
                mapping, error = None, str(e)[:300]
            try:
                app.call_from_thread(self._mapped, mapping, error)
            except Exception:
                self.busy = ""

        threading.Thread(target=work, daemon=True, name=f"catapult-map-{self.building_id}").start()

    def _mapped(self, mapping: dict | None, error: str) -> None:
        self.busy = ""
        if mapping is None:
            self.app.notify(error, title="🧠 Map", severity="error")
        else:
            cw.save_mapping(self.state_dir, mapping)
            script = self.write_script()
            self.app.notify(f"{len(mapping)} fields mapped → {script.name if script else 'no script'}", title="🧠 Map")
        self._render_list()

    def action_toggle_finish(self) -> None:
        if not self.browser:
            return
        finish = "leave" if self.config.get("finish") == "press" else "press"
        if finish == "press" and not self.config.get("submit"):
            self.app.notify("set submit — the text of the button to press", title="🎯 Catapult")
            return
        if self.save_config({"finish": finish}):
            self.write_script()
            self._render_list()

    def _done(self, shot: cp.Shot, clear: bool = True) -> None:
        self.firing = False
        cp.log(self.state_dir, shot)
        if shot.dry:
            self.refresh_data()
            return
        if shot.ok:
            self.emit("catapult.sent", f"{shot.status} {shot.url}\n\n{shot.answer}", f"{shot.status} {shot.url}")
            if clear:
                self.load.clear()
        else:
            self.emit("catapult.failed", f"{shot.error or shot.status} {shot.url}\n\n{shot.answer}".strip(),
                      shot.error or str(shot.status))
        self.refresh_data()

    def action_toggle_confirm(self) -> None:
        if self.save_config({"confirm": not self.config.get("confirm")}):
            self._render_list()

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#cat-head", Static), self.query_one("#cat-shots", OptionList)
        except Exception:
            return
        load = self.load
        url = self.config.get("url") or "no url set — 🧪 dry runs only"
        if self.browser:
            page_map = cw.load_map(self.state_dir)
            finish = "press " + repr(self.config.get("submit")) if self.config.get("finish") == "press" else "hand over"
            url = (f"🌐 {self._form_url() or 'no page set'} · "
                   + (f"{len(page_map['fields'])} fields mapped" if page_map else "not scouted (s)")
                   + f" · then {finish} (f)" + (" · fill.py edited by hand" if cw.edited_by_hand(self.state_dir) else ""))
        waits = self.wait_for
        loaded = ", ".join(f"{'✓' if s in load.items else '·'} {s}" for s in waits) if waits else \
            (f"{len(load.items)} loaded" if load.items else "fires on every cart")
        confirm = "on" if self.config.get("confirm") else "off"
        head.update(Text(("" if self.browser else f"→ {self.config.get('method') or 'POST'} ")
                         + f"{url} · {loaded} · schema "
                         f"{self.config.get('schema') or '—'} · confirm: {confirm} (c)"
                         + (" · firing…" if self.firing else "") + (f" · {self.busy}" if self.busy else ""),
                         style="dim"))
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
            p = self.form_plan()
            try:
                path = cw.path_text(cw.load_map(self.state_dir) or {})
                self.query_one("#cat-detail", Static).update(
                    (cw.describe(p) + (f"\nreached by: {path}" if path else "")) if p else "Not scouted yet: set page, press s, log in if asked, open the form "
                                             "and close the window. The Catapult marks the fields and writes fill.py.")
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

    def mini_status(self) -> list[str]:
        load = self.load
        missing = load.missing(self.wait_for)
        lines = [f"waits for {', '.join(missing)}" if missing and self.wait_for else
                 f"{len(load.items)} loaded" if load.items else "empty"]
        if self.shots:
            s = self.shots[0]
            lines.append("🧪 dry run" if s.dry else f"✓ {s.status}" if s.ok else f"✗ {(s.error or str(s.status))[:30]}")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """One short line: waiting for how many roads, or how the last shot went."""
        load, waits = self.load, self.wait_for
        if self.firing:
            return ["filling…" if self.browser else "firing…"]
        if self.busy:
            return [self.busy.split("…")[0] + "…"]
        if waits and load.missing(waits):
            return [f"wait {len(waits) - len(load.missing(waits))}/{len(waits)}"]
        if self.shots:
            s = self.shots[0]
            return ["🧪 dry" if s.dry else f"✓ {s.status}" if s.ok else f"✗ {s.status or 'err'}"]
        return ["idle"]

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
