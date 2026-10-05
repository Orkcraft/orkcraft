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

The loading, the shots, the forms and the overseer's work are the building's worker's
(core/workers/catapult.py); the view draws the shots, asks before a shot (`confirm`) and holds the
keys.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.catapult import GLOBE, CatapultWorker
from orkcraft.realm import catapult as cp, catapult_web as cw
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView


class CatapultView(TypedView):
    TYPE = "catapult"
    UI_PANES = {"head": "#cat-head", "load": "#cat-head", "shots": "#cat-shots", "forms": "#cat-detail-pane"}
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm shots on/off"),
                Binding("s", "scout", "The ork finds the forms (browser mode)"),
                Binding("l", "login", "Log in to the site (browser mode)"),
                Binding("m", "map_fields", "Map fields with a model (browser mode)"),
                Binding("f", "toggle_finish", "Hand over / press submit (browser mode)")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._asked: dict | None = None

    @property
    def worker(self) -> CatapultWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def shots(self) -> list[cp.Shot]:
        return self.worker.shots

    @property
    def firing(self) -> bool:
        return self.worker.firing

    @property
    def busy(self) -> str:
        return self.worker.busy

    @property
    def progress(self) -> str:
        return self.worker.progress

    @property
    def login_needed(self) -> str:
        return self.worker.login_needed

    @property
    def paused(self) -> bool:
        return self.worker.paused

    @property
    def failed(self) -> dict | None:
        return self.worker.failed

    @property
    def proc(self):
        return self.worker.proc

    @property
    def load(self) -> cp.Load:
        return self.worker.load

    @property
    def queue(self) -> cp.Queue:
        return self.worker.queue

    @property
    def wait_for(self) -> list[str]:
        return self.worker.wait_for

    @property
    def browser(self) -> bool:
        return self.worker.browser

    @property
    def forms(self) -> list[cw.Form]:
        return self.worker.forms

    @property
    def profile(self) -> Path:
        return self.worker.profile

    @property
    def overseer(self) -> str:
        return self.worker.overseer

    def fdir(self, form: cw.Form | str) -> Path:
        return self.worker.fdir(form)

    def form_plan(self, form: cw.Form, body=None) -> cw.Plan | None:
        return self.worker.form_plan(form, body)

    def write_script(self, form: cw.Form, body=None) -> Path | None:
        return self.worker.write_script(form, body)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def fire(self, auto: bool = False, dry: bool = False) -> bool:
        return self.worker.fire(auto, dry)

    def halt(self) -> int:
        return self.worker.halt()

    def status(self) -> str:
        return self.worker.status()

    def _logged_in(self, form: cw.Form, snap: dict | None, error: str) -> None:
        self.worker.logged_in(form, snap, error)

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="cat-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="cat-shots", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="cat-detail-pane"):
                yield Static("", id="cat-detail", markup=False, classes="-as-written")

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()
        refresh = getattr(getattr(self, "app", None), "refresh_roster", None)
        if callable(refresh):                    # a site that wants a login burns the hut
            try:
                refresh()
            except Exception:
                pass
        asking = self.worker.asking
        if asking and asking is not self._asked:    # a shot waits for a yes (`confirm`)
            self._asked = asking
            self.app.push_screen(Confirm(asking["title"], asking["text"]), lambda yes: self.worker.answer(bool(yes)))
        elif not asking:
            self._asked = None

    # -- the keys -----------------------------------------------------------------------------------

    def action_scout(self) -> None:
        self.worker.scout()

    def action_login(self) -> None:
        self.worker.login()

    def action_map_fields(self) -> None:
        self.worker.map_fields()

    def action_toggle_finish(self) -> None:
        self.worker.toggle_finish()

    def action_toggle_confirm(self) -> None:
        self.worker.toggle_confirm()

    def orders_alert(self):
        """The hut's 🔥: the site wants a login (the app shows it as the lead ork's alert)."""
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
        state = self.worker.state_text()
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

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

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
