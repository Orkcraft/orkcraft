"""📦 Loot: the review checkpoint on a road (realm/gate.py), and the files agents changed.

A cart that arrives is checked against the building's rules: it passes at once (`loot.passed`
carries it on, it is kept in the vault) or it is held in the queue. On a held cart `a` accepts it
(it passes), `e` lets the person edit a text cart and accept their version, `r` asks for a reason
(a chip and a note) and sends it back to its source for rework — after `max_rework` rounds it
stays here as *needs you* — and `d` drops it. A held cart sets the hut on 🔥 like an ork waiting
for orders.

Every decision is also what the person thinks of the building that made the cart (the last hop
of its trail), kept by `feedback.signal`: accepted as it was is a light 👍; accepted after an edit
is read by `realm/edits.py` — only added to is a 👍 too, fixed, reformatted or rewritten is a 👎
with the edit, the person's version kept as an example; sent back, dropped or past the rework
limit is a 👎, and a reason of "what came in was wrong" blames the hops before the maker. A cart
that passed by the rules and goes nowhere waits to be read: nobody opening this Loot for a day
counts as unused (`feedback.await_view`). A cart no ork worked on (no trail) teaches nobody.

Below the queue: the changed files of the working tree (or of its `path`), * for not reviewed;
`a` accepts the highlighted file, `r` rejects it (rolled back, its content kept under
`.orkcraft/generator/<id>/rejected/`), `u` brings a rejected file back. Then what passed and was
kept (realm/vault.py), with what its chain cost.

Under a waiting cart: the files its task committed on its branch (the trail names the worktree and
the branch), each with its diff or content. `o` opens the highlighted file in the system viewer —
a file only on the branch is copied out first.

The checkpoint, the decisions and the files are the building's worker's (core/workers/loot.py);
the view draws the list and the preview, asks for an edit or a reason and holds the keys.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.loot import LootWorker, label as _label
from orkcraft.realm import gate, generated, pipes, vault
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
MARK = {"A": ("+", "green"), "M": ("~", "yellow"), "D": ("−", "red")}
STATUS = {gate.NEEDS_YOU: ("🔥", "bold red", "needs you"), gate.HELD: ("⏸", "bold yellow", "held"),
          gate.REWORK: ("↩", "cyan", "in rework")}

class GeneratorView(TypedView):
    TYPE = "loot"
    BINDINGS = [Binding("a", "accept", "Accept"), Binding("e", "edit", "Edit"), Binding("r", "reject", "Reject / rework"),
                Binding("d", "drop", "Drop"), Binding("u", "restore", "Restore"), Binding("o", "open", "Open")]

    UI_PANES = {"head": "#gen-head", "queue": "#gen-files", "cart": "#gen-preview-pane"}

    @property
    def worker(self) -> LootWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def rows(self) -> list[generated.Generated]:
        return self.worker.rows

    @property
    def stored(self) -> list[vault.Stored]:
        return self.worker.stored

    @property
    def rejected(self) -> list[dict]:
        return self.worker.rejected

    @property
    def branches(self) -> dict:
        return self.worker.branches

    @property
    def error(self) -> str:
        return self.worker.error

    @property
    def review(self) -> generated.Review:
        return self.worker.review

    @property
    def queue(self) -> gate.Queue:
        return self.worker.queue

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def maker(self, item: gate.Item) -> str:
        return self.worker.maker(item)

    def accept_item(self, item: gate.Item, value: str | None = None, source: str = "loot.accepted") -> None:
        self.worker.accept_item(item, value, source)

    def rework_item(self, item: gate.Item, reason: str, tag: str = "") -> str:
        return self.worker.rework_item(item, reason, tag)

    def burning(self) -> bool:
        return self.worker.burning()

    def accept(self, rel: str) -> None:
        self.worker.accept(rel)

    def reject(self, rel: str) -> None:
        self.worker.reject(rel)

    def status(self) -> str:
        return self.worker.status()

    def compose_body(self) -> ComposeResult:
        yield Static("", id="gen-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="gen-files", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="gen-preview-pane"):
                yield Static("", id="gen-preview", classes="-as-written")

    def on_mount(self) -> None:
        w = self.worker                  # a cart goes back (or an approval) to the building's view
        w.rework_back = lambda source, payload: self.app.return_for_rework(source, payload)
        w.approved_back = lambda source, payload: self.app.return_approved(source, payload)
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- the list ---------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()
        refresh = getattr(getattr(self, "app", None), "refresh_roster", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#gen-head", Static), self.query_one("#gen-files", OptionList)
        except Exception:
            return
        waiting = sum(not g.reviewed for g in self.rows)
        open_items = self.queue.open()
        scope = self.config.get("path") or "the working tree"
        if self.error:
            head.update(Text(f"⚠ {self.error}", style="yellow"))
        else:
            q = f"{len(open_items)} in the queue · " if open_items else ""
            head.update(Text(f"{q}{waiting} files to review in {scope} · a accept · e edit · r reject / rework · d drop · "
                             "u restore · o open", style="dim"))
        keep = self._highlighted_id()
        lst.clear_options()
        ids: list[str] = []

        def add(option: Option) -> None:
            lst.add_option(option)
            ids.append(option.id or "")

        if open_items:
            add(Option(Text(f"── queue · {len(open_items)}", style="bold dim"), disabled=True))
            for it in open_items:
                icon, style, _ = STATUS[it.status]
                row = Text(no_wrap=True, overflow="ellipsis")
                row.append(f"{icon} ", style=style)
                row.append(_label(it))
                spent = pipes.spent(it.tokens, it.cost)
                row.append(f"  {it.source}" + (f" · {spent}" if spent else "")
                           + (f" · ↩{it.attempts}" if it.attempts else ""), style="dim")
                add(Option(row, id=f"q:{it.id}"))
                if it.id in self.branches:
                    for g in self.branches[it.id][1]:
                        mark, style = MARK.get(g.change, ("~", "yellow"))
                        sub = Text(no_wrap=True, overflow="ellipsis")
                        sub.append(f"   {mark} ", style=style)
                        sub.append(g.path)
                        add(Option(sub, id=f"bf:{it.id}:{g.path}"))
        if self.rows and open_items:
            add(Option(Text(f"── files · {len(self.rows)}", style="bold dim"), disabled=True))
        for g in self.rows:
            mark, style = MARK.get(g.change, ("~", "yellow"))
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("* " if not g.reviewed else "✓ ", style="bold" if not g.reviewed else "green")
            row.append(f"{mark} ", style=style)
            row.append(g.path, style="" if not g.reviewed else "dim")
            add(Option(row, id=g.path))
        if self.rejected:
            add(Option(Text(f"── rejected · {len(self.rejected)} · u restores", style="bold dim"), disabled=True))
            for i, r in enumerate(self.rejected):
                row = Text(no_wrap=True, overflow="ellipsis")
                row.append("✗ ", style="red")
                row.append(r["path"])
                row.append(f"  {r['at'][4:6]}-{r['at'][6:8]} {r['at'][9:11]}:{r['at'][11:13]}", style="dim")
                add(Option(row, id=f"rej:{i}"))
        if self.stored:
            toks = [x.tokens for x in self.stored if x.tokens is not None]
            costs = [x.cost for x in self.stored if x.cost is not None]
            spent = pipes.spent(sum(toks) if toks else None, sum(costs) if costs else None)
            add(Option(Text(f"── passed · {len(self.stored)}" + (f" · {spent}" if spent else ""),
                            style="bold dim"), disabled=True))
            for i, x in enumerate(self.stored):
                row = Text(no_wrap=True, overflow="ellipsis")
                row.append("📦 ", style="")
                row.append(f"{x.at[5:16].replace('T', ' ')} ", style="dim")
                row.append(x.title)
                each = pipes.spent(x.tokens, x.cost)
                row.append(f"  {x.source}" + (f" · {each}" if each else ""), style="dim")
                add(Option(row, id=f"stored:{i}"))
        selectable = [i for i, oid in enumerate(ids) if oid]
        if not selectable:
            self.query_one("#gen-preview", Static).update(Text("Nothing held, generated or passed yet.", style="dim"))
            return
        lst.highlighted = ids.index(keep) if keep in ids else selectable[0]
        self._show(ids[lst.highlighted])

    def _highlighted_id(self) -> str | None:
        try:
            lst = self.query_one("#gen-files", OptionList)
        except Exception:
            return None
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return None
        return lst.get_option_at_index(lst.highlighted).id

    def selected_path(self) -> str | None:
        oid = self._highlighted_id()
        return None if not oid or ":" in oid else oid       # only files under review

    def selected_item(self) -> gate.Item | None:
        oid = self._highlighted_id()
        return self.queue.get(oid[2:]) if oid and oid.startswith("q:") else None

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "gen-files" and event.option.id:
            event.stop()
            self._show(event.option.id)

    def _show(self, oid: str) -> None:
        if oid.startswith("q:"):
            item = self.queue.get(oid[2:])
            if item is not None:
                self._preview_item(item)
        elif oid.startswith("stored:"):
            self._preview_stored(int(oid[7:]))
        elif oid.startswith("bf:"):
            if (found := self._branch_file(oid)) is not None:
                br, rel = found
                head = Text(f"{rel} — on {br.branch}\n\n", style="bold")
                try:
                    text = br.preview(rel)
                except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
                    text = str(e)
                self._update(head + self._styled(text))
        elif oid.startswith("rej:"):
            r = self.rejected[int(oid[4:])]
            self._update(Text(f"{r['path']} — rejected {r['at']}\nu brings it back\n", style="bold"))
        else:
            self._preview(oid)

    def _update(self, text: Text) -> None:
        try:
            self.query_one("#gen-preview", Static).update(text)
        except Exception:
            pass

    def _preview_item(self, item: gate.Item) -> None:
        _, style, label = STATUS.get(item.status, ("", "", item.status))
        out = Text()
        out.append(f"{label.upper()}", style=style)
        out.append(f" · {item.title or item.ref} · from {item.source}\n", style="bold")
        out.append(f"why: {'; '.join(item.why)}\n", style="")
        chain = pipes.trail_line(item.hops, self._names())
        if chain:
            out.append(f"{chain}\n", style="dim")
        if item.worktree:
            out.append(f"worktree: {item.worktree}\n", style="dim")
        if item.id in self.branches:
            br, files = self.branches[item.id]
            out.append(f"{len(files)} file{'s' if len(files) != 1 else ''} on {br.branch} — listed below, "
                       "o opens the highlighted one\n", style="dim")
        for n in item.notes:
            out.append(f"↩ {n}\n", style="cyan")
        out.append("\n")
        if item.kind == pipes.TEXT:
            out.append(item.value[:20000])
        else:
            out.append(f"{item.kind}: {item.value}\n")
        self._update(out)

    def _preview_stored(self, i: int) -> None:
        x = self.stored[i]
        try:
            body = (self._get_repo_root() / x.path).read_text(encoding="utf-8", errors="replace")[:20000]
        except OSError as e:
            body = str(e)
        chain = pipes.trail_line(x.hops, self._names())
        head = Text(f"{x.path}\nfrom {x.source} · {x.at.replace('T', ' ')} · {x.bytes} bytes"
                    + (f"\n{chain}" if chain else "") + "\n\n", style="bold")
        self._update(head + Text(body))

    def _names(self) -> dict[str, str]:
        return self.worker.names()

    def _branch_file(self, oid: str) -> tuple[generated.Branch, str] | None:
        """`bf:<item>:<path>` → the branch and the file's path on it, while the branch still has it."""
        _, iid, rel = oid.split(":", 2)
        found = self.branches.get(iid)
        return (found[0], rel) if found is not None and any(g.path == rel for g in found[1]) else None

    def _preview(self, rel: str) -> None:
        try:
            text = self.review.preview(rel)
        except (RuntimeError, OSError, ValueError) as e:
            text = str(e)
        self._update(self._styled(text))

    @staticmethod
    def _styled(text: str) -> Text:
        """A diff in colour; anything else as it is."""
        out = Text()
        is_diff = text.startswith("diff --git")
        for line in text.splitlines():
            style = ""
            if is_diff:
                style = ("bold" if line.startswith(("diff ", "index ", "+++", "---")) else
                         "green" if line.startswith("+") else "red" if line.startswith("-") else
                         "cyan" if line.startswith("@@") else "")
            out.append(line + "\n", style=style)
        return out

    # -- decisions ----------------------------------------------------------------------------------

    def action_accept(self) -> None:
        if (item := self.selected_item()) is not None:
            if item.status == gate.REWORK:
                self.app.notify("it is with its source for rework", title="📦 Loot")
                return
            self.accept_item(item)
            return
        rel = self.selected_path()
        if rel:
            self.accept(rel)
            self.refresh_data()

    def action_edit(self) -> None:
        """✎ The person's version of a held text cart: saving accepts it."""
        item = self.selected_item()
        if item is None or item.status == gate.REWORK:
            return
        if item.kind != pipes.TEXT:
            self.app.notify("only a text cart is edited here", title="📦 Loot")
            return
        from orkcraft.screens.dialogs import TextBlock

        def done(text: str | None) -> None:
            if text is not None and self.queue.get(item.id) is item and item.status in gate.OPEN:
                self.accept_item(item, text)

        self.app.push_screen(TextBlock(f"✎ {item.title or item.ref}", item.value,
                                       help="ctrl+s accepts your version and sends it on · Esc cancels"), done)

    def action_reject(self) -> None:
        if (item := self.selected_item()) is not None:
            if item.status != gate.HELD:
                self.app.notify("only a held cart goes back for rework; accept or drop this one",
                                title="📦 Loot")
                return
            from orkcraft.screens.feedback_modal import ReworkModal

            def done(answer: tuple[str, str] | None) -> None:
                if answer and answer[1].strip():
                    self.rework_item(item, answer[1].strip(), answer[0])

            self.app.push_screen(ReworkModal(f"↩ Send back to {item.source} — why?", help=f"round {item.attempts + 1}"),
                                 done)
            return
        rel = self.selected_path()
        if not rel:
            return
        try:
            self.reject(rel)
        except (RuntimeError, OSError, ValueError) as e:
            self.app.notify(str(e), title="🛠 Reject failed", severity="error")
        self.refresh_data()

    def action_drop(self) -> None:
        if (item := self.selected_item()) is not None:
            self.worker.drop(item)

    def action_restore(self) -> None:
        oid = self._highlighted_id()
        if not oid or not oid.startswith("rej:"):
            return
        r = self.rejected[int(oid[4:])]
        try:
            self.worker.restore(r["path"], r["at"])
            self.app.notify(f"{r['path']} is back", title="📦 Loot")
        except (OSError, ValueError) as e:
            self.app.notify(str(e), title="📦 Restore failed", severity="error")
        self.refresh_data()

    def file_to_open(self) -> Path | None:
        """The highlighted file on disk: a branch's file copied out first; None when it is not a file."""
        oid = self._highlighted_id() or ""
        root = self._get_repo_root()
        if oid.startswith("bf:"):
            found = self._branch_file(oid)
            return found[0].export(found[1]) if found is not None else None
        if oid.startswith("stored:"):
            return root / self.stored[int(oid[7:])].path
        if oid.startswith("rej:"):
            return Path(self.rejected[int(oid[4:])]["kept"])
        if oid.startswith("q:"):
            item = self.queue.get(oid[2:])
            return root / item.value if item is not None and item.kind == pipes.FILE else None
        return generated._inside(root, oid) if oid else None

    def action_open(self) -> None:
        try:
            path = self.file_to_open()
            if path is None or not path.is_file():
                self.app.notify("highlight a file to open", title="📦 Loot")
                return
            generated.open_file(path)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
            self.app.notify(str(e), title="📦 Open failed", severity="error")

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id == "loot.accept_all":
            self.worker.accept_all()
            return True
        if action_id == "generator.accept_all":
            self.worker.accept_files()
            return True
        return False
