"""The computer kept awake while carts are in work and it is on power (gui/awake.py, gui/away.py): each system's
own way, against idle sleep only, ended with the town, and the machine's setting in Town settings."""
from __future__ import annotations

import subprocess

from orkcraft import settings
from orkcraft.gui import awake
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint


class _Proc:
    def __init__(self, argv, exits: bool = False) -> None:
        self.argv, self.exits, self.terminated = argv, exits, False

    def wait(self, timeout=None):
        if self.exits or self.terminated:
            return 1
        raise subprocess.TimeoutExpired(self.argv, timeout)

    def terminate(self):
        self.terminated = True


def _fake(exits: bool = False):
    made = []

    def popen(argv, **kw):
        made.append(_Proc(argv, exits))
        return made[-1]
    return made, popen


def _which(*have):
    return lambda name: f"/usr/bin/{name}" if name in have else None


def test_each_system_holds_off_idle_sleep_only_and_ends_with_this_process():
    how, argv = awake._argv("darwin", 42, _which("caffeinate"))
    assert how == "caffeinate" and argv == ["caffeinate", "-i", "-w", "42"]          # -i: idle sleep, not the display
    how, argv = awake._argv("linux", 42, _which("systemd-inhibit", "tail"))
    assert how == "systemd-inhibit" and "--what=sleep" in argv and argv[-4:] == ["tail", "--pid=42", "-f", "/dev/null"]
    assert awake._argv("linux", 42, _which("tail")) is None                          # no systemd: nothing to hold it
    assert awake._argv("freebsd", 42, _which("caffeinate", "systemd-inhibit", "tail")) is None


def test_it_holds_while_on_and_lets_go_when_stopped():
    made, popen = _fake()
    a = awake.Awake("darwin", popen, _which("caffeinate"))
    assert a.apply(True) == "caffeinate" and a.on
    assert a.apply(True) == "caffeinate" and len(made) == 1                          # once
    a.apply(False)
    assert made[0].terminated and not a.on and a.how == ""


def test_a_refused_hold_says_nothing_holds_it():
    made, popen = _fake(exits=True)                                                  # e.g. no right to inhibit sleep
    a = awake.Awake("linux", popen, _which("systemd-inhibit", "tail"))
    assert a.apply(True) == "" and not a.on
    assert awake.Awake("linux", popen, _which()).apply(True) == ""


def test_the_setting_is_while_carts_work_by_default_and_old_settings_keep_their_behaviour():
    assert settings.MachineSettings().keep_awake == "carts"
    assert settings.MachineSettings.from_dict({}).keep_awake == "carts"
    assert settings.MachineSettings.from_dict({"keep_awake": True}).keep_awake == "carts"     # an old "on"
    off = settings.MachineSettings.from_dict({"keep_awake": False})                       # an old "off"
    assert off.keep_awake == "off" and off.to_dict()["keep_awake"] == "off"
    phone = settings.MachineSettings.from_dict({"keep_awake": "phone", "awake_offered": True})
    assert phone.keep_awake == "phone" and phone.awake_offered and phone.to_dict()["keep_awake"] == "phone"
    assert settings.MachineSettings.from_dict({"keep_awake": "always"}).keep_awake == "carts"
    assert settings.MachineSettings().awake_offered is False


def test_town_settings_turns_it_off_and_on_at_once_while_the_town_is_open(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    made, popen = _fake()
    host.awake = awake.Awake("darwin", popen, _which("caffeinate"))
    host.away.power = lambda: True
    assert host.command("town.settings")["keep_awake"] == "carts" and host.command("town.settings")["awake_can"]
    r = host.command("awake.set", {"on": False})                                    # not open (a test): kept only
    assert r["keep_awake"] == "off" and not made
    host.awake.running = True
    r = host.command("awake.set", {"on": True})                                     # the old way of saying it
    assert r["keep_awake"] == "carts" and r["awake_how"] == "" and not made          # no cart in work: it may sleep
    host.away.service.busy = lambda: True                                           # a cart in work, on power
    r = host.command("awake.set", {"mode": "carts"})
    assert r["awake_how"] == "caffeinate" and len(made) == 1 and r["awake"]["why"] == "carts"
    r = host.command("awake.set", {"mode": "off"})
    assert r["awake_how"] == "" and made[0].terminated and r["awake"]["why"] == ""


def _phone_host(fake_repo, power=True):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    made, popen = _fake()
    host.awake = awake.Awake("darwin", popen, _which("caffeinate"))
    host.awake.running = True
    host.away.power = lambda: power
    host.away.platform = "darwin"
    _pair(True)
    return host, made


def _pair(on: bool) -> None:
    settings.save_phones([{"id": "0123456789abcdef", "name": "Phone", "hash": "a" * 64, "paired": "2026-10-15T09:00",
                           "seen": ""}] if on else [], 0)


def test_stay_reachable_holds_it_while_a_phone_is_paired_carts_or_not(fake_repo, isolated_layout_file):
    host, made = _phone_host(fake_repo)
    assert host.away.service.busy() is False                                        # no cart in work
    r = host.command("awake.set", {"mode": "phone"})
    assert r["keep_awake"] == "phone" and r["awake_how"] == "caffeinate" and r["awake"]["why"] == "phone"
    assert host.town.machine.keep_awake == "phone" and settings.load().keep_awake == "phone"
    _pair(False)                                                                    # forgotten: it may sleep again
    assert host.away.keep_awake() == "" and made[0].terminated and host.away.why == ""


def test_on_battery_stay_reachable_falls_back_and_holds_nothing(fake_repo, isolated_layout_file):
    host, made = _phone_host(fake_repo, power=False)
    host.away.service.busy = lambda: True                                           # even with carts in work
    r = host.command("awake.set", {"mode": "phone"})
    assert r["awake_how"] == "" and not made and r["awake"]["battery"] is True
    assert host.away.phone_line() == "Your Mac is on battery and may sleep."
    host.away.power = lambda: True
    host.away._power_at = -1e9                                                      # read the power again
    assert host.away.keep_awake() == "caffeinate" and host.away.phone_line() == ""


def test_the_offer_is_asked_once_when_a_phone_is_paired(fake_repo, isolated_layout_file):
    host, made = _phone_host(fake_repo)
    _pair(False)
    assert host.away.offer() == ""                                                  # no phone: nothing to ask
    _pair(True)
    assert host.away.offer() == "Mac"
    host.away.platform = "linux"
    assert host.away.offer() == "computer"
    assert host.command("awake.offer", {"yes": False}) == {"keep_awake": "carts"}   # Not now: asked, kept as it was
    assert host.away.offer() == "" and host.town.machine.awake_offered and not made
    host.town.machine.awake_offered = False
    assert host.command("awake.offer", {"yes": True}) == {"keep_awake": "phone"}
    assert host.away.offer() == "" and made and settings.load().awake_offered
