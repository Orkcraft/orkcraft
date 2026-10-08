"""The Homebrew formula, `Formula/orkcraft.rb`, written for one commit of this repository.

    python tools/brew_formula.py [--commit SHA] [--sha256 HASH]

The repository is its own tap (docs/updates.md):

    brew tap orkcraft/orkcraft https://github.com/Orkcraft/orkcraft
    brew install orkcraft/orkcraft/orkcraft

The formula installs `orkcraft[gui]` in a virtualenv from the GitHub archive of `--commit` (by default
`git rev-parse HEAD`, which must be on GitHub). The version is `__version__` and the Python packages
are the wheels `uv.lock` pins, with their hashes, for the `gui` extra: one per package where it is
pure Python, else one for each of macOS and Linux on arm and on Intel (pyobjc, for the window's
WebKit, on macOS only). Wheels install in seconds; brew building every sdist (Rust for cryptography
and rpds-py) took minutes. Without `--sha256` the archive is downloaded to hash it. Run it from the commit the formula is for, so `uv.lock` and the code agree; the release
workflow (`.github/workflows/brew.yml`) does that for every new `__version__` on `main`.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import re
import subprocess
import tomllib
import urllib.request
from pathlib import Path

from packaging import tags
from packaging.markers import Marker
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
FORMULA = ROOT / "Formula" / "orkcraft.rb"
REPO = "https://github.com/Orkcraft/orkcraft"
EXTRA = "gui"
DESC = "Run many coding agents in one project, as a real-time strategy game"   # brew: ≤ 80, no article
PYTHON = "3.13"     # Homebrew's python@3.13; it must satisfy `requires-python`
PLATFORMS = {"macos": {"sys_platform": "darwin", "platform_system": "Darwin"},
             "linux": {"sys_platform": "linux", "platform_system": "Linux"}}
ARCHES = {"arm": {"macos": "arm64", "linux": "aarch64"}, "intel": {"macos": "x86_64", "linux": "x86_64"}}
MACOS_MIN = (13, 0)     # a wheel may need at most this macOS
GLIBC_MAX = 28          # … and at most this glibc (manylinux_2_28)
LEGACY = {17: "manylinux2014", 12: "manylinux2010", 5: "manylinux1"}


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


@functools.cache
def _ranks(os: str, arch: str) -> dict[tags.Tag, int]:
    """The wheel tags CPython PYTHON takes on `os`/`arch`, best first, as {tag: rank}."""
    cpu = ARCHES[arch][os]
    if os == "macos":
        plats = list(tags.mac_platforms(MACOS_MIN, cpu))
    else:
        plats = []
        for minor in range(GLIBC_MAX, 4, -1):
            plats.append(f"manylinux_2_{minor}_{cpu}")
            if minor in LEGACY and (cpu == "x86_64" or minor == 17):
                plats.append(f"{LEGACY[minor]}_{cpu}")
    version = tuple(int(n) for n in PYTHON.split("."))
    ordered = [*tags.cpython_tags(version, [f"cp{PYTHON.replace('.', '')}"], plats),
               *tags.compatible_tags(version, f"cp{PYTHON.replace('.', '')}", plats)]
    return {t: i for i, t in reversed(list(enumerate(ordered)))}


def wheel(package: dict, os: str, arch: str) -> dict:
    """The best wheel of `package` uv.lock has for `os`/`arch`: `{name, url, sha256}`; its sdist when
    there is none (cryptography has no Intel Mac wheel: brew builds it there, with Rust)."""
    ranks, best = _ranks(os, arch), None
    for w in package.get("wheels", []):
        file = w["url"].rsplit("/", 1)[1]
        rank = min((ranks[t] for t in parse_wheel_filename(file)[3] if t in ranks), default=None)
        if rank is not None and (best is None or rank < best[0]):
            best = (rank, w)
    if best is None:
        if "sdist" not in package:
            raise SystemExit(f"{package['name']} has neither a wheel for {os} on {arch} nor an sdist in uv.lock")
        sdist = package["sdist"]
        return {"name": package["name"], "url": sdist["url"], "sha256": sdist["hash"].removeprefix("sha256:")}
    return {"name": package["name"], "url": best[1]["url"], "sha256": best[1]["hash"].removeprefix("sha256:")}


def resources(lock: dict) -> dict[str, list[dict]]:
    """The wheels by where they install: "all" (the same everywhere), "macos arm", "macos intel",
    "linux arm", "linux intel"; each list sorted by name."""
    packages = {p["name"]: p for p in lock["package"]}
    out: dict[str, list[dict]] = {"all": []}
    where = [(os, arch) for os in PLATFORMS for arch in ARCHES]
    for os, arch in where:
        out[f"{os} {arch}"] = []
    per_os = {os: needed(lock, os) for os in PLATFORMS}
    for name in sorted(set().union(*per_os.values())):
        picks = {(os, arch): wheel(packages[name], os, arch) for os, arch in where if name in per_os[os]}
        if len(picks) == len(where) and len({w["url"] for w in picks.values()}) == 1:
            out["all"].append(next(iter(picks.values())))
        else:
            for (os, arch), w in picks.items():
                out[f"{os} {arch}"].append(w)
    return out


def _resource(r: dict, indent: str) -> str:
    return (f'{indent}resource "{r["name"]}" do\n{indent}  url "{r["url"]}"\n'
            f'{indent}  sha256 "{r["sha256"]}"\n{indent}end\n')


# What an sdist needs to build: Rust (cryptography, rpds-py), and cryptography links OpenSSL.
SDIST_DEPENDS = ('depends_on "pkgconf" => :build', 'depends_on "rust" => :build', 'depends_on "openssl@3"')


def _block(os: str, wheels: dict[str, list[dict]]) -> str:
    def arch_block(arch: str) -> str:
        found = wheels[f"{os} {arch}"]
        builds = any(not r["url"].endswith(".whl") for r in found)
        depends = "".join(f"      {d}\n" for d in SDIST_DEPENDS) + "\n" if builds else ""
        return f"    on_{arch} do\n{depends}" + "\n".join(_resource(r, "      ") for r in found) + "    end\n"
    inner = "".join(arch_block(arch) for arch in ARCHES if wheels[f"{os} {arch}"])
    return f"  on_{os} do\n{inner}  end\n\n" if inner else ""


def render(commit: str, sha256: str, lock: dict | None = None) -> str:
    lock = lock or tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if PYTHON + ".0" not in SpecifierSet(project["requires-python"]):
        raise SystemExit(f"python@{PYTHON} does not satisfy requires-python {project['requires-python']}")
    wheels = resources(lock)
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
        f'  depends_on "python@{PYTHON}"\n\n',
        "\n".join(_resource(r, "  ") for r in wheels["all"]),
        "\n",
        _block("macos", wheels),
        _block("linux", wheels),
        "  def install\n",
        f'    # The `{EXTRA}` extra: the wheels above are what it needs, installed as they are (brew\'s own\n',
        "    # pip_install builds every package from source); pip builds an sdist among them, and the package.\n",
        f'    venv = virtualenv_create(libexec, "python{PYTHON}")\n',
        "    wheels = resources.map do |r|\n",
        "      r.fetch\n",
        '      wheel = buildpath/"wheels"/File.basename(r.url)\n',
        "      wheel.dirname.mkpath\n",
        "      cp r.cached_download, wheel\n",
        "      wheel\n",
        "    end\n",
        f'    system "python{PYTHON}", "-m", "pip", "--python=#{{libexec}}/bin/python", "install",\n',
        '           "--no-deps", "--no-compile", *wheels\n',
        "    venv.pip_install_and_link buildpath\n",
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
