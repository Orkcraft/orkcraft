"""Updates in the window (core/updates.py, docs/updates.md): what is out, installed with one click, then
the window restarts on it.

The list is read on a thread when the window opens and again every `CHECK_EVERY_S`; the snapshot's
`update` says what is newer (js/update.js asks once per version: loudly for a critical one). A click
installs it on a thread with the tool that installed this copy, and on success the window closes and
the same command opens it again on the new code (`RESTART`, cli.py). What runs stops, as on any close.

    up = Updates(host)
    up.tick(now)                       # from the host's clock
    host.commands.update(up.commands())   # update.check · update.install · update.restart · update.policy
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from orkcraft import __version__, settings
from orkcraft.core import updates


class Updates:
    def __init__(self, host, method: Callable[[], updates.Method] = updates.method) -> None:
        self.host = host
        self._method = method
        self.offer: updates.Offer | None = None
        self.state = "idle"            # idle · installing · installed · failed
        self.error = ""
        self.installed = ""            # the version installed now, waiting for the restart
        self.restart_wanted = False
        self.quit: Callable[[], None] = lambda: None   # the face closes the window (gui/launch.py)
        self._checked_at: float | None = None

    # -- what the page sees ------------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any] | None:
        if self.offer is None and self.state == "idle":
            return None
        way = self._method()
        out = self.offer.to_dict() if self.offer else {"version": self.installed, "critical": False, "notes": [],
                                                       "critical_notes": []}
        out.update({"current": __version__, "state": self.state, "error": self.error, "installed": self.installed,
                    "can": way.can, "how": way.describe(), "policy": self.host.town.machine.updates})
        return out

    # -- the clock ---------------------------------------------------------------------------------

    def tick(self, now: float) -> None:
        if self.host.town.demo or updates.blocked():
            return
        if self._checked_at is not None and now - self._checked_at < updates.CHECK_EVERY_S:
            return
        self._checked_at = now
        updates.check_later(lambda s: self.host.town.call(self._read, s))

    def _read(self, s: updates.State) -> None:
        found = updates.offer(s.manifest)
        if found != self.offer and self.state in ("idle", "failed"):
            self.offer = found
            self.host.on_change()

    # -- the page's commands -----------------------------------------------------------------------

    def check(self, args: dict) -> dict[str, Any] | None:
        """Read the list again now (Settings → Check for updates)."""
        try:
            s = updates.check(force=True, timeout=10.0)
        except Exception as e:
            raise UpdateError(f"The list of updates cannot be read: {e}") from None
        self._read(s)
        if self.offer is None:
            self.host.town.toast(f"Orkcraft {__version__} is the latest", title="Updates")
        return self.snapshot()

    def install(self, args: dict) -> dict[str, Any] | None:
        """Install what is offered on a thread; the window restarts when it is in."""
        if self.offer is None:
            raise UpdateError("There is no update to install")
        if self.state == "installing":
            return self.snapshot()
        way = self._method()
        if not way.can:
            raise UpdateError(way.why)
        self.state, self.error = "installing", ""
        version = self.offer.version

        def work() -> None:
            result = updates.install(way)
            updates.remember(result, version)
            self.host.town.call(self._installed, result, version)

        threading.Thread(target=work, daemon=True, name="update-install").start()
        self.host.on_change()
        return self.snapshot()

    def _installed(self, result: updates.Result, version: str) -> None:
        if result.ok:
            self.state, self.installed = "installed", result.version or version
            self.host.town.toast(f"Orkcraft {self.installed} is installed; it restarts now", title="Updates")
            self.restart({})
        else:
            self.state, self.error = "failed", result.output
            self.host.town.toast(f"The update {version} did not install. Orkcraft keeps running {__version__}.",
                                 title="Updates", severity="error", timeout=15)
        self.host.on_change()

    def restart(self, args: dict) -> bool:
        """The window closes and opens again on the code installed now."""
        if self.state != "installed":
            raise UpdateError("Nothing new is installed yet")
        self.restart_wanted = True
        self.quit()
        return True

    def policy(self, args: dict) -> dict[str, Any] | None:
        """Which updates install by themselves when the town opens: auto · critical · ask."""
        if args.get("policy") not in updates.POLICIES:
            raise UpdateError("auto, critical or ask")
        m = self.host.town.machine
        m.updates = args["policy"]
        settings.save(m)
        self.host.on_change()
        return self.snapshot()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"update.check": self.check, "update.install": self.install, "update.restart": self.restart,
                "update.policy": self.policy}


class UpdateError(Exception):
    """Said to the person as it is."""
