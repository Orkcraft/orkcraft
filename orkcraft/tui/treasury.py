"""The treasury: 🪙 spend and 🪵 context against their limits, the subscription quota, the HUD.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from orkcraft import schedule
from orkcraft.core import treasury
from orkcraft.widgets.hud import Resources


class TreasuryMixin:
    def refresh_telemetry(self) -> None:
        """Re-read this run's transcripts (only new bytes) and warn once when a limit is crossed."""
        self.refresh_worktree_marks()
        self.treasury.refresh()

    def _resource_texts(self) -> tuple[str, str, str, str]:
        """(gold, gold level, lumber, lumber level) for the HUD; "—" until a session reports."""
        return self.treasury.resources(self._active_terminal_key())

    def _quota_text(self) -> tuple[str, str, bool]:
        """(quota, its level, whether 🪙 shows): see core/treasury.py."""
        machine = self.desktop.machine
        return treasury.quota(machine, self._limits() if treasury.subscriptions(machine) else [])

    def _quota_reads(self) -> tuple[list, list[str]]:
        """(the last quota reads, the enabled subscription tools) — what the pressure of a building
        is measured against (realm/pressure.py)."""
        return self._limits(), treasury.subscriptions(self.desktop.machine)

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
        return self.treasury.exhausted()

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

    def _limits(self) -> list:
        """The last quota reads the Town Hall's Limits tab made ([] while it is not mounted)."""
        from orkcraft.screens.limits_view import LimitsView
        try:
            return next((lv.limits for lv in self.query(LimitsView)), None) or []
        except Exception:  # unmounted during shutdown
            return []
