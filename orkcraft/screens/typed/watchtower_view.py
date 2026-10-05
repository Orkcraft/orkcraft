"""🗼 Watchtower: listens to the outside and starts work in the camp.

Sources, each on when its settings are there:

    mail      IMAP, read-only (host — or `gmail` —, user_env, password_env, folder, port) — every 2 min
    github    events of owner/repo through `gh` (github)                   — every 2 min
    feeds     Slack, Jira, Confluence, Figma: comments and mentions (feeds) — every 2 min
    cron      a schedule (cron: `every 15m`, `daily 05:00`, …)             — checked every 30 s
    webhook   POSTs to http://127.0.0.1:<webhook_port>/… (webhook_secret_env to require a secret);
              /slack, /jira, /confluence, /figma become comments and mentions (realm/inbound.py)

One tower for every source: `intent` says what to listen for ("user feedback about the app"), and
the Lookout lets through only what matches (realm/lookout.py); the rest stays in the list, dimmed.

Every new signal goes down the road (`mail.received`, `watch.github`, `watch.cron`,
`watch.webhook`, `watch.comment`, `watch.mention`) and into `.orkcraft/watchtower/<id>/signals.jsonl`.
The open building lists the signals, new ones marked •; Enter reads one and marks it read (mail is
fetched without marking it read in the mailbox); ✉ opens the newest new one, ✓ marks all read.
The hut counts what is new per source: `gmail     3`, `slack   99+`.

The listening — every source, the Lookout, the webhook, read and unread — is the building's worker's
(core/workers/watchtower.py); the view draws the list and the signal read and runs the clocks.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.watchtower import CRON_S, DRAIN_S, ICON, REFRESH_S, WatchtowerWorker, count
from orkcraft.realm import feeds, mailbox, watch
from orkcraft.screens.typed.base import TypedView


class WatchtowerView(TypedView):
    TYPE = "watchtower"
    UI_PANES = {"sources": "#watch-head", "feed": "#watch-list", "item": "#watch-read-scroll"}

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._shown = ""                                   # the key of the signal the reader shows

    @property
    def worker(self) -> WatchtowerWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def look(self) -> mailbox.Look | None:
        return self.worker.look

    @property
    def signals(self) -> list[watch.Signal]:
        return self.worker.signals

    @property
    def errors(self) -> dict[str, str]:
        return self.worker.errors

    @property
    def checked(self) -> str:
        return self.worker.checked

    @property
    def hook(self) -> watch.Webhook | None:
        return self.worker.hook

    @property
    def sources(self) -> list[str]:
        return self.worker.sources

    @property
    def polled(self) -> list[feeds.Feed]:
        return self.worker.polled

    @property
    def feeds(self) -> list[feeds.Feed]:
        return self.worker.feeds

    @property
    def intent(self) -> str:
        return self.worker.intent

    def label(self, source: str) -> str:
        return self.worker.label(source)

    def _state(self) -> dict:
        return self.worker._state()

    def _save_state(self, **changes) -> None:
        self.worker._save_state(**changes)

    def add_signal(self, sig: watch.Signal, send: bool = True) -> None:
        self.worker.add_signal(sig, send)

    def heard(self, sig: watch.Signal) -> None:
        self.worker.heard(sig)

    def tick(self) -> None:
        self.worker.tick()

    def drain(self) -> None:
        self.worker.drain()

    def apply(self, look, gh, looks=None) -> None:
        self.worker.apply(look, gh, looks)

    def apply_feeds(self, looks) -> None:
        self.worker.apply_feeds(looks)

    def apply_look(self, look: mailbox.Look) -> None:
        self.worker.apply_look(look)

    def unread(self, source: str | None = None) -> list[watch.Signal]:
        return self.worker.unread(source)

    def mark_read(self, sigs: list[watch.Signal]) -> None:
        self.worker.mark_read(sigs)

    def read(self, sig: watch.Signal) -> None:
        self.worker.read(sig)

    def restart(self) -> None:
        self.worker.restart()

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="watch-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="watch-list", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="watch-read-scroll"):
                yield Markdown("", id="watch-read")

    def on_mount(self) -> None:
        super().on_mount()                            # the worker starts: the webhook, the schedule, a look
        self.set_interval(REFRESH_S, self.refresh_data)
        self.set_interval(CRON_S, self.tick)
        self.set_interval(DRAIN_S, self.drain)

    def on_unmount(self) -> None:
        w = self.worker
        if w is not None:
            w.close()

    def refresh_data(self) -> None:
        w = self.worker
        if w is not None:
            w.refresh_data()
        self._render_list()

    def redraw(self) -> None:
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#watch-head", Static), self.query_one("#watch-list", OptionList)
        except Exception:
            return
        w = self.worker
        bits = [f"{ICON[s]} {s}" for s in w.sources] or ["no source yet — set host, github, feeds, cron or webhook_port"]
        if w.unread():
            bits.append(f"{count(len(w.unread()))} new")
        if w.look is not None and not w.look.error:
            bits.append(f"{w.look.unread} unread in the mailbox")
        if w.hook is not None:
            bits.append(f"listening on 127.0.0.1:{w.hook.port}")
        if w.checked:
            bits.append(f"checked {w.checked}")
        line = Text(" · ".join(bits), style="dim")
        if w.intent:
            line.append(f"\n🎯 {w.intent}", style="cyan")
        for err in w.errors.values():
            line.append(f"\n⚠ {err}", style="yellow")
        head.update(line)
        keep = lst.highlighted
        lst.clear_options()
        for i, s in enumerate(w.signals):
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("• " if not s.read else "  ", style="bold cyan")
            row.append(f"{ICON.get(s.source, '·')} ", style="cyan")
            row.append(f"{s.at[5:16].replace('T', ' ')}  ", style="dim")
            style = "dim" if s.kept is False else ("bold" if s.mention or not s.read else "")
            row.append(s.title, style=style)
            lst.add_option(Option(row, id=f"s{i}"))
        if w.signals:
            lst.highlighted = keep if keep is not None and keep < len(w.signals) else 0
        reading = w.reading
        shown = f"{reading.get('key')}\n{reading.get('markdown')}" if reading else ""
        if shown != self._shown:
            self._shown = shown
            try:
                self.query_one("#watch-read", Markdown).update(reading.get("markdown", ""))
            except Exception:
                pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "watch-list" and event.option.id:
            event.stop()
            self.read(self.signals[int(event.option.id[1:])])

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        w = self.worker
        if action_id == "mail.refresh":
            w.check_now()
            return True
        if action_id == "watch.read_all":
            w.mark_read()
            return True
        if action_id == "mail.open_new":
            if not w.signals:
                self.app.notify("nothing came in yet", title="🗼 Watchtower")
                return True
            window = self.app.desktop.window_of(self) if hasattr(self.app.desktop, "window_of") else None
            if window is not None:
                self.app.desktop.focus_window(window)
            w.open_new()
            return True
        return False
