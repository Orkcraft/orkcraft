"""Town Scroll: path resolution for the workspace Town Scroll."""
from __future__ import annotations

import os
from pathlib import Path

from orkcraft.env import getenv

TOWN_SCROLL = ".orkcraft.json"


def default_layout_file(repo_root: Path | None = None) -> Path:
    """`$ORKCRAFT_LAYOUT_FILE`, else the Town Scroll `<workspace>/.orkcraft.json`,
    else `$XDG_CONFIG_HOME/orkcraft/layout.json` when there is no workspace."""
    env = getenv("LAYOUT_FILE")
    if env:
        return Path(env).expanduser()
    if repo_root is not None:
        return repo_root / TOWN_SCROLL
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "orkcraft" / "layout.json"
