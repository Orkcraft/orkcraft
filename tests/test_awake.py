"""The computer kept awake while Orkline is open (gui/awake.py): each system's own way, against idle sleep
only, ended with the town, and the machine's setting in Town settings."""
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


def test_the_setting_is_on_by_default_and_kept():
    assert settings.MachineSettings().keep_awake is True
    assert settings.MachineSettings.from_dict({}).keep_awake is True
    off = settings.MachineSettings.from_dict({"keep_awake": False})
    assert off.keep_awake is False and off.to_dict()["keep_awake"] is False


def test_town_settings_turns_it_off_and_on_at_once_while_the_town_is_open(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    made, popen = _fake()
    host.awake = awake.Awake("darwin", popen, _which("caffeinate"))
    assert host.command("town.settings")["keep_awake"] is True
    r = host.command("awake.set", {"on": False})                                    # not open (a test): kept only
    assert r["keep_awake"] is False and not made
    host.awake.running = True
    r = host.command("awake.set", {"on": True})
    assert r["keep_awake"] is True and r["awake_how"] == "caffeinate" and len(made) == 1
    r = host.command("awake.set", {"on": False})
    assert r["awake_how"] == "" and made[0].terminated
