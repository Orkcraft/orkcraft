"""The dashboard set's state, building by building: what each one would hold after a few days of
work, so its closed card, its command preview and its full window all have something to show.

Called by `dashboard.prepare` once the sandbox is a git repository. Everything is written to the
places the workers read (`.orkcraft/<type>/<building>/`, the ledger, the wikis); nothing here asks a
model or the network. Times are relative to the build, so "today" is today whenever it is built.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from orkcraft.core.workers import state_dir


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _iso(t: dt.datetime) -> str:
    return t.isoformat(timespec="seconds")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def before_commit(root: Path, now: dt.datetime) -> None:
    """What the first commit holds: the calendar of this week, the web folder, the general wiki."""
    for seed in (war_drum, web, general_wiki):
        seed(root, now)


def after_commit(root: Path, now: dt.datetime) -> None:
    """The branches are there: each building's state, and the web folder's changes."""
    for seed in (pit, watchtower, signpost, mills, horn, fields, forest, barracks, council, loot, crag,
                 catapult, workshop, town_hall, sessions, ledger):
        seed(root, now)


def ledger(root: Path, now: dt.datetime) -> None:
    """The runs of the buildings whose history is seeded here, in the ledger Info reads."""
    from orkcraft.realm import metrics
    for bid, runs in (("brief", ((1440, "done", 0.0), (600, "error", 0.0), (300, "done", 0.0), (40, "done", 0.0))),
                      ("notes_mill", ((280, "done", 0.03), (160, "error", 0.0), (11, "done", 0.04), (3, "error", 0.02))),
                      ("counter", ((500, "done", 0.0), (300, "done", 0.0), (180, "error", 0.0), (95, "done", 0.0),
                                   (60, "done", 0.0), (12, "done", 0.0))),
                      ("launcher", ((1500, "done", 0.0), (280, "error", 0.0), (270, "done", 0.0), (10, "done", 0.0))),
                      ("crossroads", tuple((300 - i * 40, "done", 0.0) for i in range(7))),
                      ("gate_pit", ((310, "done", 0.0), (95, "done", 0.0), (12, "done", 0.0))),
                      ("drop", ((240, "done", 0.0), (185, "done", 0.0), (40, "done", 0.04)))):
        for minutes, outcome, cost in runs:
            metrics.record_run(root, bid, outcome, cost, int(cost * 40000) or None,
                               now=now - dt.timedelta(minutes=minutes))


# -- 1. intake and routing ------------------------------------------------------------------------------

def pit(root: Path, now: dt.datetime) -> None:
    """What was dropped in the two Pits, and where each drop went (with what it cost)."""
    from orkcraft.core.workers.pit import item_id
    from orkcraft.realm import pit as pt
    note = Path(".orkcraft/pit/notes") / f"{now:%Y%m%d}-release.md"
    (root / note).parent.mkdir(parents=True, exist_ok=True)
    (root / note).write_text("release notes for v0.2: the Town Hall, typed buildings, roofs\n", encoding="utf-8")
    ago = lambda m: _iso(now - dt.timedelta(minutes=m))
    items = [pt.Item(ago(310), "doc", "docs/handbook/releases.md", "releases.md"),
             pt.Item(ago(240), "link", "https://github.com/orkcraft/orkcraft-demo/pull/12", "PR #12 · Login form"),
             pt.Item(ago(185), "image", "web/assets/logo.png", "logo.png"),
             pt.Item(ago(95), "code", "src/app.py", "app.py"),
             pt.Item(ago(40), "file", "docs/notes/ideas.md", "ideas.md"),
             pt.Item(ago(12), "text", str(note), "release notes for v0.2")]
    pt.log(root, items)
    stop = lambda b, t, ev, kind, value, m: {"building": b, "title": t, "event": ev, "kind": kind, "value": value,
                                             "at": ago(m)}
    chains = {
        "drop": {
            item_id(items[0]): {"cost": 0.0, "hops": ["drop", "brief"],
                                "stops": [stop("brief", "Daily brief", "mill.done", "text", "### Daily brief …", 309)]},
            item_id(items[4]): {"cost": 0.04, "hops": ["drop", "brief"],
                                "stops": [stop("brief", "Daily brief", "mill.done", "text", "### Daily brief\n\nideas.md", 39)]},
            item_id(items[2]): {"cost": 0.0, "hops": ["drop"], "stops": []},
        },
        "gate_pit": {
            item_id(items[5]): {"cost": 0.06, "hops": ["gate_pit", "crossroads", "notes_mill", "launcher"],
                                "stops": [stop("notes_mill", "Release notes", "mill.done", "text",
                                               '{"notes": "v0.2: the Town Hall, typed buildings, roofs"}', 11),
                                          stop("launcher", "Release hook", "catapult.fired", "text", "201 Created", 10)]},
            item_id(items[1]): {"cost": 0.0, "hops": ["gate_pit", "crossroads"], "stops": []},
            item_id(items[3]): {"cost": 0.02, "hops": ["gate_pit", "counter"],
                                "stops": [stop("counter", "Word Count", "workshop.done", "text", '{"words": 4}', 94)]},
        },
    }
    for bid, chain in chains.items():
        _json(state_dir(root, "pit", bid) / "chains.json", chain)


FEEDS = ["slack: token=DEMO_SLACK_TOKEN channels=C0DEMO1",
         "jira: site=acme.atlassian.net user=DEMO_ATL_EMAIL token=DEMO_ATL_TOKEN",
         "confluence: site=acme.atlassian.net user=DEMO_ATL_EMAIL token=DEMO_ATL_TOKEN spaces=DOC",
         "figma: token=DEMO_FIGMA_TOKEN files=AbC123demo"]


def watchtower(root: Path, now: dt.datetime) -> None:
    """A mailbox, GitHub, a schedule and four feeds: signals new and read, mentions, one source failing."""
    from orkcraft.realm import watch
    ago = lambda m: _iso(now - dt.timedelta(minutes=m))
    S = watch.Signal
    signals = [
        S(ago(600), "cron", "⏰ daily 05:00", "", read=True),
        S(ago(420), "mail", "Ann Lee: Offsite — pick a date", "Hi! Can you do the 14th or the 21st?", "101", read=True),
        S(ago(380), "github", "PR #12 opened: Login form", "feature/login → main by grub-bot", "gh-1"),
        S(ago(300), "slack", "Dana in #release: freeze is Monday, right?", "", "https://slack.example/p1"),
        S(ago(260), "jira", "PAY-431 Refund flow: moved to In Review", "", "https://acme.atlassian.net/PAY-431"),
        S(ago(210), "mail", "Registrar: Your domain expires on the 12th", "Renew orkcraft-demo.dev now.", "102"),
        S(ago(150), "slack", "@ Marco in #design: can you look at the price tag?", "", "https://slack.example/p2",
          mention=True),
        S(ago(120), "github", "Check failed on fix/parser: tests (3.11)", "1 failed, 46 passed", "gh-2"),
        S(ago(90), "confluence", "Release checklist edited by Dana", "", "https://acme.atlassian.net/wiki/p/77"),
        S(ago(70), "figma", "Marco on Checkout: the button needs a disabled state", "", "https://figma.example/c/9"),
        S(ago(45), "mail", "GitHub: [orkcraft-demo] Review requested on #14", "Pricing page copy", "103"),
        S(ago(20), "slack", "Ops bot in #alerts: deploy of web finished", "", "https://slack.example/p3"),
        S(ago(8), "mail", "Ann Lee: Re: Offsite", "The 21st works for everyone.", "104"),
    ]
    sd = state_dir(root, "watchtower", "post")
    _jsonl(sd / "signals.jsonl", [asdict(s) for s in signals])
    _json(sd / "state.json", {"read": [s.key for s in signals if s.read], "last_uid": 104, "cron_last": ago(600),
                              "simulated_errors": {f"feed:{FEEDS[1]}": "jira: 401 the token was refused"}})


def signpost(root: Path, now: dt.datetime) -> None:
    """The Gates' post: what came and the route each cart took (unmatched ones too)."""
    rows = []
    for i, (route, title, value) in enumerate((
            ("notes", "release notes for v0.1.9", "release notes for v0.1.9: hotfix for the parser"),
            ("send", "release.json", '{"notes": "v0.1.9 hotfix"}'),
            ("", "lunch?", "anyone up for lunch at 12?"),
            ("notes", "release notes draft", "release notes: Town Hall, typed buildings"),
            ("", "https://example.com/article", "https://example.com/article"),
            ("send", "release.json", '{"notes": "v0.2: Town Hall"}'),
            ("notes", "release notes for v0.2", "release notes for v0.2: the Town Hall, typed buildings, roofs"))):
        rows.append({"at": _iso(now - dt.timedelta(minutes=300 - i * 40)), "route": route, "source": "gate_pit",
                     "event": "pit.text", "title": title, "value": value})
    _jsonl(state_dir(root, "signpost", "crossroads") / "routes.jsonl", rows)


