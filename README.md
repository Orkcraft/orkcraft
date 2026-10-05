# Orkcraft building gallery (not for merging)

Every building of `orkcraft gui --demo` in its three views (closed, command, full), the Lake window and
the Answers, taken 2026-10-05 from the demo of PR #40 by `tools/gallery.py` (PR #41).

- `index.html` — the page: open it locally (it reads `shots/` next to it)
- `report.json` — what was found, building by building; page and console errors (none)
- `notes.json` — what a review of the pictures by eye found (merged into the page with `--notes`)
- `shots/` — the pictures

Run it again:

    pip install -e '.[dev,browser]'
    python tools/gallery.py --out gallery --notes notes.json
