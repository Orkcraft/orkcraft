"""The board's tracks and ideas as Wiki pages (spec 29 §2, spec 29a §2): round trips, General, order, hand edits,
the librarian's skip, the state beside the page, and the secret store."""
from __future__ import annotations

import json
import os
import stat

import pytest

from orkcraft.realm import idea_secrets, ideas, wiki


@pytest.fixture
def root(tmp_path):
    return tmp_path / "llm-wiki" / "general"


def test_general_is_made_once_and_the_wiki_is_scaffolded(root):
    (t,) = ideas.tracks(root)
    assert (t["slug"], t["title"], t["count"]) == ("general", "General", 0)
    assert (root / "WIKI.md").exists() and (root / "pages/tracks/index.md").exists()
    assert [x["slug"] for x in ideas.tracks(root)] == ["general"]
    page = (root / "pages/tracks/general.md").read_text()
    assert page.startswith("---\nowner: board\nkind: track\norder: 1\n---\n# General\n")


def test_a_dropped_idea_is_its_text_under_gist_in_the_fixed_order(root, tmp_path):
    state = tmp_path / ".orkcraft"
    slug = ideas.add_idea(root, "Dark mode for the board\nso it reads at night", state_dir=state)
    assert slug == "dark-mode-for-the-board"
    page = ideas.idea_page(root, slug)
    assert [n for n, _t in page.sections] == list(ideas.SECTIONS)
    assert page.section("Gist") == "Dark mode for the board\nso it reads at night"
    assert (page.get("owner"), page.get("kind"), page.get("track"), page.get("order")) == ("board", "idea", "general", "1")
    assert ideas.state(state, slug)["state"] == "raw"
    assert "state" not in dict(page.meta)                       # the state lives beside the page, never in it
    (i,) = ideas.ideas(root)
    assert i["thesis"] == "Dark mode for the board" and i["size"] == ""
    assert "dark-mode-for-the-board.md" in (root / "pages/ideas/index.md").read_text()
    assert ideas.add_idea(root, "Dark mode for the board") == "dark-mode-for-the-board-2"


def test_a_write_keeps_what_it_does_not_know_and_a_hand_edit_is_read_as_written(root):
    slug = ideas.add_idea(root, "Export to CSV")
    path = root / "pages/ideas" / f"{slug}.md"
    text = path.read_text().replace("kind: idea\n", "kind: idea\naliases: [csv, export]\n")
    text = text.replace("## Why\n", "## Why\nPeople ask for it **weekly**.\n")
    text += "\n## Notes of mine\nkeep me\n"
    path.write_text(text)
    assert ideas.idea_page(root, slug).section("Why") == "People ask for it **weekly**."
    ideas.set_section(root, slug, "Risks", "- big files\n## sneaky heading")
    page = ideas.idea_page(root, slug)
    assert page.get("aliases") == "[csv, export]" and page.section("Notes of mine") == "keep me"
    assert page.section("Risks") == "- big files\n### sneaky heading"       # a section never splits the page
    assert [n for n, _t in page.sections][-1] == "Notes of mine"
    with pytest.raises(ValueError):
        ideas.set_section(root, slug, "Nonsense", "x")


def test_a_missing_section_is_written_in_its_place(root):
    slug = ideas.add_idea(root, "x")
    path = root / "pages/ideas" / f"{slug}.md"
    path.write_text("---\nowner: board\nkind: idea\ntrack: general\norder: 1\n---\n# x\n\n## Gist\nx\n\n## Decisions\n- a\n")
    ideas.set_section(root, slug, "Risks", "r")
    assert [n for n, _t in ideas.idea_page(root, slug).sections] == ["Gist", "Risks", "Decisions"]


def test_order_after_a_move_and_to_another_track(root):
    a, b, c = (ideas.add_idea(root, w) for w in ("alpha", "beta", "gamma"))
    ideas.move(root, c, before=a)
    assert [i["slug"] for i in ideas.ideas(root, "general")] == [c, a, b]
    ux = ideas.add_track(root, "UX polish")
    assert ux == "ux-polish"
    ideas.move(root, a, track=ux)
    assert [i["slug"] for i in ideas.ideas(root, "general")] == [c, b]
    assert [(i["slug"], i["order"]) for i in ideas.ideas(root, ux)] == [(a, 1)]
    assert {t["slug"]: t["count"] for t in ideas.tracks(root)} == {"general": 2, ux: 1}
    with pytest.raises(ValueError):
        ideas.move(root, a, track="nowhere")


