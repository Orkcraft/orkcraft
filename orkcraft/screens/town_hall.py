"""🏰 Town Hall: the town's own building, bottom right on the map.

Three tabs: the Hall (its agents, the Elders' night, the Council's reviews and the last audit),
Sessions (every live Claude / agy session — the War Tent of old, `#chat-view`) and Limits (the quotas —
the Treasury of old, `#limits-view`). Its hut carries the two quick actions of the town: Build and
Audit, and the Elders' lamp in the corner of its first row (`LAMPS`).
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane

from orkcraft.realm import audit, elders, fastpath, feedback, modes, optimize, town_presets, weekly
from orkcraft.screens.chat_view import ChatView
from orkcraft.screens.limits_view import LimitsView

BUILDERS = (("🏗", "Mason", "plans a building's data"), ("🎨", "Artisan", "lays out its panes and hut"))

# The Elders' lamp on the hut (app.elders_state) and its word in the Hall.
LAMPS = {"advice": ("📜", "advice waits for you — ! opens it"), "watch": ("🌙", "on watch: they read the questions"),
         "full": ("⏳", "tonight's questions are used up"), "rest": ("💤", "at rest till the quiet hours"),
         "off": ("", "off — autonomy is ⛓️ Ask me")}
LAMPS_HIDDEN = {"advice": "!", "watch": "on", "full": "max", "rest": "zz", "off": ""}   # the office: no emoji
ELDERS_SHOWN = 8


class TownHallView(Container):
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

    def refresh_hall(self, report: audit.Report | None = None) -> None:
        app = self.app
        repo = getattr(app, "repo_root", None)
        report = report or (audit.load(repo) if repo is not None else None)
        t = Text()
        order = town_presets.pending_order(repo)
        if order is not None:
            t.append("📜 A town waits to be raised\n", style="bold yellow")
            t.append(f"“{order['prompt'][:300]}”\n", style="italic")
            t.append("F10 → 📜 Town Builder plans it; you approve the plan before anything is raised\n\n",
                     style="dim")
        t.append("Agents of the hall\n", style="bold")
        for icon, name, role in BUILDERS:
            t.append(f"{icon} {name}", style="bold")
            t.append(f" — {role}\n", style="dim")
        for aid, icon, name, area in audit.AGENTS:
            found = report.of(aid) if report else []
            serious = [f for f in found if f.severity != "info"]
            t.append(f"{icon} {name}", style="bold")
            t.append(f" — {area}: ", style="dim")
            if report is None:
                t.append("not audited yet\n", style="dim")
            else:
                t.append(f"{len(found)} finding{'s' if len(found) != 1 else ''}", style="yellow" if serious else "")
                t.append(f"{f', {len(serious)} to look at' if serious else ''}\n")
        self._elders_section(t, repo)
        t.append("\nThe Council's Fast Path", style="bold")
        t.append(" — every new building, agent and road from scratch\n", style="dim")
        for _, icon, name, duty, _ in fastpath.ROLES:
            t.append(f"{icon} {name}", style="bold")
            t.append(f" — {duty}\n", style="dim")
        reviews = fastpath.recent(repo, 6) if repo is not None else []
        marks = {"approved": ("✓", "green"), "overridden": ("?", "yellow"), "rejected": ("✗", "bold red"),
                 "cancelled": ("·", "dim")}
        for r in reviews:
            mark, style = marks.get(r.get("decision"), ("·", ""))
            t.append(f"{mark} ", style=style)
            t.append(f"{str(r.get('ts', ''))[5:16].replace('T', ' ')} {r.get('kind')} {r.get('id')}")
            first = next(iter(r.get("notes") or []), None)
            t.append(f" — {first['text'][:60]}\n" if first else "\n", style="dim")
        if not reviews:
            t.append("no reviews yet\n", style="dim")
        incidents = feedback.incidents(repo, 5) if repo is not None else []
        board = feedback.scores(repo) if repo is not None else {}
        t.append("\n👍 / 👎 of the stewards", style="bold")
        t.append(" — K / F on a building\n", style="dim")
        for bid, row in sorted(board.items(), key=lambda kv: -kv[1].get("penalty", 0))[:5]:
            t.append(f"{bid}: 👍 {row.get('likes', 0)} 👎 {row.get('dislikes', 0)} · penalty {row.get('penalty', 0):g}\n")
        for inc in incidents:
            who = ", ".join(f"{b} −{p:g}" for b, p in inc.blamed.items())
            t.append(f"⚠ {inc.ts[5:16].replace('T', ' ')} {inc.building} · {inc.kind} → {who}"
                     + (f" — {inc.note[:50]}" if inc.note else "") + "\n", style="yellow")
        if not board and not incidents:
            t.append("no ratings yet\n", style="dim")
        props = optimize.proposals(repo)[:4] if repo is not None else []
        t.append("\n🔧 Self-improvement", style="bold")
        t.append(" — F10 → Self-improvement\n", style="dim")
        marks = {"pending": ("⏳", "yellow"), "applied": ("✓", "green"), "dismissed": ("✗", "dim")}
        for p in props:
            mark, style = marks.get(p.status, ("·", ""))
            t.append(f"{mark} {p.ts[5:16].replace('T', ' ')} {p.building} · {p.action} {p.target}", style=style)
            t.append(f" — {p.why[:50]}\n", style="dim")
        if not props:
            t.append("no proposals yet\n", style="dim")
        wk = weekly.latest(repo) if repo is not None else None
        t.append("🗓 Weekly self-audit: ", style="bold")
        if wk is None:
            t.append("not run yet — Sunday 05:00, or F10 → Weekly self-audit\n", style="dim")
        else:
            todo = sum(1 for i in wk.items if i.applicable and i.n not in wk.applied)
            t.append(f"{wk.ts[:10]} · {len(wk.items)} items, {len(wk.applied)} applied"
                     f"{f', {todo} waiting' if todo else ''}\n")
        t.append("\n")
        if report is None:
            t.append("No audit yet — F10 → 🔍 Audit the camp.", style="dim")
        else:
            t.append(f"Last audit {report.ts[:16].replace('T', ' ')}\n", style="bold")
            for aid, icon, name, _ in audit.AGENTS:
                for f in report.of(aid)[:6]:
                    style = "bold red" if f.severity == "high" else "yellow" if f.severity == "warn" else ""
                    t.append(f"{icon} {f.text}\n", style=style)
        self.query_one("#hall-body", Static).update(t)

    def _elders_section(self, t: Text, repo) -> None:
        """🏛 What the Elders judged lately: answered (↪), advised (📜), left to you (·); ⚠ the Warder's note."""
        app = self.app
        state = app.elders_state() if hasattr(app, "elders_state") else "off"
        per_night, _ = elders.limits(repo)
        t.append("\n🏛 The Elders", style="bold")
        t.append(f" — {LAMPS.get(state, LAMPS['off'])[1]}", style="dim")
        if getattr(app, "_quiet_since", None) is not None:
            t.append(f" · {getattr(app, '_elders_count', 0)} of {per_night} tonight", style="dim")
        t.append("\n")
        records = elders.recent(repo, ELDERS_SHOWN) if repo is not None else []
        for r in records:
            options, key = r.get("options") or {}, r.get("key")
            if r.get("sent"):
                mark, style, said = "↪", "green", f"answered [{key}] {options.get(key, '')}"
            elif key is not None:
                mark, style, said = "📜", "yellow", f"advised [{key}] {options.get(key, '')}"
            else:
                mark, style, said = "·", "dim", "left to you"
            who = f"{r.get('who')} · " if r.get("who") else ""
            t.append(f"{mark} {str(r.get('ts', ''))[5:16].replace('T', ' ')} {who}{str(r.get('question', ''))[:50]}",
                     style=style)
            t.append(f" → {said}")
            if r.get("why"):
                t.append(f" — {str(r['why'])[:60]}", style="dim")
            if r.get("warn"):
                t.append(" ⚠", style="bold yellow")
            t.append("\n")
        if not records:
            t.append("nothing judged yet — they read the agents' questions in 🌙 quiet hours\n", style="dim")

    def lamp(self) -> str:
        app = self.app
        state = app.elders_state() if hasattr(app, "elders_state") else "off"
        if modes.hidden():
            return LAMPS_HIDDEN.get(state, "")
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
