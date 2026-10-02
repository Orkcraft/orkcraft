"""🎯 The Catapult: waits for its roads, checks, and sends out.

Carts are loaded under their source buildings; when everything `wait_for` names has arrived (or
on every cart, without `wait_for`) the body is checked against `schema` and sent to `url`
(realm/catapult.py) — at once by default; `c` turns a confirmation on (the `confirm` setting).
🎯 fires what is loaded now, 🧪 shows the request without sending it. `catapult.sent` carries the
answer, `catapult.failed` the reason. The sandbox (`--demo`) never sends: it dry-runs.
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

from orkcraft.realm import catapult as cp
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView


class CatapultView(TypedView):
    TYPE = "catapult"
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm shots on/off")]
    opener = None                      # tests put a fake network here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.shots: list[cp.Shot] = []
        self.firing = False

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
        waits = self.wait_for
        loaded = ", ".join(f"{'✓' if s in load.items else '·'} {s}" for s in waits) if waits else \
            (f"{len(load.items)} loaded" if load.items else "fires on every cart")
        confirm = "on" if self.config.get("confirm") else "off"
        head.update(Text(f"→ {self.config.get('method') or 'POST'} {url} · {loaded} · schema "
                         f"{self.config.get('schema') or '—'} · confirm: {confirm} (c)"
                         + (" · firing…" if self.firing else ""), style="dim"))
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

    def quick_action(self, action_id: str) -> bool:
        if action_id == "catapult.fire":
            self.fire()
            return True
        if action_id == "catapult.dry_run":
            self.fire(dry=True)
            return True
        return False
