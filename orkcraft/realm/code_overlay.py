"""A change to Orkline's own code, for a Test bench's runs only (docs/design/improve-buildings.md §5.3).

The installed app is never changed. A Test bench that tries a code change gets its own copy of the `orkcraft`
package beside it (`<state>/code/orkcraft`, the sprites linked, not copied), a git repository whose first commit is
the package as installed; an agent changes it there, and its runs start `orkcraft bench` with that copy first on
`PYTHONPATH`, so the building runs on the changed code in the run's process and nowhere else. The diff is what a
pull request carries (stage 5); dropping it takes the copy away.

    code_overlay.ensure(state_dir)          the copy, made once
    code_overlay.diff(state_dir)            what changed from the package as installed
    code_overlay.env(state_dir)             {"PYTHONPATH": …} for a run, {} when nothing changed
"""
from __future__ import annotations

import shutil
from pathlib import Path

import orkcraft
from orkcraft.design import agents
from orkcraft.realm import bench

DIR = "code"
BASE = "installed"                 # the tag of the package as installed
DIFF_MAX = 200_000                 # characters of a diff kept in the bench's state


def root(state_dir: Path) -> Path:
    return state_dir / DIR


def package() -> Path:
    return Path(orkcraft.__file__).resolve().parent


def ensure(state_dir: Path) -> Path:
    """The copy of the package a Test bench changes, made once: the package as installed, committed and tagged."""
    top = root(state_dir)
    pkg = top / "orkcraft"
    if (top / ".git").is_dir() and pkg.is_dir():
        return pkg
    if top.exists():
        shutil.rmtree(top)
    src = package()
    shutil.copytree(src, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "system"))
    system = src / "design" / "system"
    if system.exists():                           # the sprites and fonts: linked, never copied
        (pkg / "design" / "system").symlink_to(system.resolve(), target_is_directory=True)
    (top / ".gitignore").write_text("__pycache__/\n*.pyc\norkcraft/design/system\n", encoding="utf-8")
    bench.git(top, "init", "-q", "-b", "main")
    bench.git(top, "add", "-A")
    bench.git(top, *bench.AUTHOR, "commit", "-q", "-m", f"orkcraft {orkcraft.__version__} as installed")
    bench.git(top, "tag", BASE)
    return pkg


def changed(state_dir: Path) -> list[str]:
    top = root(state_dir)
    if not (top / ".git").is_dir():
        return []
    bench.git(top, "add", "-A")
    out = bench.git(top, "diff", "--cached", "--name-only", BASE)
    return [line for line in out.splitlines() if line.strip()]


def diff(state_dir: Path) -> str:
    """Every change from the package as installed, as a unified diff (paths from the repository's root)."""
    top = root(state_dir)
    if not (top / ".git").is_dir():
        return ""
    bench.git(top, "add", "-A")
    return bench.git(top, "diff", "--cached", BASE)[:DIFF_MAX]


def keep(state_dir: Path, message: str) -> None:
    top = root(state_dir)
    bench.git(top, "add", "-A")
    if bench.git(top, "status", "--porcelain").strip():
        bench.git(top, *bench.AUTHOR, "commit", "-q", "-m", message[:200])


def env(state_dir: Path) -> dict[str, str]:
    """What a run's process needs to import the changed package before the installed one; {} when nothing changed."""
    if not changed(state_dir):
        return {}
    return {"PYTHONPATH": str(root(state_dir))}


def drop(state_dir: Path) -> None:
    shutil.rmtree(root(state_dir), ignore_errors=True)


def code_prompt(title: str, detail: str, where: str, effect: str, files: list[str]) -> str:
    return f"""{agents.persona("mechanic")}

You change Orkline's own code (a Python package, here in `orkcraft/`) for one proposed improvement. Make the
smallest change that does what the proposal says, in the files that make it; keep every name other code uses, and
the style of the code around it. Change only `orkcraft/`. Do not run anything that needs the network.

The proposal: {title}
What exactly and why: {detail}
Where: {where or 'say where you changed it'}
What it should do: {effect or '—'}

The files that make the buildings involved (paths from the package):
{chr(10).join('- ' + f for f in files) or '- find them under orkcraft/core/workers, orkcraft/realm, orkcraft/gui/views'}

When done, say in two or three lines what you changed and why."""