def test_a_track_is_set_and_a_deadline_is_a_date(root):
    slug = ideas.add_track(root, "Phone first")
    ideas.set_track(root, slug, about="The phone is where ideas start.", criteria=["drop in 2 taps", " "],
                    deadline="2026-11-01")
    t = next(t for t in ideas.tracks(root) if t["slug"] == slug)
    assert (t["about"], t["criteria"], t["deadline"]) == ("The phone is where ideas start.", ["drop in 2 taps"], "2026-11-01")
    with pytest.raises(ValueError):
        ideas.set_track(root, slug, deadline="soon")


def test_the_keepers_update_writes_known_sections_and_appends_decisions(root):
    slug = ideas.add_idea(root, "x")
    assert ideas.update(root, slug, {"Why": "because", "Bogus": "no", "Decisions": "no"}, ["one", "two"]) \
        == ["Why", "Decisions"]
    ideas.update(root, slug, {}, ["three"])
    page = ideas.idea_page(root, slug)
    assert page.section("Why") == "because" and page.section("Bogus") == ""
    assert [ln.split(": ", 1)[1] for ln in page.section("Decisions").splitlines()] == ["one", "two", "three"]


def test_drop_takes_the_page_and_its_state(root, tmp_path):
    state = tmp_path / ".orkcraft"
    slug = ideas.add_idea(root, "go away", state_dir=state)
    ideas.add_turn(state, slug, "you", "hello")
    ideas.drop(root, slug, state)
    assert ideas.idea_page(root, slug) is None and not (state / "ideas" / slug).exists()


def test_state_talk_and_plan_beside_the_page(tmp_path):
    state = tmp_path / ".orkcraft"
    ideas.save_state(state, "a", state="asks", runner_key="kept")
    ideas.save_state(state, "a", session="s1")
    raw = json.loads((state / "ideas/a/state.json").read_text())
    assert raw["state"] == "asks" and raw["session"] == "s1" and raw["runner_key"] == "kept"
    for n in range(35):
        ideas.add_turn(state, "a", "you", f"t{n}")
    talk = ideas.talk(state, "a")
    assert len(talk) == 30 and talk[-1]["text"] == "t34"
    ideas.save_plan(state, "a", {"idea": "a", "passed_at": None, "todos": [], "tasks": []})
    ideas.edit_plan(state, "a", lambda p: p.update(passed_at="now"))
    with pytest.raises(ValueError):
        ideas.save_plan(state, "a", {"idea": "a"})          # a passed plan is the runner's
    with pytest.raises(ValueError):
        ideas.state(state, "../x")


def test_thesis_is_the_first_line_without_markdown():
    assert ideas.thesis("\n- **Bold** [link](x.md) and `code`\nmore") == "Bold link and code"
    assert ideas.items("- a\n- b\n") == ["a", "b"] and ideas.items("one\ntwo") == ["one", "two"]


def test_the_librarian_never_rewrites_a_board_page(root):
    slug = ideas.add_idea(root, "kept by the board")
    pages = wiki.manual_pages(root)
    assert f"pages/ideas/{slug}.md" in pages and "pages/tracks/general.md" in pages
    assert wiki.is_manual("---\nowner: board\n---\n") and not wiki.is_manual("---\nowner: orc\n---\n")


def test_a_secret_goes_to_the_store_never_to_the_plan(tmp_path):
    state = tmp_path / ".orkcraft"
    assert idea_secrets.put(state, "idea", "t1", "sk-123") == "file"          # the tests keep the keychain out
    assert idea_secrets.get(state, "idea", "t1") == "sk-123"
    assert stat.S_IMODE(os.stat(state / "secrets.json").st_mode) == 0o600
    assert "secrets.json" in (state / ".gitignore").read_text()
    idea_secrets.forget(state, "idea", ["t1"])
    assert idea_secrets.get(state, "idea", "t1") is None
    with pytest.raises(ValueError):
        idea_secrets.put(state, "../x", "t1", "v")
