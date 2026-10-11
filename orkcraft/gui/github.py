"""GitHub in the mascot's menu (js/portrait.js, docs/design/improve-buildings.md §4): connected once through the
Orkcraft Improve app's device flow, so a Test bench can send what it improved as a pull request.

Connect shows the code GitHub gave and opens github.com/login/device; a thread asks GitHub every few seconds until the
person typed it (realm/github_app.py `poll`), then the account stands connected on this machine. Install opens the
app's page when it is not on the person's account yet (it pushes to their fork there).

    host.commands.update(github.commands(host))
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from orkcraft.realm import github_app


class GithubCommandError(Exception):
    """A step that cannot be taken; its text is shown to the person."""


class Github:
    def __init__(self, host) -> None:
        self.host = host
        self.device: github_app.Device | None = None
        self.error = ""
        self._stop = threading.Event()
        self._installed: tuple[str, bool] | None = None     # (login, installed): asked once a connection

    def status(self, args: dict | None = None) -> dict[str, Any]:
        acct = github_app.account()
        out: dict[str, Any] = {"login": acct["login"] if acct else "", "install": github_app.INSTALL,
                               "error": self.error, "waiting": None}
        if self.device is not None:
            out["waiting"] = {"code": self.device.user_code, "uri": self.device.uri}
        if acct and args and args.get("check"):
            if self._installed is None or self._installed[0] != acct["login"]:
                try:
                    self._installed = (acct["login"], github_app.installed(acct))
                except github_app.GithubError as e:
                    out["error"] = str(e)
            out["installed"] = self._installed[1] if self._installed else None
        return out

    def connect(self, args: dict) -> dict[str, Any]:
        self.cancel({})
        try:
            self.device = github_app.start()
        except github_app.GithubError as e:
            raise GithubCommandError(str(e)) from None
        self.error, self._installed = "", None
        stop = self._stop = threading.Event()
        device = self.device

        def wait() -> None:
            while not stop.is_set():
                stop.wait(device.interval)
                if stop.is_set():
                    return
                try:
                    login = github_app.poll(device)
                except github_app.GithubError as e:
                    self.host.town.call(self._done, "", str(e))
                    return
                if login:
                    self.host.town.call(self._done, login, "")
                    return

        threading.Thread(target=wait, daemon=True, name="github-device").start()
        return self.status()

    def _done(self, login: str, error: str) -> None:
        self.device, self.error = None, error
        if login:
            self.host.town.toast(f"GitHub: connected as @{login}", title="GitHub")
        self.host.on_change()

    def cancel(self, args: dict) -> dict[str, Any]:
        self._stop.set()
        self.device = None
        return self.status()

    def disconnect(self, args: dict) -> dict[str, Any]:
        self.cancel({})
        github_app.disconnect()
        self._installed = None
        self.host.town.toast("GitHub: disconnected on this machine (the app stays installed on GitHub until you take it "
                             "off there)", title="GitHub")
        return self.status()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"github.status": self.status, "github.connect": self.connect, "github.cancel": self.cancel,
                "github.disconnect": self.disconnect}


def commands(host) -> dict[str, Callable[[dict], Any]]:
    host.github = Github(host)
    return host.github.commands()
