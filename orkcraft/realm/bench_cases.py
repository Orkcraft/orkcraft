"""🧪 The Test bench's shipped cases, per building type (docs/design/test-bench.md §3.1). Data only.

A code case carries its whole project (`files`) and a check that says in code whether the result is right. A case
of a building whose work is not code carries its `inputs` and what each of them should come to (`expect…`), read
by its kit (realm/bench_kits.py). A town adds its own in `.orkcraft/bench/<type>/*.json`.
"""
from __future__ import annotations

from orkcraft.realm import bench_kit_cases, bench_sets

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
    # External listeners: a morning's inbox, an intent, and which messages it should keep.
    "watchtower": [
        {
            "id": "feedback-inbox",
            "level": "medium",
            "title": "Keep the users' feedback out of a morning's mail",
            "expect": "The two bug reports, the feature requests and the double charge are kept; the newsletter, "
                      "the invoice, the lunch and the CI mail are left out. The double charge is high.",
            "inputs": {
                "intent": "feedback from the users of our booking app: bugs, complaints and feature requests",
                "messages": [
                    {"sender": "lena.k@gmail.com", "title": "Booking page crashes on Sundays",
                     "body": "Hi, every time I pick a Sunday slot the page goes white and I have to start again. "
                             "Chrome on a Mac. It worked last week.",
                     "expect": {"kept": True}},
                    {"sender": "news@saas-weekly.io", "title": "SaaS Weekly #212: pricing pages that convert",
                     "body": "This week: 7 pricing pages, a teardown of Calendly's onboarding, and our podcast.",
                     "tags": ["List-Unsubscribe"], "expect": {"kept": False}},
                    {"sender": "omar@studio-nine.com", "title": "Could you add Google Calendar sync?",
                     "body": "We love the app. The one thing missing for our studio is two-way sync with Google "
                             "Calendar, we double-book every week because of it.",
                     "expect": {"kept": True}},
                    {"sender": "billing@hostly.net", "title": "Invoice INV-20931 for October",
                     "body": "Your invoice for October is attached. Amount due: €49.00, paid by card on file.",
                     "expect": {"kept": False}},
                    {"sender": "p.martin@outlook.com", "title": "You charged me twice!!",
                     "body": "I booked one session and my card shows two charges of $80. I want my money back today "
                             "or I'm disputing it with my bank.",
                     "expect": {"kept": True, "importance": "high"}},
                    {"sender": "sam@ourteam.dev", "title": "Lunch on Friday?",
                     "body": "Thai place or the new pizza one? Team lunch is on me this week.",
                     "expect": {"kept": False}},
                    {"sender": "noreply@github.com", "title": "[booking-app] CI failed on main",
                     "body": "Run #881 failed: 2 tests in test_slots.py.", "tags": ["github"],
                     "expect": {"kept": False}},
                    {"sender": "yuki@fitness-hub.jp", "title": "Love the reminders",
                     "body": "The SMS reminders cut our no-shows in half, thank you! Any chance of a dark mode for "
                             "the staff view? We work late.",
                     "expect": {"kept": True}},
                ],
            },
        },
        *bench_kit_cases.CASES["watchtower"],
    ],
    # Task board: long cards to name, and to-dos to plan with what the wiki knows.
    "fields": [
        {
            "id": "titles-and-plans",
            "level": "medium",
            "title": "Name long cards and plan to-dos with the wiki",
            "expect": "Short titles that say what the card is; plans of 3–7 steps that use what the wiki says "
                      "(the policy number, who to call), not generic advice.",
            "files": {
                "README.md": "# Home admin\n",
                "llm-wiki/general/pages/car-insurance.md":
                    "# Car insurance\n\nPolicy 4471-B with Northgate Insurance. It renews on 1 November. "
                    "Our agent is Ann Reyes (ann@northgate.example, +44 20 7946 0102). Last year she matched a "
                    "competitor's quote of £410 when asked. The no-claims certificate is in the Documents/Car "
                    "folder.\n",
                "llm-wiki/general/pages/kitchen.md":
                    "# Kitchen\n\nThe dishwasher is a Bosch SMS4HVI33G bought in 2023 at Currys, with a 3-year "
                    "warranty (receipt in Documents/Receipts). Leaks were fixed once under warranty in May.\n",
            },
            "inputs": {
                "titles": [
                    {"text": "Need to sort out the car insurance before it renews, last year they put the price up "
                             "and I only noticed after it went through, so this time compare quotes first",
                     "expect_words": [["insurance", "car"]]},
                    {"text": "The dishwasher is leaking again from the bottom left corner after every run, call "
                             "someone or check if the warranty still covers it",
                     "expect_words": [["dishwasher", "leak"]]},
                ],
                "plans": [
                    {"title": "Renew the car insurance", "body": "Do not let it renew at a higher price.",
                     "expect_words": [["4471", "Northgate"], ["Ann"], ["quote", "quotes", "compare"]]},
                    {"title": "Get the dishwasher fixed", "body": "It leaks from the bottom again.",
                     "expect_words": [["warranty"], ["receipt", "Currys"]]},
                ],
            },
        },
        *bench_kit_cases.CASES["fields"],
    ],
    # Calendar: two meetings tomorrow, their invitations, and briefs written by the Agent pool.
    "war_drum": [
        {
            "id": "two-briefs",
            "level": "parallel",
            "title": "Brief tomorrow's design review and client call",
            "expect": "A brief per meeting, with the sections asked for, that names who comes and carries the "
                      "invitation's agenda: the booking page and reminders; Northwind's renewal and SSO.",
            "inputs": {
                "orders": "Write a short brief for each meeting with the sections ## Agenda, ## People and "
                          "## Questions to ask. Use what the invitation says.",
                "expect_headings": ["Agenda", "People", "Questions"],
                "events": [
                    {"title": "Design review", "day": 1, "at": "10:00", "minutes": 60,
                     "attendees": ["Mia Chen", "Sam Patel"],
                     "description": "Agenda:\n- the new booking page\n- email reminders\n- payments: later or now?",
                     "expect_words": [["Mia"], ["Sam"], ["booking"], ["reminder"]]},
                    {"title": "Client call: Northwind", "day": 1, "at": "14:00", "minutes": 30,
                     "attendees": ["Dana Holt"],
                     "description": "Their renewal is in December and at risk. They asked twice about SSO and "
                                    "an audit log.",
                     "expect_words": [["Northwind"], ["Dana"], ["SSO"], ["renewal", "renew"]]},
                ],
            },
        },
        *bench_kit_cases.CASES["war_drum"],
    ],
    # Research: questions whose answers are settled facts on the open web, so a run today and one next month agree.
    "mine": [
        {
            "id": "eu-ai-act-dates",
            "title": "The EU AI Act's dates",
            "expect": "The three dates, each with a source, from more than one site (the Official Journal, the "
                      "Commission, a law firm's summary).",
            "inputs": {
                "question": "When did the EU AI Act (Regulation (EU) 2024/1689) enter into force, and from when do its "
                            "bans on prohibited AI practices and its obligations for general-purpose AI models apply?",
                "rounds": 1,
                "expect_facts": [["1 August 2024", "August 1, 2024", "2024-08-01", "1st August 2024"],
                                 ["2 February 2025", "February 2, 2025", "2025-02-02", "2nd February 2025"],
                                 ["2 August 2025", "August 2, 2025", "2025-08-02", "2nd August 2025"]],
                "expect_sites": 2,
            },
        },
        {
            "id": "http3",
            "title": "HTTP/3: its RFC and its transport",
            "expect": "RFC 9114 of June 2022, over QUIC, which RFC 9000 defines; sources on more than one site.",
            "inputs": {
                "question": "Which RFC defines HTTP/3 and when was it published? Which transport protocol does HTTP/3 "
                            "run over, and which RFC defines that protocol?",
                "rounds": 1,
                "expect_facts": [["RFC 9114", "RFC9114"], ["June 2022", "2022-06"], ["QUIC"], ["RFC 9000", "RFC9000"]],
                "expect_sites": 2,
            },
        },
    ],
    # Review board: a design with flaws planted in it, and a request to send down the right exit.
    "council": [
        {
            "id": "planted-flaws",
            "title": "A login design with three planted flaws",
            "expect": "Sent back for rework, naming the weak password hashing, reset links that never expire and a "
                      "login with no limit on tries.",
            "inputs": {
                "title": "Login and password reset for the booking app",
                "roles": ["Architect", "Security reviewer"],
                "expect_verdict": "rework",
                "expect_flaws": [["MD5", "bcrypt", "argon2", "scrypt"],
                                 ["expire", "expiry", "expiration", "never expire", "lifetime", "TTL"],
                                 ["rate limit", "rate-limit", "rate limiting", "brute", "lockout", "throttl", "attempts"]],
                "document": """# Login and password reset

## Goal
Customers log in to manage their bookings; staff log in to the studio view.

## Design
- Accounts live in the `users` table: email, name, and the password stored as an MD5 hash of it.
- Login: `POST /login` with email and password; on success we set a session cookie for 30 days.
- A wrong password returns "wrong password"; an unknown email returns "no such account".
- Password reset: `POST /reset` emails a link `https://book.example/reset?token=<token>`. The token is the
  user's id and a random number; it stays valid until the password is changed.
- Staff accounts work the same way as customers'.
- The database is backed up every night to a folder on the same server.

## Rollout
Ship to all studios next Tuesday; no feature flag, the old login page is removed the same day.
""",
            },
        },
        {
            "id": "route-a-request",
            "title": "Send a customer's request down the right exit",
            "expect": "A bug report goes to Development, not to a meeting or a reply.",
            "inputs": {
                "title": "Export to CSV fails since yesterday",
                "exits": ["Development: a bug to fix or a feature to build in the product",
                          "Meeting: something only a call or a meeting can settle",
                          "Reply: a question that a written answer settles"],
                "expect_route": "development",
                "document": """From: Priya Raman <priya@harbor-yoga.example>
Subject: Export to CSV fails since yesterday

Hi,

Since yesterday's update the "Export to CSV" button on the Bookings page gives an error page ("500 Internal
Server Error") for every account in our studio. It worked on Monday. We need the export for our accountant by
Friday. Steps: Bookings → filter "This month" → Export to CSV.

Thanks,
Priya
""",
            },
        },
    ],
    # A chain of buildings the Test bench is laid across (realm/bench_kit_cases.py `CHAIN`).
    "chain": list(bench_kit_cases.CASES["chain"]),
}
