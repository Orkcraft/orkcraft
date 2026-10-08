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


# A module that knows the agent tools (`realm/harnesses.py`) and starts processes itself registers them in
# `realm/halt.py`, the one list of what runs: the HUD counts agents from it and 🛑 Stop all kills what is on it.
# These start only short commands that are not agents, or keep their own list (tech-debt T13).
STARTS_WITHOUT_HALT = {
    "realm/model_families.py": "asks a tool for its model list; no model runs",
    "realm/masonry.py": "git log",
    "sources/sessions.py": "git log",
    "tools.py": "a tool's version and login state",
    "core/sessions.py": "the War Tent's terminal sessions; Stop all interrupts them through Sessions.interrupt_all",
}
_STARTS = {("subprocess", "Popen"), ("subprocess", "run"), ("subprocess", "call"), ("subprocess", "check_output"),
           ("pty", "fork"), ("os", "execvpe"), ("os", "execvp")}


def _starts_and_names(path: Path) -> tuple[bool, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    starts = any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and (n.value.id, n.attr) in _STARTS
                 for n in ast.walk(tree))
    names = {m.split(".")[-1] for _line, m in _imports(path)}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            names |= {a.name for a in n.names}
    return starts, names


def test_whoever_starts_an_agent_registers_it_in_halt():
    bad = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.split("/")[0] in ("tui", "screens", "widgets", "wm") or rel in ("app.py", "realm/halt.py"):
            continue
        starts, names = _starts_and_names(path)
        if starts and "harnesses" in names and "halt" not in names and rel not in STARTS_WITHOUT_HALT:
            bad.append(f"{rel} starts processes and knows the agent tools, but never uses realm/halt.py")
    assert not bad, "\n".join(bad)
    assert all((ROOT / rel).is_file() for rel in STARTS_WITHOUT_HALT), "a listed module is gone: drop it from the list"
