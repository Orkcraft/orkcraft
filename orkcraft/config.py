"""Configuration and environment helpers for orkcraft."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from orkcraft.env import getenv

from orkcraft.wm.persist import default_layout_file


def find_project_root(start_path: Path | None = None) -> Path:
    """Find project root by walking up looking for .orkcraft.json or .git.

    Can start from start_path or Path.cwd().
    Raises FileNotFoundError if not inside a valid project.
    """
    p = (start_path or Path.cwd()).resolve()
    for c in [p, *p.parents]:
        if (c / ".orkcraft.json").exists() or (c / ".git").exists():
            return c
    raise FileNotFoundError(
        f"orkcraft: project root (.orkcraft.json or .git) not found starting from {p}"
    )


def get_editor() -> str:
    """Return the preferred editor from environment variables, defaulting to nano."""
    return os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"


@dataclass
class Config:
    """orkcraft configuration settings."""
    repo_root: Path = field(default_factory=find_project_root)
    auto_commit: bool = True
    git_co_author: str = "Co-Authored-By: orkcraft <noreply@local>"
    layout_file: Path | None = None  # None → the Town Scroll of repo_root

    def __post_init__(self) -> None:
        if self.layout_file is None:
            self.layout_file = default_layout_file(self.repo_root)
        env_commit = getenv("AUTO_COMMIT").lower()
        if env_commit in ("0", "false", "no", "off"):
            self.auto_commit = False
        elif env_commit in ("1", "true", "yes", "on"):
            self.auto_commit = True
