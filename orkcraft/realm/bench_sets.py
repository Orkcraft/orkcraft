"""🧪 More Test bench cases for the Barracks, in sets of three (docs/design/test-bench.md §3.1). Data only.

Each set has a `simple` case (short, its tests judge it: one ork, no steward call), a `medium` one (one ork's
job that needs thought, then the steward's review) and a `parallel` one (independent parts, then one that
needs them all: the steward plans it). `bench_cases.CASES` takes them after its own.
"""
from __future__ import annotations

# The tests pass, and they are the ones the case came with (a result that changed them does not pass).
_CHECK = "git diff --quiet $(git rev-list --max-parents=0 HEAD) -- tests && python -m pytest -q tests"
_KEEP = "make them pass without changing them."


def _case(cid: str, level: str, title: str, task: str, files: dict[str, str], expect: str) -> dict:
    return {"id": cid, "level": level, "title": title, "task": task, "check": _CHECK, "expect": expect,
            "files": {"src/__init__.py": "", "README.md": f"# {title}\n", **files}}


# -- simple ---------------------------------------------------------------------------------------------------

_ROMAN_TEST = '''import pytest

from src.numerals import to_roman


@pytest.mark.parametrize("n, text", [(1, "I"), (4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"),
                                     (90, "XC"), (400, "CD"), (1994, "MCMXCIV"), (3999, "MMMCMXCIX")])
def test_to_roman(n, text):
    assert to_roman(n) == text


@pytest.mark.parametrize("bad", [0, -1, 4000])
def test_out_of_range(bad):
    with pytest.raises(ValueError):
        to_roman(bad)
'''

_CHUNK_TEST = '''import pytest

from src.lists import chunk


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk("abcd", 4) == [["a", "b", "c", "d"]]
    assert chunk([], 3) == []


def test_any_iterable():
    assert chunk(range(3), 1) == [[0], [1], [2]]


def test_size_must_be_positive():
    with pytest.raises(ValueError):
        chunk([1], 0)
'''

_TOP_WORDS_TEST = '''from src.words import top_words


def test_top_words():
    text = "The ork and the Warchief. The ork! A warchief, an ork?"
    assert top_words(text, 2) == [("ork", 3), ("the", 3)]


def test_ties_are_alphabetical_and_n_may_exceed():
    assert top_words("b a c b a", 10) == [("a", 2), ("b", 2), ("c", 1)]


def test_apostrophes_stay_in_a_word():
    assert top_words("don't Don't stop", 1) == [("don't", 2)]
'''

# -- medium ---------------------------------------------------------------------------------------------------

_LRU_TEST = '''import pytest

from src.lru import LRUCache


def test_evicts_the_least_recently_used():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert "b" not in c and "a" in c and "c" in c and len(c) == 2


def test_put_on_a_known_key_refreshes_it():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10 and c.get("b") is None


def test_peek_does_not_refresh_and_get_has_a_default():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.peek("a") == 1
    c.put("c", 3)
    assert c.get("a", "gone") == "gone"


def test_evicted_keys_are_reported():
    seen = []
    c = LRUCache(1, on_evict=lambda k, v: seen.append((k, v)))
    c.put("a", 1)
    c.put("b", 2)
    assert seen == [("a", 1)]


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        LRUCache(0)
'''

_SEMVER_TEST = '''import pytest

from src.semver import Version, parse


def test_parse():
    v = parse("1.2.3-beta.2+build.5")
    assert (v.major, v.minor, v.patch, v.pre, v.build) == (1, 2, 3, ("beta", 2), "build.5")
    assert str(v) == "1.2.3-beta.2+build.5"


@pytest.mark.parametrize("bad", ["1.2", "01.2.3", "1.2.3-", "a.b.c", "1.2.3-beta..1", ""])
def test_bad_versions(bad):
    with pytest.raises(ValueError):
        parse(bad)


def test_precedence():
    order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
             "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.10.0", "2.0.0"]
    versions = [parse(v) for v in order]
    assert sorted(reversed(versions)) == versions


def test_build_is_ignored_in_comparisons():
    assert parse("1.0.0+a") == parse("1.0.0+b")
    assert isinstance(parse("1.0.0"), Version)


def test_bump():
    assert str(parse("1.2.3-rc.1").bump("patch")) == "1.2.4"
    assert str(parse("1.2.3").bump("minor")) == "1.3.0"
    assert str(parse("1.2.3").bump("major")) == "2.0.0"
'''

