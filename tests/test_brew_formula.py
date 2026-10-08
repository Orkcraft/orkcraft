"""The Homebrew formula (Formula/orkcraft.rb, tools/brew_formula.py): what `brew install orkcraft` builds."""
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
    assert re.search(r'^  depends_on "python@\d+\.\d+"$', FORMULA, re.M) and "virtualenv_install_with_resources" in FORMULA


def test_every_resource_is_an_sdist_with_its_hash():
    resources = re.findall(r'resource "([^"]+)" do\n\s+url "([^"]+)"\n\s+sha256 "([0-9a-f]{64})"\n', FORMULA)
    assert len(resources) == FORMULA.count('resource "')
    assert all(url.startswith("https://files.pythonhosted.org/") and url.endswith(".tar.gz") for _, url, _ in resources)


def test_the_gui_extra_is_in_and_pyobjc_only_on_macos():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    common, mac = brew_formula.resources(lock)
    names = {r["name"] for r in common}
    assert {"textual", "pywebview", "websockets", "cryptography", "segno"} <= names
    assert {"pytest", "playwright"}.isdisjoint(names)
    assert mac and all(r["name"].startswith("pyobjc") for r in mac)
    text = brew_formula.render("0" * 40, "1" * 64, lock)
    assert text.index("on_macos do") < text.index('resource "pyobjc-core"') < text.index('resource "attrs"')