def mills(root: Path, now: dt.datetime) -> None:
    """Runs of the two Mills: input → output for every step, an agent step with its cost, one failure."""
    from orkcraft.realm import jobs

    def job(bid, n, minutes, inp, steps, outcome="done", cost=None, failed=0, trigger="road", agent=0):
        start = now - dt.timedelta(minutes=minutes)
        last = steps[-1]
        return jobs.Job(f"{bid}-{n}", "milled" if outcome == "done" else "mill failed", "mill", inp,
                        started=_iso(start), ended=_iso(start + dt.timedelta(seconds=2)), outcome=outcome,
                        result=last.get("out", ""), error=last.get("error", ""), cost_usd=cost,
                        tokens=int(cost * 40000) if cost else None, trigger=trigger,
                        meta={"steps": steps, "failed": failed, "agent": agent, "items": 1, "cut": False})

    brief = jobs.Log(state_dir(root, "mill", "brief"))
    agenda = "**Today** — 3 events\n\n- Standup\n- Design sync\n- 1:1 with Ann"
    for j in (job("brief", 1, 1440, agenda, [{"step": "script: brief", "out": "### Daily brief\n\n" + agenda}]),
              job("brief", 2, 600, "Write the Barracks docs · To Do → In Progress",
                  [{"step": "script: brief", "error": "python3: can't open file 'brief.py': No such file"}],
                  outcome="error", failed=1),
              job("brief", 3, 300, "releases.md", [{"step": "script: brief", "out": "### Daily brief\n\nreleases.md"}]),
              job("brief", 4, 40, "ideas.md", [{"step": "script: brief", "out": "### Daily brief\n\nideas.md"}],
                  trigger="manual")):
        brief.append(j)
    notes = jobs.Log(state_dir(root, "mill", "notes_mill"))
    text = "release notes for v0.2: the Town Hall, typed buildings, roofs"
    steps = lambda inp: [
        {"step": "grep: (?i)release", "out": inp},
        {"step": "replace: (?i)release notes for (v[0-9.]+): => \\1 — ", "out": "v0.2 — the Town Hall, typed buildings, roofs"},
        {"step": "agent: rewrite as three short bullet points for the changelog",
         "out": "- The Town Hall: build and ask in one place\n- Typed buildings\n- Roofs"},
        {"step": "to_json",
         "out": '{"notes": "- The Town Hall: build and ask in one place\\n- Typed buildings\\n- Roofs"}'}]
    for j in (job("notes_mill", 1, 280, "release notes for v0.1.9: hotfix for the parser", steps(text), cost=0.03, agent=1),
              job("notes_mill", 2, 160, "release notes draft",
                  [{"step": "grep: (?i)release", "out": "release notes draft"},
                   {"step": "replace: (?i)release notes for (v[0-9.]+): => \\1 — ", "out": "release notes draft"},
                   {"step": "agent: rewrite as three short bullet points for the changelog",
                    "error": "the agent answered nothing: the text names no version"}], outcome="error", failed=3),
              job("notes_mill", 3, 11, text, steps(text), cost=0.04, agent=1),
              job("notes_mill", 4, 3, "release notes for v0.2.1: the Lake as a window",
                  [{"step": "grep: (?i)release", "out": "release notes for v0.2.1: the Lake as a window"},
                   {"step": "replace: (?i)release notes for (v[0-9.]+): => \\1 — ", "out": "v0.2.1 — the Lake as a window"},
                   {"step": "agent: rewrite as three short bullet points for the changelog",
                    "error": "the agent's answer was not a list"}], outcome="error", failed=3, cost=0.02, agent=1)):
        notes.append(j)


