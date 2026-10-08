"""🗼 Watchtower's work: listens to the outside and starts work in the camp.

Sources, each on when its settings are there:

    mail      IMAP, read-only (host — or `gmail` —, user_env, password_env, folder, port) — every 2 min
    github    events of owner/repo through `gh` (github)                   — every 2 min
    feeds     Slack, Jira, Confluence, Figma, GitHub (many repos, notifications), GitLab, Discord:
              comments and mentions (feeds) — every 2 min
    cron      a schedule (cron: `every 15m`, `daily 05:00`, …)             — checked every 30 s
    webhook   POSTs to http://127.0.0.1:<webhook_port>/… (webhook_secret_env to require a secret);
              /slack, /jira, /confluence, /figma become comments and mentions (realm/inbound.py)

One tower for every source: `intent` says what to listen for ("user feedback about the app"), and
the Lookout lets through only what matches (realm/lookout.py); the rest stays in the list, dimmed.

Every new signal goes down the road (`mail.received`, `watch.github`, `watch.cron`,
`watch.webhook`, `watch.comment`, `watch.mention`) and into `.orkcraft/watchtower/<id>/signals.jsonl`.
`read` opens one and marks it read (mail is fetched without marking it read in the mailbox; what it
says is `reading`); `open_new` reads the newest new one, `mark_read` marks them all.

The face runs the clocks: `refresh_data` every `REFRESH_S`, `tick` (the schedule) every `CRON_S`,
`drain` (what the webhook heard, from its server's thread) every `DRAIN_S` — or `pulse` once a
second, which does each when it is due. `close` stops the webhook when the face goes.

A source that fails says which way (`fails(key)`: `login`, `target` or `network`), so its line
offers the one fix: Log in again, Edit, or nothing — it tries again (watchtower_add.py).
"""
from __future__ import annotations

import datetime as dt
import imaplib
import json
import os
import queue
import re
import textwrap
import threading
import time
import urllib.request
from dataclasses import asdict

from orkcraft.core.workers import Worker
from orkcraft.core.workers.watchtower_add import Adding
from orkcraft.core.workers.watchtower_places import Desk
from orkcraft.realm import fastpath, feeds, feeds_agent, halt, inbound, lookout, mailbox, paths, watch

REFRESH_S = 120.0
CRON_S = 30.0
DRAIN_S = 0.5
KEEP = 200
READ_KEEP = 1000                                        # read marks remembered
RAW_KEEP = 20000                                        # a raw webhook's body, as kept
ICON = {"mail": "✉", "github": "🐙", "cron": "⏰", "webhook": "🪝", **feeds.ICON}
LABEL = {"webhook": "hooks", "confluence": "confl"}     # six cells on the hut
PREVIEW_W = 14                                          # a hut this wide previews the newest message
ORDER = ("mail", "slack", "discord", "jira", "confluence", "figma", "github", "gitlab", "agent", "webhook", "cron")


def count(n: int) -> str:
    return "99+" if n > 99 else str(n)