_INTERVALS_TEST = '''import pytest

from src.intervals import merge, subtract, total


def test_merge():
    assert merge([(5, 7), (1, 3), (2, 4), (7, 8), (10, 10)]) == [(1, 4), (5, 8)]
    assert merge([]) == []


def test_subtract():
    assert subtract([(0, 10)], [(2, 3), (5, 7)]) == [(0, 2), (3, 5), (7, 10)]
    assert subtract([(0, 5), (8, 12)], [(4, 9)]) == [(0, 4), (9, 12)]
    assert subtract([(1, 2)], [(0, 5)]) == []


def test_total():
    assert total([(0, 2), (1, 3), (10, 11)]) == 4


def test_a_reversed_interval_is_refused():
    with pytest.raises(ValueError):
        merge([(3, 1)])
'''

_DIG_TEST = '''import pytest

from src.dig import dig, put

DATA = {"camp": {"orks": [{"name": "Grub", "tags": ["cook"]}, {"name": "Mogka"}], "a.b": 1}}


def test_dig():
    assert dig(DATA, "camp.orks[1].name") == "Mogka"
    assert dig(DATA, "camp.orks[0].tags[0]") == "cook"
    assert dig(DATA, "camp.orks[-1].name") == "Mogka"
    assert dig(DATA, 'camp["a.b"]') == 1


def test_missing_gives_the_default():
    assert dig(DATA, "camp.orks[5].name") is None
    assert dig(DATA, "camp.nope", default=0) == 0
    assert dig(DATA, "camp.orks.name", default="x") == "x"


def test_bad_paths():
    for bad in ("camp..orks", "camp.orks[", "camp.orks[x]", ""):
        with pytest.raises(ValueError):
            dig(DATA, bad)


def test_put_makes_what_is_missing():
    d = {}
    put(d, "a.b[0].c", 3)
    assert d == {"a": {"b": [{"c": 3}]}}
'''

# -- parallel -------------------------------------------------------------------------------------------------

_GRADES_TESTS = {
    "tests/test_letters.py": '''import pytest

from src.letters import letter


@pytest.mark.parametrize("score, grade", [(100, "A"), (90, "A"), (89.9, "B"), (80, "B"), (70, "C"),
                                          (60, "D"), (59.99, "F"), (0, "F")])
def test_letter(score, grade):
    assert letter(score) == grade


def test_out_of_range():
    with pytest.raises(ValueError):
        letter(101)
''',
    "tests/test_stats.py": '''import pytest

from src.stats import mean, median


def test_mean_and_median():
    assert mean([1, 2, 3, 4]) == 2.5
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5


def test_empty():
    with pytest.raises(ValueError):
        mean([])
    with pytest.raises(ValueError):
        median([])
''',
    "tests/test_roster.py": '''import pytest

from src.roster import parse_roster


def test_parse_roster():
    text = "# the camp\\nGrub: 90, 80.5\\n\\n  Mogka :100\\n"
    assert parse_roster(text) == {"Grub": [90.0, 80.5], "Mogka": [100.0]}


def test_a_bad_line_names_its_number():
    with pytest.raises(ValueError, match="line 2"):
        parse_roster("Grub: 1\\nMogka 2")
''',
    "tests/test_gradebook.py": '''from src.gradebook import report


def test_report():
    text = "Mogka: 100, 95\\nGrub: 70, 80, 60\\nZug: 50\\n"
    assert report(text) == (
        "Grub    70.0  C\\n"
        "Mogka   97.5  A\\n"
        "Zug     50.0  F\\n"
        "median  70.0"
    )
''',
}

_ROUTE_TESTS = {
    "tests/test_geo.py": '''import pytest

from src.geo import distance_km


def test_distance():
    assert distance_km((0, 0), (0, 0)) == 0
    assert distance_km((51.5074, -0.1278), (48.8566, 2.3522)) == pytest.approx(343.5, abs=1)
    assert distance_km((0, 0), (0, 180)) == pytest.approx(20015.1, abs=1)
''',
    "tests/test_points.py": '''import pytest

from src.points import parse_point


def test_parse_point():
    assert parse_point(" 51.5, -0.12 ") == (51.5, -0.12)
    assert parse_point("-90,180") == (-90.0, 180.0)


@pytest.mark.parametrize("bad", ["91,0", "0,181", "1", "a,b", "1,2,3"])
def test_bad_points(bad):
    with pytest.raises(ValueError):
        parse_point(bad)
''',
    "tests/test_units.py": '''from src.units import human_distance


def test_human_distance():
    assert human_distance(0.8504) == "850 m"
    assert human_distance(0.9996) == "1.0 km"
    assert human_distance(12.345) == "12.3 km"
    assert human_distance(1234.5) == "1,234 km"
''',
    "tests/test_route.py": '''from src.route import route_length


def test_route_length():
    text = "# London to Paris and back\\n51.5074,-0.1278\\n48.8566,2.3522\\n\\n51.5074,-0.1278\\n"
    assert route_length(text) == "687 km over 2 legs"


def test_one_point_is_no_route():
    assert route_length("1,1") == "0 m over 0 legs"
''',
}

