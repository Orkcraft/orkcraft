"""🗼 Add a source, as the Watchtower's worker runs it: the three steps' state, their work in threads.

The page shows the state (`view()`), the acts move it on: `open` → `start` (a service, or a pasted
link) → `log_in` (or a login this machine has) → `what` (the picks) → `save`. Every call to a
service runs in a thread and comes back through `town.call`; the state lives here, so the panel can
close and open again — or the person go make a token — and find the step where they left it. A
typed secret is never kept: it goes to realm/logins.py on a good login, and is dropped on a bad one.

docs/design/watchtower-quick-add.md §4.
"""
from __future__ import annotations

import re
import subprocess
import threading
import urllib.request
from dataclasses import asdict

from orkcraft.realm import feeds, quickadd, sources_link
from orkcraft.realm.quickadd import Refused, Verified



class Adding:
    def __init__(self, worker) -> None:
        self.w = worker
        self.gh = ""                      # who gh is logged in as ("" not yet known or not logged in)
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
            runner = self._runner()
            threading.Thread(target=lambda: self.w.town.call(self._gh, quickadd.gh_login(runner)),
                             daemon=True, name=f"watch-gh-{self.w.building_id}").start()

    def _gh(self, who: str) -> None:
        self.gh = who
        self.w.changed()

    def recognise(self, text: str) -> sources_link.Link | None:
        link = sources_link.recognise(text)
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
            runner = self._runner()

            def logged_in(who: str) -> None:
                self.gh = who
                self.use(Verified("github", who, who))

            self._thread("Asking gh…", lambda: quickadd.verify("github", {}, runner=runner).who, logged_in)
            return
        self.w.changed()

    def logins_here(self) -> list[Verified]:
        return quickadd.kept(self.service) if self.service else []

    def log_in(self, values: dict) -> None:
        """Check the login with the service; a good one is kept and step 2 lists what there is."""
        if self.link and self.link.site and self.service in quickadd.ATLASSIAN and not values.get("site"):
            values = {**values, "site": self.link.site}
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
        self._thread("Looking what there is…", lambda: quickadd.options(login, opener, runner, root, files), self._listed)

    def use_kept(self, account: str) -> None:
        login = next((x for x in self.logins_here() if x.account == account), None)
        if login is None:
            raise Refused("That login is gone — log in again")
        self.use(login)

    def _listed(self, found: list[quickadd.Option]) -> None:
        self.options = found
        ids = {o.id for o in found}
        self.picks = [p for p in self.picks if p in ids or self.service == "figma"] + \
                     [o.id for o in found if o.picked and o.id not in self.picks]

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

    def what(self, picks: list[str], about_me: bool, folder: str = "INBOX") -> None:
        """The picks → the setting it makes, and the first look, before anything is saved."""
        if self.login is None:
            raise Refused("Log in first")
        self.picks, self.about_me, self.folder = picks, about_me, folder
        p = quickadd.plan(self.login, picks, about_me, folder)
        login, opener, runner, imap = self.login, self._opener(), self._runner(), type(self.w).imap_factory

        def done(result: tuple[int, str]) -> None:
            found, problem = result
            self.plan, self.found = p, found
            self.step = "check"
            self.error = problem

        self._thread("Making the first look…", lambda: quickadd.first_look(login, p, opener, runner, imap), done)

    def save(self) -> str:
        """Add: the setting is saved and the tower listens with it. The source's id."""
        if self.plan is None or self.step != "check" or self.error:
            raise Refused("Check it first")
        changes = dict(self.plan.changes)
        if self.plan.feed:
            changes["feeds"] = quickadd.with_feed(self.w.config.get("feeds") or [], self.plan.feed)
        if not self.w.save_config(changes):
            raise Refused("Not saved")
        service = self.service
        self.reset()
        self.w.restart()
        return service

    def back(self) -> None:
        before = {"login": "pick", "what": "login", "check": "what"}.get(self.step, "pick")
        self.step = "pick" if before == "login" and self.service == "github" else before   # gh's login is no step
        if self.step == "pick":
            self.service, self.login, self.link = "", None, None
        self.error = ""
        self.w.changed()

    def close(self) -> None:
        self.reset()
        self.w.changed()

    # -- what the page draws ------------------------------------------------------------------------------

    def services(self) -> list[dict]:
        out = []
        for s in quickadd.SERVICES.values():
            kept = quickadd.kept(s.id) if s.id != "github" else []
            mark = (f"✓ gh · {self.gh}" if s.id == "github" and self.gh else
                    f"✓ {kept[0].account}" if kept else
                    {"github": "gh", "gmail": "an app password"}.get(s.id, "a token"))
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
        out.update(label=s.label, note=s.note, picks_of=s.picks, about_me_says=s.about_me,
                   fields=[asdict(f) for f in s.fields], how=[{"text": t, "url": u} for t, u in s.how],
                   kept=[{"account": x.account, "who": x.who} for x in self.logins_here()],
                   who=self.login.who if self.login else "",
                   options=[asdict(o) for o in self.options], picks=list(self.picks), about_me=self.about_me,
                   folder=self.folder)
        if self.step == "check" and self.plan is not None:
            out.update(says=self.plan.says, found=self.found, line=self.plan.feed or "",
                       every="every 2 min")
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
    jql = o.get("jql", "")
    if feed.kind in ("slack", "confluence") or (feed.kind == "jira" and (not jql or feeds.JIRA_JQL in jql)):
        out.append("about you")
    keys = re.search(r"project in \(([^)]*)\)", jql)
    if keys:
        out.append(f"projects {keys.group(1)}")
    elif jql and feeds.JIRA_JQL not in jql:
        out.append(f"JQL {jql}")
    for k, word in (("channels", "channels"), ("spaces", "spaces"), ("files", "files"), ("cql", "CQL")):
        if o.get(k):
            out.append(f"{word} {o[k]}")
    return out


def listed(worker) -> list[dict]:
    """The tower's sources as Sources & intent lists them: what, how, its state, the id to remove it by."""
    c = worker.config
    out = []
    if c.get("host"):
        who = c.get("user") or c.get("user_env") or ""
        out.append({"id": "mail", "kind": "mail", "label": worker.label("mail"),
                    "line": f"{who} · {c.get('folder') or 'INBOX'}".strip(" ·"), "why": worker.why("mail")})
    if c.get("github"):
        out.append({"id": "github", "kind": "github", "label": "GitHub", "line": str(c["github"]), "why": worker.why("github")})
    for line in [str(x) for x in c.get("feeds") or []]:
        feed, _ = feeds.parse(line)
        kind = feed.kind if feed else "?"
        what = " · ".join(_hears(feed)) if feed else line
        how = "a login" if feed and any(v.startswith("keychain:") for v in feed.opts.values()) else "the environment"
        out.append({"id": f"feed:{line}", "kind": kind, "label": quickadd.SERVICES[kind].label if kind in quickadd.SERVICES else kind,
                    "line": f"{what} · {how}".strip(" ·"), "why": worker.errors.get(f"feed:{line}", "")})
    if c.get("cron"):
        out.append({"id": "cron", "kind": "cron", "label": "Schedule", "line": str(c["cron"]), "why": ""})
    if c.get("webhook_port"):
        out.append({"id": "webhook", "kind": "webhook", "label": "Webhook", "line": f"127.0.0.1:{c['webhook_port']}",
                    "why": worker.why("webhook")})
    return out
