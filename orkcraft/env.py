"""Environment variables: `ORKCRAFT_<NAME>`, falling back to the older `ORCRAFT_<NAME>` and `MGTUI_<NAME>`."""
from __future__ import annotations

import os

PREFIXES = ("ORKCRAFT_", "ORCRAFT_", "MGTUI_")


def getenv(name: str, default: str = "") -> str:
    for prefix in PREFIXES:
        value = os.environ.get(prefix + name)
        if value:
            return value.strip()
    return default.strip()
