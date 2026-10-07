"""`orkcraft gui`: the town in a window of its own (pywebview) or in the browser (`--browser`).

The window is the system's own web view (WKWebView on macOS), so the GUI carries no browser of its
own. The server runs on a thread; the window takes the main thread, as macOS wants. It returns
`updates.RESTART` when it closed to open again on an update it installed (gui/updates.py, cli.py).
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from orkcraft.core import updates
from orkcraft.gui.host import Host
from orkcraft.gui.server import Server

TITLE = "Orkcraft"
SIZE = (1440, 900)


def run(repo_root: Path | None = None, auto_commit: bool | None = None, layout_file: Path | None = None,
        demo: bool = False, browser: bool = False, port: int = 0) -> int:
    host = Host(repo_root, auto_commit, layout_file, demo=demo)
    server = Server(host, port)
    thread = server.start_thread()
    done = lambda: updates.RESTART if host.updates.restart_wanted else 0   # noqa: E731
    if not browser:
        try:
            import webview
        except ImportError:
            sys.stderr.write("orkcraft: no window toolkit (pip install 'orkcraft[gui]'); opening the browser\n")
            browser = True
    if browser:
        host.updates.quit = server.stop
        print(f"Orkcraft is at {server.url} — Ctrl+C stops it")
        webbrowser.open(server.url)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
            thread.join(10)
        return done()
    window = webview.create_window(TITLE, server.url, width=SIZE[0], height=SIZE[1], min_size=(960, 600),
                          background_color="#141210")
    host.updates.quit = window.destroy
    try:
        webview.start()
    finally:
        server.stop()
        thread.join(10)
    return done()
