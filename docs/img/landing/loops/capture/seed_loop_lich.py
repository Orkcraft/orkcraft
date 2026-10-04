"""Lich's daily status loop: calendar, board and GitHub fan in to one digest; stuck reviews go to
the Council; an overloaded column sounds the Horn."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from classes import *

ROOT = Path(sys.argv[1])
D = dt.date.today()
T = D.strftime("%Y%m%d")
CAL = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//loop//EN"] + [
    line for s, e, t in ((f"{T}T100000", f"{T}T101500", "Standup"), (f"{T}T140000", f"{T}T150000", "Sprint 14 review"))
    for line in ("BEGIN:VEVENT", f"UID:{s}@loop", f"DTSTART:{s}", f"DTEND:{e}", f"SUMMARY:{t}", "END:VEVENT")]
    + ["END:VCALENDAR"]) + "\r\n"
TASKS = "# Sprint 14\n\n## To Do\n" + "".join(f"- [ ] Story {i}\n" for i in range(9)) + "\n## In Progress\n" + \
        "".join(f"- [ ] {t}\n" for t in ("Security review OAuth", "Checkout 500", "Tokens v2", "Onboarding copy",
                                         "Audit log", "Invite flow", "SSO spike")) + "\n## Done\n- [x] Stripe webhooks\n"
B = [
    typed("drum", "war_drum", "War Drum", "🥁", "Drummer", "the day's meetings", "tent", ics="calendar.ics"),
    typed("board", "fields", "Sprint Board", "🌾", "Farmer", "Sprint 14", "thatch", path="TASKS.md"),
    typed("watch", "watchtower", "Watchtower", "🗼", "Lookout", "GitHub and 09:00", "flag", cron="daily 09:00"),
    typed("digest", "catapult", "Digest Catapult", "🎯", "Loader", "one digest, three sources", "flag",
          url="https://example.com/hooks/team-chat", method="POST", wait_for=["drum", "board", "watch"]),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "digests on record", "snow"),
    typed("totem", "totem", "Totem", "🗿", "Spirit Guide", "finds what is stuck", "pagoda",
          rules=["stuck: matches (?i)waiting [2-9] d|blocked", "fyi: else"]),
    typed("review", "council", "Orc Council", "🔥", "Chieftains", "an unblock plan", "pagoda", goal="Unblock it",
          members=["Planner:claude", "Critic:agy"], max_rounds=3, budget_usd=2.0),
    typed("tally", "crag", "Tally Crag", "🪨", "Crag Carver", "tasks per column", "castle", source="tasks",
          orientation="horizontal", warn=5, crit=6),
    typed("horn", "horn", "The Horn", "📯", "Hornblower", "too much in progress", "flag",
          sounds=["charts.threshold: alarm", "*: chime"]),
]
ROADS = [
    ("digest", "drum", "calendar.day_schedule", "today", None, None),
    ("digest", "board", "tasks.status_changed", "moves", None, None),
    ("digest", "watch", "watch.cron", "09-00", None, None),
    ("vault", "digest", "catapult.sent", "on-record", None, None),
    ("totem", "watch", "watch.github", "events", None, None),
    ("review", "totem", "totem.routed", "stuck", None, {"route": ["stuck"]}),
    ("horn", "tally", "charts.threshold", "overload", None, None),
]
sc = scenario("loop_lich", "Daily-Status", "💀", B, {"TASKS.md": TASKS, "calendar.ics": CAL}, ROADS)
sc["biome"] = "ice"
sc["layout"] = [(0.0, 0.0, 0.2, 0.4)] * len(B)
root = build(ROOT, sc)
fake_gh(root / ".orkcraft" / "bin", [])
signals(root, "watch", [{"at": (NOW - dt.timedelta(minutes=m)).isoformat(), "source": s, "title": t, "body": ""}
                        for m, s, t in ((90, "cron", "09:00 digest"), (15, "github", "#41 review waiting 2 d"))])
p = root / ".orkcraft.json"; d = json.loads(p.read_text())
POS = {"drum": [0.0, 0.0], "board": [0.0, 0.5], "watch": [0.0, 1.0], "digest": [0.33, 0.0], "vault": [0.66, 0.0],
       "totem": [0.33, 1.0], "review": [0.66, 1.0], "tally": [1.0, 0.45], "horn": [1.0, 0.0]}
for b in d["buildings"]:
    if b["id"] in POS:
        b["hut"] = POS[b["id"]]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(root)