def horn(root: Path, now: dt.datetime) -> None:
    from orkcraft.realm import horn as hn
    sd = state_dir(root, "horn", "gate_horn")
    for minutes, source, event, title, sound, played in (
            (500, "gate_pit", "pit.text", "lunch?", "chime", "quiet"),
            (300, "gate_pit", "pit.text", "release notes for v0.1.9", "chime", "page"),
            (299, "crossroads", "signpost.routed", "notes", "horn", "page"),
            (298, "crossroads", "signpost.routed", "notes", "horn", "cooldown"),
            (180, "crossroads", "signpost.unmatched", "lunch?", "ding", "page"),
            (60, "gate_pit", "pit.text", "release notes draft", "chime", "page"),
            (12, "gate_pit", "pit.text", "release notes for v0.2", "chime", "page"),
            (11, "crossroads", "signpost.routed", "notes", "horn", "page")):
        hn.log(sd, hn.Call(_iso(now - dt.timedelta(minutes=minutes)), source, event, title, sound, played))


# -- 2. queues and execution ----------------------------------------------------------------------------

def fields(root: Path, now: dt.datetime) -> None:
    """Some cards are new to the person: their lanes wear `*`."""
    from orkcraft.realm import tasklist
    seen = [tasklist.slug(t) for t in ("Plan the v0.2 release", "Answer Ann about the offsite", "Write the Barracks docs",
                                       "Town Hall audit", "Git building", "A calendar roof", "Mail digests at 05:00")]
    _json(state_dir(root, "fields", "todo") / "seen.json", seen)


