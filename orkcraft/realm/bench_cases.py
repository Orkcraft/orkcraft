"""🧪 The Test bench's shipped cases, per building type (docs/design/test-bench.md §3.1). Data only.

A case carries its whole project (`files`), so it runs the same on any machine, and a check that says in
code whether the result is right. A town adds its own in `.orkcraft/bench/<type>/*.json`.
"""
from __future__ import annotations

from orkcraft.realm import bench_sets

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

_LIMITER_PY = '''"""Rate limiting for the camp's outgoing calls."""
'''

_LIMITER_TEST = '''import pytest

from src.limiter import TokenBucket


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_starts_full_and_runs_dry():
    bucket = TokenBucket(rate=2, capacity=3, clock=Clock())
    assert [bucket.take() for _ in range(4)] == [True, True, True, False]


def test_refills_with_time_but_never_past_capacity():
    clock = Clock()
    bucket = TokenBucket(rate=2, capacity=3, clock=clock)
    for _ in range(3):
        bucket.take()
    clock.now += 0.5
    assert bucket.take() and not bucket.take()
    clock.now += 100
    assert bucket.available() == pytest.approx(3)


def test_take_many_is_all_or_nothing():
    bucket = TokenBucket(rate=1, capacity=5, clock=Clock())
    assert bucket.take(4)
    assert not bucket.take(2)
    assert bucket.available() == pytest.approx(1)


def test_wait_time_says_how_long_until_enough():
    bucket = TokenBucket(rate=4, capacity=4, clock=Clock())
    bucket.take(4)
    assert bucket.wait_time(2) == pytest.approx(0.5)
    assert bucket.wait_time(0) == 0


def test_bad_arguments():
    with pytest.raises(ValueError):
        TokenBucket(rate=0, capacity=1)
    with pytest.raises(ValueError):
        TokenBucket(rate=1, capacity=0)
    bucket = TokenBucket(rate=1, capacity=2, clock=Clock())
    with pytest.raises(ValueError):
        bucket.take(3)
    with pytest.raises(ValueError):
        bucket.wait_time(-1)


def test_the_real_clock_is_the_default():
    assert TokenBucket(rate=1, capacity=1).take()
'''

_MONEY_TEST = '''import pytest

from src.money import format_money, parse_money


def test_format():
    assert format_money(1234567) == "12,345.67"
    assert format_money(5) == "0.05"
    assert format_money(-150) == "-1.50"


def test_parse():
    assert parse_money("12,345.67") == 1234567
    assert parse_money("-1.5") == -150
    assert parse_money("7") == 700


def test_parse_refuses_junk():
    for bad in ("", "1.234", "abc", "1,2,3.00x"):
        with pytest.raises(ValueError):
            parse_money(bad)
'''

_DATES_TEST = '''import pytest

from src.dates import iso_week, month_of


def test_iso_week():
    assert iso_week("2026-01-01") == "2026-W01"
    assert iso_week("2027-01-01") == "2026-W53"


def test_month_of():
    assert month_of("2026-10-10") == "2026-10"


def test_dates_must_be_iso():
    with pytest.raises(ValueError):
        iso_week("10/10/2026")
    with pytest.raises(ValueError):
        month_of("2026-13-01")
'''

_CSVIN_TEST = '''from src.csvin import read_rows


def test_read_rows(tmp_path):
    path = tmp_path / "in.csv"
    path.write_text("date,category,amount\\n2026-01-01,food,12.50\\n\\n2026-01-02, Tools ,3\\n")
    assert read_rows(path) == [
        {"date": "2026-01-01", "category": "food", "amount": "12.50"},
        {"date": "2026-01-02", "category": "tools", "amount": "3"},
    ]
'''

_REPORT_TEST = '''from src.report import monthly_report


def test_monthly_report(tmp_path):
    path = tmp_path / "in.csv"
    path.write_text('date,category,amount\\n2026-01-30,food,12.50\\n2026-02-01,tools,"1,000.00"\\n'
                    "2026-01-02,Food,0.50\\n2026-01-03,tools,-1\\n")
    assert monthly_report(path) == (
        "2026-01  food      13.00\\n"
        "2026-01  tools     -1.00\\n"
        "2026-02  tools  1,000.00"
    )
'''

# The tests pass, and they are the ones the case came with (a result that changed them does not pass).
_CHECK = "git diff --quiet $(git rev-list --max-parents=0 HEAD) -- tests && python -m pytest -q tests"

CASES: dict[str, list[dict]] = {
    "barracks": [
        {
            "id": "slugify",
            "level": "simple",
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
            "level": "simple",
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
        {
            "id": "rate-limiter",
            "level": "medium",
            "title": "A token bucket for outgoing calls",
            "task": "Write `TokenBucket(rate, capacity, clock=time.monotonic)` in `src/limiter.py`. It starts full "
                    "and refills `rate` tokens a second, never past `capacity`. `take(n=1)` takes n tokens when "
                    "there are enough and says True, else takes nothing and says False. `available()` is how many "
                    "there are now, `wait_time(n=1)` how many seconds until n are there (0 when they already are). "
                    "A rate or capacity of 0 or less, a negative n, or n above the capacity raise ValueError. "
                    "`tests/test_limiter.py` says what is wanted; make it pass without changing it.",
            "files": {"src/__init__.py": "", "src/limiter.py": _LIMITER_PY,
                      "tests/test_limiter.py": _LIMITER_TEST, "README.md": "# Limiter\n"},
            "check": _CHECK,
            "expect": "One ork's job that needs thought (an injected clock, floats compared with care), then "
                      "the steward's review; the tests unchanged.",
        },
        {
            "id": "ledger",
            "level": "parallel",
            "title": "A monthly ledger report from a CSV",
            "task": "Build a small ledger in `src/`, one module per part:\n\n"
                    "1. `src/money.py`: `format_money(cents)` gives `12,345.67` (thousands with commas, a minus "
                    "in front) and `parse_money(text)` gives cents; anything else raises ValueError.\n"
                    "2. `src/dates.py`: `iso_week(\"2026-01-01\")` gives `2026-W01` and `month_of(date)` gives "
                    "`2026-01`; a date that is not ISO raises ValueError.\n"
                    "3. `src/csvin.py`: `read_rows(path)` gives a list of dicts by the header row (a quoted value "
                    "may hold commas), blank lines skipped, values stripped, the category lower case.\n"
                    "4. `src/report.py`: `monthly_report(path)` uses the three above: the total per month and "
                    "category, sorted by both, one line each with two spaces between the columns, the categories "
                    "padded to the longest and the amounts right-aligned.\n\n"
                    "Parts 1–3 do not depend on each other; part 4 needs them all. The tests in `tests/` say "
                    "what is wanted; make them pass without changing them.",
            "files": {"src/__init__.py": "", "tests/test_money.py": _MONEY_TEST, "tests/test_dates.py": _DATES_TEST,
                      "tests/test_csvin.py": _CSVIN_TEST, "tests/test_report.py": _REPORT_TEST,
                      "README.md": "# Ledger\n"},
            "check": _CHECK,
            "expect": "Three independent parts in parallel, then the report that waits for them all; the tests "
                      "unchanged.",
        },
        *bench_sets.CASES,
    ],
}
