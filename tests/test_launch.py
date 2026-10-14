"""`orkcraft gui` (gui/launch.py): a window when the machine can draw one, else the browser — also when
pywebview is installed but finds no toolkit to draw with (Linux without GTK or Qt)."""
from __future__ import annotations

import sys
import types

from orkcraft.gui import launch


def test_a_window_toolkit_that_cannot_start_falls_back_to_the_browser(fake_repo, monkeypatch, capsys):
    servers, opened = [], []

    class Server(launch.Server):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            servers.append(self)

    def start():
        raise RuntimeError("You must have either QT or GTK with Python extensions installed")

    fake = types.SimpleNamespace(create_window=lambda *a, **k: types.SimpleNamespace(destroy=lambda: None),
                                 start=start)
    monkeypatch.setitem(sys.modules, "webview", fake)
    monkeypatch.setattr(launch, "_toolkit", lambda: True)        # a toolkit seems there, and still fails
    monkeypatch.setattr(launch, "Server", Server)
    monkeypatch.setattr(launch.folders, "attach", lambda window: None)
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: opened.append(url) or servers[0].stop())
    assert launch.run(fake_repo, auto_commit=False) == 0
    assert opened == [servers[0].url]
    out = capsys.readouterr()
    assert "no window here" in out.err and "Orkline is at" in out.out


def test_linux_without_gtk_or_qt_opens_the_browser_without_asking_pywebview(monkeypatch):
    from importlib import util
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(util, "find_spec", lambda name: None)
    assert launch._toolkit() is False
    monkeypatch.setattr(sys, "platform", "darwin")
    assert launch._toolkit() is True