def calendar(now: dt.datetime) -> tuple[str, list[tuple[str, str]]]:
    """Today around `now` (one meeting now, the next ones after it, one this morning) and the week:
    the .ics text and (uid, document) of the meetings that have a document."""
    end_of_day = now.replace(hour=23, minute=50, second=0)
    step = max(min((end_of_day - now) / 4, dt.timedelta(minutes=75)), dt.timedelta(minutes=10))
    at = lambda t: t.strftime("%Y%m%dT%H%M%S")
    t0 = now.replace(second=0) - dt.timedelta(minutes=20)
    today = [("now", t0, t0 + dt.timedelta(minutes=50), "Design sync: Town Hall", "docs/meetings/design-sync.md")]
    for i, (title, doc) in enumerate((("Standup", ""), ("1:1 with Ann", "docs/meetings/one-on-one-ann.md"),
                                      ("Release v0.2 go / no-go", "docs/handbook/releases.md")), 1):
        start = now.replace(second=0) + step * i
        if start.date() == now.date():
            today.append((f"next{i}", start, start + dt.timedelta(minutes=25), title, doc))
    morning = now.replace(hour=0, minute=30, second=0) if now.hour < 6 else now.replace(hour=5, minute=30, second=0)
    if morning < t0:
        today.append(("morning", morning, morning + dt.timedelta(minutes=30), "Morning review (orkcraft)", ""))
    week = [(f"d{d}", (now + dt.timedelta(days=d)).replace(hour=h, minute=0, second=0),
             (now + dt.timedelta(days=d)).replace(hour=h, minute=0, second=0) + dt.timedelta(minutes=m), title, "")
            for d, h, m, title in ((1, 10, 60, "Release v0.2"), (1, 14, 30, "Pricing review"),
                                   (2, 11, 30, "Standup"), (3, 9, 30, "Dentist"), (4, 16, 45, "Retro"))]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//demo//EN"]
    docs = []
    for uid, start, end, title, doc in today + week:
        lines += ["BEGIN:VEVENT", f"UID:{uid}@demo", f"DTSTART:{at(start)}", f"DTEND:{at(end)}", f"SUMMARY:{title}",
                  "END:VEVENT"]
        if doc:
            docs.append((f"{uid}@demo", doc))
    return "\r\n".join(lines + ["END:VCALENDAR"]) + "\r\n", docs


MEETING_DOCS = {
    "docs/meetings/design-sync.md": "# Design sync: Town Hall\n\n## Agenda\n1. Build in one place\n"
                                    "2. Ask me anything: what the Warchief may answer\n3. Limits\n\n## Notes\n- \n",
    "docs/meetings/one-on-one-ann.md": "# 1:1 with Ann\n\n- The offsite: the 21st\n- Her move to the pricing team\n"
                                       "- Feedback on the Barracks docs\n",
}


def war_drum(root: Path, now: dt.datetime) -> None:
    from orkcraft.realm import daybook
    from orkcraft.sources import ics
    text, docs = calendar(now)
    (root / "demo" / "calendar.ics").write_text(text, encoding="utf-8")
    events = ics.parse_ics(text, "demo", now.date(), now.date() + dt.timedelta(days=7))
    by_uid = dict(docs)
    kept = {daybook.meet_id(e): {"path": by_uid[e.uid], "title": e.summary, "at": _iso(now)}
            for e in events if e.uid in by_uid}
    _json(state_dir(root, "war_drum", "days") / "docs.json", kept)


def web(root: Path, now: dt.datetime) -> None:
    """The web folder as committed: a page, its styles, a logo."""
    files = {"index.html": "<!doctype html>\n<title>Orkcraft demo</title>\n<main>\n  <span class=\"price\">€9</span>\n</main>\n",
             "styles.css": ":root { --accent: #3A7CA5; }\n.price { color: var(--accent); }\n",
             "app/main.js": "document.querySelector('.price').title = 'per month';\n",
             "app/cart.js": "export const cart = [];\n"}
    for rel, text in files.items():
        (root / "web" / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "web" / rel).write_text(text, encoding="utf-8")
    (root / "web" / "assets").mkdir(parents=True, exist_ok=True)
    (root / "web" / "assets" / "logo.png").write_bytes(png(16, (228, 87, 46)))


def forest(root: Path, now: dt.datetime) -> None:
    """The web folder after a day of work: two files changed, one new."""
    (root / "web" / "styles.css").write_text(":root { --accent: #E4572E; }\n.price { color: var(--accent); }\n"
                                             ".price--old { text-decoration: line-through; }\n", encoding="utf-8")
    (root / "web" / "index.html").write_text("<!doctype html>\n<title>Orkcraft demo</title>\n<main>\n"
                                             "  <span class=\"price\">€12</span>\n</main>\n", encoding="utf-8")
    (root / "web" / "pricing.html").write_text("<!doctype html>\n<title>Pricing</title>\n<h1>Plans</h1>\n",
                                               encoding="utf-8")


NOT_TAKEN = "docs/notes/retro.md"        # a note the general wiki has not taken in yet (in My Day's files)


