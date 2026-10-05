"""🚏 The Signpost: rules send what arrives down one of its roads, no model.

The rules (realm/signpost.py) are read top to bottom; the first that matches names the route, and
the cart goes out as `signpost.routed` with that route — each road from the Signpost waits for its own
route (Y on the receiver offers one road per route). No rule → `signpost.unmatched`. `e` edits the
rules. The open building shows the rules and what went where.

The routing and its log are the building's worker's (core/workers/signpost.py); the view draws
them and holds the keys.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.signpost import HELP, KEEP, SignpostWorker  # noqa: F401 (old names)
from orkcraft.realm import signpost
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView


class SignpostView(TypedView):
    TYPE = "signpost"
    UI_PANES = {"rules": "#signpost-rules", "test": "#signpost-rules", "history": "#signpost-history",
                "cart": "#signpost-cart"}
    BINDINGS = [Binding("e", "edit_rules", "Edit rules")]

    @property
    def worker(self) -> SignpostWorker:
        return super().worker

    @property
    def history(self) -> list[dict]:
        return self.worker.history

    @property
    def rules_text(self) -> list[str]:
        return self.worker.rules_text

    @property
    def log_file(self):
        return self.worker.log_file

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def status(self) -> str:
        return self.worker.status()

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="signpost-rules", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="signpost-history", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="signpost-cart"):
                yield Static("", id="signpost-detail", markup=False)

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#signpost-rules", Static), self.query_one("#signpost-history", OptionList)
        except Exception:
            return
        rules, problems = signpost.rules_of(self.rules_text)
        t = Text()
        for r in self.rules_text:
            t.append(f"🚏 {r}\n")
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
            self.query_one("#signpost-detail", Static).update(
                f"from {h.get('source', '?')} · {h.get('event', '')}\nroute: {h['route'] or '— none matched'}\n\n"
                f"{h.get('value', '')[:3000]}")
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "signpost-history" and event.option_index < len(self.history):
            event.stop()
            self._show(self.history[event.option_index])

    def action_edit_rules(self) -> None:
        def done(text: str | None) -> None:
            if text is not None and self.worker.set_rules(text.splitlines()):
                self.spec = self.worker.spec
                self._render_list()

        self.app.push_screen(TextBlock("🚏 The Signpost — rules, first match wins", "\n".join(self.rules_text), HELP), done)

    # -- the hut ----------------------------------------------------------------------------------

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()
