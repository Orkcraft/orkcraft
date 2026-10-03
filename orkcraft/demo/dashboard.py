"""The dashboard set of the showcase (T1105 stage 9, camp buildings of T1107): three orkspaces.

    orkcraft --demo --demo-set dashboard

F1 My Day — Task Fields, War Drum, Scroll Dump, File Forest, The Pit and a Watchtower (it shows
how to connect a mailbox; the sandbox has none), with a Daily Brief mill that gets the War Drum's
digest, task moves and what is dropped in the Pit.
F2 Agent Yard — The Forge, a Barracks whose foreman has already hired, an Orc Council with a
finished debate, a Loot Vault with changes to review and a Tally Crag over a day of runs.
F3 Gates — The Pit feeds a Totem whose rules send a patch or a link to the Lake of Insight and a
release note out through the Catapult (checked against a schema; the sandbox only dry-runs); a
Workshop built from scratch counts the words of every paste with its approved script; the Horn
sounds a chime for every paste and a horn for every route the Totem takes.
The Town Hall shows the T1108 pipeline seeded: the Council's reviews, 👍 / 👎 with an incident,
a self-improvement proposal and a weekly report.

The sandbox is a real git repository (so the Forge, the Forest and the Loot show real things);
agents never run in it — the Barracks and the Council answer with simulated text.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

SEL = "on_selection_change"
TODAY = dt.date.today()
_T = lambda d=0: (TODAY + dt.timedelta(days=d)).strftime("%Y%m%d")
BRIEF = ("python3 -c \"import sys; t = sys.stdin.read().strip(); "
         "print('### Daily brief' + chr(10) + chr(10) + (t or 'nothing new'))\"")


def typed(bid: str, kind: str, title: str, icon: str, orc: str, role: str, roof: str | None = None, **config) -> dict:
    spec = {"id": bid, "type": kind, "title": title, "icon": icon, "summary": role,
            "orc": {"name": orc, "role": role}}
    if config:
        spec["config"] = config
    if roof:
        spec["roof"] = roof
    return spec


CALENDAR = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//demo//EN"] + [
    line for start, end, title in (
        (f"{_T()}T053000", f"{_T()}T060000", "Morning review (orkcraft)"),
        (f"{_T()}T110000", f"{_T()}T113000", "Standup"),
        (f"{_T()}T150000", f"{_T()}T160000", "Design sync: Town Hall"),
        (f"{_T(1)}T100000", f"{_T(1)}T110000", "Release v0.2"),
        (f"{_T(3)}T090000", f"{_T(3)}T093000", "Dentist"),
    ) for line in ("BEGIN:VEVENT", f"UID:{start}@demo", f"DTSTART:{start}", f"DTEND:{end}", f"SUMMARY:{title}",
                   "END:VEVENT")] + ["END:VCALENDAR"]) + "\r\n"

MY_DAY = {
    "id": "my_day", "name": "My Day", "icon": "🏡", "biome": "forest", "git": {"enabled": False},
    "segment": "Everyone", "story": "A personal dashboard: the day, the tasks, the notes, the mail",
    "nodes": [],
    "files": {
        "TASKS.md": "# My tasks\n\n## To Do\n- [ ] Plan the v0.2 release\n- [ ] Answer Ann about the offsite\n"
                    "- [ ] Renew the domain\n\n## In Progress\n- [ ] Write the Barracks docs\n\n## Done\n"
                    "- [x] Town Hall audit\n- [x] Git building\n",
        "demo/calendar.ics": CALENDAR,
        "docs/handbook/onboarding.md": "# Onboarding\n\n## Your first day\nRead the town map.\n\n## Tools\n- orkcraft\n- git\n",
        "docs/handbook/releases.md": "# Releases\n\n## Versioning\nSemVer.\n\n## Checklist\n- tag\n- changelog\n- announce\n",
        "docs/notes/ideas.md": "# Ideas\n\n## A calendar roof\n## Mail digests at 05:00\n",
        "src/app.py": "def main():\n    print('hello from the demo')\n",
        "src/billing.py": "PRICE = 9\n",
    },
    "buildings": [
        typed("todo", "fields", "Task Fields", "🌾", "Taskmaster", "keeps my three columns", "tiles", path="TASKS.md"),
        typed("days", "war_drum", "War Drum", "🥁", "Drummer", "today and this week", "flag",
              ics="demo/calendar.ics", day_starts="05:00"),
        typed("notes", "scrolls", "Scroll Dump", "🗑️", "Scroll Scrapper", "my handbook and notes", "dome",
              paths=["docs/handbook", "docs/notes"]),
        typed("tree", "forest", "File Forest", "🌲", "Woodcutter", "the source folder", "gable", path="src"),
        typed("drop", "pit", "The Pit", "🕳️", "Scavenger", "drop a file to brief it"),
        typed("post", "watchtower", "Watchtower", "🗼", "Lookout", "my inbox", "chimney",
              host="imap.example.com", user_env="DEMO_MAIL_USER", password_env="DEMO_MAIL_PASSWORD"),
        typed("brief", "mill", "Daily Brief", "⚙️", "Miller", "turns what arrives into a brief", "thatch",
              steps=[f"script: {BRIEF}"]),
    ],
    "layout": [(0.0, 0.0, 0.32, 0.46), (0.34, 0.0, 0.32, 0.46), (0.68, 0.0, 0.32, 0.46),
               (0.0, 0.54, 0.24, 0.46), (0.26, 0.54, 0.16, 0.46), (0.44, 0.54, 0.26, 0.46), (0.72, 0.54, 0.28, 0.46)],
    "roads": [
        ("brief", "days", "calendar.day_schedule", "on_digest", None, None),
        ("brief", "todo", "tasks.status_changed", "on_task_moved", None, None),
        ("brief", "drop", "drop.file", "on_drop", None, None),
    ],
    "payloads": {
        ("days", "calendar.day_schedule"): ("text", f"**{TODAY:%A %d %B}** — 3 events\n\n- 05:30 Morning review\n"
                                                    "- 11:00 Standup\n- 15:00 Design sync", "today"),
        ("todo", "tasks.status_changed"): ("node", "write-the-barracks-docs", "Write the Barracks docs · To Do → In Progress"),
        ("drop", "drop.file"): ("file", "docs/notes/ideas.md", "ideas.md"),
    },
}

AGENT_YARD = {
    "id": "agent_yard", "name": "Agent Yard", "icon": "⚔", "biome": "void", "git": {"enabled": False},
    "segment": "Developers", "story": "Branches, parallel orcs, a team that agrees, files to review",
    "nodes": [],
    "files": {},
    "buildings": [
        typed("branches", "forge", "The Forge", "⚒️", "Smith", "branches, PRs, changes", "castle"),
        typed("camp", "barracks", "Barracks", "🏕️", "Grunts", "runs tasks in parallel", "tent",
              max_orcs=3, providers=["claude", "agy"], budget_usd=5.0),
        typed("council", "council", "Orc Council", "🔥", "Chieftains", "agrees on plans", "pagoda",
              goal="Agree on the v0.2 release plan", members=["Planner:claude", "Critic:agy", "Security:claude"],
              max_rounds=3, budget_usd=2.0),
        typed("outputs", "loot", "Loot Vault", "📦", "Quartermaster", "files agents wrote, to review", "snow"),
        typed("crag", "crag", "Tally Crag", "🪨", "Crag Carver", "spend and load", "castle", source="spend",
              warn=2.0, crit=5.0),
    ],
    "layout": [(0.0, 0.0, 0.44, 0.46), (0.56, 0.0, 0.44, 0.46), (0.0, 0.54, 0.3, 0.46), (0.35, 0.54, 0.3, 0.46),
               (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        ("camp", "branches", "git.pr_opened", "on_pr_opened", None, None),
        ("council", "camp", "pool.done", "on_task_done", None, None),
        ("crag", "outputs", "generator.accepted", "on_accepted", None, None),
    ],
    "payloads": {
        ("branches", "git.pr_opened"): ("text", "feature/login: #12 Login form", "feature/login"),
        ("camp", "pool.done"): ("text", "**Login form** — Grub (claude)\n\nform, validation, tests", "Login form"),
        ("outputs", "generator.accepted"): ("file", "docs/release-notes.md", "release-notes.md"),
    },
}

RELEASE_SCHEMA = '{"type": "object", "required": ["notes"], "properties": {"notes": {"type": "string"}}}\n'

GATES = {
    "id": "gates", "name": "Gates", "icon": "🗿", "biome": "ice", "git": {"enabled": False},
    "segment": "Everyone", "story": "What comes in is sorted by rules: a look in the Lake, or out through the Catapult",
    "nodes": [],
    "files": {"demo/release.schema.json": RELEASE_SCHEMA},
    "buildings": [
        typed("gate_pit", "pit", "The Pit", "🕳️", "Scavenger", "drop or paste anything"),
        typed("crossroads", "totem", "Totem", "🗿", "Spirit Guide", "routes by rules", "pagoda",
              rules=["view: matches (?i)diff --git|http", "send: contains release", "view: else"]),
        typed("insight", "lake", "Lake of Insight", "🌊", "Seer", "shows what it is given", "dome"),
        typed("launcher", "catapult", "The Catapult", "🎯", "Loader", "sends releases out", "flag",
              url="https://example.com/hooks/release", schema="demo/release.schema.json", method="POST"),
        typed("counter", "workshop", "Word Count", "🔢", "Tinker", "counts the words of every paste",
              runtime="python", layout="card", inputs=["gate_pit:pit.text"]),
        typed("gate_horn", "horn", "The Horn", "📯", "Hornblower", "sounds what comes in",
              sounds=["pit.text: chime", "crossroads/totem.routed: horn", "*: ding"], quiet="23:00-07:00"),
    ],
    "layout": [(0.0, 0.0, 0.3, 0.46), (0.35, 0.0, 0.3, 0.46), (0.7, 0.0, 0.3, 0.46), (0.0, 0.54, 0.3, 0.46),
               (0.35, 0.54, 0.3, 0.46), (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        ("crossroads", "gate_pit", "pit.text", "on_drop", None, None),
        ("counter", "gate_pit", "pit.text", "on_paste", None, None),
        ("insight", "crossroads", "totem.routed", "view", None, {"route": ["view"]}),
        ("launcher", "crossroads", "totem.routed", "send", None, {"route": ["send"]}),
        ("gate_horn", "gate_pit", "pit.text", "on_paste", None, None),
        ("gate_horn", "crossroads", "totem.routed", "routed", None, None),
    ],
    "payloads": {
        ("gate_pit", "pit.text"): ("text", "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n"
                                           "@@ -1 +1 @@\n-print('hello')\n+print('hello, camp')\n", "patch"),
        ("crossroads", "totem.routed"): ("text", "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n"
                                                 "+++ b/src/app.py\n@@ -1 +1 @@\n-print('hello')\n+print('hello, camp')\n",
                                         "view"),
    },
}

DASHBOARD_SCENARIOS = [MY_DAY, AGENT_YARD, GATES]


# -- the repository and the seeded state ----------------------------------------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def prepare(root: Path) -> None:
    """Make the sandbox a git repository with two feature branches, then leave a few files changed
    for the File Generator to review; seed the Barracks and the Council."""
    (root / ".gitignore").write_text(".orkcraft/\n.orkcraft.json\n.orkcraft-demo\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "demo@orkcraft.local")
    _git(root, "config", "user.name", "Orkcraft Demo")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "demo: the town is founded")
    for branch, path, lines, msg in (("feature/login", "src/login.py", 42, "login form with validation"),
                                     ("fix/parser", "src/parser.py", 7, "parser handles empty lines")):
        _git(root, "checkout", "-q", "-b", branch)
        (root / path).write_text("".join(f"line_{i} = {i}\n" for i in range(lines)), encoding="utf-8")
        _git(root, "add", path)
        _git(root, "commit", "-q", "-m", msg)
        _git(root, "checkout", "-q", "main")
    # what the agents "generated": the File Generator and the File Tree see them
    (root / "docs" / "release-notes.md").write_text("# v0.2\n\n- Town Hall\n- typed buildings\n- roofs\n", encoding="utf-8")
    (root / "src" / "billing.py").write_text("PRICE = 12  # raised by the pricing agent\n", encoding="utf-8")
    _seed_barracks(root)
    _seed_council(root)
    _seed_ledger(root)
    _seed_pipeline(root)


WORD_COUNT = """import json, sys