def general_wiki(root: Path, now: dt.datetime) -> None:
    """My Day's Scroll Dump: a wiki of the handbook and the notes, one note not taken in yet."""
    from orkcraft.realm import wiki
    from orkcraft.sources import lore
    wroot = wiki.root_of(root, None, "general")
    wiki.scaffold(wroot, "general")
    pages = {
        "index.md": "# Index — general\n\n- [Handbook](pages/handbook/index.md) — onboarding, releases\n"
                    "- [Notes](pages/notes/index.md) — ideas\n",
        "pages/handbook/index.md": "# Handbook\n\n- [onboarding](onboarding.md)\n- [releases](releases.md)\n",
        "pages/handbook/onboarding.md": "---\nkind: handbook\nsources: [../../docs/handbook/onboarding.md]\n"
                                        "updated: 2026-10-01\nowner: ork\n---\n# Onboarding\n\nRead the town map; "
                                        "the tools are orkcraft and git.\n",
        "pages/handbook/releases.md": "---\nkind: handbook\nsources: [../../docs/handbook/releases.md]\n"
                                      "updated: 2026-10-01\nowner: human\n---\n# Releases\n\nSemVer. Tag, changelog, "
                                      "announce.\n",
        "pages/notes/index.md": "# Notes\n\n- [ideas](ideas.md)\n",
        "pages/notes/ideas.md": "---\nkind: notes\nsources: [../../docs/notes/ideas.md]\nupdated: 2026-10-01\n"
                                "owner: ork\n---\n# Ideas\n\nA calendar roof; mail digests at 05:00.\n",
        "log.md": "# Log\n\n## 2026-10-01\nTook in docs/handbook/*, docs/notes/ideas.md.\n",
    }
    for rel, text in pages.items():
        (wroot / rel).parent.mkdir(parents=True, exist_ok=True)
        (wroot / rel).write_text(text, encoding="utf-8")
    cfg = {"topic": "general", "paths": ["docs/handbook", "docs/notes"]}
    lib = lore.Library(lore.from_config(cfg, root))
    lib.scan()
    prints = wiki.Fingerprints(root)
    wiki.save_manifest(wroot, {n.path: prints.of(n) for n in lib.notes() if n.path != NOT_TAKEN})


# -- 3. agents ------------------------------------------------------------------------------------------

PRICING_BASE = "PRICE = 9\n"


def forge(root: Path, now: dt.datetime) -> None:
    """Two more branches (one conflicts with main), the PRs `gh` would list and the last merges."""
    for branch, path, text, msg in (
            ("feature/pricing-page", "src/billing.py", "PRICE = 15  # the pricing page's plan\nYEARLY = 150\n",
             "pricing page: yearly plan"),
            ("docs/barracks", "docs/barracks.md", "# Barracks\n\nHow the orks take tasks, in parallel.\n",
             "docs: the Barracks")):
        _git(root, "checkout", "-q", "-b", branch)
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
        _git(root, "add", path)
        _git(root, "commit", "-q", "-m", msg)
        _git(root, "checkout", "-q", "main")
    (root / "src" / "billing.py").write_text("PRICE = 10\n", encoding="utf-8")       # main moved on: a conflict
    _git(root, "commit", "-q", "-am", "billing: price 10")
    url = "https://github.com/orkcraft/orkcraft-demo/pull/"
    at = lambda m: _iso((now - dt.timedelta(minutes=m)).astimezone(dt.timezone.utc)).replace("+00:00", "Z")
    gh = {"prs": [
        {"number": 14, "state": "OPEN", "headRefName": "feature/pricing-page", "url": url + "14",
         "title": "Pricing page: yearly plan", "isDraft": False, "labels": [{"name": "needs-review"}]},
        {"number": 12, "state": "OPEN", "headRefName": "feature/login", "url": url + "12", "title": "Login form",
         "isDraft": False, "labels": []},
        {"number": 13, "state": "OPEN", "headRefName": "docs/barracks", "url": url + "13", "title": "Docs: the Barracks",
         "isDraft": True, "labels": []}],
        "views": {
            "12": {"comments": [{"author": {"login": "ann"}, "body": "Looks good; can the error say which field?",
                                 "createdAt": at(200)},
                                {"author": {"login": "grub-bot"}, "body": "Done: the message names the field.",
                                 "createdAt": at(150)}],
                   "reviews": [{"author": {"login": "dana"}, "body": "Ship it.", "state": "APPROVED",
                                "submittedAt": at(90)}]},
            "14": {"comments": [{"author": {"login": "marco"}, "body": "Is €15 final? The page still says €12.",
                                 "createdAt": at(60)}],
                   "reviews": [{"author": {"login": "dana"}, "body": "The yearly price needs the 2 free months.",
                                "state": "CHANGES_REQUESTED", "submittedAt": at(30)}]}}}
    sd = state_dir(root, "forge", "branches")
    _json(sd / "gh.json", gh)
    when = lambda m: (now - dt.timedelta(minutes=m)).strftime("%Y-%m-%d %H:%M")
    _jsonl(sd / "merges.jsonl", [
        {"at": when(1500), "result": {"ok": True, "branch": "fix/typo", "base": "main", "commit": "3f2a9c1d7e",
                                      "message": "fix: typo in the README", "conflicts": [],
                                      "tests": "12 passed in 0.41s", "error": ""}},
        {"at": when(35), "result": {"ok": False, "branch": "feature/pricing-page", "base": "main", "commit": "",
                                    "message": "", "conflicts": ["src/billing.py"], "tests": "",
                                    "error": "conflict in src/billing.py"}}])


