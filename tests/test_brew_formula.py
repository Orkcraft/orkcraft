"""The Homebrew formula (Formula/orkcraft.rb, tools/brew_formula.py): what `brew install orkcraft/orkcraft/orkcraft` builds."""
from __future__ import annotations

import importlib.util
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMULA = (ROOT / "Formula" / "orkcraft.rb").read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("brew_formula", ROOT / "tools" / "brew_formula.py")
brew_formula = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brew_formula)


def test_the_formula_installs_a_published_release_from_a_commit_archive():
    version = re.search(r'^  version "([^"]+)"', FORMULA, re.M).group(1)
    released = [r["version"] for r in json.loads((ROOT / "updates.json").read_text(encoding="utf-8"))["releases"]]
    assert version in released
    assert re.search(r'^  url "https://github\.com/Orkcraft/orkcraft/archive/[0-9a-f]{40}\.tar\.gz"$', FORMULA, re.M)
    assert re.search(r'^  sha256 "[0-9a-f]{64}"$', FORMULA, re.M)
    assert re.search(r'^  depends_on "python@\d+\.\d+"$', FORMULA, re.M) and "virtualenv_create(libexec" in FORMULA


def test_every_resource_is_a_pinned_download_from_pypi():
    resources = re.findall(r'resource "([^"]+)" do\n\s+url "([^"]+)"\n\s+sha256 "([0-9a-f]{64})"\n', FORMULA)
    assert len(resources) == FORMULA.count('resource "')
    assert all(url.startswith("https://files.pythonhosted.org/") for _, url, _ in resources)


def test_each_platform_gets_a_wheel_it_can_take_and_pyobjc_only_on_macos():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    wheels = brew_formula.resources(lock)
    shared = {r["name"] for r in wheels["all"]}
    for where in ("macos arm", "macos intel", "linux arm", "linux intel"):
        names = shared | {r["name"] for r in wheels[where]}
        assert {"textual", "pywebview", "websockets", "cryptography", "segno", "rpds-py"} <= names, where
        assert {"pytest", "playwright"}.isdisjoint(names)
        assert any(n.startswith("pyobjc") for n in names) == where.startswith("macos")
    arm = {r["name"]: r["url"] for r in wheels["macos arm"]}
    assert arm["cryptography"].endswith("macosx_11_0_arm64.whl") and "cp313-cp313t" not in arm["rpds-py"]
    assert "manylinux" in {r["name"]: r["url"] for r in wheels["linux intel"]}["rpds-py"]
    text = brew_formula.render("0" * 40, "1" * 64, lock)
    assert text.index('resource "attrs"') < text.index("on_macos do") < text.index("on_linux do") < text.index("def install")
    assert 'depends_on "rust" => :build' not in text.split("on_macos do")[0]   # only where an sdist is built
