"""📯 The Horn in the core and in the GUI: the worker without a face, its card, detail and acts."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.core.workers.horn import HornWorker
from orkcraft.gui import views
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, masonry
from orkcraft.realm.pipes import Payload


def _horn(repo: Path, **config) -> None:
    for s in ({"id": "gate_pit", "title": "The Pit", "icon": "🕳️", "orc": {"name": "Scavenger"}, "type": "pit"},
              {"id": "horn", "title": "The Horn", "icon": "📯", "orc": {"name": "Hornblower"}, "type": "horn",
               "config": config}):
        assert masonry.save_spec(repo, s) == []


def test_the_horn_worker_sounds_through_its_face_or_the_page(fake_repo, monkeypatch):
    _horn(fake_repo, sounds=["pit.link: alarm"], cooldown=0)
    town = Town(fake_repo)
    ts.subscribe(town.scroll, "horn", "gate_pit", "pit.link")
    ts.subscribe(town.scroll, "horn", "gate_pit", "pit.text")
    seen: list = []
    town.bus.subscribe(bus.WORKER, seen.append)
    w = town.worker("horn")
    assert isinstance(w, HornWorker) and w.rows() == [("gate_pit", "pit.link"), ("gate_pit", "pit.text"), ("", "*")]
    town.deliver("horn", Payload("text", "https://x", "gate_pit", "pit.link", "a link"))
    assert (w.plays, w.played) == (1, "alarm") and w.calls[0].played == "page" and w.calls[0].heard   # the page plays it
    played: list = []
    w.player = lambda path, sound: played.append((sound, path.name)) or "player"                   # a face that plays
    assert w.cycle("gate_pit", "pit.text") == "chime" and played == [("chime", "chime.wav")]
    assert w.config["sounds"] == ["pit.link: alarm", "pit.text: chime"] and w.plays == 1
    assert w.mute() and w.status() == "MUTED" and w.hut_lines([8]) == ["🔇 muted"]
    w.receive(Payload("text", "x", "gate_pit", "pit.link", "muted"), "muted", "")
    assert w.calls[0].played == "muted" and len(played) == 1 and not w.mute()
    assert seen


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_the_horn_in_the_gui_card_detail_and_acts(fake_repo):
    _horn(fake_repo, sounds=["pit.link: alarm"], cooldown=0)
    (fake_repo / "sounds").mkdir()
    (fake_repo / "sounds" / "ping.wav").write_bytes(b"RIFF....WAVE")
    host = _host(fake_repo)
    ts.subscribe(host.town.scroll, "horn", "gate_pit", "pit.link")
    w = host.town.worker("horn")
    snap = host.snapshot()
    hut = next(b for b in snap["buildings"] if b["id"] == "horn")
    assert hut["page"] and hut["card"] == {"muted": False, "plays": 0, "played": ""}

    act = lambda name, **args: host.command("act", {"id": "horn", "act": name, "args": args})
    assert act("cycle", source="gate_pit", event="pit.link") == "drum" and w.plays == 1 and w.played == "drum"
    d = host.detail("horn")
    assert [p["id"] for p in d["ui"]["panes"]] == ["settings", "table", "log"]
    rows = d["data"]["rows"]
    assert [(r["label"], r["from"], r["sound"]) for r in rows] == [("link pasted", "The Pit", "drum"),
                                                                   ("everything else", "", "horn")]
    assert act("set", event="*", sound="sounds/ping.wav") and host.detail("horn")["data"]["rows"][-1]["file"]
    url = act("audio", sound="sounds/ping.wav")["url"]
    assert url.startswith("data:audio/wav;base64,") and base64.b64decode(url.split(",", 1)[1]) == b"RIFF....WAVE"
    assert act("audio", sound="horn")["url"].startswith("data:audio/wav") and act("audio", sound="bell")["url"] == ""
    for bad in ({"sound": "/etc/passwd.wav"}, {"sound": "kazoo"}):
        with pytest.raises(CommandError):
            act("audio", **bad)
    with pytest.raises(CommandError):
        act("set", event="*", sound="missing.mp3")
    assert act("settings", quiet="22:00-08:00", cooldown=30, default="ding")
    assert w.config["quiet"] == "22:00-08:00" and w.cooldown == 30 and w.default == "ding"
    for bad in ({"quiet": "late"}, {"cooldown": 9000}, {"default": "kazoo"}):
        with pytest.raises(CommandError):
            act("settings", **bad)
    assert act("mute") and next(b for b in host.snapshot()["buildings"] if b["id"] == "horn")["card"]["muted"]
    host.town.deliver("horn", Payload("text", "x", "gate_pit", "pit.link", "while muted"))
    call = host.detail("horn")["data"]["calls"][0]
    assert not call["heard"] and call["why"] == "muted" and call["title"] == "while muted"
    assert act("test", event="*") == "page" and w.played == "sounds/ping.wav"


def test_every_horn_act_is_a_view_act():
    assert set(views.of("horn").ACTS) == {"cycle", "set", "test", "mute", "settings", "audio"}
