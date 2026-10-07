"""A building named after what was asked for it: at most four words (realm/naming.py)."""
from __future__ import annotations

import pytest

from orkcraft.realm import blueprint, builders, naming


@pytest.mark.parametrize("prompt, title", [
    ("sort my inbox into tasks", "Sort inbox into tasks"),
    ("What should I build? watch my work inbox for messages from the release team", "Watch work inbox"),
    ("Please, I need to build a calendar for releases", "Calendar for releases"),
    ("track CI failures. Ping me on Slack too", "Track CI failures"),
    ("make me a digest of new pull requests every morning at nine", "Digest new pull requests"),
])
def test_a_title_is_the_request_s_first_four_words_that_carry_it(prompt, title):
    got = naming.from_prompt(prompt)
    assert got == title and len(got.split()) <= naming.MAX_WORDS


@pytest.mark.parametrize("prompt", ["Добавь здание тасков", "add a task building", "Создай постройку для задач",
                                    "build me a new building"])
def test_a_request_for_a_building_alone_keeps_the_type_s_title(prompt):
    assert naming.from_prompt(prompt, "Task Fields") == "Task Fields"


def test_a_request_in_russian_drops_its_asking_too():
    assert naming.from_prompt("Создай здание, которое сортирует почту") == "Сортирует почту"
    assert naming.from_prompt("build me a building that sorts mail") == "Sorts mail"


def test_nothing_to_name_it_after_keeps_the_fallback():
    assert naming.from_prompt("  the  ", "Task Fields") == "Task Fields"
    assert naming.from_prompt("", "") == ""


def test_any_title_is_clipped_to_four_words():
    assert naming.clip("Pull Requests Waiting For My Review") == "Pull Requests Waiting For"
    assert naming.clip("CI Monitor") == "CI Monitor" and naming.clip("") == ""
    assert len(naming.clip("x" * 80)) == naming.MAX_CHARS


def test_the_builders_ask_for_four_words_and_keep_to_them(tmp_path, monkeypatch):
    assert "at most 4 words" in builders.MASON and "at most 4 words" in builders.FOREMAN
    assert "at most 4 words" in blueprint.BUILDER
    monkeypatch.setattr(builders.masonry, "validate_spec", lambda *a, **k: [])
    long = '{"type": "fields", "id": "my_board", "title": "A Very Long Board Of Every Task", "icon": "📋"}'
    result = builders.propose("a board for every task", tmp_path, "fields", runner=lambda p: (long, None),
                              max_attempts=1)
    assert result.spec["title"] == "A Very Long Board"
    untitled = builders.propose("track CI failures", tmp_path, "fields", max_attempts=1,
                                runner=lambda p: ('{"type": "fields", "id": "ci", "title": ""}', None))
    assert untitled.spec["title"] == "Track CI failures"            # the model gave none: the request names it
    out = blueprint.normalise({"title": "Count The Words Of Every Paste", "id": "wc"}, {"purpose": "count words"})
    assert out["title"] == "Count The Words Of"
