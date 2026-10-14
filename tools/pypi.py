"""Orkline on PyPI (docs/distribution-howto.md): the package `orkline`, built from this repository.

    python tools/pypi.py rename                    # pyproject.toml's name → orkline, in this checkout (CI only)
    python tools/pypi.py check dist/ [--tag v0.3.0]   # what was built is what PyPI should get

From git, the distribution keeps its name `orkcraft`: copies installed from GitHub upgrade themselves by that name
(core/updates.py), and pip refuses a URL whose package is named otherwise. Only the release workflow
(.github/workflows/pypi.yml) renames it, in its own checkout, just before building. The import package stays
`orkcraft`, and both commands (`orkline`, `orkcraft`) are in the wheel.

`check` reads the wheel and the sdist: their name and version, both commands, and none of what is meant for
readers rather than the GUI (the design system's previews and notes, the docs and their generated reference
sheets). Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "orkline"
GIT_NAME = "orkcraft"
COMMANDS = ("orkline", "orkcraft")
# Paths a wheel or sdist must not carry: art and pages meant for the docs, never read at run time.
NOT_SHIPPED = (
    re.compile(r"(^|/)docs/"),
    re.compile(r"(^|/)references?/"),
    re.compile(r"design/system/previews/"),
    re.compile(r"design/system/.*\.md$"),
    re.compile(r"(^|/)design-system/"),
    re.compile(r"\.(psd|aseprite|kra|xcf|mp4|mov|gif)$"),
)
_NAME_LINE = re.compile(r'^name = "orkcraft"', re.M)


def version(root: Path = ROOT) -> str:
    text = (root / "orkcraft" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    if not found:
        raise ValueError("orkcraft/__init__.py has no __version__")
    return found.group(1)


def rename(pyproject: Path) -> None:
    """`name = "orkcraft"` → `name = "orkline"` in this pyproject.toml. Raises ValueError when the line is not
    there (already renamed, or the file changed shape)."""
    text = pyproject.read_text(encoding="utf-8")
    if not _NAME_LINE.search(text):
        raise ValueError(f'{pyproject} has no line name = "{GIT_NAME}"')
    pyproject.write_text(_NAME_LINE.sub(f'name = "{NAME}"', text, count=1), encoding="utf-8")


def _not_shipped(names: list[str]) -> list[str]:
    return [n for n in names if any(p.search(n) for p in NOT_SHIPPED)]


def check_wheel(path: Path, want: str) -> list[str]:
    """What is wrong with this wheel ([] when nothing)."""
    problems = []
    if not path.name.startswith(f"{NAME}-{want}-"):
        problems.append(f"{path.name}: expected {NAME}-{want}-…whl")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        info = f"{NAME}-{want}.dist-info"
        try:
            meta = z.read(f"{info}/METADATA").decode("utf-8")
            entry = z.read(f"{info}/entry_points.txt").decode("utf-8")
        except KeyError as e:
            return problems + [f"{path.name}: no {e.args[0]}"]
    if f"\nName: {NAME}\n" not in meta or f"\nVersion: {want}\n" not in meta:
        problems.append(f"{path.name}: METADATA does not say Name: {NAME}, Version: {want}")
    for command in COMMANDS:
        if f"{command} = orkcraft.cli:main" not in entry:
            problems.append(f"{path.name}: no `{command}` command")
    if "orkcraft/__init__.py" not in names or "orkcraft/gui/static/index.html" not in names:
        problems.append(f"{path.name}: the orkcraft package or the GUI's files are missing")
    problems += [f"{path.name}: carries {n}" for n in _not_shipped(names)]
    return problems


def check_sdist(path: Path, want: str) -> list[str]:
    problems = []
    if path.name != f"{NAME}-{want}.tar.gz":
        problems.append(f"{path.name}: expected {NAME}-{want}.tar.gz")
    with tarfile.open(path) as t:
        names = [n.split("/", 1)[1] for n in t.getnames() if "/" in n]
    problems += [f"{path.name}: carries {n}" for n in _not_shipped(names)]
    return problems


def check(dist: Path, tag: str | None = None, root: Path = ROOT) -> list[str]:
    """Everything wrong with the wheel and sdist in `dist` ([] when they are ready for PyPI)."""
    want = version(root)
    problems = []
    if tag is not None and tag != f"v{want}":
        problems.append(f"the tag {tag} is not v{want}, the version in orkcraft/__init__.py")
    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return problems + [f"{dist}: expected one wheel and one sdist, found {len(wheels)} and {len(sdists)}"]
    return problems + check_wheel(wheels[0], want) + check_sdist(sdists[0], want)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/pypi.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    rn = sub.add_parser("rename", help=f"name the distribution {NAME} in pyproject.toml (CI's checkout only)")
    rn.add_argument("--pyproject", type=Path, default=ROOT / "pyproject.toml")
    ck = sub.add_parser("check", help="check the built wheel and sdist")
    ck.add_argument("dist", type=Path)
    ck.add_argument("--tag", default=None, help="the release tag being published (v<version>)")
    args = parser.parse_args(argv)
    if args.action == "rename":
        try:
            rename(args.pyproject)
        except ValueError as e:
            print(f"pypi: {e}", file=sys.stderr)
            return 1
        print(f"pypi: {args.pyproject} names the distribution {NAME}")
        return 0
    problems = check(args.dist, args.tag)
    for p in problems:
        print(f"pypi: {p}", file=sys.stderr)
    if not problems:
        print(f"pypi: {NAME} {version()} is ready for PyPI")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
