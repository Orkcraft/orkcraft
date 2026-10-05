"""The GUI face (docs/design/gui-migration.md, stage 4): the town in a window, Office look first.

    host.py     the Town, its clocks and the page's commands, on one thread (no toolkit)
    state.py    what the page shows, as one JSON snapshot
    server.py   the page, the design system and one WebSocket on 127.0.0.1
    launch.py   `orkcraft gui`: a pywebview window (WKWebView on macOS) or the browser
    static/     the page: Preact + htm + signals as ES modules, no build step

Like tui/, this is a face: core/, realm/ and design/ never import it.
"""
