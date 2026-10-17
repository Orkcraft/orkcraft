"""What reached the branch without the person's eyes (realm/idea_merged.py, spec 29c §1, §4): merged.jsonl, Looked,
and the digest at its hours."""
from __future__ import annotations

import datetime as dt
import json

from orkcraft.realm import idea_merged, ideas


def _row(n: int, idea: str = "demo", cost: float = 0.1) -> dict:
    return {"idea": idea, "task": f"k{n}", "title": f"Task {n}", "goal": "Make it", "subject": f"Subject {n}",
            "commit": f"{n:07x}", "tests": "3 passed", "cost": cost, "estimate": [0.1, 0.3],
            "at": f"2026-10-17T09:0{n % 10}:00"}


def test_a_merged_line_is_appended_unseen_and_read_newest_first(tmp_path):
    for n in range(1, 4):
        idea_merged.add(tmp_path, {**_row(n), "seen": True, "reverted": True, "evil": "x"})
    lines = (tmp_path / "ideas" / "merged.jsonl").read_text().splitlines()
    first = json.loads(lines[0])
    assert set(first) == set(idea_merged.KEYS) and first["seen"] is False and first["reverted"] is False
    shown, more = idea_merged.unseen(tmp_path)
    assert [r["task"] for r in shown] == ["k3", "k2", "k1"] and more == 0
    (tmp_path / "ideas" / "merged.jsonl").open("a").write("not json\n")
    assert len(idea_merged.rows(tmp_path)) == 3


def test_at_most_twenty_are_shown_and_the_rest_are_counted(tmp_path):
    for n in range(1, 26):
        idea_merged.add(tmp_path, _row(n))
    shown, more = idea_merged.unseen(tmp_path)
    assert len(shown) == 20 and shown[0]["task"] == "k25" and more == 5


def test_looked_marks_one_an_ideas_or_all(tmp_path):
    for n in range(1, 4):
        idea_merged.add(tmp_path, _row(n))
    idea_merged.add(tmp_path, _row(9, idea="other"))
    assert idea_merged.mark(tmp_path, "demo", "k2", seen=True) == 1
    assert [r["task"] for r in idea_merged.unseen(tmp_path)[0]] == ["k9", "k3", "k1"]
    assert idea_merged.mark(tmp_path, "other", seen=True) == 1
    assert idea_merged.mark(tmp_path, seen=True) == 2
    assert idea_merged.unseen(tmp_path) == ([], 0)


def test_the_tests_line_and_the_tasks_share_of_the_estimate():
    assert idea_merged.tests_line("....\n14 passed in 2.1s\n") == "14 passed"
    assert idea_merged.tests_line("== 3 passed, 1 skipped in 0.4s ==") == "3 passed, 1 skipped"
    assert idea_merged.tests_line("no test files to run") == ""
    assert idea_merged.share({"usd_low": 1.0, "usd_high": 3.0}, [1.0, 3.0], 1) == [0.75, 2.25]
    assert idea_merged.share(None, [1.0], 0) == [0.0, 0.0]


def test_the_digest_goes_once_at_each_of_its_hours_and_only_with_something_unseen(tmp_path):
    hours = [9, 13, 18]
    at = lambda h, m=0: dt.datetime(2026, 10, 17, h, m)   # noqa: E731
    assert idea_merged.due(tmp_path, hours, at(9)) is None              # nothing unseen at nine
    idea_merged.add(tmp_path, _row(1, cost=0.25))
    assert idea_merged.due(tmp_path, hours, at(9, 30)) is None          # nine's digest was nothing: kept so
    assert idea_merged.due(tmp_path, hours, at(11)) is None             # not a digest hour
    ideas.save_state(tmp_path, "demo", state="done")
    idea_merged.add(tmp_path, _row(2, cost=0.5))
    d = idea_merged.due(tmp_path, hours, at(13, 2))
    assert d == {"at": "2026-10-17T13", "merged": 2, "done": 1, "spent": "$0.75"}
    idea_merged.add(tmp_path, _row(3))
    assert idea_merged.due(tmp_path, hours, at(13, 40)) == d             # frozen for the hour: said once
    idea_merged.mark(tmp_path, seen=True)
    assert idea_merged.due(tmp_path, hours, at(18)) is None
    assert idea_merged.due(tmp_path, [], at(9)) is None
