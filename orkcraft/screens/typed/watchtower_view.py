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
"""
from __future__ import annotations

import datetime as dt
import imaplib
import json
import os
import queue
import re
from dataclasses import asdict

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import fastpath, feeds, inbound, lookout, mailbox, watch
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 120.0
CRON_S = 30.0
KEEP = 200
READ_KEEP = 1000                                        # read marks remembered
RAW_KEEP = 20000                                        # a raw webhook's body, as kept
ICON = {"mail": "✉", "github": "🐙", "cron": "⏰", "webhook": "🪝", **feeds.ICON}
LABEL = {"webhook": "hooks", "confluence": "confl"}     # six cells on the hut
ORDER = ("mail", "slack", "jira", "confluence", "figma", "github", "webhook", "cron")


def count(n: int) -> str:
    return "99+" if n > 99 else str(n)


class WatchtowerView(TypedView):
    TYPE = "watchtower"
    imap_factory = staticmethod(imaplib.IMAP4_SSL)      # tests put a fake server here
    gh_runner = None                                    # and a fake `gh` here
    feed_opener = None                                  # and fake Slack / Jira / Confluence / Figma here
    judge_runner = None                                 # and a fake light model here
    clock = staticmethod(dt.datetime.now)

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.look: mailbox.Look | None = None
        self.signals: list[watch.Signal] = []
        self.errors: dict[str, str] = {}
        self.checked = ""
        self.hook: watch.Webhook | None = None
        self.inbox: queue.SimpleQueue = queue.SimpleQueue()   # webhook signals, from the server's thread
        self.pending: list[watch.Signal] = []                 # waiting for the Lookout's verdict
        self._looking = False
        self._judging = False

    # -- settings and state -------------------------------------------------------------------------

    @property
    def sources(self) -> list[str]:
        c = self.config
        kinds = [f.kind for f in self.feeds]
        return [s for s, on in (("mail", c.get("host")), ("github", c.get("github")), ("cron", c.get("cron")),
                                ("webhook", c.get("webhook_port"))) if on] + sorted(set(kinds), key=kinds.index)

    @property
    def polled(self) -> list[feeds.Feed]:
        return [f for f in self.feeds if f.poll]

    @property
    def feeds(self) -> list[feeds.Feed]:
        lines = self.config.get("feeds")
        return [f for f in (feeds.parse(x)[0] for x in (lines if isinstance(lines, list) else [])) if f]

    @property
    def intent(self) -> str:
        return str(self.config.get("intent") or "").strip()

    def label(self, source: str) -> str:
        if source == "mail":
            host = str(self.config.get("host") or "").lower()
            return host if host in mailbox.PROVIDERS else "mail"
        return LABEL.get(source, source)

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
        read = set(self._state().get("read") or [])
        for s in self.signals:
            s.read = s.read or s.key in read
        self.start_webhook()
        self.tick()                                   # the schedule's baseline: it fires from now on
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)
        self.set_interval(CRON_S, self.tick)
        self.set_interval(0.5, self.drain)

    def drain(self) -> None:
        while not self.inbox.empty():
            self.heard(self.inbox.get_nowait())

    def heard(self, sig: watch.Signal) -> None:
        """A webhook delivery: a service's becomes its comments and mentions, the rest stays raw."""
        service = inbound.service_of(sig.ref)
        token, unnamed = self._unnamed(service, sig.body)
        if unnamed:                                       # who wrote it, by name: users.info first
            opener = type(self).feed_opener

            def work() -> None:
                feeds.slack_names(token, unnamed, *([opener] if opener else []))
                try:
                    self.app.call_from_thread(self._heard, service, sig)
                except Exception:
                    pass

            self.run_worker(work, thread=True, group="watch-names")
            return
        self._heard(service, sig)

    def _unnamed(self, service: str, body: str) -> tuple[str, set[str]]:
        """(the Slack token to ask with, the people a delivery names that have no name yet)."""
        token = next((f.env("token") for f in self.feeds if f.kind == "slack" and f.env("token")), "")
        if service != "slack" or not token:
            return "", set()
        try:
            ev = json.loads(body).get("event") or {}
        except (ValueError, AttributeError):
            return "", set()
        people = {ev.get("user", "")} | set(re.findall(r"<@([A-Z0-9]+)>", str(ev.get("text", ""))))
        return token, {p for p in people if p and p not in feeds.SLACK_NAMES}

    def _heard(self, service: str, sig: watch.Signal) -> None:
        st = self._state()
        items = inbound.parse(service, sig.body, (st.get("feeds_me") or {}).get(service)) if service else None
        if items is inbound.IGNORED:
            return
        if items is None:
            sig.body = sig.body[:RAW_KEEP]
            self.add_signal(sig)
            return
        heard = dict(st.get("hook_seen") or {})
        known = set(heard.get(service) or [])
        for ident, keys in (st.get("feeds_seen") or {}).items():
            if ident.startswith(f"{service}|"):
                known.update(keys)
        fresh = [i for i in items if i.key not in known]
        if fresh:
            heard[service] = ((heard.get(service) or []) + [i.key for i in fresh])[-feeds.SEEN_KEEP:]
            self._save_state(hook_seen=heard)
        for item in fresh:
            self.add_signal(watch.Signal(watch.local_iso(item.at) if item.at else sig.at, service, item.title,
                                         f"{item.body}\n\n{item.url}".strip(), item.url or sig.ref, item.mention))

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
        """A new signal: with an intent the Lookout looks at it first (not the schedule's)."""
        if not send:
            sig.read = True                            # the first look's: listed, not new
        elif self.intent and sig.source != "cron":
            self.pending.append(sig)
            self.judge()
            return
        self._keep(sig, send)

    def _keep(self, sig: watch.Signal, send: bool) -> None:
        self.signals.insert(0, sig)
        del self.signals[KEEP:]
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.state_dir / "signals.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(sig), ensure_ascii=False) + "\n")
        if send:
            title = f"{sig.source} · {sig.title}" if sig.source in watch.FEEDS else sig.title   # which service
            body = f"{title}\n\n{sig.body}".strip() if sig.source != "mail" else sig.body
            if sig.why:
                body += f"\n\n🎯 {sig.why}"
            self.emit(sig.event, body, title)
        self._render_list()

    def judge(self) -> None:
        """The Lookout's verdict on what waits, a batch at a time, off the UI thread."""
        if self._judging or not self.pending or (not self.simulated and self.out_of_gold()):
            return                                       # out of 🪙: the signals wait, unjudged
        self._judging = True
        batch, self.pending = self.pending[:lookout.BATCH], self.pending[lookout.BATCH:]
        intent, app = self.intent, self.app
        runner = None if self.simulated else (type(self).judge_runner or fastpath.light_runner(self._get_repo_root()))

        def work() -> None:
            verdicts, problem = lookout.judge(intent, batch, runner)
            try:
                app.call_from_thread(self.judged, batch, verdicts, problem)
            except Exception:
                self._judging = False

        self.run_worker(work, thread=True, group="watch-judge")

    def judged(self, batch: list[watch.Signal], verdicts: list[lookout.Verdict], problem: str) -> None:
        self._judging = False
        self.errors.pop("intent", None) if not problem else self.errors.update(intent=problem)
        for sig, v in zip(batch, verdicts):
            sig.kept, sig.why = v.kept, v.why
            sig.read = not v.kept                     # a miss is not news
            self._keep(sig, v.kept)
        self.judge()

    def start_webhook(self) -> None:
        port = self.config.get("webhook_port")
        if not port or self.simulated or self.hook is not None:
            return
        secret = os.environ.get(str(self.config.get("webhook_secret_env") or ""), "")
        secrets = {f.kind: f.env("secret") for f in self.feeds if f.opts.get("secret") and f.env("secret")}
        try:                                         # the sender gets its 202 at once; the UI drains the inbox
            self.hook = watch.Webhook(int(port), secret, self.inbox.put, secrets)
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
        if self._looking or not ({"mail", "github", *watch.FEEDS} & set(self.sources)):
            self._render_list()
            return
        self._looking = True
        cfg, factory, runner, app = self.config, type(self).imap_factory, type(self).gh_runner, self.app
        gh_last = str(self._state().get("gh_last", ""))
        opener, watched = type(self).feed_opener, self.polled

        def work() -> None:
            look = mailbox.look(cfg, factory) if cfg.get("host") else None
            gh = watch.github_events(str(cfg["github"]), gh_last, *([runner] if runner else [])) \
                if cfg.get("github") else None
            looks = [(f, feeds.look(f, *([opener] if opener else []))) for f in watched]
            try:
                app.call_from_thread(self.apply, look, gh, looks)
            except Exception:
                self._looking = False

        self.run_worker(work, thread=True, exclusive=True, group="watch-look")

    def apply(self, look: mailbox.Look | None, gh: tuple | None, looks: list | None = None) -> None:
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
        if looks:
            self.apply_feeds(looks)
        self._render_list()

    def apply_feeds(self, looks: list[tuple[feeds.Feed, feeds.Look]]) -> None:
        """Each feed's new items become signals, each once however many feeds or webhooks found it;
        a feed that failed keeps what it had seen."""
        st = self._state()
        seen, me = dict(st.get("feeds_seen") or {}), dict(st.get("feeds_me") or {})
        last, before = dict(st.get("feeds_at") or {}), dict(st.get("feeds_at") or {})
        lines = dict(st.get("feeds_line") or {})
        heard = st.get("hook_seen") or {}
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for key in [k for k in self.errors if k.startswith("feed:")]:
            del self.errors[key]
        sent: set[str] = set()
        for feed, got in looks:
            if got.error:
                self.errors[f"feed:{feed.line}"] = got.error
                continue
            if got.me:
                me[feed.kind] = got.me                    # the webhook tells mentions by it
            ident = feed.identity
            edited = lines.get(ident) not in (None, feed.line)   # channels, files or a query changed
            fresh, seen[ident] = feeds.new_items(got, seen.get(ident), before.get(ident, "") if edited else "")
            last[ident], lines[ident] = now, feed.line
            pushed = set(heard.get(feed.kind) or [])      # came by webhook already
            for item in (i for i in fresh if f"{feed.kind}:{i.key}" not in sent and i.key not in pushed):
                sent.add(f"{feed.kind}:{item.key}")
                self.add_signal(watch.Signal(watch.local_iso(item.at) if item.at else watch.now_iso(), feed.kind,
                                             item.title, f"{item.body}\n\n{item.url}".strip(), item.url,
                                             item.mention))
        live = {f.identity for f, _ in looks}
        self._save_state(feeds_seen={k: v for k, v in seen.items() if k in live},
                         feeds_at={k: v for k, v in last.items() if k in live},
                         feeds_line={k: v for k, v in lines.items() if k in live}, feeds_me=me)

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

    # -- read and unread ----------------------------------------------------------------------------

    def unread(self, source: str | None = None) -> list[watch.Signal]:
        return [s for s in self.signals if not s.read and (source is None or s.source == source)]

    def mark_read(self, sigs: list[watch.Signal]) -> None:
        fresh = [s for s in sigs if not s.read]
        if not fresh:
            return
        for s in fresh:
            s.read = True
        read = (list(self._state().get("read") or []) + [s.key for s in fresh])[-READ_KEEP:]
        self._save_state(read=read)
        self._render_list()

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#watch-head", Static), self.query_one("#watch-list", OptionList)
        except Exception:
            return
        bits = [f"{ICON[s]} {s}" for s in self.sources] or ["no source yet — set host, github, feeds, cron or webhook_port"]
        if self.unread():
            bits.append(f"{count(len(self.unread()))} new")
        if self.look is not None and not self.look.error:
            bits.append(f"{self.look.unread} unread in the mailbox")
        if self.hook is not None:
            bits.append(f"listening on 127.0.0.1:{self.hook.port}")
        if self.checked:
            bits.append(f"checked {self.checked}")
        line = Text(" · ".join(bits), style="dim")
        if self.intent:
            line.append(f"\n🎯 {self.intent}", style="cyan")
        for err in self.errors.values():
            line.append(f"\n⚠ {err}", style="yellow")
        head.update(line)
        keep = lst.highlighted
        lst.clear_options()
        for i, s in enumerate(self.signals):
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("• " if not s.read else "  ", style="bold cyan")
            row.append(f"{ICON.get(s.source, '·')} ", style="cyan")
            row.append(f"{s.at[5:16].replace('T', ' ')}  ", style="dim")
            style = "dim" if s.kept is False else ("bold" if s.mention or not s.read else "")
            row.append(s.title, style=style)
            lst.add_option(Option(row, id=f"s{i}"))
        if self.signals:
            lst.highlighted = keep if keep is not None and keep < len(self.signals) else 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "watch-list" and event.option.id:
            event.stop()
            self.read(self.signals[int(event.option.id[1:])])

    def read(self, sig: watch.Signal) -> None:
        self.mark_read([sig])
        verdict = ("" if sig.kept is None else
                   f"\n\n🎯 {'matches' if sig.kept else 'not for'} the intent{': ' + sig.why if sig.why else ''}")
        if sig.source != "mail" or not sig.ref.isdigit():
            self._show(f"**{sig.title}**\n\n{sig.source} · {sig.at}{verdict}\n\n---\n\n```\n{sig.body}\n```" if sig.body
                       else f"**{sig.title}**\n\n{sig.source} · {sig.at}{verdict}")
            return
        cfg, factory, app = self.config, type(self).imap_factory, self.app
        self._show("_reading…_")

        def work() -> None:
            try:
                text = mailbox.read(cfg, int(sig.ref), factory)
            except Exception as e:  # network trouble of every kind
                text = f"_could not read it: {e}_\n\n{sig.body}"
            try:
                app.call_from_thread(self._show, text + verdict)
            except Exception:
                pass

        self.run_worker(work, thread=True, exclusive=True, group="watch-read")

    def _show(self, md: str) -> None:
        try:
            self.query_one("#watch-read", Markdown).update(md[:60000])
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def _failing(self, source: str) -> bool:
        return source in self.errors or any(k.startswith(f"feed:{source}") for k in self.errors)

    def mini_status(self) -> list[str]:
        if not self.sources:
            return ["no source yet"]
        lines = []
        if "mail" in self.sources:
            lines.append(f"⚠ {self.errors['mail'][:50]}" if "mail" in self.errors else
                         f"{self.look.unread} unread" if self.look else "checking…")
        new, mentions = self.unread(), [s for s in self.unread() if s.mention]
        lines.append(" ".join(ICON[s] for s in self.sources) + (f" · {count(len(new))} new" if new else "")
                     + (f" · @{count(len(mentions))}" if mentions else ""))
        lines += [f"{ICON.get(s.source, '·')} {s.title}" for s in new[:2]]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """What is new per source, ten cells a line — `gmail    3`, `slack  99+`; ERR when it fails."""
        if not self.sources:
            return ["no source", "yet", "", ""]
        shown = sorted(self.sources, key=lambda s: ORDER.index(s) if s in ORDER else len(ORDER))
        rows = len(widths) or 4
        if len(shown) > rows:
            rest = shown[rows - 1:]
            shown = shown[:rows - 1]
        else:
            rest = []
        width = widths[0] if widths else 10
        lines = []
        for s in shown:
            n = "ERR" if self._failing(s) else count(len(self.unread(s)))
            lines.append(f"{self.label(s)[:width - 4]:<{width - 4}}{n:>4}")
        if rest:
            more = sum(len(self.unread(s)) for s in rest)
            lines.append(f"+{len(rest)} more"[:width - 4].ljust(width - 4) + f"{count(more):>4}")
        return lines + [""] * (rows - len(lines))

    def quick_action(self, action_id: str) -> bool:
        if action_id == "mail.refresh":
            self.refresh_data()
            self.tick()
            return True
        if action_id == "watch.read_all":
            self.mark_read(self.signals)
            return True
        if action_id == "mail.open_new":
            new = self.unread()
            if not self.signals:
                self.app.notify("nothing came in yet", title="🗼 Watchtower")
                return True
            window = self.app.desktop.window_of(self) if hasattr(self.app.desktop, "window_of") else None
            if window is not None:
                self.app.desktop.focus_window(window)
            self.read(new[0] if new else self.signals[0])
            return True
        return False