def barracks(root: Path, now: dt.datetime) -> None:
    """Three orks with their models and costs; tasks done (with a PR), failed, in review, one asking."""
    from orkcraft.realm import barracks as bk
    ago = lambda m: _iso(now - dt.timedelta(minutes=m))
    st = bk.Barracks(state_dir(root, "barracks", "camp"))
    st.orcs = [
        bk.PoolOrc("Grub", "claude", "sonnet", keys=["T1042"], done=3, last=ago(40), hired=ago(400), cost_usd=0.92,
                   tokens=61000, branch="feature/login", recent=["T1042 login form", "Docs for the API"]),
        bk.PoolOrc("Mogka", "agy", bk.AGY_CODE, done=1, failed=1, last=ago(30), hired=ago(380), cost_usd=0.11,
                   tokens=9000, branch="fix/parser", recent=["Fix the parser"]),
        bk.PoolOrc("Snaga", "claude", "haiku", done=2, last=ago(15), hired=ago(200), cost_usd=0.18, tokens=22000,
                   branch="feature/pricing-page", recent=["Pricing page copy"])]
    st.queue = [bk.PoolTask("q1", "Docs for the API", "Write the API docs", "", ago(25), wait_for="t3"),
                bk.PoolTask("q2", "Yearly billing", "Add a yearly plan with two months free", "T1050", ago(20),
                            wait_for="t3"),
                bk.PoolTask("q3", "Changelog for v0.2", "Write the changelog from the merged PRs", "", ago(5),
                            wait_for="t4")]
    st.tasks = [
        bk.PoolTask("t1", "T1042 login form", "A login form with validation and tests", "T1042", ago(390), status="done",
                    orc="Grub", result="form + validation + 9 tests", cost_usd=0.52, branch="feature/login", base="main",
                    attempts=2, feedback="name the field in the error", pr="https://github.com/orkcraft/orkcraft-demo/pull/12",
                    scope="external", files=["src/login.py", "tests/test_login.py"],
                    qa=[["Which validation library?", "None — plain checks", "steward"]]),
        bk.PoolTask("t2", "Fix the parser", "Empty lines break the parser", "", ago(370), status="failed", orc="Mogka",
                    error="tests failed: test_empty_lines (1 of 47)", cost_usd=0.08, branch="fix/parser", base="main"),
        bk.PoolTask("t3", "Pricing page copy", "Write the pricing page copy for the yearly plan", "", ago(120),
                    status="reviewing", orc="Snaga", result="copy for 2 plans, FAQ", cost_usd=0.12,
                    branch="feature/pricing-page", base="main", files=["web/pricing.html"]),
        bk.PoolTask("t4", "Release notes v0.2", "Draft the release notes", "", ago(60), status="asked", orc="Grub",
                    question="Should the notes mention the Lake becoming a window, or keep it for v0.3?",
                    cost_usd=0.03),
        bk.PoolTask("t5", "README badges", "Add CI and PyPI badges", "", ago(330), status="done", orc="Snaga",
                    result="2 badges", cost_usd=0.02, pr="https://github.com/orkcraft/orkcraft-demo/pull/9",
                    pr_state="MERGED", scope="external", files=["README.md"])]
    st.stats = {"claude:sonnet": {"runs": 4, "ok": 4, "cost": 0.92}, f"agy:{bk.AGY_CODE}": {"runs": 2, "ok": 1, "cost": 0.11},
                "claude:haiku": {"runs": 2, "ok": 2, "cost": 0.18}}
    st.save()
    for d in (bk.Decision(ago(400), "t1", "hire", "Grub", "0/4 orks busy → hire; claude: no record yet; fits a code task"),
              bk.Decision(ago(380), "t2", "hire", "Mogka", "1/4 orks busy → hire; agy: no record yet"),
              bk.Decision(ago(200), "t3", "hire", "Snaga", "copy is light work → haiku"),
              bk.Decision(ago(60), "t4", "follow-up", "Grub", "the release was Grub's"),
              bk.Decision(ago(25), "q1", "queue", "", "waits for the pricing copy's review")):
        st.log(d)


def council(root: Path, now: dt.datetime) -> None:
    """A second review, in its second cycle now: two members agree, one does not yet."""
    from orkcraft.realm import team as tm
    folder = root / ".orkcraft" / "council" / "council"
    copy = ("# Pricing page copy\n\n## Monthly — €12\nEverything in the town, billed monthly.\n\n"
            "## Yearly — €120\nTwo months free.\n\n## FAQ\n- Can I switch plans? Yes, any time.\n")
    first = tm.new("Pricing page copy", copy.replace("€120\nTwo months free.", "€144"))
    first.started, first.ended, first.outcome, first.spent = (_iso(now - dt.timedelta(minutes=90)),
                                                              _iso(now - dt.timedelta(minutes=86)), "rework", 0.16)
    first.decision = "1. The yearly plan must show the two free months.\n2. Say what happens on a plan switch."
    first.turns = [tm.Turn("Product manager", "review", "1. The yearly price hides the discount.", "changes"),
                   tm.Turn("Architect", "review", "", "approve"),
                   tm.Turn("Security", "review", "No claims about data we cannot back.", "approve"),
                   tm.Turn("Steward", "decide", first.decision, "rework")]
    tm.save(folder, first)
    second = tm.new("Pricing page copy", copy, cycle=2)
    second.started, second.spent = _iso(now - dt.timedelta(minutes=8)), 0.09
    second.turns = [tm.Turn("Product manager", "review", "The discount reads well now.", "approve"),
                    tm.Turn("Architect", "review", "", "approve"),
                    tm.Turn("Security", "review", "\"Cancel any time\" needs the refund terms linked.", "changes")]
    tm.save(folder, second)


