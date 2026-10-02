"""📦 Loot Vault: files agents generated, accepted or rejected one by
one — and the finished things that came by road, kept with when and what they cost.

Left: the changed files of the working tree (or of its `path`), * for not reviewed. Right: the
diff or the new file. `a` accepts the highlighted file, `r` rejects it (rolled back, its content
kept under `.orkcraft/generator/<id>/rejected/`); the hut's ✓ accepts every file still waiting.
Each decision sends `generator.accepted` / `generator.rejected` with the file's path. A cart that
arrives is stored (realm/vault.py) and listed below the review, `loot.stored` goes on.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import generated, vault
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
MARK = {"A": ("+", "green"), "M": ("~", "yellow"), "D": ("−", "red")}


class GeneratorView(TypedView):
    TYPE = "loot"
    BINDINGS = [Binding("a", "accept", "Accept"), Binding("r", "reject", "Reject")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.rows: list[generated.Generated] = []
        self.stored: list[vault.Stored] = []
        self.error = ""

    @property
    def review(self) -> generated.Review:
        return generated.Review(self._get_repo_root(), self.state_dir, str(self.config.get("path", "")))

    def compose_body(self) -> ComposeResult:
        yield Static("", id="gen-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="gen-files", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="gen-preview")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- the list ---------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        try:
            self.rows, self.error = self.review.files(), ""
        except (RuntimeError, OSError, ValueError) as e:
            self.rows, self.error = [], str(e)[:200]
        self.stored = vault.stored(self.state_dir)
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#gen-head", Static), self.query_one("#gen-files", OptionList)
        except Exception:
            return
        waiting = sum(not g.reviewed for g in self.rows)
        scope = self.config.get("path") or "the working tree"
        head.update(Text(f"⚠ {self.error}", style="yellow") if self.error else
                    Text(f"{waiting} to review in {scope} · a accept · r reject", style="dim"))
        keep = self.selected_path()
        lst.clear_options()
        for g in self.rows:
            mark, style = MARK.get(g.change, ("~", "yellow"))
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("* " if not g.reviewed else "✓ ", style="bold" if not g.reviewed else "green")
            row.append(f"{mark} ", style=style)
            row.append(g.path, style="" if not g.reviewed else "dim")
            lst.add_option(Option(row, id=g.path))
        if self.stored:
            spent = sum(x.cost or 0 for x in self.stored)
            lst.add_option(Option(Text(f"── stored · {len(self.stored)}" + (f" · ${spent:.2f}" if spent else ""),
                                       style="bold dim"), disabled=True))
            for i, x in enumerate(self.stored):
                row = Text(no_wrap=True, overflow="ellipsis")
                row.append("📦 ", style="")
                row.append(f"{x.at[5:16].replace('T', ' ')} ", style="dim")
                row.append(x.title)
                row.append(f"  {x.source}" + (f" · ${x.cost:.2f}" if x.cost else ""), style="dim")
                lst.add_option(Option(row, id=f"stored:{i}"))
        paths = [g.path for g in self.rows]
        if paths:
            lst.highlighted = paths.index(keep) if keep in paths else 0
            self._preview(paths[lst.highlighted])
        elif self.stored:
            lst.highlighted = 1
            self._preview_stored(0)
        else:
            self.query_one("#gen-preview", Static).update(Text("Nothing generated or stored yet.", style="dim"))

    def selected_path(self) -> str | None:
        try:
            lst = self.query_one("#gen-files", OptionList)
        except Exception:
            return None
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return None
        oid = lst.get_option_at_index(lst.highlighted).id
        return None if not oid or oid.startswith("stored:") else oid       # only files under review

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "gen-files" and event.option.id:
            event.stop()
            if event.option.id.startswith("stored:"):
                self._preview_stored(int(event.option.id[7:]))
            else:
                self._preview(event.option.id)

    def _preview_stored(self, i: int) -> None:
        x = self.stored[i]
        try:
            body = (self._get_repo_root() / x.path).read_text(encoding="utf-8", errors="replace")[:20000]
        except OSError as e:
            body = str(e)
        head = Text(f"{x.path}\nfrom {x.source} · {x.at.replace('T', ' ')} · {x.bytes} bytes"
                    + (f" · ${x.cost:.2f}" if x.cost else "") + "\n\n", style="bold")
        try:
            self.query_one("#gen-preview", Static).update(head + Text(body))
        except Exception:
            pass

    def receive(self, payload, title: str, markdown: str) -> None:
        """A finished thing came by road: kept in the vault, `loot.stored` goes on."""
        item = vault.store(self._get_repo_root(), self.building_id, self.state_dir, payload.kind,
                           markdown if payload.kind == "text" and markdown else payload.value,
                           payload.title or title, payload.source)
        self.emit("loot.stored", item.path, item.title)
        self.refresh_data()

    def _preview(self, rel: str) -> None:
        try:
            text = self.review.preview(rel)
        except (RuntimeError, OSError, ValueError) as e:
            text = str(e)
        out = Text()
        is_diff = text.startswith("diff --git")
        for line in text.splitlines():
            style = ""
            if is_diff:
                style = ("bold" if line.startswith(("diff ", "index ", "+++", "---")) else
                         "green" if line.startswith("+") else "red" if line.startswith("-") else
                         "cyan" if line.startswith("@@") else "")
            out.append(line + "\n", style=style)
        try:
            self.query_one("#gen-preview", Static).update(out)
        except Exception:
            pass

    # -- decisions ----------------------------------------------------------------------------------

    def accept(self, rel: str) -> None:
        self.review.accept(rel)
        self.emit("generator.accepted", rel, rel)

    def reject(self, rel: str) -> None:
        self.review.reject(rel)
        self.emit("generator.rejected", rel, rel)

    def action_accept(self) -> None:
        rel = self.selected_path()
        if rel:
            self.accept(rel)
            self.refresh_data()

    def action_reject(self) -> None:
        rel = self.selected_path()
        if not rel:
            return
        try:
            self.reject(rel)
        except (RuntimeError, OSError, ValueError) as e:
            self.app.notify(str(e), title="🛠 Reject failed", severity="error")
        self.refresh_data()

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        waiting = [g for g in self.rows if not g.reviewed]
        stored = [f"📦 {len(self.stored)} stored"] if self.stored else []
        if not self.rows:
            return stored or ["nothing generated"]
        lines = [f"{len(waiting)} to review" if waiting else "all reviewed ✓"] + stored
        lines += [f"* {g.path.rsplit('/', 1)[-1]}" for g in waiting[:3]]
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id != "generator.accept_all":
            return False
        waiting = [g.path for g in self.rows if not g.reviewed]
        for rel in waiting:
            self.accept(rel)
        self.refresh_data()
        self.app.notify(f"{len(waiting)} file{'s' if len(waiting) != 1 else ''} accepted", title="🛠 File Generator")
        return True
