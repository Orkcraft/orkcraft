"""🗼 Add a source, as the Watchtower's worker runs it: the three steps' state, their work in threads.

The page shows the state (`view()`), the acts move it on: `open` → `start` (a service, or a pasted
link) → `log_in` (or a login this machine has) → `what` (the picks) → `save`. A source already
listed comes back by `edit`: at step 2 with its picks (Edit), or at step 1 with the rest kept (Log
in again); its Add then puts the new line where the old one was. Every call to a
service runs in a thread and comes back through `town.call`; the state lives here, so the panel can
close and open again — or the person go make a token — and find the step where they left it. A
typed secret is never kept: it goes to realm/logins.py on a good login, and is dropped on a bad one.

A service Claude Code has a connector for (`claude mcp list`, names only) offers a second way at
step 1: *Use Claude's connection* — no token, an `agent:` line (realm/feeds_agent.py), step 2 asks
what to listen for and how often, Check makes one paid look (§7.3).

docs/design/watchtower-quick-add.md §4.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import threading
import urllib.request
from dataclasses import asdict

from orkcraft.realm import feeds, feeds_agent, logins, quickadd, sources_link
from orkcraft.realm.quickadd import Refused, Verified



class Adding:
    def __init__(self, worker) -> None:
        self.w = worker
        self.gh = ""                      # who gh is logged in as ("" not yet known or not logged in)
        self.claude: list[feeds_agent.Connector] = []     # the servers Claude Code has (asked when the picker opens)
        self.reset()

    def reset(self) -> None:
        self.step = ""                    # "" closed · pick · login · what · check
        self.service = ""
        self.busy = ""                    # what runs now, in words ("" idle)
        self.error = ""
        self.link: sources_link.Link | None = None
        self.login: Verified | None = None
        self.options: list[quickadd.Option] = []
        self.picks: list[str] = []
        self.about_me = True
        self.folder = "INBOX"
        self.plan: quickadd.Plan | None = None
        self.found = 0
        self.editing = ""                 # the source being made again (`feed:<line>`, `mail`, `github`), or ""
        self.me = ""                      # Discord: the person's user id, to tell mentions
        self.invite = ""                  # Discord: the link that adds the bot to a server
        self.prefill: dict[str, str] = {}     # what the login form starts with (never a secret)
        self.everything = False           # the whole service at once (§6)
        self.intent = ""                  # what to listen for, asked with Everything when the tower has none
        self.guilds: tuple[str, ...] = ()     # Discord: the servers the bot is in
        self.via: feeds_agent.Connector | None = None     # through Claude's connection instead of a login
        self.ask = ""
        self.every = feeds_agent.EVERY_DEFAULT
        self.ceiling = feeds_agent.CEILING_DEFAULT
        self.first: feeds.Look | None = None  # the agent source's first look: what it saw, its ids, its cost

    # -- the runners: the worker's, so tests fake one place ----------------------------------------------

    def _opener(self):
        return type(self.w).feed_opener or urllib.request.urlopen

    def _runner(self):
        return type(self.w).gh_runner or subprocess.run

    def _thread(self, busy: str, work, done) -> None:
        """Run `work()` off the town's thread; `done(result)` back on it, a Refused shown as the step's error."""
        self.busy, self.error = busy, ""
        self.w.changed()

        def run() -> None:
            try:
                result, problem = work(), ""
            except Refused as e:
                result, problem = None, str(e)
            except Exception as e:                    # a broken call never breaks the tower
                result, problem = None, f"Something went wrong: {e}"[:300]
            self.w.town.call(self._back, done, result, problem)

        threading.Thread(target=run, daemon=True, name=f"watch-add-{self.w.building_id}").start()

    def _back(self, done, result, problem: str) -> None:
        self.busy = ""
        if problem:
            self.error = problem
        else:
            done(result)
        self.w.changed()

    # -- the steps ----------------------------------------------------------------------------------------

    def open(self) -> None:
        """The picker: which services already have a login here (gh asked in a thread)."""
        self.reset()
        self.step = "pick"
        self.w.changed()
        if not self.w.simulated:
            runner, mcp = self._runner(), type(self.w).mcp_runner
            threading.Thread(target=lambda: self.w.town.call(self._gh, quickadd.gh_login(runner)),
                             daemon=True, name=f"watch-gh-{self.w.building_id}").start()
            threading.Thread(target=lambda: self.w.town.call(self._claude, feeds_agent.connectors(mcp)),
                             daemon=True, name=f"watch-mcp-{self.w.building_id}").start()

    def _gh(self, who: str) -> None:
        self.gh = who
        self.w.changed()

    def _claude(self, found: list) -> None:
        self.claude = found
        self.w.changed()

    def connector(self, service: str = "") -> feeds_agent.Connector | None:
        return feeds_agent.connector_for(service or self.service, self.claude)

    def recognise(self, text: str) -> sources_link.Link | None:
        link = sources_link.recognise(text, [e["account"] for e in logins.listed("gitlab")])
        if link is None or link.service not in quickadd.SERVICES:
            return None
        return link

    def start(self, service: str, link: sources_link.Link | None = None) -> None:
        if service not in quickadd.SERVICES:
            raise Refused(f"{service!r} cannot be added here yet")
        if self.w.simulated:
            raise Refused("The demo asks no service: add sources in a real town")
        keep_gh = self.gh
        self.reset()
        self.gh, self.service, self.link, self.step = keep_gh, service, link, "login"
        if link and link.target:
            self.picks = [link.target]
        if service == "github":                       # gh's login: asked again each time (Check again)
            self.check_gh()
            return
        if service == "gitlab" and (not link or link.site == "gitlab.com"):
            self._glab("gitlab.com")
            return
        if link and link.site and service == "gitlab":
            self.prefill = {"host": link.site}
        self.w.changed()

    def check_gh(self) -> None:
        runner = self._runner()

        def logged_in(who: str) -> None:
            self.gh = who
            self.use(Verified("github", who, who))

        self._thread("Asking gh…", lambda: quickadd.verify("github", {}, runner=runner).who, logged_in)

    def _glab(self, host: str) -> None:
        """GitLab: glab's login, when there is one, is step 1 done; else the form, without a word *(check)*."""
        runner = self._runner()

        def work():
            try:
                return quickadd.verify("gitlab", {"host": host}, runner=runner)
            except Refused:
                return None

        self._thread("Asking glab…", work, lambda login: login and self.use(login))

    def logins_here(self) -> list[Verified]:
        return quickadd.kept(self.service) if self.service else []

    def log_in(self, values: dict) -> None:
        """Check the login with the service; a good one is kept and step 2 lists what there is."""
        if self.link and self.link.site and self.service in quickadd.ATLASSIAN and not values.get("site"):
            values = {**values, "site": self.link.site}
        if self.service == "gitlab" and not values.get("host"):
            values = {**values, "host": (self.link.site if self.link and self.link.site else "") or
                      self.prefill.get("host", "")}
        opener, runner, imap = self._opener(), self._runner(), type(self.w).imap_factory
        self._thread("Checking the login…", lambda: quickadd.verify(self.service, values, opener, runner, imap), self.use)

    def use(self, login: Verified) -> None:
        """A login that works (just made, or kept here): on to what to hear."""
        self.login, self.step, self.error = login, "what", ""
        if self.service == "gmail":
            self.w.changed()
            return
        opener, runner, root = self._opener(), self._runner(), self.w.repo_root
        files = list(self.picks) if self.service == "figma" else None
        if self.service == "discord":                 # the invite needs the bot's id
            def work():
                bot = quickadd.discord_bot(login, opener)
                return bot, quickadd.options(bot, opener), quickadd.discord_guilds(bot, opener)

            def listed(result) -> None:
                self.login, self.invite, self.guilds = result[0], quickadd.discord_invite(result[0]), result[2]
                self._listed(result[1])

            self._thread("Looking what the bot can see…", work, listed)
            return
        self._thread("Looking what there is…", lambda: quickadd.options(login, opener, runner, root, files), self._listed)

    def list_again(self) -> None:
        """Step 2 asks the service again (Discord: after the bot was invited)."""
        if self.login is None or self.step != "what":
            raise Refused("Log in first")
        self.use(self.login)

    def use_kept(self, account: str) -> None:
        login = next((x for x in self.logins_here() if x.account == account), None)
        if login is None:
            raise Refused("That login is gone — log in again")
        self.use(login)

    def _listed(self, found: list[quickadd.Option]) -> None:
        ids = {o.id for o in found}
        kept = [quickadd.Option(p, p, "picked before" if self.editing else "from the link", True)
                for p in self.picks if p not in ids]          # a pick the list does not show stays, ticked
        self.options = kept + found
        self.picks = list(self.picks) + [o.id for o in found if o.picked and o.id not in self.picks]

    # -- through Claude's connection (§7.3): no token, a paid look every `every` minutes -----------------

    def use_claude(self) -> None:
        c = self.connector()
        if c is None:
            raise Refused(f"Claude Code has no {quickadd.SERVICES[self.service].label} connection here")
        if c.status != "connected":
            raise Refused(f"Claude's {c.name} connection {c.status} — run /mcp in Claude Code, then try again")
        self.via, self.login, self.step, self.error = c, None, "what", ""
        self.ask = self.ask or feeds_agent.READS[self.service][2]
        self.w.changed()

    def what_claude(self, ask: str, every: int, ceiling: float) -> None:
        """The agent line, and its first look — one model run, paid — before anything is saved."""
        if self.via is None:
            raise Refused("Pick Claude's connection first")
        self.ask = " ".join(ask.split())[:300] or feeds_agent.READS[self.service][2]
        self.every, self.ceiling = max(feeds_agent.EVERY_MIN, every), max(0.0, ceiling)
        text = feeds_agent.line(self.service, self.via.server, self.ask, self.every, self.ceiling)
        feed, err = feeds.parse(text)
        if feed is None:
            raise Refused(err)
        run, label = type(self.w).agent_runner, quickadd.SERVICES[self.service].label

        def done(got: feeds.Look) -> None:
            self.plan = quickadd.Plan({}, f"{label} through Claude's {self.via.name} — {self.ask}", text)
            self.first, self.found, self.step, self.error = got, len(got.items), "check", got.error

        self._thread("Asking Claude — about half a minute…", lambda: feeds_agent.look(feed, run=run), done)

    def _seed(self, line: str) -> None:
        """The first look counts: what it saw is seen, its ids kept, its cost spent, the next look in `every`."""
        feed, _ = feeds.parse(line)
        got = self.first
        if feed is None or got is None or got.error:
            return
        st, ident = self.w._state(), feed.identity
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        spend = dict(st.get("agent_spend") or {})
        today = dt.date.today().isoformat()
        day = spend.get(ident) or {}
        spend[ident] = {"day": today, "usd": round((float(day.get("usd") or 0.0) if day.get("day") == today else 0.0)
                                                    + (got.cost or 0.0), 4)}
        self.w._save_state(feeds_seen={**(st.get("feeds_seen") or {}), ident: [i.key for i in got.items][-feeds.SEEN_KEEP:]},
                           feeds_at={**(st.get("feeds_at") or {}), ident: now},
                           feeds_line={**(st.get("feeds_line") or {}), ident: line},
                           agent_at={**(st.get("agent_at") or {}), ident: now}, agent_spend=spend,
                           agent_keep={**(st.get("agent_keep") or {}), ident: got.keep} if got.keep else
                           dict(st.get("agent_keep") or {}))

    def add_files(self, text: str) -> None:
        """Figma: pasted file (or team) links join the list."""
        keys = []
        for part in text.split():
            link = sources_link.recognise(part)
            if link and link.service == "figma":
                keys.append(link.target)
        if not keys:
            raise Refused("Paste a Figma link — figma.com/design/… or figma.com/files/team/…")
        login = self.login
        opener = self._opener()
        files = [k for k in keys if k.startswith("team:")]
        self.picks += [k for k in keys if not k.startswith("team:") and k not in self.picks]
        known = {o.id for o in self.options}
        self.options += [quickadd.Option(k, k, "from the link", True) for k in self.picks if k not in known]
        if files and login is not None:
            self._thread("Looking in the team…", lambda: quickadd.options(login, opener, files=files),
                         lambda more: self.options.extend(o for o in more if o.id not in {x.id for x in self.options}))
        else:
            self.w.changed()

    def what(self, picks: list[str], about_me: bool, folder: str = "INBOX", me: str = "",
             everything: bool = False, intent: str = "") -> None:
        """The picks → the setting it makes, and the first look, before anything is saved. Everything with
        an intent keeps the intent too (the Lookout keeps a whole service calm)."""
        if self.login is None:
            raise Refused("Log in first")
        s = quickadd.SERVICES[self.service]
        self.picks, self.about_me, self.folder, self.me = picks, about_me, folder, me.strip()
        self.everything, self.intent = everything and bool(s.everything), " ".join(intent.split())[:500]
        login, opener, runner, imap = self.login, self._opener(), self._runner(), type(self.w).imap_factory
        whole, guilds, ask = self.everything, self.guilds, self.intent
        quickadd.plan(login, picks, about_me, folder, "", whole, guilds)     # what is wrong with the picks, at once

        def work():
            p = quickadd.plan(login, picks, about_me, folder, quickadd.discord_me(login, self.me, opener)
                              if login.service == "discord" else "", whole, guilds)
            if whole and ask and not self.w.intent:
                p.changes["intent"] = ask
            return p, quickadd.first_look(login, p, opener, runner, imap)

        def done(result) -> None:
            p, (found, problem) = result
            self.plan, self.found = p, found
            self.step = "check"
            self.error = problem

        self._thread("Making the first look…", work, done)

    def save(self) -> str:
        """Add: the setting is saved and the tower listens with it. The source's id."""
        if self.plan is None or self.step != "check" or self.error:
            raise Refused("Check it first")
        changes = dict(self.plan.changes)
        lines = [str(x) for x in self.w.config.get("feeds") or []]
        if self.editing.startswith("feed:"):              # the new line where the old one was
            old = self.editing[5:]
            at = lines.index(old) if old in lines else len(lines)
            lines = [x for x in lines if x != old]
            if self.plan.feed and self.plan.feed not in lines:
                lines.insert(at, self.plan.feed)
            changes["feeds"] = quickadd.with_feed(lines, self.plan.feed) if self.plan.feed else (lines or None)
        elif self.plan.feed:
            changes["feeds"] = quickadd.with_feed(lines, self.plan.feed)
        if self.service == "github" and (self.editing == "github" or str(self.w.config.get("github") or "") in self.picks):
            changes["github"] = None                      # the old one-repo setting moves into the line
        if not self.w.save_config(changes):
            raise Refused("Not saved")
        if self.via is not None and self.plan.feed:
            self._seed(self.plan.feed)
        service = self.service
        self.reset()
        self.w.restart()
        return service

    def edit(self, source: str, relogin: bool = False) -> None:
        """A listed source made again: Edit at step 2 with its picks, Log in again at step 1, the rest kept."""
        if self.w.simulated:
            raise Refused("The demo asks no service: change sources in a real town")
        agent = _agent(source)
        if agent is not None:                             # through Claude: step 2, what it asks and how often
            feed, service = agent
            keep_gh = self.gh
            self.reset()
            self.gh, self.service, self.editing, self.step = keep_gh, service, source, "what"
            self.via = feeds_agent.Connector(feed.opts["server"], "connected")
            self.ask, self.every, self.ceiling = feed.opts.get("ask", ""), feeds_agent.every(feed), feeds_agent.ceiling(feed)
            self.w.changed()
            return
        made = quickadd.from_source(self.w.config, source)
        keep_gh = self.gh
        self.reset()
        login = made.login
        self.gh, self.service, self.editing = keep_gh, login.service, source
        self.picks, self.about_me, self.folder, self.me = list(made.picks), made.about_me, made.folder, made.me
        self.everything = made.everything
        if login.service == "gmail":
            self.prefill = {"email": login.account}
        elif login.site and login.service in (*quickadd.ATLASSIAN, "gitlab"):
            self.link = sources_link.Link(login.service, login.site, "", "")
            self.prefill = {"site" if login.service in quickadd.ATLASSIAN else "host": login.site}
        if relogin or (login.service != "github" and not all(logins.resolve(r) for r in login.refs.values())):
            self.step = "login"                           # a login that is gone cannot list step 2
            self.w.changed()
            return
        if login.service == "github" and not login.refs:
            self.step = "login"
            self.check_gh()
            return
        self.use(login)

    def back(self) -> None:
        before = {"login": "pick", "what": "login", "check": "what"}.get(self.step, "pick")
        self.step = "pick" if before == "login" and self.service == "github" else before   # gh's login is no step
        if self.step == "login":
            self.via = None                               # back to the choice: a login, or Claude's connection
        if self.step == "pick":                           # back to the picker: no longer the source being edited
            self.service, self.login, self.link, self.editing, self.prefill = "", None, None, "", {}
        self.error = ""
        self.w.changed()

    def close(self) -> None:
        self.reset()
        self.w.changed()

    # -- what the page draws ------------------------------------------------------------------------------

    def services(self) -> list[dict]:
        out = []
        for s in quickadd.SERVICES.values():
            kept = quickadd.kept(s.id)
            c = self.connector(s.id)
            mark = (f"✓ gh · {self.gh}" if s.id == "github" and self.gh else
                    f"✓ {kept[0].account}" if kept else
                    "✓ in Claude" if c and c.status == "connected" else
                    f"in Claude, {c.status}" if c else
                    {"github": "gh or a token", "gitlab": "glab or a token", "gmail": "an app password",
                     "discord": "a bot"}.get(s.id, "a token"))
            out.append({"id": s.id, "label": s.label, "mark": mark, "ready": mark.startswith("✓")})
        return out

    def view(self) -> dict | None:
        if not self.step:
            return None
        s = quickadd.SERVICES.get(self.service)
        out: dict = {"step": self.step, "service": self.service, "busy": self.busy, "error": self.error,
                     "link": asdict(self.link) if self.link else None}
        if self.step == "pick":
            out["services"] = self.services()
            return out
        c = self.connector()
        out["claude"] = {"name": c.name, "status": c.status} if c and self.service in feeds_agent.READS else None
        out["via"] = self.via.name if self.via else ""
        if self.via:
            out.update(ask=self.ask, every_min=self.every, ceiling=self.ceiling, every_min_least=feeds_agent.EVERY_MIN)
        host = self.prefill.get("host") or (self.link.site if self.link and self.service == "gitlab" else "") or "gitlab.com"
        out.update(label=s.label, note=s.note, picks_of=s.picks, about_me_says=s.about_me,
                   fields=[asdict(f) for f in s.fields],
                   how=[{"text": t, "url": u.replace("{host}", host)} for t, u in s.how],
                   editing=self.editing, prefill=dict(self.prefill), me=self.me, invite=self.invite,
                   everything_says=s.everything, everything=self.everything, intent=self.intent,
                   asks_intent=not self.w.intent,
                   whole_team="Whole team — needs push, not built yet" if self.service == "figma" else "",
                   kept=[] if self.editing and self.step == "login" else       # Log in again: not the refused one
                   [{"account": x.account, "who": x.who} for x in self.logins_here()],
                   who=self.login.who if self.login else f"Claude's {self.via.name} connection" if self.via else "",
                   options=[asdict(o) for o in self.options], picks=list(self.picks), about_me=self.about_me,
                   folder=self.folder)
        if self.step == "check" and self.plan is not None:
            every = "every 2 min"
            if self.via:                                  # through Claude: what each look costs
                cost = self.first.cost if self.first else None
                every = (f"every {self.every} min, a model run each look"
                         + (f" — this one ≈ ${cost:.2f}" if cost is not None else "") + f", at most ${self.ceiling:.2f} a day")
            out.update(says=self.plan.says, found=self.found, line=self.plan.feed or "", every=every,
                       listens_for=str(self.plan.changes.get("intent") or self.w.intent or ""))
        return out