_TOC_TESTS = {
    "tests/test_anchors.py": '''from src.anchors import anchor, unique_anchors


def test_anchor():
    assert anchor("Hello, World!") == "hello-world"
    assert anchor("  The `orks` API  ") == "the-orks-api"
    assert anchor("Ünïcode ok") == "ünïcode-ok"


def test_unique_anchors():
    assert unique_anchors(["Setup", "Setup", "Setup"]) == ["setup", "setup-1", "setup-2"]
''',
    "tests/test_headings.py": '''from src.headings import headings


def test_headings_skip_code_fences():
    md = "# Title\\ntext\\n## Install\\n```sh\\n# not a heading\\n```\\n### From source ###\\n####### too deep\\n#nospace\\n"
    assert headings(md) == [(1, "Title"), (2, "Install"), (3, "From source")]
''',
    "tests/test_outline.py": '''from src.outline import bullets


def test_bullets_nest_by_level_from_the_shallowest():
    items = [(2, "A", "a"), (3, "B", "b"), (4, "C", "c"), (2, "D", "d")]
    assert bullets(items) == "- [A](#a)\\n  - [B](#b)\\n    - [C](#c)\\n- [D](#d)"
''',
    "tests/test_toc.py": '''from src.toc import toc


def test_toc_leaves_out_the_title():
    md = "# Guide\\n## Setup\\n### Setup\\n## Use it\\n```\\n## no\\n```\\n"
    assert toc(md) == "- [Setup](#setup)\\n  - [Setup](#setup-1)\\n- [Use it](#use-it)"
''',
}

_INVOICE_TESTS = {
    "tests/test_lines.py": '''import pytest

from src.lines import parse_line


def test_parse_line():
    assert parse_line("2 x axe @ 12.50") == ("axe", 2, 1250)
    assert parse_line("  1 x  war drum @ 99 ") == ("war drum", 1, 9900)


@pytest.mark.parametrize("bad", ["x axe @ 1", "0 x axe @ 1", "2 x @ 1", "2 x axe @ 1.234", "2 axe 1"])
def test_bad_lines(bad):
    with pytest.raises(ValueError):
        parse_line(bad)
''',
    "tests/test_discounts.py": '''import pytest

from src.discounts import apply_code


def test_codes():
    assert apply_code(10000, "") == 10000
    assert apply_code(10000, "TENOFF") == 9000
    assert apply_code(10001, "TENOFF") == 9001
    assert apply_code(500, "FIVER") == 0
    assert apply_code(10000, "fiver") == 9500


def test_unknown_code():
    with pytest.raises(KeyError):
        apply_code(100, "FREE")
''',
    "tests/test_tax.py": '''import pytest

from src.tax import tax


def test_tax_rounds_half_up():
    assert tax(1000, "EU") == 200
    assert tax(1005, "UK") == 201
    assert tax(999, "US") == 0


def test_unknown_region():
    with pytest.raises(KeyError):
        tax(1, "MARS")
''',
    "tests/test_invoice.py": '''from src.invoice import invoice


def test_invoice():
    text = "2 x axe @ 12.50\\n1 x rope @ 3.00\\n"
    assert invoice(text, "EU", "TENOFF") == (
        "axe   2  25.00\\n"
        "rope  1   3.00\\n"
        "subtotal  28.00\\n"
        "discount  -2.80\\n"
        "tax        5.04\\n"
        "total     30.24"
    )
''',
}