cart = json.load(sys.stdin)
words = cart.get("value", "").split()
if not words:
    sys.exit(3)                       # nothing to count: the steward would say what it is
print(json.dumps({"words": len(words), "lines": cart.get("value", "").count(chr(10)) + 1, "first": words[0][:20]}))
sys.exit(4 if len(words) > 400 else 0)
"""


def _seed_pipeline(root: Path) -> None:
    """T1108: the Workshop's approved script and blueprint, the Council's reviews, 👍 / 👎 with an
    incident, a waiting self-improvement proposal and a weekly report — what the Town Hall shows."""
    import json

    from orkcraft.realm import fastpath, feedback, optimize, weekly, workshop
    now = dt.datetime.now().replace(microsecond=0)
    mocks = [workshop.cart("pit.text", "gate_pit", "release notes for v0.2"), workshop.cart("pit.text", "gate_pit", "")]
    workshop.save_script(root, "counter", "python", WORD_COUNT)
    workshop.save_blueprint(root, "counter", {"id": "counter", "title": "Word Count", "runtime": "python",
                                              "layout": "card", "inputs": ["gate_pit:pit.text"], "mocks": mocks,
                                              "purpose": "count the words of what I paste into the pit"})
    for kind, bid, decision, notes in (
            ("building", "counter", "approved", []),
            ("road", "gate_pit->crossroads", "approved", []),
            ("building", "fetcher", "rejected", [{"role": "warder", "severity": "block",
                                                   "text": "mill step pipes the network into a shell: curl x | sh"}]),
            ("agent", "Summariser", "overridden", [{"role": "chief", "severity": "object",
                                                     "text": "a chain could keep only the failed checks"}])):
        path = root / fastpath.COUNCIL_DIR / "reviews.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now.isoformat(), "kind": kind, "id": bid, "decision": decision, "model": "haiku",
                                "cost_usd": 0.001, "error": "", "notes": notes}) + "\n")
    feedback.record_output(root, "counter", "workshop.done", '{"words": 5, "lines": 1, "first": "release"}')
    feedback.like(root, "counter")
    feedback.record_output(root, "brief", "mill.done", "### Daily brief\n\nnothing new")
    scroll = type("S", (), {"buildings": [type("B", (), {"id": "brief", "roads": [type("R", (), {"source": "days"})()]})()]})()
    feedback.dislike(root, scroll, "brief", "inputs", "the War Drum sent yesterday's schedule")
    optimize.save(root, optimize.Proposal("demo1", now.isoformat(), "camp", "shrink", "orders",
                                          "Work through every task carefully, explain each change in detail, …",
                                          "Do the task; list changed files; one-line summary.",
                                          "the same job in a third of the words", "~60 % input tokens", 41000))
    weekly.save(root, weekly.Report(now.isoformat(), "The Barracks spends most of the week; the Tally Crag "
                                    "warns too early.", [
        weekly.Item(1, "Shorter Barracks orders", "same job, fewer words", "shrink", "camp", {"target": "orders"}),
        weekly.Item(2, "Warn at $3", "$2 fires every day", "set_config", "crag", {"key": "warn", "value": 3.0}),
        weekly.Item(3, "Try a Totem before the Lake", "advice", "note")], "opus", 1.4))


def _seed_ledger(root: Path) -> None:
    """A day of runs, so the Tally Crag has something to carve."""
    from orkcraft.realm import metrics
    now = dt.datetime.now().replace(second=0, microsecond=0)
    for i, (h, b, cost, out) in enumerate(((22, "camp", 0.4, "done"), (19, "council", 0.24, "done"),
                                            (15, "camp", 0.9, "done"), (12, "camp", 0.3, "error"),
                                            (8, "brief", 0.0, "done"), (5, "camp", 1.1, "done"),
                                            (2, "council", 0.5, "done"), (1, "camp", 0.6, "done"))):
        metrics.record_run(root, b, out, cost, int(cost * 40000), now=now - dt.timedelta(hours=h, minutes=i))


def _seed_barracks(root: Path) -> None:
    from orkcraft.realm import barracks as bk
    st = bk.Barracks(root / ".orkcraft" / "barracks" / "camp")
    st.orcs = [bk.PoolOrc("Grub", "claude", keys=["T1042"], done=3, last="2026-10-02T05:20:00", hired="2026-10-02T05:00:00"),
               bk.PoolOrc("Mogka", "agy", bk.AGY_CODE, done=1, failed=1, last="2026-10-02T05:25:00",
                          hired="2026-10-02T05:05:00")]
    st.queue = [bk.PoolTask("q1", "Docs for the API", "Write the API docs", "", "2026-10-02T05:30:00")]
    st.tasks = [bk.PoolTask("t1", "T1042 login form", "x", "T1042", status="done", orc="Grub", result="form + tests"),
                bk.PoolTask("t2", "Fix the parser", "x", status="failed", orc="Mogka", error="tests failed")]
    st.stats = {"claude": {"runs": 3, "ok": 3, "cost": 0.9}, f"agy:{bk.AGY_CODE}": {"runs": 2, "ok": 1, "cost": 0.1}}
    st.save()
    for d in (bk.Decision("2026-10-02T05:00:00", "t1", "hire", "Grub", "0/3 orcs busy → hire; claude: no record yet; fits a code task"),
              bk.Decision("2026-10-02T05:05:00", "t2", "hire", "Mogka", "1/3 orcs busy → hire; agy: no record yet"),
              bk.Decision("2026-10-02T05:21:00", "t3", "follow-up", "Grub", "T1042 was Grub's"),
              bk.Decision("2026-10-02T05:30:00", "q1", "queue", "", "paused for the night")):
        st.log(d)


def _seed_council(root: Path) -> None:
    from orkcraft.realm import team as tm
    d = tm.new("Agree on the v0.2 release plan", "Agree on the v0.2 release plan")
    d.started, d.ended, d.outcome, d.round, d.spent = "2026-10-02T05:10:00", "2026-10-02T05:14:00", "agreed", 2, 0.24
    d.draft = ("# v0.2 release plan\n\n1. Freeze features on Monday\n2. Run the secret scan on the wheel\n"
               "3. Tag and sign `v0.2.0`\n4. Publish to PyPI\n5. Roll back: yank and re-tag if the smoke test fails\n"
               "6. The operator announces")
    d.turns = [tm.Turn(1, "Planner", "draft", "# v0.2 release plan\n\n1. Freeze\n2. Tag\n3. Publish\n4. Announce"),
               tm.Turn(1, "Critic", "review", "OBJECT: 1. No rollback step. 2. Who announces?", False),
               tm.Turn(1, "Security", "review", "OBJECT: sign the release and scan the wheel", False),
               tm.Turn(1, "Moderator", "revise", d.draft),
               tm.Turn(2, "Critic", "review", "AGREE", True), tm.Turn(2, "Security", "review", "AGREE", True)]
    tm.save(root / ".orkcraft" / "council" / "council", d)


def payload_of(sc: dict, source: str, event: str):
    from orkcraft.realm.pipes import Payload
    kind, value, title = sc["payloads"][(source, event)]
    return Payload(kind, value, source, event, title)

