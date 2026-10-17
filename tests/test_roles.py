"""The agents' roles and the task types (spec 34 §3): the files, the two built-ins, dropping a role, the type → role table."""
from __future__ import annotations

import pytest

from orkcraft.realm import roles


def test_the_two_built_in_roles_exist_by_themselves_and_can_be_edited_not_dropped(tmp_path):
    got = roles.roles(tmp_path)
    assert [r["slug"] for r in got] == ["taskmaster", "grunt"] and all(r["builtin"] for r in got)
    assert got[0]["name"] == "Taskmaster" and got[0]["model"] == "elder" and got[1]["name"] == "Grunt"
    roles.save(tmp_path, "Grunt", "warrior", 3, "Be quick.", "grunt")
    grunt = roles.role(tmp_path, "grunt")
    assert (grunt["model"], grunt["max_parallel"], grunt["instruction"]) == ("warrior", 3, "Be quick.")
    for slug in roles.BUILTIN:
        with pytest.raises(ValueError, match="edited, not deleted"):
            roles.drop(tmp_path, slug)


def test_a_role_is_a_small_file_the_person_can_read(tmp_path):
    slug = roles.save(tmp_path, "Docs scribe", "laborer", 2, "Write plainly.\n\n# not a title")
    text = (tmp_path / "roles" / f"{slug}.md").read_text()
    assert text.startswith("---\nname: Docs scribe\nmodel: laborer\nmax_parallel: 2\n---\n") and "Write plainly." in text
    r = roles.role(tmp_path, slug)
    assert r["name"] == "Docs scribe" and r["instruction"] == "Write plainly.\n\n# not a title" and not r["builtin"]
    assert [x["slug"] for x in roles.roles(tmp_path)] == ["taskmaster", "grunt", slug]
    edited = roles.save(tmp_path, "Scribe", "warrior", 1, "", slug)
    assert edited == slug and roles.role(tmp_path, slug)["name"] == "Scribe"


def test_a_role_is_checked(tmp_path):
    for bad in (dict(name="  ", model="warrior", n=1), dict(name="X", model="", n=1), dict(name="X", model="warrior", n=0),
                dict(name="X", model="warrior", n=9), dict(name="X", model="warrior", n="many")):
        with pytest.raises(ValueError):
            roles.save(tmp_path, bad["name"], bad["model"], bad["n"])
    roles.save(tmp_path, "One", "warrior", 1)
    with pytest.raises(ValueError, match="already"):
        roles.save(tmp_path, "one", "warrior", 1)
    assert roles.save(tmp_path, "Taskmaster 2", "warrior", 1) != "taskmaster"


def test_each_task_type_has_a_role_grunt_by_default_and_a_dropped_role_sends_them_back(tmp_path):
    assert roles.TASK_KINDS == ("code", "tests", "docs", "text", "research")
    assert set(roles.kinds(tmp_path).values()) == {"grunt"}
    slug = roles.save(tmp_path, "Writer", "laborer", 2, "Plain words.")
    roles.set_kind(tmp_path, "docs", slug)
    roles.set_kind(tmp_path, "text", slug)
    assert roles.role_for(tmp_path, "docs")["slug"] == slug and roles.role_for(tmp_path, "code")["slug"] == "grunt"
    assert roles.role_for(tmp_path, "")["slug"] == "grunt" and roles.role_for(tmp_path, "nonsense")["slug"] == "grunt"
    assert sorted(roles.drop(tmp_path, slug)) == ["docs", "text"]
    assert roles.role(tmp_path, slug) is None and roles.role_for(tmp_path, "docs")["slug"] == "grunt"
    with pytest.raises(ValueError, match="No task type"):
        roles.set_kind(tmp_path, "poetry", "grunt")
    with pytest.raises(ValueError, match="No agent"):
        roles.set_kind(tmp_path, "docs", "ghost")
    with pytest.raises(ValueError, match="does not do tasks"):
        roles.set_kind(tmp_path, "docs", "taskmaster")


def test_the_models_are_the_tiers_and_the_claude_harness_s(tmp_path):
    ids = [m["id"] for m in roles.models()]
    assert ids[:4] == ["", "elder", "warrior", "laborer"] and {"opus", "sonnet", "haiku"} <= set(ids)
