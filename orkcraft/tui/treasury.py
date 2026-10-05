"""The treasury: 🪙 spend and 🪵 context against their limits, the subscription quota, the HUD.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations



from orkcraft import schedule
from orkcraft.sources import telemetry
from orkcraft.widgets.hud import Resources



class TreasuryMixin:
    def refresh_telemetry(self) -> None:
        """Re-read this run's transcripts (only new bytes) and warn once when a limit is crossed."""
        self.refresh_worktree_marks()
        try:
            self.snapshot = self.telemetry.refresh()
        except OSError:
            return
        budget = self.scroll.budget
        if not self._gold_warned and self.snapshot.spent_usd >= budget.gold_session_limit_usd > 0:
            self._gold_warned = True
            self.notify(
                f"🪙 ${self.snapshot.spent_usd:.2f} spent of ${budget.gold_session_limit_usd:.2f} this run — new "
                "sessions are held until you raise budget.gold_session_limit_usd in .orkcraft.json",
                title="Treasury empty", severity="error", timeout=12,
            )
        for key, ctx in self.snapshot.context_by_terminal.items():
            if ctx >= budget.lumber_context_limit_tokens > 0 and key not in self._lumber_warned:
                self._lumber_warned.add(key)
                self.notify(
                    f"🪵 {telemetry.fmt_tokens(ctx)} of context in {key} (limit "
                    f"{telemetry.fmt_tokens(budget.lumber_context_limit_tokens)}) — /compact or start fresh",
                    title="Lumber over the limit", severity="warning", timeout=10,
                )

    def _resource_texts(self) -> tuple[str, str, str, str]:
        """(gold, gold level, lumber, lumber level) for the HUD; "—" until a session reports."""
        budget, snap = self.scroll.budget, self.snapshot
        gold_limit = f"${budget.gold_session_limit_usd:.2f}"
        if snap.sessions or snap.unpriced or snap.side_usd:
            # "+" marks spend that could not be priced (agy, or a model with no published price).
            gold = f"${snap.spent_usd:.2f}{'+' if snap.unpriced else ''} / {gold_limit}"
        else:
            gold = f"$— / {gold_limit}"
        gold_level = telemetry.level(snap.spent_usd, budget.gold_session_limit_usd)
        key = self._active_terminal_key()
        ctx = snap.context_by_terminal.get(key) if key else None
        if ctx is None and snap.context_by_terminal:
            ctx = max(snap.context_by_terminal.values())
        lumber_limit = telemetry.fmt_tokens(budget.lumber_context_limit_tokens)
        lumber = f"{telemetry.fmt_tokens(ctx)} / {lumber_limit}" if ctx is not None else f"— / {lumber_limit}"
        lumber_level = telemetry.level(ctx or 0, budget.lumber_context_limit_tokens)
        return gold, gold_level, lumber, lumber_level

    def _quota_text(self) -> tuple[str, str, bool]:
        """(quota, its level, whether 🪙 shows): the HUD corner follows each tool's billing
        (settings.py) — the used share of the tightest window for a subscription, 🪙 for an API."""
        machine = self.desktop.machine
        on = [t for t, c in machine.tools.items() if c.enabled]
        subs = [t for t in on if machine.tools[t].billing == "subscription"]
        if not subs:
            return "", "ok", True
        from orkcraft.screens.limits_view import LimitsView
        limits = next((lv.limits for lv in self.query(LimitsView)), None) or []
        parts, worst = [], 0.0
        for t in subs:
            left = [x.remaining for x in limits if x.provider == t and x.remaining is not None]
            if left:
                used = round((1 - min(left)) * 100)
                worst = max(worst, used)
                parts.append(f"{t} {used}%")
            else:
                parts.append(f"{t} —")
        return " · ".join(parts), telemetry.level(worst, 100), len(subs) < len(on)

    def _quota_reads(self) -> tuple[list, list[str]]:
        """(the last quota reads, the enabled subscription tools) — what the pressure of a building
        is measured against (realm/pressure.py)."""
        machine = self.desktop.machine
        subs = [t for t, c in machine.tools.items() if c.enabled and c.billing == "subscription"]
        from orkcraft.screens.limits_view import LimitsView
        try:
            limits = next((lv.limits for lv in self.query(LimitsView)), None) or []
        except Exception:  # unmounted during shutdown
            limits = []
        return limits, subs

    def _active_terminal_key(self) -> str | None:
        try:
            term = self.chat.current_terminal
        except Exception:  # the War Tent may be unmounted during shutdown
            return None
        if term is None:
            return None
        return next((k for k, t in self.chat.terminals.items() if t is term), None)

    def gold_exhausted(self) -> bool:
        """True (and says so) when this run's spend reached the 🪙 limit: no new sessions."""
        limit = self.scroll.budget.gold_session_limit_usd
        if limit > 0 and self.snapshot.spent_usd >= limit:
            self.notify(f"🪙 ${self.snapshot.spent_usd:.2f} of ${limit:.2f} spent this run — raise "
                        "budget.gold_session_limit_usd in .orkcraft.json to summon more",
                        title="Treasury empty", severity="warning")
            return True
        return False

    def refresh_hud(self) -> None:
        gold, gold_level, lumber, lumber_level = self._resource_texts()
        quota, quota_level, show_gold = self._quota_text()
        hour = schedule.status(self.desktop.machine)
        self._hud.set_resources(Resources(
            budget=self.scroll.budget,
            supply=self.roster.active, supply_max=self.scroll.budget.supply_max_workers,
            alerts=len(self.roster.alerts), commit=self.config.auto_commit,
            gold=gold, gold_level=gold_level, lumber=lumber, lumber_level=lumber_level,
            quota=quota, quota_level=quota_level, show_gold=show_gold, hour=hour,
        ))
