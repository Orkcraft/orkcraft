"""📦 What a cart is before it is opened (realm/content.py): read off where a draft goes out, a file's
name, the files on the cart's branch, or the text."""
from __future__ import annotations

import pytest

from orkcraft.realm import content, pipes


@pytest.mark.parametrize("place, kind", [
    ("Slack #release", content.MESSAGE), ("email to team@example.com", content.MESSAGE),
    ("Telegram, канал релизов", content.MESSAGE), ("DM to Anna", content.MESSAGE),
    ("Jira, project APP, a new Bug", content.TICKET), ("GitHub issue", content.TICKET),
    ("Linear, team WEB", content.TICKET),
    ("Confluence, space ENG, page Release", content.DOC), ("Notion project page", content.DOC),
    ("Google Docs", content.DOC), ("GitHub PR", content.CODE),
    ("somewhere", content.TEXT), ("Dmitry", content.TEXT),
])
def test_where_a_draft_goes_out_says_what_it_is(place, kind):
    assert content.of_place(place) == kind


def test_a_draft_shows_what_goes_out_without_the_ork_s_report():
    c = content.of(pipes.TEXT, "Done: wrote it.\n\nPUBLISH: Slack #release\n\nShipping **v2** today\n\nThanks")
    assert (c.type, c.where, c.body) == (content.MESSAGE, "Slack #release", "Shipping **v2** today\n\nThanks")
    assert c.lines == ["Shipping v2 today", "Thanks"]


@pytest.mark.parametrize("path, kind", [("art/logo.png", content.IMAGE), ("src/app.py", content.CODE),
                                        ("docs/notes.md", content.DOC), ("out/rows.csv", content.DATA),
                                        ("LICENSE", content.TEXT)])
def test_a_file_cart_is_what_its_name_says(path, kind):
    c = content.of(pipes.FILE, path)
    assert c.type == kind and c.files == 1 and c.images == ([path] if kind == content.IMAGE else [])


def test_the_files_on_its_branch_say_what_the_work_is():
    trail = (pipes.hop("camp", "grub", "agent", worktree=".", branch="feature/x", outcome="done"),)
    code = content.of(pipes.TEXT, "Report", trail, ["src/a.py", "docs/a.md", "art/a.png"])
    assert (code.type, code.where, code.files, code.images) == (content.CODE, "feature/x", 3, ["art/a.png"])
    assert content.of(pipes.TEXT, "Report", trail, ["a.png", "b.svg"]).type == content.IMAGE
    assert content.of(pipes.TEXT, "Report", trail, ["a.md", "b.rst"]).type == content.DOC


def test_a_text_is_data_a_doc_or_text():
    assert content.of(pipes.TEXT, '{"notes": "v2"}').type == content.DATA
    assert content.of(pipes.TEXT, "## Pricing\n\nMonthly €12").type == content.DOC
    assert content.of(pipes.TEXT, "lunch?").type == content.TEXT


@pytest.mark.parametrize("line, kind, where", [
    ("ticket, Jira, project APP, a new Bug", content.TICKET, "Jira, project APP, a new Bug"),
    ("message — Slack #release", content.MESSAGE, "Slack #release"),
    ("Doc: Confluence, space ENG", content.DOC, "Confluence, space ENG"),
    ("data, POST https://example.com/hooks/release", content.DATA, "POST https://example.com/hooks/release"),
    ("doc, Slack canvas", content.DOC, "Slack canvas"),                 # the ork's word over the place's
    ("Jira, project APP", content.TICKET, "Jira, project APP"),         # an older draft: the place says it
    ("documentation site", content.TEXT, "documentation site"),         # not the kind "doc"
])
def test_the_ork_names_what_it_publishes_first(line, kind, where):
    c = content.of(pipes.TEXT, f"Done.\n\nPUBLISH: {line}\n\nthe text")
    assert (c.type, c.where, c.body) == (kind, where, "the text")


def test_the_ork_is_told_every_kind_it_may_name():
    from orkcraft.realm import barracks
    kinds = [k for k, _ in barracks.PUBLISH_KINDS]
    assert set(kinds) <= set(content.TYPES)
    assert all(f"{k} (" in barracks.OUTSIDE_RULE for k in kinds) and "PUBLISH: <kind>, <where>" in barracks.OUTSIDE_RULE
