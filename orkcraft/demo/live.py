"""The sandbox's live terminals: what a few orks would have on their screens, with a question
waiting, so the Answers and the Barracks' ork tabs show something real — and no model runs.

`dashboard.prepare` writes the screens (`SESSIONS`); a face that opens the demo calls `open_all`,
which plays each screen on a PTY with a plain shell: the person's answer is echoed, nothing else.
"""
from __future__ import annotations

import json
from pathlib import Path

SESSIONS = Path(".orkcraft") / "demo-sessions"
# A screen is printed, the answer read and echoed; then the session idles, taking what is typed.
PLAY = 'cat "$1"; read answer; printf "\\n  → %s\\n" "$answer"; exec cat >/dev/null'


def write(root: Path, screens: list[dict]) -> None:
    """[{key, title, harness, ork, screen}] into the sandbox."""
    folder = root / SESSIONS
    folder.mkdir(parents=True, exist_ok=True)
    index = []
    for i, s in enumerate(screens):
        name = f"{i}.txt"
        (folder / name).write_text(s["screen"].replace("\n", "\r\n"), encoding="utf-8")
        index.append({k: s[k] for k in ("key", "title", "harness", "ork")} | {"screen": name})
    (folder / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")


def open_all(sessions, root: Path) -> list[str]:
    """Open the sandbox's terminals; the keys opened (none when it has none or a PTY fails)."""
    folder = Path(root) / SESSIONS
    try:
        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    opened = []
    for s in index:
        try:
            sessions.open(s["key"], ["sh", "-c", PLAY, "sh", str(folder / s["screen"])], s["harness"], s["title"],
                          ork=s.get("ork", ""), cwd=str(root))
        except (OSError, KeyError, ValueError):
            continue
        opened.append(s["key"])
    return opened
