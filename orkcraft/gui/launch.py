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
from orkcraft.gui import folders
from orkcraft.gui.host import Host
from orkcraft.gui.server import Server

TITLE = "Orkline"
SIZE = (1440, 900)


def run(repo_root: Path | None = None, auto_commit: bool | None = None, layout_file: Path | None = None,
        demo: bool = False, browser: bool = False, port: int = 0) -> int:
    host = Host(repo_root, auto_commit, layout_file, demo=demo)
    server = Server(host, port)
    thread = server.start_thread()
    host.awake.running = True                    # the screen may turn off; the computer does not sleep (gui/awake.py)
    host.awake.apply(host.town.machine.keep_awake)
    done = lambda: updates.RESTART if host.updates.restart_wanted else 0   # noqa: E731
    if not browser and not _toolkit():
        sys.stderr.write("orkline: no window here (GTK or Qt for Python is not installed); opening the browser\n")
        browser = True
    if not browser:
        try:
            import webview
        except ImportError:
            sys.stderr.write("orkcraft: no window toolkit (pip install 'orkcraft[gui]'); opening the browser\n")
            browser = True
    if browser:
        return _in_browser(host, server, thread, done)
    window = webview.create_window(TITLE, server.url, width=SIZE[0], height=SIZE[1], min_size=(960, 600),
                          background_color="#141210")
    host.updates.quit = window.destroy
    folders.attach(window)                       # the Wiki's folder dialog and dropped folders' paths
    try:
        webview.start()
    except Exception as e:                       # pywebview is there, a toolkit for it is not (Linux without GTK or Qt)
        sys.stderr.write(f"orkline: no window here ({e}); opening the browser\n")
        return _in_browser(host, server, thread, done)
    except BaseException:
        _stop(host, server, thread)
        raise
    _stop(host, server, thread)
    return done()


def _toolkit() -> bool:
    """Whether pywebview has something to draw with: macOS and Windows always do; Linux needs GTK (gi) or Qt
    (qtpy), and without them pywebview prints its own tracebacks before it gives up."""
    if not sys.platform.startswith("linux"):
        return True
    from importlib.util import find_spec
    return any(find_spec(name) is not None for name in ("gi", "qtpy"))


def _in_browser(host: Host, server: Server, thread, done) -> int:
    host.updates.quit = server.stop
    print(f"Orkline is at {server.url} — Ctrl+C stops it")
    webbrowser.open(server.url)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        _stop(host, server, thread)
    return done()


def _stop(host: Host, server: Server, thread) -> None:
    server.stop()
    thread.join(10)
    host.awake.stop()
