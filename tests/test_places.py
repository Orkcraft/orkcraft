"""📍 Places, stage 1 of docs/design/phone-places.md: a paired phone says it came to a place or left it, the
Watchtower acts on it as freely as the place allows, the cart never names the place, and the history stays on
this machine."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings, roads
from orkcraft.gui import mobile, phones, tailnet
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, places

from tests.test_phones import _https, _pair, _serve


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _report(place: str = "home", change: str = "arrived", rid: str = "", at: str = "") -> dict:
    return {"id": rid or f"r{time.time_ns()}", "place": place, "change": change, "at": at or _now()}


# -- the rules, without a town ------------------------------------------------------------------------

def test_a_place_is_a_name_and_how_freely_its_news_is_acted_on():
    got = places.parse({"places": ["Home", {"name": "office", "autonomy": "free", "shelf_h": 99, "say": " Go "},
                                   "home", {"name": "!!"}, "gym autonomy=bold shelf=3 say=Go  now"]})
    assert [p.name for p in got] == ["home", "office", "gym"]
    assert got[0].autonomy == "chains" and got[1].autonomy == "free" and got[2].autonomy == "chains"
    assert got[1].shelf_h == places.SHELF_MAX_H and got[1].say == "Go"
    assert got[0].text("arrived") == places.SAY["arrived"]
    assert got[2].shelf_h == 3 and got[2].say == "Go now" and got[2].line() == "gym shelf=3 say=Go now"
    assert places.place_of(got[1].line()) == got[1]
    assert places.keep_days({}) == 7 and places.keep_days({"places_keep_days": 9999}) == 365


def test_a_report_is_checked_before_anything_hears_it():
    now = dt.datetime(2026, 10, 8, 19, 0)
    ok = places.check({"id": "abcdef12", "place": "Home", "change": "left", "at": "2026-10-08T18:59:00"},
                      ["home"], "Ann's phone", "0123456789abcdef", now)
    assert ok == places.Report("abcdef12", "home", "left", "2026-10-08T18:59:00", "Ann's phone", "0123456789abcdef")
    bad = [({"id": "x", "place": "home", "change": "left"}, "id is"),
           ({"id": "abcdef12", "place": "gym", "change": "left"}, "No place named 'gym'"),
           ({"id": "abcdef12", "place": "home", "change": "came"}, "arrived or left"),
           ({"id": "abcdef12", "place": "home", "change": "left", "at": "soon"}, "not a time"),
           ({"id": "abcdef12", "place": "home", "change": "left", "at": "2026-10-08T20:00:00"}, "future"),
           ("home", "Not a place report")]
    for body, says in bad:
        with pytest.raises(places.PlaceError, match=says):
            places.check(body, ["home"], now=now)


def test_a_report_in_another_zone_is_read_as_local_time():
    now = dt.datetime.now()
    utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    r = places.check({"id": "abcdef12", "place": "home", "change": "left", "at": utc}, ["home"], now=now)
    assert abs((dt.datetime.fromisoformat(r.at) - now).total_seconds()) < 5


def test_the_history_lives_beside_the_machine_settings_never_in_the_project(fake_repo, tmp_path):
    f = places.history_file(fake_repo)
    assert tmp_path in f.parents and fake_repo not in f.parents
    h = places.History(f, keep=7)
    now = dt.datetime(2026, 10, 8, 12, 0)
    old = places.Report("old00001", "home", "left", "2026-09-01T08:00:00", "p", "d1")
    h.add(old, "sent", now - dt.timedelta(days=30))
    h.add(places.Report("new00001", "home", "arrived", "2026-10-08T11:59:00", "p", "d1"), "asked", now)
    assert [x.id for x in h.all()] == ["new00001"]                      # what was older than a week went
    h.add(places.Report("other001", "home", "arrived", "2026-10-08T11:59:00", "q", "d2"), "sent", now)
    assert h.seen("other001") and places.forget_device("d1", f.parent) == 1
    assert [x.id for x in h.all()] == ["other001"]
    h.clear()
    assert not f.exists()


# -- in the town -----------------------------------------------------------------------------------------

def _town(repo: Path, autonomy: str = "chains", road: str = "home-arrived"):
    checkpoint.ensure(repo)
    host = Host(repo, auto_commit=False)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    pool = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    w = host.town.worker(tower)
    assert w.save_config({"places": [f"home autonomy={autonomy} say=You may start the evening's work.", "office"]})
    if road:
        assert roads.lay(host.town, pool, tower, f"watch.place#{road}", None, quiet=True) is not None
    carts = []
    real = host.town.roads.emit
    host.town.roads.emit = lambda p: (carts.append(p), real(p))[1]
    return host, w, carts


def test_propose_only_asks_in_answers_and_the_cart_never_names_the_place(fake_repo):
    host, w, carts = _town(fake_repo)
    r = _report()
    assert host.command("place.report", {**r, "device": "Ann's phone"}) == {"outcome": "asked"}
    assert host.command("place.report", r) == {"outcome": "asked"}             # a retry is heard once
    key, title, context, options = w.orders_alert()
    assert "Ann's phone" in title and "home" in title and ("send", "Send") in options
    assert not carts
    assert w.answer_alert("send") == "sent" and w.orders_alert() is None
    [cart] = carts
    assert cart.mode == "watch.place" and cart.route == "home-arrived"
    assert "home" not in f"{cart.title}\n{cart.value}" and r["at"][11:16] not in f"{cart.title}\n{cart.value}"
    assert cart.value == "You may start the evening's work."
    assert [h.outcome for h in w.desk.history.all()] == ["sent"]
    assert not (w.state_dir / "signals.jsonl").exists()                       # never a signal, never the Lookout


def test_skip_sends_nothing(fake_repo):
    host, w, carts = _town(fake_repo)
    host.command("place.report", _report())
    assert w.answer_alert("dismiss") == "refused" and not carts


def test_apply_at_once_goes_and_a_place_no_road_takes_goes_nowhere(fake_repo):
    host, w, carts = _town(fake_repo, autonomy="free")
    assert host.command("place.report", _report())["outcome"] == "sent" and len(carts) == 1
    assert host.command("place.report", _report(change="left"))["outcome"] == "no road"
    assert host.command("place.report", _report(place="office"))["outcome"] == "no road"
    assert len(carts) == 1
    ends = {e["route"] for e in w.loose_ends()}
    assert ends == {"home-left", "office-arrived", "office-left"}           # stubs to pull a road from


def test_a_late_report_is_kept_but_is_news_no_longer(fake_repo):
    host, w, carts = _town(fake_repo, autonomy="free")
    late = (dt.datetime.now() - dt.timedelta(hours=3)).isoformat(timespec="seconds")
    assert host.command("place.report", _report(at=late))["outcome"] == "stale" and not carts


def test_apply_if_unanswered_goes_by_itself_unless_stop_all_came(fake_repo):
    host, w, carts = _town(fake_repo, autonomy="clock")
    assert host.command("place.report", _report())["outcome"] == "waiting"
    w.desk.tick(time.monotonic() + places.CLOCK_MIN * 60 + 1)
    assert len(carts) == 1 and w.orders_alert() is None
    host.command("place.report", _report())
    assert w.halt() == 1
    w.desk.tick(time.monotonic() + places.CLOCK_MIN * 60 + 1)
    assert len(carts) == 1 and w.orders_alert() is not None                 # it waits on the person now


def test_an_unknown_place_is_refused_with_what_the_phone_is_told(fake_repo):
    host, _, _ = _town(fake_repo)
    with pytest.raises(CommandError, match="No place named 'gym'"):
        host.command("place.report", _report(place="gym"))


def test_the_tower_shows_its_places_and_saves_them(fake_repo):
    host, w, _ = _town(fake_repo)
    host.command("place.report", _report())
    view = w.desk.view()
    assert view["places"][0]["roads"] == ["arrived"] and view["waiting"] == 1
    assert view["history"][0]["outcome"] == "asked"
    assert w.desk.save([{"name": "office"}], 3)                              # home gone: its question too
    assert w.config["places"] == ["office"]
    assert w.config["places_keep_days"] == 3 and w.orders_alert() is None


def test_a_phone_may_report_a_place_and_the_listener_names_the_phone(fake_repo):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    assert mobile.allowed(host, "place.report", {})
    args = mobile.guard("place.report", {"place": "home", "device": "forged"}, {"id": "0123456789abcdef", "name": "Ann"})
    assert args["device"] == "Ann" and args["device_id"] == "0123456789abcdef"


# -- over the network --------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shortcuts_reports_a_place_with_its_own_token(fake_repo):
    server, task = await _serve(fake_repo)
    try:
        host = server.host
        tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
        assert host.town.worker(tower).save_config({"places": ["home"]})
        await _pair(server)
        got = host.command("phones.recipe", {"name": "Shortcuts"})
        recipe = got["recipe"]
        assert recipe["url"] == f"{server.phones.address}/api/place" and recipe["token"]
        assert "token" not in json.dumps(got["phones"])
        auth = {"Authorization": f"Bearer {recipe['token']}"}
        status, body, _ = await asyncio.to_thread(_https, server.phones.address, "POST", "/api/place", _report(), auth)
        assert status == 200 and body == {"outcome": "no road"}, body
        status, body, _ = await asyncio.to_thread(_https, server.phones.address, "POST", "/api/place",
                                                  _report(place="gym"), auth)
        assert status == 400 and "gym" in body["error"]
        status, _, _ = await asyncio.to_thread(_https, server.phones.address, "POST", "/api/place", _report(),
                                               {"Authorization": "Bearer nope"})
        assert status == 403
        status, _, _ = await asyncio.to_thread(_https, server.phones.address, "POST", "/api/place", None, auth,
                                               raw=b"x" * 2000)
        assert status == 413
        w = host.town.worker(tower)
        assert [h.device for h in w.desk.history.all()] == ["Shortcuts"]
        host.command("phones.forget", {"id": recipe["id"]})
        assert w.desk.history.all() == []                                     # forgotten: what it said goes too
        assert "places" in host.command("mobile.hello") and host.command("mobile.hello")["places"] == ["home"]
    finally:
        server.stop()
        await task


# -- Tailscale ---------------------------------------------------------------------------------------------

def _ran(stdout: str = "", code: int = 0, then=None):
    def run(argv, **kw):
        if then:
            then(argv)
        return subprocess.CompletedProcess(argv, code, stdout, "")
    return run


def test_tailscale_is_found_when_it_runs_and_logged_in():
    status = {"BackendState": "Running", "Self": {"TailscaleIPs": ["100.64.0.7", "fd7a::7"], "DNSName": "Town.tail12.ts.net."}}
    assert tailnet.find(_ran(json.dumps(status))) == tailnet.Tail("100.64.0.7", "town.tail12.ts.net")
    assert tailnet.find(_ran(json.dumps({**status, "BackendState": "NeedsLogin"}))) is None
    assert tailnet.find(_ran("", 1)) is None


def test_tailscale_is_left_alone_when_told(monkeypatch):
    monkeypatch.setenv("ORKCRAFT_TAILSCALE", "off")
    assert tailnet.find(_ran(json.dumps({"BackendState": "Running", "Self": {"TailscaleIPs": ["100.64.0.7"]}}))) is None


def test_the_tailnet_certificate_is_asked_once_a_month(tmp_path):
    tail, asked = tailnet.Tail("100.64.0.7", "town.tail12.ts.net"), []

    def make(argv):
        asked.append(argv)
        Path(argv[argv.index("--cert-file") + 1]).write_text("c")
        Path(argv[argv.index("--key-file") + 1]).write_text("k")
    crt, key = tailnet.cert(tail, tmp_path, _ran(then=make))
    assert asked[0][-1] == "town.tail12.ts.net" and oct(key.stat().st_mode & 0o777) == "0o600"
    assert tailnet.cert(tail, tmp_path, _ran(then=make)) == (crt, key) and len(asked) == 1
    tailnet.cert(tail, tmp_path, _ran(then=make), now=time.time() + 31 * 86400)
    assert len(asked) == 2
    assert tailnet.cert(tailnet.Tail("100.64.0.7", ""), tmp_path, _ran(then=make)) is None   # no MagicDNS


@pytest.mark.asyncio
async def test_the_listener_listens_on_the_tailnet_too_and_the_qr_code_says_so(fake_repo, monkeypatch):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    listener = phones.Listener(host)
    monkeypatch.setattr(phones, "lan_ip", lambda: None)                      # no Wi-Fi: the tailnet alone
    listener.tail_find = lambda: tailnet.Tail("127.0.0.1", "")
    try:
        offer = listener.pair()
        for _ in range(200):
            if listener.tail_server is not None and not isinstance(listener.tail_server, phones._Pending):
                break
            await asyncio.sleep(0.02)
        assert listener.tail_address.startswith("https://127.0.0.1:") and not listener.tail_trusted
        assert offer["link"].startswith("orkcraft://pair?v=1&addr=https%3A%2F%2F127.0.0.1")
        status, _, fp = await asyncio.to_thread(_https, listener.tail_address, "GET", "/api/version", None,
                                                   {"Authorization": f"Bearer {offer['code']}"})
        assert status == 200 and fp == offer["fingerprint"]
    finally:
        listener.stop()
    assert not listener.listening and listener.tail_address == ""
