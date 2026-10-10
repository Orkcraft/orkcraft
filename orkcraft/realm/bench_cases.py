"""🧪 The Test bench's shipped cases, per building type (docs/design/test-bench.md §3.1). Data only.

A code case carries its whole project (`files`) and a check that says in code whether the result is right. A case
of a building whose work is not code carries its `inputs` and what each of them should come to (`expect…`), read
by its kit (realm/bench_kits.py). A town adds its own in `.orkcraft/bench/<type>/*.json`.
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
    # External listeners: a morning's inbox, an intent, and which messages it should keep.
    "watchtower": [
        {
            "id": "feedback-inbox",
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
    ],
    # Task board: long cards to name, and to-dos to plan with what the wiki knows.
    "fields": [
        {
            "id": "titles-and-plans",
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
    ],
    # Calendar: two meetings tomorrow, their invitations, and briefs written by the Agent pool.
    "war_drum": [
        {
            "id": "two-briefs",
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
}
