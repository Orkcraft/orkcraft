"""🏰 Town Hall: the town's own building, bottom right on the map.

Three tabs: the Hall (its agents, the Elders' night, the Council's reviews and the last audit — the
hall's worker keeps them, core/workers/town_hall.py, and this view draws them),
Sessions (every live Claude / agy session — the War Tent of old, `#chat-view`) and Limits (the quotas —
the Treasury of old, `#limits-view`). Its hut carries the two quick actions of the town: Build and
Audit, and the Elders' lamp in the corner of its first row (`LAMPS`).
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane

from orkcraft.realm import audit, elders, modes, optimize, town_presets, weekly
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.chat_view import ChatView
from orkcraft.screens.limits_view import LimitsView

# The Elders' lamp on the hut (app.elders_state) and its word in the Hall.
LAMPS = {"advice": ("📜", "advice waits for you — ! opens it"), "watch": ("🌙", "on watch: they read the questions"),
         "full": ("⏳", "tonight's questions are used up"), "rest": ("💤", "at rest till the quiet hours"),
         "off": ("", "off — autonomy is ⛓️ Ask me")}
LAMPS_OFFICE = {"advice": "!", "watch": "on", "full": "max", "rest": "zz", "off": ""}   # the office: no emoji


class TownHallView(Container):
    # The panes of its contract (design/buildings/town_hall.json) and the widget that draws each: the
    # tab strip and a tab per pane. Only named: the hall keeps its tabs as they are.
    UI_PANES = {"tabs": "#hall-tabs ContentTabs", "hall": "#hall-tab-hall", "sessions": "#hall-tab-sessions",
                "limits": "#hall-tab-limits"}
    DEFAULT_CSS = """
    TownHallView { height: 1fr; }
    TownHallView TabbedContent { height: 1fr; }
    TownHallView TabPane { padding: 0; height: 1fr; }
    #hall-body { padding: 0 1; }
    """

    def compose(self) -> ComposeResult:
        with TabbedContent(id="hall-tabs", initial="hall-tab-hall"):
            with TabPane("🏰 Hall", id="hall-tab-hall"):
                with VerticalScroll():
                    yield Static("", id="hall-body", markup=False)
            with TabPane("💬 Sessions", id="hall-tab-sessions"):
                yield ChatView(id="chat-view")
            with TabPane("📊 Limits", id="hall-tab-limits"):
                yield LimitsView(id="limits-view")

    def on_mount(self) -> None:
        self.refresh_hall()

    def show_tab(self, name: str) -> None:
        self.query_one("#hall-tabs", TabbedContent).active = f"hall-tab-{name}"

    # -- the Hall tab -----------------------------------------------------------------------------

    def worker(self):
        """The hall's work is its worker's (core/workers/town_hall.py); this view draws it."""
        core = getattr(self.app, "core", None)
        return core.worker(TOWN_HALL) if core is not None else None

    def refresh_hall(self, report: audit.Report | None = None) -> None:
        w = self.worker()
        if w is None:
            return
        h = w.hall(report)
        t = Text()
        if h["order"]:
            t.append("📜 A town waits to be raised\n", style="bold yellow")
            t.append(f"“{h['order']}”\n", style="italic")
            t.append("F10 → 📜 Town Builder plans it; you approve the plan before anything is raised\n\n",
                     style="dim")
        t.append("Agents of the hall\n", style="bold")
        for b in h["builders"]:
            t.append(f"{b['icon']} {b['name']}", style="bold")
            t.append(f" — {b['role']}\n", style="dim")
        for a in h["agents"]:
            t.append(f"{a['icon']} {a['name']}", style="bold")
            t.append(f" — {a['area']}: ", style="dim")
            if h["audit"] is None:
                t.append("not audited yet\n", style="dim")
            else:
                n, serious = a["found"], a["serious"]
                t.append(f"{n} finding{'s' if n != 1 else ''}", style="yellow" if serious else "")
                t.append(f"{f', {serious} to look at' if serious else ''}\n")
        self._elders_section(t, w.repo_root, h["elders"])
        t.append("\nThe Council's Fast Path", style="bold")
        t.append(" — every new building, agent and road from scratch\n", style="dim")
        for r in h["fast_path"]:
            t.append(f"{r['icon']} {r['name']}", style="bold")
            t.append(f" — {r['duty']}\n", style="dim")
        marks = {"approved": ("✓", "green"), "overridden": ("?", "yellow"), "rejected": ("✗", "bold red"),
                 "cancelled": ("·", "dim")}
        for r in h["reviews"]:
            mark, style = marks.get(r["decision"], ("·", ""))
            t.append(f"{mark} ", style=style)
            t.append(f"{r['ts']} {r['kind']} {r['id']}")
            t.append(f" — {r['note']}\n" if r["note"] else "\n", style="dim")
        if not h["reviews"]:
            t.append("no reviews yet\n", style="dim")
        t.append("\n👍 / 👎 of the stewards", style="bold")
        t.append(" — K / F on a building, and what you do with their results\n", style="dim")
        for row in h["board"]:
            t.append(f"{row['building']}: 👍 {row['likes']} 👎 {row['dislikes']} · penalty {row['penalty']:g}")
            t.append(f" · from your work {row['quiet']:+.1f}\n" if row["quiet"] is not None else "\n", style="dim")
        for inc in h["incidents"]:
            how = f" ({inc['how']})" if inc["how"] else ""
            t.append(f"⚠ {inc['ts']} {inc['building']} · {inc['kind']}{how} → {inc['blamed']}"
                     + (f" — {inc['note']}" if inc["note"] else "") + "\n", style="yellow")
        if not h["board"] and not h["incidents"]:
            t.append("no ratings yet\n", style="dim")
        t.append("\n🔧 Building retro", style="bold")
        t.append(" — F10 → Building retro\n", style="dim")
        marks = {"pending": ("⏳", "yellow"), "applied": ("✓", "green"), "dismissed": ("✗", "dim")}
        for p in h["proposals"]:
            mark, style = marks.get(p["status"], ("·", ""))
            t.append(f"{mark} {p['ts']} {p['building']} · {p['action']} {p['target']}", style=style)
            t.append(f" — {p['why']}\n", style="dim")
        if not h["proposals"]:
            t.append("no proposals yet\n", style="dim")
        wk = h["weekly"]
        t.append("🗓 Town retro: ", style="bold")
        if wk is None:
            t.append("not run yet — Sunday 05:00, or F10 → Town retro\n", style="dim")
        else:
            waiting = f", {wk['waiting']} waiting" if wk["waiting"] else ""
            t.append(f"{wk['ts'][:10]} · {wk['items']} items, {wk['applied']} applied{waiting}\n")
        t.append("\n")
        if h["audit"] is None:
            t.append("No audit yet — F10 → 🔍 Audit the camp.", style="dim")
        else:
            t.append(f"Last audit {h['audit']['ts'][:16].replace('T', ' ')}\n", style="bold")
            for f in h["audit"]["findings"]:
                style = "bold red" if f["severity"] == "high" else "yellow" if f["severity"] == "warn" else ""
                t.append(f"{f['icon']} {f['text']}\n", style=style)
        self.query_one("#hall-body", Static).update(t)

    def _elders_section(self, t: Text, repo, records: list[dict]) -> None:
        """🏛 What the Elders judged lately: answered (↪), advised (📜), left to you (·); ⚠ the Warder's note."""
        app = self.app
        state = app.elders_state() if hasattr(app, "elders_state") else "off"
        per_night, _ = elders.limits(repo)
        t.append("\n🏛 The Elders", style="bold")
        t.append(f" — {LAMPS.get(state, LAMPS['off'])[1]}", style="dim")
        if getattr(app, "_quiet_since", None) is not None:
            t.append(f" · {getattr(app, '_elders_count', 0)} of {per_night} tonight", style="dim")
        t.append("\n")
        looks = {"answered": ("↪", "green", "answered"), "advised": ("📜", "yellow", "advised")}
        for r in records:
            mark, style, word = looks.get(r["how"], ("·", "dim", ""))
            said = f"{word} [{r['key']}] {r['option']}" if word else "left to you"
            who = f"{r['who']} · " if r["who"] else ""
            t.append(f"{mark} {r['ts']} {who}{r['question']}", style=style)
            t.append(f" → {said}")
            if r["why"]:
                t.append(f" — {r['why']}", style="dim")
            if r["warn"]:
                t.append(" ⚠", style="bold yellow")
            t.append("\n")
        if not records:
            t.append("nothing judged yet — they read the agents' questions in 🌙 quiet hours\n", style="dim")

    def lamp(self) -> str:
        app = self.app
        state = app.elders_state() if hasattr(app, "elders_state") else "off"
        if modes.office():
            return LAMPS_OFFICE.get(state, "")
        return LAMPS.get(state, LAMPS["off"])[0]

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        app = self.app
        lines = []
        if town_presets.pending_order(getattr(app, "repo_root", None)) is not None:
            lines.append("📜 a town order waits")
        warder = [o for o in getattr(app, "roster", None).orcs if o.name == "Warder"] if getattr(app, "roster", None) else []
        lines.append("🛡 Warder: alert" if warder and warder[0].alert else "🛡 all quiet")
        snap, budget = getattr(app, "snapshot", None), getattr(getattr(app, "scroll", None), "budget", None)
        if snap is not None and budget is not None:
            lines.append(f"🪙 ${snap.spent_usd:.2f} / ${budget.gold_session_limit_usd:.0f}")
        try:
            limits = self.query_one(LimitsView).mini_status()
        except Exception:
            limits = []
        if limits and limits[0] and "unknown" not in limits[0] and "not read" not in limits[0]:
            lines.append(limits[0])
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """The Elders' lamp first (the corner of the heading row), then the status lines."""
        app = self.app
        repo = getattr(app, "repo_root", None)
        try:
            lamp = self.lamp()
        except Exception:
            lamp = ""
        lines = [lamp, *self.mini_status()]
        if repo is not None:
            report = audit.load(repo)
            lines.append(f"audit: {len(report.findings)} findings" if report else "audit: not run")
            lines.append(f"proposals: {len(optimize.pending(repo))}")
            wk = weekly.latest(repo)
            lines.append(f"weekly: {wk.ts[:10]}" if wk else "weekly: not run")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "hall.preset":               # T1108: the hut's two buttons build
            self.app.action_presets_catalog()
            return True
        if action_id == "hall.scratch":
            self.app.action_build_scratch()
            return True
        if action_id == "hall.build":
            self.app.action_build_menu()
            return True
        if action_id == "hall.audit":
            self.app.run_audit()
            return True
        return False
