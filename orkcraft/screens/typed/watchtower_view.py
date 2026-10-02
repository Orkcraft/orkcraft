"""🗼 Watchtower: listens to the outside and starts work in the camp.

Sources, each on when its settings are there:

    mail      IMAP, read-only (host, user_env, password_env, folder, port) — every 2 min
    github    events of owner/repo through `gh` (github)                   — every 2 min
    cron      a schedule (cron: `every 15m`, `daily 05:00`, …)             — checked every 30 s
    webhook   POSTs to http://127.0.0.1:<webhook_port>/… (webhook_secret_env to require a secret)

Every new signal goes down the road (`mail.received`, `watch.github`, `watch.cron`,
`watch.webhook`) and into `.orkcraft/watchtower/<id>/signals.jsonl`. The open building lists the
signals, Enter reads one (mail is fetched without marking it read); ✉ opens the newest.
"""
from __future__ import annotations

import datetime as dt
import imaplib
import json
import os
import queue
from dataclasses import asdict

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import mailbox, watch
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 120.0
CRON_S = 30.0
KEEP = 200
ICON = {"mail": "✉", "github": "🐙", "cron": "⏰", "webhook": "🪝"}


class WatchtowerView(TypedView):
    TYPE = "watchtower"
    imap_factory = staticmethod(imaplib.IMAP4_SSL)      # tests put a fake server here
    gh_runner = None                                    # and a fake `gh` here
    clock = staticmethod(dt.datetime.now)

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.look: mailbox.Look | None = None
        self.signals: list[watch.Signal] = []
        self.errors: dict[str, str] = {}
        self.checked = ""
        self.hook: watch.Webhook | None = None
        self.inbox: queue.SimpleQueue = queue.SimpleQueue()   # webhook signals, from the server's thread
        self._looking = False

    # -- settings and state -------------------------------------------------------------------------

    @property
    def sources(self) -> list[str]:
        c = self.config
        return [s for s, on in (("mail", c.get("host")), ("github", c.get("github")), ("cron", c.get("cron")),
                                ("webhook", c.get("webhook_port"))) if on]

    def _state(self) -> dict:
        try:
            return json.loads((self.state_dir / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        try:                                             # T1105's mail watcher kept only the last uid
            return {"last_uid": json.loads((self.state_dir / "mail.json").read_text(encoding="utf-8"))["last_uid"]}
        except (OSError, ValueError, KeyError):
            return {}

    def _save_state(self, **changes) -> None:
        st = {**self._state(), **changes}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "state.json").write_text(json.dumps(st), encoding="utf-8")

    def compose_body(self) -> ComposeResult:
        yield Static("", id="watch-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="watch-list", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="watch-read")

    def on_mount(self) -> None:
        try:
            lines = (self.state_dir / "signals.jsonl").read_text(encoding="utf-8").splitlines()[-KEEP:]
            self.signals = [watch.Signal(**json.loads(x)) for x in reversed(lines)]
        except (OSError, ValueError, TypeError):
            self.signals = []
        self.start_webhook()
        self.tick()                                   # the schedule's baseline: it fires from now on
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)
        self.set_interval(CRON_S, self.tick)
        self.set_interval(0.5, self.drain)

    def drain(self) -> None:
        while not self.inbox.empty():
            self.add_signal(self.inbox.get_nowait())

    def on_unmount(self) -> None:
        if self.hook is not None:
            self.hook.stop()

    def restart(self) -> None:
        """New settings (T1108 weekly audit): the webhook listens again with them."""
        if self.hook is not None:
            self.hook.stop()
            self.hook = None
        self.start_webhook()
        self.refresh_data()

    # -- signals ------------------------------------------------------------------------------------

    def add_signal(self, sig: watch.Signal, send: bool = True) -> None:
        self.signals.insert(0, sig)
        del self.signals[KEEP:]
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.state_dir / "signals.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(sig), ensure_ascii=False) + "\n")
        if send:
            self.emit(sig.event, f"{sig.title}\n\n{sig.body}".strip() if sig.source != "mail" else sig.body, sig.title)
        self._render_list()

    def start_webhook(self) -> None:
        port = self.config.get("webhook_port")
        if not port or self.simulated or self.hook is not None:
            return
        secret = os.environ.get(str(self.config.get("webhook_secret_env") or ""), "")
        try:                                         # the sender gets its 202 at once; the UI drains the inbox
            self.hook = watch.Webhook(int(port), secret, self.inbox.put)
            self.hook.start()
            self.errors.pop("webhook", None)
        except OSError as e:
            self.hook, self.errors["webhook"] = None, f"webhook: port {port}: {e.strerror or e}"

    def tick(self) -> None:
        expr = str(self.config.get("cron") or "")
        if not expr:
            return
        now = self.clock()
        last = self._state().get("cron_last")
        last_dt = dt.datetime.fromisoformat(last) if last else now
        if last and watch.cron_due(expr, last_dt, now):
            self.add_signal(watch.Signal(now.isoformat(timespec="seconds"), "cron", f"⏰ {expr}", ""))
        if not last or watch.cron_due(expr, last_dt, now):
            self._save_state(cron_last=now.isoformat(timespec="seconds"))

    def refresh_data(self) -> None:
        if self._looking or not ({"mail", "github"} & set(self.sources)):
            self._render_list()
            return
        self._looking = True
        cfg, factory, runner, app = self.config, type(self).imap_factory, type(self).gh_runner, self.app
        gh_last = str(self._state().get("gh_last", ""))

        def work() -> None:
            look = mailbox.look(cfg, factory) if cfg.get("host") else None
            gh = watch.github_events(str(cfg["github"]), gh_last, *([runner] if runner else [])) \
                if cfg.get("github") else None
            try:
                app.call_from_thread(self.apply, look, gh)
            except Exception:
                self._looking = False

        self.run_worker(work, thread=True, exclusive=True, group="watch-look")

    def apply(self, look: mailbox.Look | None, gh: tuple | None) -> None:
        self._looking, self.checked = False, watch.now_iso()[11:16]
        if look is not None:
            self.apply_look(look)
        if gh is not None:
            signals, newest, err = gh
            self.errors.pop("github", None) if not err else self.errors.update(github=err)
            for s in signals:
                self.add_signal(s)
            if newest:
                self._save_state(gh_last=newest)
        self._render_list()

    def apply_look(self, look: mailbox.Look) -> None:
        self._looking = False
        self.look = look
        if look.error:
            self.errors["mail"] = look.error
            self._render_list()
            return
        self.errors.pop("mail", None)
        if look.messages:
            last = self._state().get("last_uid")
            first = last is None                     # the first look: the unread are listed, not sent
            new = [m for m in reversed(look.messages) if m.unread] if first else mailbox.new_since(int(last), look)
            for m in new:
                self.add_signal(watch.Signal(watch.now_iso(), "mail", f"{m.sender}: {m.subject}", m.text(), str(m.uid)),
                                send=not first)
            self._save_state(last_uid=max(m.uid for m in look.messages))
        self._render_list()

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#watch-head", Static), self.query_one("#watch-list", OptionList)
        except Exception:
            return
        bits = [f"{ICON[s]} {s}" for s in self.sources] or ["no source yet — set host, github, cron or webhook_port"]
        if self.look is not None and not self.look.error:
            bits.append(f"{self.look.unread} unread")
        if self.hook is not None:
            bits.append(f"listening on 127.0.0.1:{self.hook.port}")
        if self.checked:
            bits.append(f"checked {self.checked}")
        line = Text(" · ".join(bits), style="dim")
        for err in self.errors.values():
            line.append(f"\n⚠ {err}", style="yellow")
        head.update(line)
        keep = lst.highlighted
        lst.clear_options()
        for i, s in enumerate(self.signals):
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{ICON.get(s.source, '·')} ", style="cyan")
            row.append(f"{s.at[5:16].replace('T', ' ')}  ", style="dim")
            row.append(s.title)
            lst.add_option(Option(row, id=f"s{i}"))
        if self.signals:
            lst.highlighted = keep if keep is not None and keep < len(self.signals) else 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "watch-list" and event.option.id:
            event.stop()
            self.read(self.signals[int(event.option.id[1:])])

    def read(self, sig: watch.Signal) -> None:
        if sig.source != "mail" or not sig.ref.isdigit():
            self._show(f"**{sig.title}**\n\n{sig.source} · {sig.at}\n\n---\n\n```\n{sig.body}\n```" if sig.body
                       else f"**{sig.title}**\n\n{sig.source} · {sig.at}")
            return
        cfg, factory, app = self.config, type(self).imap_factory, self.app
        self._show("_reading…_")

        def work() -> None:
            try:
                text = mailbox.read(cfg, int(sig.ref), factory)
            except Exception as e:  # network trouble of every kind
                text = f"_could not read it: {e}_\n\n{sig.body}"
            try:
                app.call_from_thread(self._show, text)
            except Exception:
                pass

        self.run_worker(work, thread=True, exclusive=True, group="watch-read")

    def _show(self, md: str) -> None:
        try:
            self.query_one("#watch-read", Markdown).update(md[:60000])
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if not self.sources:
            return ["no source yet"]
        lines = []
        if "mail" in self.sources:
            lines.append(f"⚠ {self.errors['mail'][:50]}" if "mail" in self.errors else
                         f"{self.look.unread} unread" if self.look else "checking…")
        lines.append(" ".join(ICON[s] for s in self.sources) + (f" · {len(self.signals)} signals" if self.signals else ""))
        lines += [f"{ICON.get(s.source, '·')} {s.title}" for s in self.signals[:2]]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """Eight cells a line: port, events, state, the last signal — `prt:8080 evts:  3 stat: OK log: mail`."""
        if not self.sources:
            return ["no source", "yet", "", ""]
        port = self.config.get("webhook_port")
        last = self.signals[0].source[:4] if self.signals else "nil"
        return [f"prt:{port}" if port else "prt:  —", f"evts:{len(self.signals):>3}",
                f"stat:{'ERR' if self.errors else 'OK':>4}", f"log:{last:>5}"]

    def quick_action(self, action_id: str) -> bool:
        if action_id == "mail.refresh":
            self.refresh_data()
            self.tick()
            return True
        if action_id == "mail.open_new":
            if not self.signals:
                self.app.notify("nothing came in yet", title="🗼 Watchtower")
                return True
            window = self.app.desktop.window_of(self) if hasattr(self.app.desktop, "window_of") else None
            if window is not None:
                self.app.desktop.focus_window(window)
            self.read(self.signals[0])
            return True
        return False
