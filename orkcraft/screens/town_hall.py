"""🏰 Town Hall: the town's own building, bottom right on the map.

Three tabs: the Hall (its agents and the last audit), Sessions (every live Claude / agy session —
the War Tent of old, `#chat-view`) and Limits (the quotas — the Treasury of old, `#limits-view`).
Its hut carries the two quick actions of the town: Build and Audit.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane

from orkcraft.realm import audit, fastpath, feedback, optimize, town_presets, weekly
from orkcraft.screens.chat_view import ChatView
from orkcraft.screens.limits_view import LimitsView

BUILDERS = (("🏗", "Mason", "plans a building's data"), ("🎨", "Artisan", "lays out its panes and hut"))


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
        t.append("\n🔧 Building retro", style="bold")
        t.append(" — F10 → Building retro\n", style="dim")
        marks = {"pending": ("⏳", "yellow"), "applied": ("✓", "green"), "dismissed": ("✗", "dim")}
        for p in props:
            mark, style = marks.get(p.status, ("·", ""))
            t.append(f"{mark} {p.ts[5:16].replace('T', ' ')} {p.building} · {p.action} {p.target}", style=style)
            t.append(f" — {p.why[:50]}\n", style="dim")
        if not props:
            t.append("no proposals yet\n", style="dim")
        wk = weekly.latest(repo) if repo is not None else None
        t.append("🗓 Town retro: ", style="bold")
        if wk is None:
            t.append("not run yet — Sunday 05:00, or F10 → Town retro\n", style="dim")
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
        app = self.app
        repo = getattr(app, "repo_root", None)
        lines = self.mini_status()
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