def remove(worker, source: str) -> bool:
    """Take a source out of the tower's settings: `mail`, `github`, `cron`, `webhook` or `feed:<line>`."""
    if source.startswith("feed:"):
        line = source[5:]
        lines = [str(x) for x in worker.config.get("feeds") or []]
        if line not in lines:
            raise Refused("That source is gone already")
        changes: dict = {"feeds": [x for x in lines if x != line] or None}
    else:
        changes = {"mail": {"host": None, "user": None, "user_env": None, "password_env": None, "folder": None, "port": None},
                   "github": {"github": None}, "cron": {"cron": None},
                   "webhook": {"webhook_port": None, "webhook_secret_env": None}}.get(source)
        if changes is None:
            raise Refused(f"{source!r} is not a source")
    if not worker.save_config(changes):
        raise Refused("Not saved")
    worker.restart()
    return True


def _hears(feed: feeds.Feed) -> list[str]:
    """What a feed line hears, in words: `acme.atlassian.net · about you · projects WEB`."""
    o = feed.opts
    out = [o["site"]] if o.get("site") else []
    if feed.kind == "agent":
        from orkcraft.realm import feeds_agent
        return [f"via Claude · {o.get('server', '')}", f"every {feeds_agent.every(feed)} min", o.get("ask", "")]
    if (feed.on("everything") or o.get("notifications") == "all" or o.get("guilds")
            or o.get("jql") == feeds.EVERYTHING_JQL or o.get("cql") == feeds.EVERYTHING_CQL):
        out.append("everything" + (f" · servers {o['guilds']}" if o.get("guilds") else ""))
        if o.get("repos"):
            out.append(f"repos {o['repos']}")
        return out + (["mentions of you told"] if o.get("me") else [])
    jql = o.get("jql", "")
    if feed.kind in ("slack", "confluence") or (feed.kind == "jira" and (not jql or feeds.JIRA_JQL in jql)):
        out.append("about you")
    keys = re.search(r"project in \(([^)]*)\)", jql)
    if keys:
        out.append(f"projects {keys.group(1)}")
    elif jql and feeds.JIRA_JQL not in jql:
        out.append(f"JQL {jql}")
    if feed.kind == "gitlab":
        out.append(feed.host)
    if feed.on("notifications") or feed.on("todos"):
        out.append("your notifications" if feed.kind == "github" else "your to-dos")
    for k, word in (("channels", "channels"), ("spaces", "spaces"), ("files", "files"), ("cql", "CQL"),
                    ("repos", "repos"), ("projects", "projects")):
        if o.get(k):
            out.append(f"{word} {o[k]}")
    if o.get("me"):
        out.append("mentions of you told")
    return out


