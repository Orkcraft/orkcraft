"""📦 Loot: the review checkpoint on a road (realm/gate.py), and the files agents changed.

A cart that arrives is checked against the building's rules: it passes at once (`loot.passed`
carries it on, it is kept in the vault) or it is held in the queue. On a held cart `a` accepts it
(it passes), `r` asks for a reason and sends it back to its source for rework — after
`max_rework` rounds it stays here as *needs you* — and `d` drops it. A held cart sets the hut on
🔥 like an orc waiting for orders.

Below the queue: the changed files of the working tree (or of its `path`), * for not reviewed;
`a` accepts the highlighted file, `r` rejects it (rolled back, its content kept under
`.orkcraft/generator/<id>/rejected/`), `u` brings a rejected file back. Then what passed and was
kept (realm/vault.py), with what its chain cost.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import gate, generated, pipes, vault
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
MARK = {"A": ("+", "green"), "M": ("~", "yellow"), "D": ("−", "red")}
STATUS = {gate.NEEDS_YOU: ("🔥", "bold red", "needs you"), gate.HELD: ("⏸", "bold yellow", "held"),
          gate.REWORK: ("↩", "cyan", "in rework")}
EGRESS = ("catapult",)                   # types that send things out of the town


def _label(item: gate.Item) -> str:
    first = item.value.strip().splitlines()[0][:60] if item.value.strip() else ""
    return item.title or first or item.ref


class GeneratorView(TypedView):
    TYPE = "loot"
    BINDINGS = [Binding("a", "accept", "Accept"), Binding("r", "reject", "Reject / rework"),
                Binding("d", "drop", "Drop"), Binding("u", "restore", "Restore")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.rows: list[generated.Generated] = []
        self.stored: list[vault.Stored] = []
        self.rejected: list[dict] = []
        self.error = ""
        self._queue: gate.Queue | None = None

    @property
    def review(self) -> generated.Review:
        return generated.Review(self._get_repo_root(), self.state_dir, str(self.config.get("path", "")))

    @property
    def queue(self) -> gate.Queue:
        if self._queue is None:
            self._queue = gate.Queue(self.state_dir)
        return self._queue

    def compose_body(self) -> ComposeResult:
        yield Static("", id="gen-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="gen-files", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="gen-preview")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- the checkpoint -----------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart came by road: it passes by the rules, or waits in the queue."""
        if payload.kind == pipes.TEXT and markdown and markdown != payload.value:
            payload = pipes.Payload(payload.kind, markdown, payload.source, payload.mode, payload.title or title,
                                    payload.trail, payload.ref)
        back = self.queue.by_ref(payload.ref)
        why = gate.reasons(payload, self.config, self._rule_context(payload))
        if back is not None:
            why = [f"back from rework (round {back.attempts})"] + why
        if not why:
            self._pass(payload)
        else:
            item = self.queue.arrive(payload, why)
            self.app.notify(f"{item.title or item.value[:60]} — {'; '.join(why)}", title=f"📦 {self.btype.title}: held")
        self._changed()

    def _rule_context(self, payload: pipes.Payload) -> gate.Context:
        files: list[str] = []
        wt = gate.worktree_of(payload)
        if wt and (self._get_repo_root() / wt).is_dir():
            try:
                files = [g.path for g in generated.Review(self._get_repo_root() / wt, self.state_dir / "wt").files()]
            except (RuntimeError, OSError, ValueError):
                pass
        return gate.Context(files, self._leaves_town())

    def _leaves_town(self) -> bool:
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        if scroll is None:
            return False
        from orkcraft.realm import catalog
        for b in getattr(scroll, "buildings", ()):
            spec = getattr(self.app, "custom_specs", {}).get(b.id)
            t = catalog.type_of(spec) if spec else None
            if t and t.id in EGRESS and any(r.source == self.building_id and r.event == "loot.passed" for r in b.roads):
                return True
        return False

    def _pass(self, payload: pipes.Payload) -> None:
        """Carry the cart on, and keep it in the vault (the history of what passed)."""
        item = vault.store(self._get_repo_root(), self.building_id, self.state_dir, payload.kind, payload.value,
                           payload.title, payload.source, trail=payload.trail, ref=payload.ref)
        self.emit("loot.passed", payload.value, payload.title, trail=payload.trail, ref=payload.ref)
        self.emit("loot.stored", item.path, item.title, trail=payload.trail, ref=payload.ref)

    def accept_item(self, item: gate.Item, value: str | None = None) -> None:
        self.queue.accept(item, value)
        self._pass(item.payload())
        self._changed()

    def rework_item(self, item: gate.Item, reason: str) -> str:
        """Send `item` back with `reason`; past the limit (or with nobody to take it) it needs you.
        Returns its status."""
        ok, why = self.queue.can_rework(item, self.config)
        if ok:
            self.queue.rework(item, reason)
            md = gate.rework_markdown(item, reason, self.spec.get("title") or self.btype.title)
            back = pipes.Payload(pipes.TEXT, md, self.building_id, "loot.rework",
                                 f"rework: {item.title or item.ref}", item.hops, item.ref)
            taker = getattr(self.app, "return_for_rework", None)
            if taker is not None and (to := taker(item.source, back)):
                self.emit("loot.rework", md, back.title, trail=item.hops, ref=item.ref)
                self.app.notify(f"sent back to {to} (round {item.attempts}): {reason}", title="📦 Loot")
                self._changed()
                return item.status
            item.attempts -= 1
            item.notes.pop()
            why = f"{item.source} cannot take work back"
        self.queue.needs_you(item, f"{reason} — not sent back: {why}")
        self.emit("loot.needs_you", f"**{item.title or item.ref}** needs you: {why}\n\n{reason}", item.title,
                  trail=item.hops, ref=item.ref)
        self.app.notify(f"{item.title or item.ref}: {why} — it waits for you", title="🔥 Loot", severity="warning")
        self._changed()
        return item.status

    def burning(self) -> bool:
        """A cart waits for the person: the hut burns."""
        return any(i.status in (gate.HELD, gate.NEEDS_YOU) for i in self.queue.items)

    def _changed(self) -> None:
        self.refresh_data()
        refresh = getattr(getattr(self, "app", None), "refresh_roster", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    # -- the list ---------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        try:
            self.rows, self.error = self.review.files(), ""
        except (RuntimeError, OSError, ValueError) as e:
            self.rows, self.error = [], str(e)[:200]
        self.stored = vault.stored(self.state_dir)
        try:
            self.rejected = self.review.rejected()
        except (OSError, ValueError):
            self.rejected = []
        self._render_list()

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
            head.update(Text(f"{q}{waiting} files to review in {scope} · a accept · r reject / rework · d drop · "
                             "u restore", style="dim"))
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
        """Building ids → titles, for the chain line."""
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        return {b.id: b.title for b in getattr(scroll, "buildings", ())} if scroll is not None else {}

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
        self._update(out)

    # -- decisions ----------------------------------------------------------------------------------

    def accept(self, rel: str) -> None:
        self.review.accept(rel)
        self.emit("generator.accepted", rel, rel)

    def reject(self, rel: str) -> None:
        self.review.reject(rel)
        self.emit("generator.rejected", rel, rel)

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

    def action_reject(self) -> None:
        if (item := self.selected_item()) is not None:
            if item.status != gate.HELD:
                self.app.notify("only a held cart goes back for rework; accept or drop this one",
                                title="📦 Loot")
                return
            from orkcraft.screens.dialogs import TextPrompt

            def done(reason: str | None) -> None:
                if reason and reason.strip():
                    self.rework_item(item, reason.strip())

            self.app.push_screen(TextPrompt(f"↩ Send back to {item.source}", placeholder="what to fix",
                                            help=f"round {item.attempts + 1}"), done)
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
            self.queue.drop(item)
            self._changed()

    def action_restore(self) -> None:
        oid = self._highlighted_id()
        if not oid or not oid.startswith("rej:"):
            return
        r = self.rejected[int(oid[4:])]
        try:
            self.review.restore(r["path"], r["at"])
            self.app.notify(f"{r['path']} is back", title="📦 Loot")
        except (OSError, ValueError) as e:
            self.app.notify(str(e), title="📦 Restore failed", severity="error")
        self.refresh_data()

    # -- the hut ----------------------------------------------------------------------------------

    def _queue_lines(self) -> list[str]:
        q = self.queue
        held, you = q.count(gate.HELD), q.count(gate.NEEDS_YOU)
        if not held and not you and not q.count(gate.REWORK):
            return []
        parts = [f"{held} held"] + ([f"{you} needs you"] if you else []) + \
            ([f"{q.count(gate.REWORK)} in rework"] if q.count(gate.REWORK) else [])
        lines = [" · ".join(parts)]
        lines += [f"{STATUS[i.status][0]} {_label(i)[:40]}" for i in q.open()[:3]]
        return lines

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        queue = self._queue_lines()
        waiting = [g for g in self.rows if not g.reviewed]
        stored = [f"📦 {len(self.stored)} stored"] if self.stored else []
        if not self.rows:
            return queue + stored or ["nothing generated"]
        lines = queue + [f"{len(waiting)} to review" if waiting else "all reviewed ✓"] + stored
        lines += [f"* {g.path.rsplit('/', 1)[-1]}" for g in waiting[:3]]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        waiting = [g for g in self.rows if not g.reviewed]
        files = [f"{len(waiting)} files to review" if waiting else "all reviewed ✓" if self.rows else ""]
        files += [f"* {g.path.rsplit('/', 1)[-1]}" for g in waiting]
        lines = [ln for ln in self._queue_lines() + files if ln][:6] or ["nothing held"]
        return lines + [""] * (6 - len(lines)) + [f"passed: {len(self.stored)}"]

    def quick_action(self, action_id: str) -> bool:
        if action_id == "loot.accept_all":
            held = [i for i in self.queue.items if i.status == gate.HELD]
            for item in held:
                self.queue.accept(item)
                self._pass(item.payload())
            self._changed()
            self.app.notify(f"{len(held)} cart{'s' if len(held) != 1 else ''} passed", title="📦 Loot")
            return True
        if action_id != "generator.accept_all":
            return False
        waiting = [g.path for g in self.rows if not g.reviewed]
        for rel in waiting:
            self.accept(rel)
        self.refresh_data()
        self.app.notify(f"{len(waiting)} file{'s' if len(waiting) != 1 else ''} accepted", title="🛠 File Generator")
        return True
