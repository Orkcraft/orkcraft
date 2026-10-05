"""`orkcraft gui`: the town in a window of its own (pywebview) or in the browser (`--browser`).

The window is the system's own web view (WKWebView on macOS), so the GUI carries no browser of its
own. The server runs on a thread; the window takes the main thread, as macOS wants.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from orkcraft.gui.host import Host
from orkcraft.gui.server import Server

TITLE = "Orkcraft"
SIZE = (1440, 900)


def run(repo_root: Path | None = None, auto_commit: bool | None = None, layout_file: Path | None = None,
        demo: bool = False, browser: bool = False, port: int = 0, look: str = "office") -> int:
    server = Server(Host(repo_root, auto_commit, layout_file, demo=demo, look=look), port)
    thread = server.start_thread()
    if not browser:
        try:
            import webview
        except ImportError:
            sys.stderr.write("orkcraft: no window toolkit (pip install 'orkcraft[gui]'); opening the browser\n")
            browser = True
    if browser:
        print(f"Orkcraft is at {server.url} — Ctrl+C stops it")
        webbrowser.open(server.url)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
            thread.join(10)
        return 0
    webview.create_window(TITLE, server.url, width=SIZE[0], height=SIZE[1], min_size=(960, 600),
                          background_color="#1a1813")
    try:
        webview.start()
    finally:
        server.stop()
        thread.join(10)
    return 0
