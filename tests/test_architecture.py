"""The core and the domain have no face: neither Textual nor Rich (docs/design/gui-migration.md §2).

Every import counts, a lazy one inside a function too: a GUI must be able to load these packages
without a terminal toolkit."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "orkcraft"
FACELESS = ["core", "realm", "design"]
FORBIDDEN = ("textual", "rich")


def _imports(path: Path) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append((node.lineno, node.module))
    return out


@pytest.mark.parametrize("package", FACELESS)
def test_no_face_in(package):
    bad = []
    for path in sorted((ROOT / package).rglob("*.py")):
        for line, module in _imports(path):
            top = module.split(".")[0]
            if top in FORBIDDEN or module.startswith(("orkcraft.tui", "orkcraft.screens", "orkcraft.widgets",
                                                      "orkcraft.wm", "orkcraft.app")):
                bad.append(f"{path.relative_to(ROOT.parent)}:{line} imports {module}")
    assert not bad, "\n".join(bad)
