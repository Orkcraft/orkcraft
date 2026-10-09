"""🏰 Town Hall (T1105 stage 4): the audit's rules, the hall on every canvas, its tabs."""
from __future__ import annotations

from pathlib import Path


from orkcraft import scroll as ts
from orkcraft.realm import audit
from orkcraft.realm.buildings import TOWN_HALL

SIZE = (200, 46)

MAIL = {"id": "inbox", "title": "Inbox", "icon": "📬", "orc": {"name": "Courier"}, "type": "mail",
        "config": {"host": "imap.example.com", "user_env": "MAIL_USER", "password_env": "hunter2-plain"}}


# -- the Town Hall's worker and the Warchief (docs/design/building-views.md §3) -------------------

def test_an_old_scroll_s_chieftain_is_the_warchief_and_keeps_its_id():
    """The hall's ork was the Chieftain: a scroll that has one still loads, the ork renamed, its id
    (its sessions, its orders) kept."""
    from orkcraft.realm import lexicon
    from orkcraft.realm.buildings import presets, registry

    old = {k: dict(v) for k, v in presets(registry()).items()}
    old[TOWN_HALL] = {**old[TOWN_HALL], "orc": "Chieftain"}
    old[TOWN_HALL].pop("was")
    scroll = ts.default_scroll(old)
    assert scroll.building(TOWN_HALL).garrison.steward.name == "Chieftain"
    scroll = ts.TownScroll.from_dict(scroll.to_dict())                 # as it comes back from the file
    ts.ensure_presets(scroll, presets(registry()))
    lead = scroll.building(TOWN_HALL).garrison.steward
    assert (lead.id, lead.name) == ("chieftain", "Warchief") and ts.validate(scroll.to_dict()) == []
    fresh = ts.default_scroll(presets(registry())).building(TOWN_HALL).garrison.steward
    assert (fresh.id, fresh.name) == ("warchief", "Warchief")
    assert lexicon.term("orc.town_hall") == "Warchief"
    assert lexicon.words("Ask the Warchief") == "Ask the Warchief"


def test_custom_leaves_the_catalog_and_an_old_one_still_loads():
    from orkcraft.core.workers.town_hall import buildable
    from orkcraft.realm import catalog

    assert "custom" in catalog.RETIRED_TYPES and "custom" not in {t.id for t in buildable()}
    assert "forest" in catalog.RETIRED_TYPES and "forest" not in {t.id for t in buildable()}
    assert catalog.type_of({"type": "custom"}).id == "custom" and catalog.validate({"id": "x", "title": "X", "type": "custom"}) == []
    assert [a.id for a in catalog.TYPES[TOWN_HALL].actions] == ["hall.build", "hall.audit"]


def _answered(w, messages: int) -> None:
    import time
    for _ in range(300):
        if len(w.chat) >= messages and not w.thinking:
            return
        time.sleep(0.01)
    raise AssertionError("the Warchief never answered")


def test_the_hall_is_its_worker_s_and_the_warchief_answers(fake_repo: Path, monkeypatch):
    from orkcraft.core import runners
    from orkcraft.core.town import Town

    asked = []
    monkeypatch.setattr(runners, "WARCHIEF_RUNNER",
                        lambda prompt: asked.append(prompt) or ("A board keeps them.\nBUILD: fields", 0.01))
    town = Town(fake_repo, auto_commit=False)
    w = town.worker(TOWN_HALL)
    assert w is not None and w.TYPE == "town_hall" and w.warchief == "Warchief"
    h = w.hall()
    assert h["audit"] is None and [a["name"] for a in h["agents"]][:3] == ["Warder", "Pathfinder", "Treasurer"]
    assert w.ask("   ") and not w.thinking                              # nothing asked: said why
    assert w.ask("Where do my bugs go?") == ""
    _answered(w, 2)
    assert "Where do my bugs go?" in asked[0] and "fields — Task Fields" in asked[0] and "town_hall" in asked[0]
    assert 'DO: <one JSON object>' in asked[0]                         # he delegates, he does not build
    you, chief = w.chat[-2:]
    assert you == {**you, "who": "you", "text": "Where do my bugs go?"}
    assert chief["who"] == "warchief" and chief["text"] == "A board keeps them."
    assert chief["card"]["kind"] == "build" and chief["card"]["type"] == "fields"      # an older BUILD line still reads
    assert w.ask("And then?") == ""
    _answered(w, 4)
    assert "The conversation so far" in asked[1] and "A board keeps them." in asked[1]
    again = Town(fake_repo, auto_commit=False).worker(TOWN_HALL)
    assert [m["text"] for m in again.chat] == [m["text"] for m in w.chat]       # the chat is kept
    w.forget()
    assert w.chat == [] and Town(fake_repo, auto_commit=False).worker(TOWN_HALL).chat == []
    report = w.audit()
    assert audit.load(fake_repo).summary() == report.summary() and w.hall()["audit"]["ts"] == report.ts


def test_the_warchief_of_the_sandbox_answers_from_the_catalog(fake_repo: Path):
    from orkcraft.core.town import Town

    town = Town(fake_repo, auto_commit=False)
    town.demo = True
    w = town.worker(TOWN_HALL)
    assert w.ask("I want a board for tasks and notes") == ""
    assert not w.thinking and w.chat[-1]["card"]["type"] == "fields" and "demo" in w.chat[-1]["text"]
    w.read_limits()
    assert w.lowest() == ["claude 62% left", "agy 40% left", "codex 70% left"]
