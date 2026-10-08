"""The Homebrew formula, `Formula/orkcraft.rb`, written for one commit of this repository.

    python tools/brew_formula.py [--commit SHA] [--sha256 HASH]

The repository is its own tap (docs/updates.md):

    brew tap orkcraft/orkcraft https://github.com/Orkcraft/orkcraft
    brew install orkcraft

The formula installs `orkcraft[gui]` in a virtualenv from the GitHub archive of `--commit` (by default
`git rev-parse HEAD`, which must be on GitHub). The version is `__version__` and the Python packages
are the sdists `uv.lock` pins, with their hashes, for the `gui` extra: the ones only macOS needs
(pyobjc, for the window's WebKit) under `on_macos`. Without `--sha256` the archive is downloaded to
hash it. Run it from the commit the formula is for, so `uv.lock` and the code agree; the release
workflow (`.github/workflows/brew.yml`) does that for every new `__version__` on `main`.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tomllib
import urllib.request
from pathlib import Path

from packaging.markers import Marker
from packaging.specifiers import SpecifierSet

ROOT = Path(__file__).resolve().parents[1]
FORMULA = ROOT / "Formula" / "orkcraft.rb"
REPO = "https://github.com/Orkcraft/orkcraft"
EXTRA = "gui"
DESC = "Run many coding agents in one project, as a real-time strategy game"   # brew: ≤ 80, no article
PYTHON = "3.13"     # Homebrew's python@3.13; it must satisfy `requires-python`
# Built from source by brew (`--no-binary=:all:`): Rust for cryptography and rpds-py, OpenSSL for cryptography.
PLATFORMS = {"macos": {"sys_platform": "darwin", "platform_system": "Darwin"},
             "linux": {"sys_platform": "linux", "platform_system": "Linux"}}


def version() -> str:
    text = (ROOT / "orkcraft" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', text, re.M).group(1)


def _environment(platform: str) -> dict[str, str]:
    full = PYTHON + ".0"
    return {"python_version": PYTHON, "python_full_version": full, "implementation_name": "cpython",
            "platform_python_implementation": "CPython", "os_name": "posix", "extra": "",
            **PLATFORMS[platform]}


def needed(lock: dict, platform: str) -> set[str]:
    """The packages `orkcraft[EXTRA]` installs on `platform`, by uv.lock's graph and markers."""
    packages = {p["name"]: p for p in lock["package"]}
    env = _environment(platform)
    root = packages["orkcraft"]
    todo = list(root.get("dependencies", [])) + list(root.get("optional-dependencies", {}).get(EXTRA, []))
    seen: set[str] = set()
    while todo:
        dep = todo.pop()
        if dep["name"] in seen or ("marker" in dep and not Marker(dep["marker"]).evaluate(env)):
            continue
        seen.add(dep["name"])
        todo.extend(packages[dep["name"]].get("dependencies", []))
    return seen


def resources(lock: dict) -> tuple[list[dict], list[dict]]:
    """(on every platform, on macOS only): each `{name, url, sha256}`, sorted by name."""
    packages = {p["name"]: p for p in lock["package"]}
    mac, linux = needed(lock, "macos"), needed(lock, "linux")
    if linux - mac:
        raise SystemExit(f"packages only Linux needs: {sorted(linux - mac)}; add an on_linux block")

    def entry(name: str) -> dict:
        sdist = packages[name].get("sdist")
        if not sdist:
            raise SystemExit(f"{name} has no sdist in uv.lock; Homebrew builds every package from source")
        return {"name": name, "url": sdist["url"], "sha256": sdist["hash"].removeprefix("sha256:")}

    return [entry(n) for n in sorted(mac & linux)], [entry(n) for n in sorted(mac - linux)]


def _resource(r: dict, indent: str) -> str:
    return (f'{indent}resource "{r["name"]}" do\n{indent}  url "{r["url"]}"\n'
            f'{indent}  sha256 "{r["sha256"]}"\n{indent}end\n')


def render(commit: str, sha256: str, lock: dict | None = None) -> str:
    lock = lock or tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if PYTHON + ".0" not in SpecifierSet(project["requires-python"]):
        raise SystemExit(f"python@{PYTHON} does not satisfy requires-python {project['requires-python']}")
    common, mac = resources(lock)
    out = [
        "# Written by tools/brew_formula.py for one commit: run it again rather than editing this file.\n",
        "class Orkcraft < Formula\n",
        "  include Language::Python::Virtualenv\n\n",
        f'  desc "{DESC}"\n',
        f'  homepage "{REPO}"\n',
        f'  url "{REPO}/archive/{commit}.tar.gz"\n',
        f'  version "{version()}"\n',
        f'  sha256 "{sha256}"\n',
        '  license "Apache-2.0"\n',
        f'  head "{REPO}.git", branch: "main"\n\n',
        '  depends_on "pkgconf" => :build\n',
        '  depends_on "rust" => :build\n',
        '  depends_on "openssl@3"\n',
        f'  depends_on "python@{PYTHON}"\n\n',
        '  uses_from_macos "libffi"\n\n',
        "  on_macos do\n",
        "\n".join(_resource(r, "    ") for r in mac),
        "  end\n\n",
        "\n".join(_resource(r, "  ") for r in common),
        "\n",
        "  def install\n",
        f'    # The `{EXTRA}` extra: the packages above are what it needs; pip installs the package itself.\n',
        "    virtualenv_install_with_resources\n",
        "  end\n\n",
        "  test do\n",
        '    assert_match "orkcraft", shell_output("#{bin}/orkcraft --help")\n',
        '    assert_equal version.to_s,\n',
        '                 shell_output("#{libexec}/bin/python -c \'import orkcraft; print(orkcraft.__version__)\'").strip\n',
        f'    system libexec/"bin/python", "-c", "import webview, websockets, cryptography, segno"\n',
        "  end\n",
        "end\n",
    ]
    return "".join(out)


def archive_sha256(commit: str) -> str:
    with urllib.request.urlopen(f"{REPO}/archive/{commit}.tar.gz", timeout=120) as r:
        return hashlib.sha256(r.read()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", help="the commit on GitHub the formula installs (default: HEAD)")
    ap.add_argument("--sha256", help="the archive's sha256 (default: download it and hash it)")
    args = ap.parse_args()
    commit = args.commit or subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True,
                                           capture_output=True, text=True).stdout.strip()
    sha = args.sha256 or archive_sha256(commit)
    FORMULA.parent.mkdir(exist_ok=True)
    FORMULA.write_text(render(commit, sha), encoding="utf-8")
    print(f"{FORMULA.relative_to(ROOT)}: orkcraft {version()} at {commit[:12]} ({sha[:12]}…)")


if __name__ == "__main__":
    main()
