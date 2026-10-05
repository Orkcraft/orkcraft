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
                                                      "orkcraft.wm", "orkcraft.app", "orkcraft.gui")):
                bad.append(f"{path.relative_to(ROOT.parent)}:{line} imports {module}")
    assert not bad, "\n".join(bad)


def test_loading_the_core_loads_no_face():
    """Transitively too: importing every module of core/, realm/ and design/ pulls in no toolkit."""
    import subprocess
    import sys
    modules = [f"orkcraft.{p.relative_to(ROOT).with_suffix('').as_posix().replace('/', '.')}"
               for package in FACELESS for p in sorted((ROOT / package).rglob("*.py"))]
    modules = [m.removesuffix(".__init__") for m in modules]
    code = ("import importlib, sys\n"
            f"for m in {modules!r}: importlib.import_module(m)\n"
            "print(sorted({n.split('.')[0] for n in sys.modules} & {'textual', 'rich'}))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


def test_the_gui_face_has_no_terminal_toolkit():
    """gui/ is a face of its own: it loads without Textual or Rich, and never reaches into the TUI."""
    bad = []
    for path in sorted((ROOT / "gui").rglob("*.py")):
        for line, module in _imports(path):
            if module.split(".")[0] in FORBIDDEN or module.startswith(("orkcraft.tui", "orkcraft.screens",
                                                                       "orkcraft.widgets", "orkcraft.wm",
                                                                       "orkcraft.app")):
                bad.append(f"{path.relative_to(ROOT.parent)}:{line} imports {module}")
    assert not bad, "\n".join(bad)