FIX = {"login": "Log in again", "target": "Edit", "network": ""}      # what a failing source's line offers


def _agent(source: str) -> tuple[feeds.Feed, str] | None:
    """An `agent:` line the steps can make again: the feed and its service."""
    feed, _ = feeds.parse(source.removeprefix("feed:")) if source.startswith("feed:") else (None, "")
    if feed is None or feed.kind != "agent" or feed.opts.get("tool", "claude") != "claude":
        return None
    service = feeds_agent.service_of(feed)
    return (feed, service) if service else None


def _editable(worker, source: str) -> bool:
    if _agent(source) is not None:
        return True
    try:
        quickadd.from_source(worker.config, source)
    except Refused:
        return False
    return True


def _entry(worker, source: str, kind: str, label: str, line: str, why: str) -> dict:
    fails = worker.fails(source) if why else ""
    return {"id": source, "kind": kind, "label": label, "line": line, "why": why, "fails": fails,
            "fix": FIX.get(fails, ""), "editable": _editable(worker, source)}


def listed(worker) -> list[dict]:
    """The tower's sources as Sources & intent lists them: what, how, its state, the id to remove it by."""
    c = worker.config
    out = []
    if c.get("host"):
        who = c.get("user") or c.get("user_env") or ""
        out.append(_entry(worker, "mail", "mail", worker.label("mail"),
                          f"{who} · {c.get('folder') or 'INBOX'}".strip(" ·"), worker.why("mail")))
    if c.get("github"):
        out.append(_entry(worker, "github", "github", "GitHub", f"repos {c['github']} · gh", worker.errors.get("github", "")))
    for line in [str(x) for x in c.get("feeds") or []]:
        feed, _ = feeds.parse(line)
        kind = feed.kind if feed else "?"
        what = " · ".join(_hears(feed)) if feed else line
        how = ("a login" if feed and any(v.startswith("keychain:") for v in feed.opts.values()) else
               "gh" if kind == "github" and not feed.opts.get("token") else
               "glab" if kind == "gitlab" and not feed.opts.get("token") else "the environment")
        if kind == "agent":                               # no login here: what it costs instead
            how = f"≈ ${worker.spent_today(feed):.2f} today"
            if line in worker.waiting:
                how += f" · {worker.waiting[line]}"
        out.append(_entry(worker, f"feed:{line}", kind, quickadd.SERVICES[kind].label if kind in quickadd.SERVICES else
                          "Through Claude" if kind == "agent" else kind,
                          f"{what} · {how}".strip(" ·"), worker.errors.get(f"feed:{line}", "")))
    if c.get("cron"):
        out.append(_entry(worker, "cron", "cron", "Schedule", str(c["cron"]), ""))
    if c.get("webhook_port"):
        out.append(_entry(worker, "webhook", "webhook", "Webhook", f"127.0.0.1:{c['webhook_port']}", worker.why("webhook")))
    return out
