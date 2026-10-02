"""🗿 The Totem: rules send what arrives down one of its roads, no model.

The rules (realm/totem.py) are read top to bottom; the first that matches names the route, and
the cart goes out as `totem.routed` with that route — each road from the Totem waits for its own
route (Y on the receiver offers one road per route). No rule → `totem.unmatched`. `e` edits the
rules. The open building shows the rules and what went where.
"""
from __future__ import annotations

import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import jobs, totem
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

KEEP = 100
HELP = ("route: contains text · route: matches regex · route: kind text|file|node · route: source building · "
        "route: event id · route: field == value · route: field != value · route: else")


class TotemView(TypedView):
    TYPE = "totem"
    BINDINGS = [Binding("e", "edit_rules", "Edit rules")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.history: list[dict] = []

    @property
    def rules_text(self) -> list[str]:
        return [str(r) for r in (self.config.get("rules") or [])]

    @property
    def log_file(self):
        return self.state_dir / "routes.jsonl"

    def compose_body(self) -> ComposeResult:
        yield Static("", id="totem-rules", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="totem-history", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="totem-detail", markup=False)

    def refresh_data(self) -> None:
        try:
            lines = self.log_file.read_text(encoding="utf-8").splitlines()[-KEEP:]
            self.history = [json.loads(x) for x in reversed(lines)]
        except (OSError, ValueError):
            self.history = []
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#totem-rules", Static), self.query_one("#totem-history", OptionList)
        except Exception:
            return
        rules, problems = totem.rules_of(self.rules_text)
        t = Text()
        for r in self.rules_text:
            t.append(f"🗿 {r}\n")
        if not self.rules_text:
            t.append("no rules yet — e edits them\n", style="dim")
        for p in problems:
            t.append(f"⚠ {p}\n", style="yellow")
        head.update(t)
        lst.clear_options()
        for h in self.history:
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{h['at'][11:16]} ")
            row.append(f"→ {h['route'] or '∅ no rule'}  ", style="bold green" if h["route"] else "yellow")
            row.append(h.get("title", ""), style="dim")
            lst.add_option(Option(row))
        if self.history:
            lst.highlighted = 0
            self._show(self.history[0])

    def _show(self, h: dict) -> None:
        try:
            self.query_one("#totem-detail", Static).update(
                f"from {h.get('source', '?')} · {h.get('event', '')}\nroute: {h['route'] or '— none matched'}\n\n"
                f"{h.get('value', '')[:3000]}")
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "totem-history" and event.option_index < len(self.history):
            event.stop()
            self._show(self.history[event.option_index])

    # -- routing ------------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        rules, _ = totem.rules_of(self.rules_text)
        route = totem.route(rules, payload)
        rec = {"at": jobs.now_iso(), "route": route or "", "source": payload.source, "event": payload.mode,
               "title": payload.title or title, "value": payload.value[:4000]}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if route:
            self.emit("totem.routed", payload.value, route)
        else:
            self.emit("totem.unmatched", payload.value, payload.title or title)
        self.refresh_data()

    def action_edit_rules(self) -> None:
        def done(text: str | None) -> None:
            if text is None:
                return
            rules = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if self.save_config({"rules": rules}):
                self._render_list()

        self.app.push_screen(TextBlock("🗿 The Totem — rules, first match wins", "\n".join(self.rules_text), HELP), done)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        routes = totem.routes(self.rules_text)
        lines = [f"routes: {', '.join(routes)}" if routes else "no rules yet"]
        if self.history:
            h = self.history[0]
            lines.append(f"last → {h['route'] or '∅'}")
        return lines