def loot(root: Path, now: dt.datetime) -> None:
    """Carts waiting for review, with the chain each came through and what it cost; what passed."""
    from orkcraft.realm import gate, pipes, vault
    sd = state_dir(root, "loot", "outputs")
    q = gate.Queue(sd)
    at = lambda m: now - dt.timedelta(minutes=m)
    camp = lambda orc, tok, cost, branch, m: pipes.hop("camp", orc, "agent", tok, cost, ".", branch, "done",
                                                       now=at(m), base="main")
    clan = lambda tok, cost, m, out="approved": pipes.hop("council", "Chieftains", "team", tok, cost, outcome=out, now=at(m))
    q.arrive(pipes.Payload("text", "## Pricing page copy\n\nMonthly €12 · Yearly €120 (two months free)", "council",
                           "team.approved", "Pricing page copy",
                           (camp("Snaga", 4800, 0.12, "feature/pricing-page", 100), clan(9000, 0.25, 9))),
             ["a review approved it"], now=at(8))
    q.arrive(pipes.Payload("file", "docs/release-notes.md", "camp", "pool.done", "release-notes.md",
                           (camp("Grub", 2100, 0.05, "feature/login", 70),)), ["files: 1"], now=at(60))
    item = q.arrive(pipes.Payload("text", "Parser fix: skip empty lines", "camp", "pool.failed", "Fix the parser",
                                  (camp("Mogka", 3000, 0.08, "fix/parser", 360),)), ["it failed"], now=at(350))
    q.needs_you(item, "failed twice — look at it yourself", now=at(340))
    item = q.arrive(pipes.Payload("text", "API docs, first draft", "camp", "pool.done", "Docs for the API",
                                  (camp("Grub", 7000, 0.21, "feature/login", 200),)), ["cost $0.21 over $0.20"],
                    now=at(190))
    q.rework(item, "too long: keep it to the endpoints", now=at(180))
    for m, kind, value, title, source, orc, tok, cost in (
            (900, "text", "## v0.1.9\n\n- the parser hotfix", "v0.1.9 notes", "council", "Grub", 5200, 0.14),
            (600, "file", "README.md", "README.md", "camp", "Mogka", 1900, 0.03),
            (300, "text", "Badges: CI, PyPI", "README badges", "camp", "Snaga", 800, 0.02)):
        vault.store(root, "outputs", sd, kind, value, title, source, now=at(m),
                    trail=(camp(orc, tok, cost, "feature/login", m + 20),))


