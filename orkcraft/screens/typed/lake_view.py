"""🌊 The Lake of Insight: the inspector.

A cart's file, diff, Markdown, URL or branch name is shown the way it reads best (realm/lake.py):
a diff side by side, Markdown rendered, a page as text. The setting `url` (a local dev server)
is shown when nothing else has arrived; ↗ opens what is shown in the browser. Each view sends
`lake.viewed`.
"""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from orkcraft.realm import lake
from orkcraft.screens.typed.base import TypedView

STYLE = {"-": ("red", ""), "+": ("", "green"), "~": ("red", "green"), "@": ("bold cyan", "bold cyan"), " ": ("", "")}
DIFF_ROWS = 2000


class LakeView(TypedView):
    TYPE = "lake"
    opener = None                  # tests catch the browser here
    fetcher = None                 # and the network

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.view: lake.View | None = None

    def compose_body(self) -> ComposeResult:
        yield Static("", id="lake-head", classes="typed-head")
        with VerticalScroll(id="lake-scroll"):
            yield Static("", id="lake-plain")
            yield Markdown("", id="lake-md")

    def on_mount(self) -> None:
        url = str(self.config.get("url") or "")
        if url and self.view is None:
            self.show_value("text", url, url)
        else:
            self._render_view()

    def receive(self, payload, title: str, markdown: str) -> None:
        self.show_value(payload.kind, payload.value, payload.title or title)

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        repo, app = self._get_repo_root(), self.app
        fetch = type(self).fetcher

        def work() -> None:
            v = lake.look(repo, kind, value, title, *([fetch] if fetch else []))
            try:
                app.call_from_thread(self.show, v)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name=f"lake-{self.building_id}").start()

    def show(self, v: lake.View) -> None:
        self.view = v
        self._render_view()
        self.emit("lake.viewed", v.target or v.title, f"{v.kind}: {v.title}")

    def _render_view(self) -> None:
        try:
            head, plain, md = (self.query_one("#lake-head", Static), self.query_one("#lake-plain", Static),
                               self.query_one("#lake-md", Markdown))
        except Exception:
            return
        v = self.view
        if v is None:
            head.update(Text("nothing to look at yet — a road brings a file, a diff, a URL or a branch", style="dim"))
            plain.update("")
            md.update("")
            return
        head.update(Text.assemble((f"{v.kind} · ", "bold"), (v.title, ""),
                                  ("  ↗ opens it in the browser" if v.target else "", "dim")))
        md.display = v.kind == "markdown"
        plain.display = v.kind != "markdown"
        if v.kind == "markdown":
            md.update(v.text)
        elif v.kind == "diff":
            table = Table(show_header=True, header_style="bold", expand=True, box=None, pad_edge=False)
            table.add_column("before", ratio=1, overflow="fold")
            table.add_column("after", ratio=1, overflow="fold")
            for left, right, change in v.rows[:DIFF_ROWS]:
                ls, rs = STYLE.get(change, ("", ""))
                table.add_row(Text(left, style=ls), Text(right, style=rs))
            plain.update(table)
        else:
            plain.update(Text(v.text))

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if self.view is None:
            return ["nothing shown"]
        v = self.view
        lines = [f"{v.kind}: {v.title.rsplit('/', 1)[-1]}"]
        if v.kind == "diff":
            plus = sum(1 for r in v.rows if r[2] in "+~")
            minus = sum(1 for r in v.rows if r[2] in "-~")
            lines.append(f"+{plus} −{minus}")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """The panorama: the left pane the diff (or the first lines of what is shown), the right
        one what it is — interleaved, row by row, as the silhouette's slots come."""
        v = self.view
        left_w, right_w = (widths[0], widths[1]) if len(widths) >= 14 else (28, 24)
        if v is None:
            left, right, last = ["nothing shown yet"], [], "open the building to look at something"
        else:
            if v.kind == "diff":
                left = []
                for l, r, c in v.rows:
                    if c == "-":
                        left.append(f"- {l}")
                    elif c == "+":
                        left.append(f"+ {r}")
                    elif c == "~":
                        left += [f"- {l}", f"+ {r}"]
                plus = sum(1 for r in v.rows if r[2] in "+~")
                minus = sum(1 for r in v.rows if r[2] in "-~")
                right = [f"kind: diff", f"+{plus} −{minus}", f"rows: {len(v.rows)}"]
            else:
                left = [ln for ln in v.text.splitlines() if ln.strip()]
                right = [f"kind: {v.kind}", f"lines: {len(v.text.splitlines())}"]
            right.insert(0, v.title.rsplit("/", 1)[-1])
            last = f"{v.kind} · {v.target or v.title}"
        out: list[str] = []
        for i in range(6):
            out.append(left[i] if i < len(left) else "")
            out.append(right[i] if i < len(right) else "")
        return out + [last]

    def quick_action(self, action_id: str) -> bool:
        if action_id != "lake.open":
            return False
        target = self.view.target if self.view else str(self.config.get("url") or "")
        if not target:
            self.app.notify("nothing to open — a URL or a file shows here first", title="🌊 Lake")
            return True
        url = target if target.startswith(("http://", "https://")) else Path(target).resolve().as_uri()
        try:
            (type(self).opener or webbrowser.open)(url)
        except Exception as e:
            self.app.notify(str(e), title="🌊 Lake", severity="error")
        return True