class WatchtowerWorker(Worker):
    TYPE = "watchtower"
    imap_factory = staticmethod(imaplib.IMAP4_SSL)      # tests put a fake server here
    gh_runner = None                                    # and a fake `gh` here
    feed_opener = None                                  # and fake Slack / Jira / Confluence / Figma here
    judge_runner = None                                 # and a fake light model here
    agent_runner = None                                 # and a fake `claude -p` for the agent source here
    mcp_runner = None                                   # and a fake `claude mcp list` for the picker
    clock = staticmethod(dt.datetime.now)

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.look: mailbox.Look | None = None
        self.signals: list[watch.Signal] = []
        self.errors: dict[str, str] = {}
        self.kinds: dict[str, str] = {}                       # an error's key → login | target | network
        self.waiting: dict[str, str] = {}                     # an agent source's line → why it does not look now
        self.checked = ""
        self.hook: watch.Webhook | None = None
        self.inbox: queue.SimpleQueue = queue.SimpleQueue()   # webhook signals, from the server's thread
        self.pending: list[watch.Signal] = []                 # waiting for the Lookout's verdict
        self.reading: dict = {}                               # {key, markdown}: the signal read in full
        self._looking = False
        self._judging = False
        self._clocks = {"look": 0.0, "tick": 0.0}             # monotonic: when `pulse` last did each
        self.adding = Adding(self)                            # Add a source: its three steps (watchtower_add.py)
        self.desk = Desk(self)                                # 📍 what a paired phone says of places (watchtower_places.py)

    # -- settings and state ---------------------------------------------------------------------

    @property
    def sources(self) -> list[str]:
        c = self.config
        kinds = [f.kind for f in self.feeds]
        out = [s for s, on in (("mail", c.get("host")), ("github", c.get("github")), ("cron", c.get("cron")),
                               ("webhook", c.get("webhook_port"))) if on]
        return out + [k for k in sorted(set(kinds), key=kinds.index) if k not in out]

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

    def shown(self) -> list[str]:
        """The sources in the hut's order."""
        return sorted(self.sources, key=lambda s: ORDER.index(s) if s in ORDER else len(ORDER))

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

    def _thread(self, work, name: str) -> None:
        threading.Thread(target=work, daemon=True, name=f"{name}-{self.building_id}").start()

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
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
        now = time.monotonic()
        self._clocks = {"look": now, "tick": now}

    def pulse(self) -> None:
        """Once a second (the GUI's clock): what the webhook heard, the schedule, a look when due."""
        self.drain()
        now = time.monotonic()
        self.desk.tick(now)
        if now - self._clocks["tick"] >= CRON_S:
            self._clocks["tick"] = now
            self.tick()
        if now - self._clocks["look"] >= REFRESH_S:
            self._clocks["look"] = now
            self.refresh_data()

    def close(self) -> None:
        """The face goes: the webhook stops listening."""
        if self.hook is not None:
            self.hook.stop()
            self.hook = None

    def restart(self) -> None:
        """New settings (T1108 weekly audit): the webhook listens again with them."""
        self.close()
        self.start_webhook()
        self.refresh_data()

    def status(self) -> str:
        return "ERROR" if self.errors else ""

    # -- places (docs/design/phone-places.md) -----------------------------------------------------

    def report_place(self, report) -> str:
        """A paired phone came to one of its places or left it (realm/places.py `Report`)."""
        return self.desk.report(report)

    def orders_alert(self):
        return self.desk.alert()

    def answer_alert(self, key: str) -> str | None:
        return self.desk.answer(key)

    def loose_ends(self) -> list[dict]:
        return self.desk.loose_ends()

    def halt(self) -> int:
        return self.desk.halt()

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
                self.town.call(self._heard, service, sig)

            self._thread(work, "watch-names")
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

    # -- signals --------------------------------------------------------------------------------

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
            self.emit(sig.event, body, title, want=paths.source_want(self.config, sig.source))   # §4: by its source
        self.changed()

    def judge(self) -> None:
        """The Lookout's verdict on what waits, a batch at a time, in a thread."""
        if self._judging or not self.pending or (not self.simulated and self.out_of_gold()):
            return                                       # out of 🪙: the signals wait, unjudged
        self._judging = True
        batch, self.pending = self.pending[:lookout.BATCH], self.pending[lookout.BATCH:]
        intent = self.intent
        # its steward judges (its `judge`: realm/steward.py WORK); the Council's light-model switch still stops it,
        # as it runs by itself on every signal
        on = fastpath.settings(self.repo_root).get("fast_llm")
        runner = None if self.simulated else (type(self).judge_runner or (self.steward_runner("judge") if on else None))

        def work() -> None:
            try:
                verdicts, problem = lookout.judge(intent, batch, runner)
            except halt.Stopped:                         # 🛑 Halt All: the batch waits, unjudged
                self.town.call(self._unjudged, batch)
                return
            except Exception as e:                       # a judge that broke never stops the tower
                verdicts, problem = [lookout.Verdict(True, "") for _ in batch], f"intent: {e}"
            self.town.call(self.judged, batch, verdicts, problem)

        self._thread(work, "watch-judge")

    def _unjudged(self, batch: list[watch.Signal]) -> None:
        self.pending[:0] = batch
        self._judging = False

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
        try:                                         # the sender gets its 202 at once; the clock drains the inbox
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
        """Check now: the mailbox, GitHub and the feeds, in a thread."""
        if self.simulated:
            self._simulated_look()
            return
        if self._looking or not ({"mail", "github", *watch.FEEDS} & set(self.sources)):
            self.changed()
            return
        self._looking = True
        self.changed()
        cfg, factory, runner = self.config, type(self).imap_factory, type(self).gh_runner
        st = self._state()
        gh_last = str(st.get("gh_last", ""))
        opener, watched = type(self).feed_opener, self._due(st)
        seen, since, ask = dict(st.get("feeds_seen") or {}), dict(st.get("feeds_at") or {}), type(self).agent_runner
        keep = dict(st.get("agent_keep") or {})

        def one(f: feeds.Feed) -> feeds.Look:
            if f.kind == "agent":                          # through Claude: the last look's time, what it saw, its ids
                return feeds_agent.look(f, since.get(f.identity, ""), seen.get(f.identity) or [], ask,
                                        keep=keep.get(f.identity))
            return feeds.look(f, opener or urllib.request.urlopen, runner)

        def work() -> None:
            try:
                look = mailbox.look(cfg, factory) if cfg.get("host") else None
                gh = watch.github_events(str(cfg["github"]), gh_last, *([runner] if runner else [])) \
                    if cfg.get("github") else None
                looks = [(f, one(f)) for f in watched]
            except Exception as e:                       # a look that broke never stops the tower
                self.town.call(self._failed, str(e))
                return
            self.town.call(self.apply, look, gh, looks)

        self._thread(work, "watch-look")

    def spent_today(self, feed: feeds.Feed, st: dict | None = None) -> float:
        """What an agent source spent today, in dollars."""
        day = ((st or self._state()).get("agent_spend") or {}).get(feed.identity) or {}
        return float(day.get("usd") or 0.0) if day.get("day") == dt.date.today().isoformat() else 0.0

    def _due(self, st: dict) -> list[feeds.Feed]:
        """The feeds to look at now: every one but an agent source whose time has not come, whose ceiling
        is reached, or while the run is out of 🪙. An agent source's look is marked started (`agent_at`),
        so one that fails waits its `every=` too."""
        out, started, at = [], dict(st.get("agent_at") or {}), (st.get("agent_at") or {})
        self.waiting = {}
        for f in self.polled:
            if f.kind != "agent":
                out.append(f)
                continue
            why = feeds_agent.due(f, at.get(f.identity, ""), self.spent_today(f, st))
            if not why and not self.simulated and self.out_of_gold():
                why = "🪙 budget exhausted — it waits"
            if why:
                if why != "not yet":
                    self.waiting[f.line] = why
                continue
            started[f.identity] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            out.append(f)
        if started != at:
            self._save_state(agent_at=started)
        return out

    def _simulated_look(self) -> None:
        """The demo asks no server: the signals stay as the sandbox left them, and a source fails
        only as its state says (`simulated_errors`: source or `feed:<line>` → why; `simulated_kinds`: → how)."""
        sim = self._state().get("simulated_errors") or {}
        self.kinds.update({str(k): str(v) for k, v in (self._state().get("simulated_kinds") or {}).items()})
        for key in [k for k in self.errors if k in ("mail", "github", "look") or k.startswith("feed:")]:
            del self.errors[key]
        self.errors.update({str(k): str(v) for k, v in sim.items()})
        self.look = mailbox.Look(unread=len(self.unread("mail")), error=str(sim.get("mail", "")))
        self._looking, self.checked = False, watch.now_iso()[11:16]
        self.changed()

    def _failed(self, problem: str) -> None:
        self._looking = False
        self.errors["look"] = problem
        self.changed()

    def apply(self, look: mailbox.Look | None, gh: tuple | None, looks: list | None = None) -> None:
        self.errors.pop("look", None)
        if look is not None:
            self.apply_look(look)
        if gh is not None:
            signals, newest, err = gh
            self.errors.pop("github", None) if not err else self.errors.update(github=err)
            if err:
                self.kinds["github"] = watch.error_kind(err)
            for s in signals:
                self.add_signal(s)
            if newest:
                self._save_state(gh_last=newest)
        if looks:
            self.apply_feeds(looks)
        self._looking, self.checked = False, watch.now_iso()[11:16]      # last: `checked` means all of it
        self.changed()

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
        spend, today = dict(st.get("agent_spend") or {}), dt.date.today().isoformat()
        keep = dict(st.get("agent_keep") or {})
        for feed, got in looks:
            if got.keep:                                  # the ids it looked up: the next look skips those turns
                keep[feed.identity] = feeds_agent.kept({**(keep.get(feed.identity) or {}), **got.keep})
            if got.cost is not None:                      # an agent source's look, paid: today's spend
                day = spend.get(feed.identity) or {}
                usd = (float(day.get("usd") or 0.0) if day.get("day") == today else 0.0) + got.cost
                spend[feed.identity] = {"day": today, "usd": round(usd, 4)}
            if got.error:
                self.errors[f"feed:{feed.line}"] = got.error
                self.kinds[f"feed:{feed.line}"] = got.kind or "network"
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
        live = {f.identity for f, _ in looks} | {f.identity for f in self.feeds}   # an agent source not due keeps its own
        self._save_state(feeds_seen={k: v for k, v in seen.items() if k in live},
                         feeds_at={k: v for k, v in last.items() if k in live},
                         feeds_line={k: v for k, v in lines.items() if k in live}, feeds_me=me,
                         agent_spend={k: v for k, v in spend.items() if k in live},
                         agent_keep={k: v for k, v in keep.items() if k in live})
        self.changed()

    def apply_look(self, look: mailbox.Look) -> None:
        self._looking = False
        self.look = look
        if look.error:
            self.errors["mail"] = look.error
            self.kinds["mail"] = look.kind or "network"
            self.changed()
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
        self.changed()

    # -- read and unread ------------------------------------------------------------------------

    def unread(self, source: str | None = None) -> list[watch.Signal]:
        return [s for s in self.signals if not s.read and (source is None or s.source == source)]

    def signal(self, key: str) -> watch.Signal | None:
        return next((s for s in self.signals if s.key == key), None)

    def mark_read(self, sigs: list[watch.Signal] | None = None) -> int:
        """Mark `sigs` (all of them when None) read; how many were new."""
        fresh = [s for s in (self.signals if sigs is None else sigs) if not s.read]
        if not fresh:
            return 0
        for s in fresh:
            s.read = True
        read = (list(self._state().get("read") or []) + [s.key for s in fresh])[-READ_KEEP:]
        self._save_state(read=read)
        self.changed()
        return len(fresh)

    def read(self, sig: watch.Signal) -> None:
        """Read a signal in full (`reading`), and mark it read. Mail is fetched in a thread."""
        self.mark_read([sig])
        verdict = ("" if sig.kept is None else
                   f"\n\n🎯 {'matches' if sig.kept else 'not for'} the intent{': ' + sig.why if sig.why else ''}")
        if sig.source != "mail" or not sig.ref.isdigit():
            self._show(sig.key, f"**{sig.title}**\n\n{sig.source} · {sig.at}{verdict}\n\n---\n\n```\n{sig.body}\n```"
                       if sig.body else f"**{sig.title}**\n\n{sig.source} · {sig.at}{verdict}")
            return
        cfg, factory = self.config, type(self).imap_factory
        self._show(sig.key, "_reading…_")

        def work() -> None:
            try:
                text = mailbox.read(cfg, int(sig.ref), factory)
            except Exception as e:  # network trouble of every kind
                text = f"_could not read it: {e}_\n\n{sig.body}"
            self.town.call(self._show, sig.key, text + verdict)

        self._thread(work, "watch-read")

    def _show(self, key: str, md: str) -> None:
        self.reading = {"key": key, "markdown": md[:60000]}
        self.changed()

    def open_new(self) -> watch.Signal | None:
        """✉ Open new: the newest new signal (else the newest), read. None when nothing came in yet."""
        if not self.signals:
            return None
        new = self.unread()
        sig = new[0] if new else self.signals[0]
        self.read(sig)
        return sig

    def check_now(self) -> None:
        """↻ Check now: every source looks again, the schedule too."""
        self.refresh_data()
        self.tick()

    def simulate(self, source: str, title: str, body: str = "") -> watch.Signal | None:
        """The sandbox only (no server is asked there): a mail or a message arrives as if its source had
        sent it — kept, shown and sent down the roads like any new signal. None outside the sandbox."""
        if not self.simulated or source not in ICON or not title.strip():
            return None
        sig = watch.Signal(watch.now_iso(), source, title.strip(), body.strip(), f"sim-{time.time_ns()}")
        self.add_signal(sig)
        return sig

    # -- what is failing, and why ----------------------------------------------------------------

    def failing(self, source: str) -> bool:
        return source in self.errors or any(k.startswith(f"feed:{source}") for k in self.errors)

    def fails(self, key: str) -> str:
        """How the source under `key` (`mail`, `github`, `feed:<line>`) fails: login, target, network, or ""."""
        if key not in self.errors:
            return ""
        return self.kinds.get(key) or "network"

    def why(self, source: str) -> str:
        """What is wrong with a source, or ""."""
        if source in self.errors:
            return self.errors[source]
        return next((v for k, v in self.errors.items() if k.startswith(f"feed:{source}")), "")

    # -- the hut --------------------------------------------------------------------------------

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

    def counters(self, rows: int = 4) -> tuple[list[tuple[str, str]], tuple[int, str] | None]:
        """What is new per source, as the hut shows it: [(label, `3` | `99+` | `ERR`)] and, when more
        sources than `rows`, (how many more, what is new in them)."""
        shown = self.shown()
        rest: list[str] = []
        if len(shown) > rows:
            shown, rest = shown[:rows - 1], shown[rows - 1:]
        out = [(self.label(s), "ERR" if self.failing(s) else count(len(self.unread(s)))) for s in shown]
        more = (len(rest), count(sum(len(self.unread(s)) for s in rest))) if rest else None
        return out, more

    def newest(self) -> watch.Signal | None:
        """The newest signal kept (one the Lookout let through, or any when no intent is asked)."""
        return next((s for s in self.signals if s.kept is not False), None)

    def hut_lines(self, widths: list[int]) -> list[str]:
        """A narrow hut: what is new per source, a line each — `gmail    3`, `slack  99+`; ERR when it fails.
        A wide one (PREVIEW_W cells or more): the counters on one line, then a preview of the newest
        message — `✉ Dana Reyes: Can we move Thursday's…` — over the rows left, cut with an ellipsis."""
        rows = len(widths) or 4
        width = widths[0] if widths else 10
        if not self.sources:
            return ["no source", "yet"] + [""] * max(rows - 2, 0)
        if width < PREVIEW_W:
            shown, more = self.counters(rows)
            lines = [f"{label[:width - 4]:<{width - 4}}{n:>4}" for label, n in shown]
            if more:
                lines.append(f"+{more[0]} more"[:width - 4].ljust(width - 4) + f"{more[1]:>4}")
            return lines + [""] * (rows - len(lines))
        shown, more = self.counters(len(self.shown()))
        status = " ".join(f"{label} {n}" for label, n in shown)
        lines = [status if len(status) <= width else status[:width - 1] + "…"]
        sig = self.newest()
        if sig is not None:
            words = f"{ICON.get(sig.source, '·')} {sig.at[11:16]} {' '.join(sig.title.split())}"
            wrapped = textwrap.wrap(words, width) or [""]
            left = max(rows - 1, 1)
            if len(wrapped) > left:                         # cut cleanly: the last line that fits ends in …
                wrapped = wrapped[:left]
                wrapped[-1] = wrapped[-1][:width - 1].rstrip() + "…"
            lines += wrapped
        return lines[:rows] + [""] * (rows - len(lines))
