"""🧪 The Test bench's shipped cases, per building type (docs/design/test-bench.md §3.1). Data only.

A case carries its whole project (`files`), so it runs the same on any machine, and a check that says in
code whether the result is right. A town adds its own in `.orkcraft/bench/<type>/*.json`.
"""
from __future__ import annotations

_TEXT_PY = '''"""Text helpers."""


def words(text: str) -> list[str]:
    return text.split()
'''

_SLUGIFY_TEST = '''from src.text import slugify


def test_plain():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_and_spaces():
    assert slugify("  Ork, meet the  Warchief!  ") == "ork-meet-the-warchief"


def test_accents_are_dropped():
    assert slugify("Café déjà vu") == "cafe-deja-vu"


def test_empty():
    assert slugify("!!!") == ""
'''

_INVENTORY_PY = '''"""A tiny inventory: items, their counts, and a report."""
import json


class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, name, count=1):
        self.items[name] = self.items.get(name, 0) + count

    def remove(self, name, count=1):
        self.items[name] = self.items.get(name, 0) - count

    def report(self):
        return "\\n".join(f"{k}: {v}" for k, v in self.items.items())
'''

_INVENTORY_TEST = '''import json

import pytest

from src.inventory import Inventory


def test_add_and_report():
    inv = Inventory()
    inv.add("axe", 2)
    inv.add("rope")
    assert inv.report() == "axe: 2\\nrope: 1"


def test_remove_never_goes_below_zero():
    inv = Inventory()
    inv.add("axe")
    with pytest.raises(ValueError):
        inv.remove("axe", 2)
    assert inv.items["axe"] == 1


def test_remove_the_last_one_drops_the_item():
    inv = Inventory()
    inv.add("axe")
    inv.remove("axe")
    assert "axe" not in inv.items


def test_report_is_sorted():
    inv = Inventory()
    inv.add("rope")
    inv.add("axe")
    assert inv.report() == "axe: 1\\nrope: 1"


def test_save_and_load(tmp_path):
    inv = Inventory()
    inv.add("axe", 3)
    path = tmp_path / "inv.json"
    inv.save(path)
    assert json.loads(path.read_text()) == {"axe": 3}
    assert Inventory.load(path).items == {"axe": 3}
'''

# The tests pass, and they are the ones the case came with (a result that changed them does not pass).
_CHECK = "git diff --quiet $(git rev-list --max-parents=0 HEAD) -- tests && python -m pytest -q tests"

CASES: dict[str, list[dict]] = {
    "barracks": [
        {
            "id": "slugify",
            "title": "Add a slugify helper",
            "task": "Add `slugify(text)` to `src/text.py`: lower case, accents dropped, every run of other "
                    "characters becomes one '-', no '-' at either end. `tests/test_text.py` says what is wanted; "
                    "make it pass without changing it.",
            "files": {"src/__init__.py": "", "src/text.py": _TEXT_PY, "tests/test_text.py": _SLUGIFY_TEST,
                      "README.md": "# Text helpers\n"},
            "check": _CHECK,
            "expect": "One small function, standard library only, the tests unchanged.",
        },
        {
            "id": "inventory",
            "title": "Harden the inventory and let it save",
            "task": "Three changes to `src/inventory.py`: (1) `remove` raises ValueError instead of going below "
                    "zero, and an item whose count reaches zero is dropped; (2) `report` lists items sorted by name; "
                    "(3) `save(path)` writes the items as JSON and `Inventory.load(path)` reads them back. "
                    "`tests/test_inventory.py` says what is wanted; make it pass without changing it.",
            "files": {"src/__init__.py": "", "src/inventory.py": _INVENTORY_PY,
                      "tests/test_inventory.py": _INVENTORY_TEST, "README.md": "# Inventory\n"},
            "check": _CHECK,
            "expect": "Three separable changes in one file: a planner may split them; the tests unchanged.",
        },
    ],
}