CASES: list[dict] = [
    _case("roman", "simple", "Roman numerals",
          "Add `to_roman(n)` to `src/numerals.py` for 1 to 3999 (subtractive forms: IV, IX, XL, …); anything "
          f"else raises ValueError. `tests/test_numerals.py` says what is wanted; {_KEEP}",
          {"src/numerals.py": '"""Numerals."""\n', "tests/test_numerals.py": _ROMAN_TEST},
          "A dozen lines, no library; the tests unchanged."),
    _case("chunk", "simple", "Split a list into chunks",
          "Add `chunk(items, size)` to `src/lists.py`: any iterable in, a list of lists of at most `size` out, the "
          f"last one shorter; a size below 1 raises ValueError. `tests/test_lists.py` says what is wanted; {_KEEP}",
          {"src/lists.py": '"""List helpers."""\n', "tests/test_lists.py": _CHUNK_TEST},
          "A few lines; the tests unchanged."),
    _case("top-words", "simple", "The most common words",
          "Add `top_words(text, n)` to `src/words.py`: the n most common words, lower case, as (word, count), "
          "ties in alphabetical order. A word is letters with apostrophes inside. `tests/test_words.py` says what "
          f"is wanted; {_KEEP}",
          {"src/words.py": '"""Word helpers."""\n', "tests/test_words.py": _TOP_WORDS_TEST},
          "A regex and a Counter; the tests unchanged."),
    _case("lru-cache", "medium", "An LRU cache",
          "Write `LRUCache(capacity, on_evict=None)` in `src/lru.py`. `put(key, value)` stores a value and makes the "
          "key the most recently used; over capacity, the least recently used goes and `on_evict(key, value)` "
          "hears of it. `get(key, default=None)` gives the value and refreshes the key; `peek(key, default=None)` "
          "gives it without refreshing. `len()` and `in` work. A capacity below 1 raises ValueError. Keep every "
          f"operation O(1). `tests/test_lru.py` says what is wanted; {_KEEP}",
          {"src/lru.py": '"""A cache."""\n', "tests/test_lru.py": _LRU_TEST},
          "One class on an OrderedDict or a dict and a linked list; the tests unchanged."),
    _case("semver", "medium", "Semantic versions",
          "Write `src/semver.py`: `parse(text)` gives a `Version` with major, minor, patch, `pre` (a tuple of its "
          "dot-separated parts, numbers as int) and `build` (the text after `+`), by the Semantic Versioning 2.0.0 "
          "rules: no leading zeros, no empty parts, ValueError on anything else. `str()` gives the text back. "
          "Versions compare by precedence: pre-releases before the release, numeric parts numerically and before "
          "text ones, a shorter pre-release first when the rest is equal, the build ignored. `bump(part)` adds one "
          f"to the major, minor or patch number, sets the lower ones to 0 and drops the pre-release and build. `tests/test_semver.py` says what is wanted; {_KEEP}",
          {"src/semver.py": '"""Versions."""\n', "tests/test_semver.py": _SEMVER_TEST},
          "A frozen dataclass with ordering by a sort key; precedence exactly as the spec; the tests unchanged."),
    _case("intervals", "medium", "Merge and subtract intervals",
          "Write `src/intervals.py` for half-open intervals `(start, end)`. `merge(intervals)` sorts them and joins "
          "those that overlap or touch, dropping empty ones. `subtract(intervals, holes)` gives what is left of the "
          "first list once every hole is cut out, merged and sorted. `total(intervals)` is the length they cover "
          "together. An interval whose end is before its start raises ValueError. `tests/test_intervals.py` says "
          f"what is wanted; {_KEEP}",
          {"src/intervals.py": '"""Intervals."""\n', "tests/test_intervals.py": _INTERVALS_TEST},
          "A sort and a sweep, no quadratic loops; the tests unchanged."),
    _case("dig", "medium", "Read and write nested data by a path",
          "Write `src/dig.py`. `dig(data, path, default=None)` follows a path like `camp.orks[1].name` into dicts "
          "and lists: a dot before a key, `[n]` for a list index (negative ones count from the end), `[\"a.b\"]` "
          "for a key with dots in it. Whatever is missing on the way (a key, an index, a list where a dict should "
          "be) gives the default; a path that does not parse (empty, `..`, an open bracket, `[x]`) raises "
          "ValueError. `put(data, path, value)` sets the value, making dicts and lists on the way. "
          f"`tests/test_dig.py` says what is wanted; {_KEEP}",
          {"src/dig.py": '"""Nested data."""\n', "tests/test_dig.py": _DIG_TEST},
          "A small tokenizer for the path, then a walk; the tests unchanged."),
    _case("gradebook", "parallel", "A gradebook report",
          "Build a gradebook in `src/`, one module per part:\n\n"
          "1. `src/letters.py`: `letter(score)` gives A (90 and up), B (80), C (70), D (60) or F, for 0–100; "
          "anything else raises ValueError.\n"
          "2. `src/stats.py`: `mean(values)` and `median(values)`; an empty list raises ValueError.\n"
          "3. `src/roster.py`: `parse_roster(text)` reads lines `Name: score, score, …` into a dict of float "
          "lists, skipping blank lines and `#` comments; a bad line raises ValueError naming its line number.\n"
          "4. `src/gradebook.py`: `report(text)` uses the three above: one line per student by name, their mean "
          "with one decimal and its letter, then `median` and the median of the means; the names padded to the "
          "longest word in the first column, two spaces between columns, the numbers right-aligned.\n\n"
          f"Parts 1–3 do not depend on each other; part 4 needs them all. The tests in `tests/` say what is wanted; "
          f"{_KEEP}",
          _GRADES_TESTS, "Three independent parts in parallel, then the report; the tests unchanged."),
    _case("route", "parallel", "The length of a route",
          "Build a route measurer in `src/`, one module per part:\n\n"
          "1. `src/geo.py`: `distance_km(a, b)` between two (lat, lon) points by the haversine formula, the earth's "
          "radius 6371.0088 km.\n"
          "2. `src/points.py`: `parse_point(text)` reads `lat,lon` into a tuple of floats; a latitude past ±90, a "
          "longitude past ±180 or anything else raises ValueError.\n"
          "3. `src/units.py`: `human_distance(km)` gives metres below 1 km (`850 m`, rounded), else km with one "
          "decimal below 100 (`12.3 km`), else whole km with thousands commas (`1,234 km`).\n"
          "4. `src/route.py`: `route_length(text)` uses the three above: the points one per line (blank lines and "
          "`#` comments skipped), the total of the legs between them, as `<distance> over <n> legs`.\n\n"
          f"Parts 1–3 do not depend on each other; part 4 needs them all. The tests in `tests/` say what is wanted; "
          f"{_KEEP}",
          _ROUTE_TESTS, "Three independent parts in parallel, then the route; the tests unchanged."),
    _case("toc", "parallel", "A table of contents for Markdown",
          "Build a table-of-contents maker in `src/`, one module per part:\n\n"
          "1. `src/anchors.py`: `anchor(text)` makes a heading's link anchor as GitHub does (lower case, inline code "
          "marks and punctuation dropped, spaces to `-`, letters of any script kept); `unique_anchors(texts)` adds "
          "`-1`, `-2`, … to repeats.\n"
          "2. `src/headings.py`: `headings(markdown)` gives (level, text) of the ATX headings `#` to `######` "
          "(a space after the marks, closing `#`s dropped), none inside ``` fences.\n"
          "3. `src/outline.py`: `bullets(items)` turns (level, text, anchor) into a Markdown list of links, two "
          "spaces of indent per level below the shallowest.\n"
          "4. `src/toc.py`: `toc(markdown)` uses the three above for every heading but the first level-1 one.\n\n"
          f"Parts 1–3 do not depend on each other; part 4 needs them all. The tests in `tests/` say what is wanted; "
          f"{_KEEP}",
          _TOC_TESTS, "Three independent parts in parallel, then the table; the tests unchanged."),
    _case("invoice", "parallel", "An invoice from order lines",
          "Build an invoice maker in `src/`, money in integer cents throughout, one module per part:\n\n"
          "1. `src/lines.py`: `parse_line(text)` reads `<qty> x <item> @ <price>` into (item, qty, cents); a qty "
          "below 1, an empty item, a price with more than two decimals or any other shape raises ValueError.\n"
          "2. `src/discounts.py`: `apply_code(cents, code)`: no code changes nothing, `TENOFF` takes 10 % off "
          "(the cents left rounded up), `FIVER` takes 5.00 off but never below 0; codes in any case; an unknown "
          "one raises KeyError.\n"
          "3. `src/tax.py`: `tax(cents, region)` at EU 20 %, UK 20 %, US 0 %, rounded half up; an unknown region "
          "raises KeyError.\n"
          "4. `src/invoice.py`: `invoice(text, region, code)` uses the three above: a line per item (name, qty, "
          "line total), then subtotal, discount, tax (on the discounted amount) and total; columns two spaces "
          "apart, names padded to the longest, amounts right-aligned with two decimals.\n\n"
          f"Parts 1–3 do not depend on each other; part 4 needs them all. The tests in `tests/` say what is wanted; "
          f"{_KEEP}",
          _INVOICE_TESTS, "Three independent parts in parallel, then the invoice; the tests unchanged."),
]