def crag(root: Path, now: dt.datetime) -> None:
    """The load of the day for the charts that do not come from the ledger, and two crossings."""
    from orkcraft.realm import metrics
    sd = state_dir(root, "crag", "crag")
    for h in range(24):
        t = now - dt.timedelta(hours=23 - h)
        metrics.sample(sd, "orcs", float((1, 0, 0, 0, 0, 1, 2, 3, 3, 2, 1, 2)[h % 12]), now=t)
        metrics.sample(sd, "limits", 30 + h * 2.2, by="claude weekly", now=t)
        metrics.sample(sd, "limits", 10 + (h % 6) * 9, by="claude 5h", now=t)
    for m in range(0, 60, 5):
        metrics.sample(sd, "cpu", (0.4, 0.9, 1.6, 2.2, 1.1, 0.7)[m // 5 % 6], now=now - dt.timedelta(minutes=60 - m))
    _jsonl(sd / "crossings.jsonl", [
        {"at": _iso(now - dt.timedelta(hours=9)), "chart": "Spend today", "source": "spend", "value": 2.1,
         "line": 2.0, "level": "warning"},
        {"at": _iso(now - dt.timedelta(hours=3)), "chart": "Quotas", "source": "limits", "value": 81.0, "line": 80.0,
         "level": "warning"}])


def catapult(root: Path, now: dt.datetime) -> None:
    """What was fired at the release hook (a refusal among them) and a load that fails the schema."""
    from orkcraft.realm import catapult as cp
    sd = state_dir(root, "catapult", "launcher")
    url = "https://example.com/hooks/release"
    for m, ok, status, body, answer, error in (
            (1500, True, 201, '{"notes": "v0.1.8"}', '{"id": 418, "status": "published"}', ""),
            (280, False, 422, '{"note": "v0.1.9 hotfix"}', '{"error": "notes is required"}', "HTTP 422"),
            (270, True, 201, '{"notes": "v0.1.9 hotfix"}', '{"id": 419, "status": "published"}', ""),
            (10, True, 201, '{"notes": "- The Town Hall\\n- Typed buildings\\n- Roofs"}',
             '{"id": 420, "status": "published"}', "")):
        cp.log(sd, cp.Shot(_iso(now - dt.timedelta(minutes=m)), ok, status, url, body, answer, error, False))
    _json(sd / "loaded.json", {"groups": {"#0": {"notes_mill": {"v": {"title": "v0.2.1", "draft": True},
                                                                "at": _iso(now - dt.timedelta(minutes=2))}}},
                               "seq": 1})


def workshop(root: Path, now: dt.datetime) -> None:
    from orkcraft.realm import workshop as ws
    sd = state_dir(root, "workshop", "counter")
    for m, inp, code, out, err in (
            (500, "lunch?", 0, '{"words": 1, "lines": 1, "first": "lunch?"}', ""),
            (300, "release notes for v0.1.9: hotfix for the parser", 0,
             '{"words": 8, "lines": 1, "first": "release"}', ""),
            (180, "", 3, "", "nothing to count"),
            (95, "def main():\n    print('hello from the demo')", 0, '{"words": 4, "lines": 2, "first": "def"}', ""),
            (60, "release notes draft", 0, '{"words": 3, "lines": 1, "first": "release"}', ""),
            (12, "release notes for v0.2: the Town Hall, typed buildings, roofs", 0,
             '{"words": 11, "lines": 1, "first": "release"}', "")):
        ws.log(sd, ws.Run(_iso(now - dt.timedelta(minutes=m)), "pit.text", "gate_pit", inp, code, out, err,
                          40 + m % 30, ""))


def town_hall(root: Path, now: dt.datetime) -> None:
    """A morning's talk with the Warchief, and the last audit."""
    from orkcraft.realm import audit
    at = lambda m: _iso(now - dt.timedelta(minutes=m))
    _jsonl(state_dir(root, "town_hall", "town_hall") / "chat.jsonl", [
        {"who": "you", "text": "What did the orks do overnight?", "ts": at(120)},
        {"who": "warchief", "text": "Three tasks finished in the **Barracks** (login form, README badges, pricing "
                                    "copy waits for review), one failed: *Fix the parser* — a test on empty lines. "
                                    "Spend so far: **$1.21** of $5.", "ts": at(119)},
        {"who": "you", "text": "I want mail from Ann to ring a bell.", "ts": at(30)},
        {"who": "warchief", "text": "A **Horn** on a road from the Watchtower does it: `mail.received` from "
                                    "*Ann Lee* → `bell`. Build it?", "ts": at(29), "suggest": "horn"},
        {"who": "you", "text": "Later. Why is the Forge red?", "ts": at(4)},
        {"who": "warchief", "text": "`feature/pricing-page` conflicts with main in `src/billing.py`: main moved the "
                                    "price to 10, the branch to 15. Say which one stays and I will ask Snaga to "
                                    "rebase.", "ts": at(3)}])
    report = audit.Report(at(60), [
        audit.Finding("warder", "Release hook: the URL is not on the allow list", "launcher", "warn"),
        audit.Finding("treasurer", "Barracks: 74% of today's spend; Snaga on haiku did the same work for a fifth",
                      "camp", "info"),
        audit.Finding("pathfinder", "Signpost: 2 carts matched no rule today", "crossroads", "info"),
        audit.Finding("peon", "ledger.jsonl is 1.2 MB — Clean up", severity="info")])
    audit.save(root, report)


def sessions(root: Path, now: dt.datetime) -> None:
    """Two orks' screens, each with a question for the person (the Answers)."""
    from orkcraft.demo import live
    live.write(root, [
        {"key": "pool:camp/grub", "title": "Grub · Barracks", "harness": "claude", "ork": "",
         "screen": "\x1b[1m✻ Grub\x1b[0m · release notes v0.2 · feature/login\n\n"
                   "● Read(docs/release-notes.md)\n  ⎿  Read 6 lines\n\n"
                   "● Update(docs/release-notes.md)\n  ⎿  +3 −0\n\n"
                   "Do you want to make this edit to release-notes.md?\n"
                   "❯ 1. Yes\n  2. Yes, and don't ask again this session\n  3. No, and say what to do instead\n"},
        {"key": "pool:camp/snaga", "title": "Snaga · Barracks", "harness": "claude", "ork": "",
         "screen": "\x1b[1m✻ Snaga\x1b[0m · pricing page copy · feature/pricing-page\n\n"
                   "● Bash(git rebase main)\n  ⎿  CONFLICT (content): Merge conflict in src/billing.py\n\n"
                   "Keep main's price (10) or the branch's (15)?\n"
                   "❯ 1. Keep main's: PRICE = 10\n  2. Keep the branch's: PRICE = 15\n  3. Stop the rebase\n"}])


def png(size: int, rgb: tuple[int, int, int]) -> bytes:
    """A square of one colour as a PNG: the web folder's logo, an image the File Forest previews."""
    import struct
    import zlib
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
