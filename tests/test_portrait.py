"""The portrait's menu (docs/design/portrait.md): the look and Do not disturb, per machine. While Do not
disturb holds the Horn keeps quiet, only an error toast shows, every push waits but the spend over its
limit; when it ends one line says everything that gathered."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import disturb, settings
from orkcraft import scroll as ts
from orkcraft.gui import mobile, notify
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, masonry
from orkcraft.realm.pipes import Payload
from orkcraft.schedule import Span

NOON = dt.datetime(2026, 10, 8, 12, 0)


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_do_not_disturb_holds_for_an_hour_until_morning_or_until_turned_off():
    m = settings.MachineSettings()
    assert not disturb.holds(m, NOON) and disturb.choice(m, NOON) == "off" and disturb.label(m, NOON) == ""
    disturb.choose(m, "1h", NOON)
    assert m.dnd_until == "2026-10-08T13:00" and disturb.choice(m, NOON) == "1h" and disturb.label(m, NOON) == "Until 13:00"
    assert not disturb.ended(m, NOON) and disturb.ended(m, NOON + dt.timedelta(hours=1)) and m.dnd_until == ""
    disturb.choose(m, "morning", NOON)                          # no quiet hours: the next 9:00
    assert m.dnd_until == "2026-10-09T09:00" and disturb.choice(m, NOON) == "morning"
    m.quiet = Span.parse("23:00", "07:30")                      # …else where the quiet hours end
    disturb.choose(m, "morning", NOON)
    assert m.dnd_until == "2026-10-09T07:30"
    disturb.choose(m, "on", NOON)
    assert disturb.holds(m, NOON + dt.timedelta(days=30)) and disturb.label(m, NOON) == "On"
    assert not disturb.ended(m, NOON + dt.timedelta(days=30))
    disturb.choose(m, "off", NOON)
    assert not disturb.holds(m, NOON)


def test_the_look_and_do_not_disturb_are_kept_per_machine(tmp_path):
    file = tmp_path / "settings.json"
    m = settings.MachineSettings(look="office", dnd_until="on")
    settings.save(m, file)
    back = settings.load(file)
    assert (back.look, back.dnd_until) == ("office", "on")
    assert settings.MachineSettings.from_dict({"look": "neon", "dnd_until": "soon"}).look == "camp"
    assert settings.MachineSettings.from_dict({"dnd_until": "soon"}).dnd_until == ""


def test_while_it_holds_toasts_wait_but_errors_and_it_ends_with_what_gathered(fake_repo):
    host = _host(fake_repo)
    shown: list[dict] = []
    host.on_toast = shown.append
    snap = host.command("you.dnd", {"dnd": "on"})
    assert snap["dnd"]["on"] and snap["dnd"]["choice"] == "on" and host.town.hushed()
    host.town.toast("Saved", title="Wiki")
    host.town.toast("boom", title="Forge", severity="error")
    assert [t["title"] for t in shown] == ["Forge"]               # only the error shows
    host.command("you.dnd", {"dnd": "off"})
    said = host.snapshot()["portrait"]["summary"]
    assert said["text"] == "While you were away: 1 error, 1 message held."
    host.command("you.seen")
    assert host.snapshot()["portrait"]["summary"] is None
    host.town.toast("Saved again", title="Wiki")
    assert shown[-1]["title"] == "Wiki"
    with pytest.raises(CommandError):
        host.command("you.dnd", {"dnd": "forever"})


def test_a_timed_one_ends_by_the_clock(fake_repo):
    host = _host(fake_repo)
    host.command("you.dnd", {"dnd": "1h"})
    host.town.machine.dnd_until = "2000-01-01T00:00"            # an hour that passed
    host.tick()
    assert not host.town.hushed() and settings.load().dnd_until == ""
    assert host.snapshot()["portrait"]["summary"]["text"] == "While you were away: nothing came."


def test_the_horn_keeps_its_sound_and_says_why(fake_repo):
    for s in ({"id": "gate_pit", "title": "The Pit", "icon": "🕳️", "orc": {"name": "Scavenger"}, "type": "pit"},
              {"id": "horn", "title": "The Horn", "icon": "📯", "orc": {"name": "Hornblower"}, "type": "horn",
               "config": {"sounds": ["pit.link: alarm"], "cooldown": 0}}):
        assert masonry.save_spec(fake_repo, s) == []
    host = _host(fake_repo)
    ts.subscribe(host.town.scroll, "horn", "gate_pit", "pit.link")
    w = host.town.worker("horn")
    host.command("you.dnd", {"dnd": "on"})
    host.town.deliver("horn", Payload("text", "https://x", "gate_pit", "pit.link", "a link"))
    assert w.plays == 0 and w.calls[0].played == "dnd" and not w.calls[0].heard
    host.command("you.dnd", {"dnd": "off"})
    summary = host.snapshot()["portrait"]["summary"]
    assert "1 sound kept" in summary["text"] and summary["open"] == "horn" and summary["building"] == "horn"
    host.town.deliver("horn", Payload("text", "https://y", "gate_pit", "pit.link", "another"))
    assert w.plays == 1


class _Phones:
    def __init__(self) -> None:
        self.phones = {"p": object()}
        self.sent: list[dict] = []
        self.on_push = None

    def broadcast(self, msg: dict) -> None:
        self.sent.append(msg)


def test_pushes_wait_but_the_spend_over_its_limit(fake_repo):
    host = _host(fake_repo)
    phones = _Phones()
    n = notify.Notifier(host, phones)
    before = {"alerts": [], "hud": {"gold_level": "ok"}}
    n.after(before)
    host.command("you.dnd", {"dnd": "on"})
    n.after({"alerts": [{"id": "a1", "title": "Proceed?", "who": "Worker"}], "hud": {"gold_level": "over", "gold": "$9"},
             "resources": {"gold": "Spend"}})
    lines = [x["line"] for m in phones.sent for x in m["news"]]
    assert lines == ["Spend is over its limit: $9"]               # the question waits, the budget does not
    host.command("you.dnd", {"dnd": "off"})
    assert phones.sent[-1]["news"][0]["kind"] == "dnd" and "1 push held" in phones.sent[-1]["news"][0]["line"]


def test_the_phone_reads_and_sets_the_portrait(fake_repo):
    host = _host(fake_repo)
    assert mobile.allowed(host, "you.dnd") and mobile.allowed(host, "you.look")
    host.command("you.look", {"look": "office"})
    small = mobile.compact(host.snapshot())
    assert small["look"] == "office" and small["portrait"]["mono"] and small["portrait"]["dnd"]["choice"] == "off"
