"""The town in a phone's browser (gui/pwa.py): the app's files from the phone listener, a browser's socket that
names its token as a subprotocol, the pairing link on the tailnet, and Tailscale's state for the desktop."""
from __future__ import annotations

import asyncio
import http.client
import json
import subprocess

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from orkcraft.gui import phone_tls, phones, pwa, tailnet
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint
from tests.test_phones import _pair, _pinned, _serve, _ws_url


def _get(address: str, path: str, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    host, port = address.removeprefix("https://").rsplit(":", 1)
    conn = http.client.HTTPSConnection(host, int(port), context=_pinned(), timeout=5)
    try:
        conn.request(method, path)
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        conn.close()


# -- the files, without a network -------------------------------------------------------------------------

def _split(raw: bytes) -> tuple[str, bytes]:
    head, _, body = raw.partition(b"\r\n\r\n")
    return head.decode("ascii"), body


def test_the_app_is_its_own_files_and_nothing_else():
    names = set(pwa.files())
    assert {"index.html", "app.js", "app.css", "manifest.webmanifest", "sw.js", "icon-192.png", "icon-512.png",
            "apple-touch-icon.png"} <= names
    head, body = _split(pwa.serve("GET", "/app/"))
    assert head.startswith("HTTP/1.1 200") and b'src="app.js"' in body
    assert "Content-Security-Policy: default-src 'self'; script-src 'self';" in head
    head, _ = _split(pwa.serve("GET", "/app/app.js"))
    assert "text/javascript" in head and "Content-Security-Policy" not in head
    assert "Service-Worker-Allowed: /app/" in _split(pwa.serve("GET", "/app/sw.js"))[0]
    for path in ("/app/../phones.py", "/app/..%2Fphones.py", "/app/nothing.js", "/app/js/app.js"):
        assert _split(pwa.serve("GET", path))[0].startswith("HTTP/1.1 404"), path
    assert _split(pwa.serve("POST", "/app/"))[0].startswith("HTTP/1.1 405")
    assert "Location: /app/" in _split(pwa.serve("GET", "/app"))[0]
    head, body = _split(pwa.serve("HEAD", "/app/app.css"))
    assert head.startswith("HTTP/1.1 200") and body == b""


def test_the_manifest_carries_a_token_only_as_a_token():
    plain = json.loads(_split(pwa.serve("GET", "/app/manifest.webmanifest"))[1])
    assert plain["start_url"] == "./" and plain["display"] == "standalone"
    token = "A" * 43
    with_k = json.loads(_split(pwa.serve("GET", f"/app/manifest.webmanifest?k={token}"))[1])
    assert with_k["start_url"] == f"./#k={token}" and with_k["name"] == plain["name"]
    for bad in ("short", "x" * 43 + '"}', "%22%7D" + "a" * 40):
        assert json.loads(_split(pwa.serve("GET", f"/app/manifest.webmanifest?k={bad}"))[1])["start_url"] == "./"


def test_a_browser_names_its_token_among_the_subprotocols():
    token = "abc_DEF-123" * 4
    assert pwa.ws_token({"sec-websocket-protocol": f"orkcraft.v1, bearer.{token}"}) == token
    assert pwa.ws_token({"sec-websocket-protocol": "orkcraft.v1"}) == ""
    assert pwa.ws_token({"sec-websocket-protocol": "bearer.no spaces"}) == ""
    assert pwa.ws_token({}) == ""
    assert pwa.select(None, ["orkcraft.v1", "bearer.x"]) == "orkcraft.v1" and pwa.select(None, []) is None
    assert pwa.link("https://town.tail1.ts.net:4443", "a/b") == "https://town.tail1.ts.net:4443/app/#pair=a%2Fb"


# -- over the listener ------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_listener_serves_the_app_and_a_browsers_socket(fake_repo):
    server, task = await _serve(fake_repo)
    try:
        _, token = await _pair(server)
        status, headers, body = await asyncio.to_thread(_get, server.phones.address, "/app/")
        assert status == 200 and b"Orkcraft" in body and "content-security-policy" in headers
        async with connect(_ws_url(server), ssl=_pinned(), subprotocols=["orkcraft.v1", f"bearer.{token}"]) as ws:
            assert ws.subprotocol == "orkcraft.v1"
            first = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert first["t"] == "state"
        with pytest.raises(InvalidStatus) as e:
            async with connect(_ws_url(server), ssl=_pinned(), subprotocols=["orkcraft.v1", "bearer." + "x" * 43]):
                pass
        assert e.value.response.status_code == 403
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_the_apps_link_is_offered_only_on_a_tailnet_with_its_certificate(fake_repo, monkeypatch, tmp_path):
    checkpoint.ensure(fake_repo)
    listener = phones.Listener(Host(fake_repo, auto_commit=False), cert_folder=tmp_path)
    monkeypatch.setattr(phones, "lan_ip", lambda: None)
    listener.tail_find = lambda: tailnet.Tail("127.0.0.1", "")
    try:
        offer = listener.pair()
        assert offer["app_link"] == "" and offer["app_qr"] is None             # no name, no certificate a browser trusts
    finally:
        listener.stop()
    listener.tail_find = lambda: tailnet.Tail("127.0.0.1", "town.tail12.ts.net")
    listener.tail_cert = lambda tail: phone_tls.ensure(tmp_path)             # stands in for `tailscale cert`
    try:
        offer = listener.pair()
        assert listener.tail_trusted
        assert offer["app_link"] == f"{listener.tail_address}/app/#pair={offer['code']}"
        assert offer["app_link"].startswith("https://town.tail12.ts.net:") and offer["app_qr"].startswith("data:image/svg")
    finally:
        listener.stop()


# -- Tailscale's state, for the desktop ---------------------------------------------------------------------

def _ran(stdout: str, code: int = 0):
    return lambda argv, **kw: subprocess.CompletedProcess(argv, code, stdout, "")


STATUS = {"BackendState": "Running",
          "Self": {"TailscaleIPs": ["100.64.0.7"], "DNSName": "town.tail12.ts.net.", "UserID": 7},
          "User": {"7": {"LoginName": "orkboss@example.com"}},
          "Peer": {"a": {"HostName": "iphone-15", "OS": "iOS", "Online": False},
                   "b": {"HostName": "pixel", "OS": "android", "Online": True},
                   "c": {"HostName": "nas", "OS": "linux", "Online": True}}}


def test_the_phones_in_the_tailnet_and_the_account_to_log_in_as():
    got = tailnet.phones(_ran(json.dumps(STATUS)))
    assert got == {"account": "orkboss@example.com", "phones": [
        {"name": "pixel", "os": "Android", "online": True}, {"name": "iphone-15", "os": "iOS", "online": False}]}
    assert tailnet.phones(_ran(json.dumps({**STATUS, "BackendState": "Stopped"}))) is None
    assert tailnet.phones(_ran("", 1)) is None
    assert tailnet.find(_ran(json.dumps(STATUS))) == tailnet.Tail("100.64.0.7", "town.tail12.ts.net")


def test_the_desktop_reads_tailscale_at_most_every_few_seconds():
    asked = []

    class L:
        tail_trusted = True

    t = pwa.Tailnet(L(), lambda: asked.append(1) or {"account": "a", "phones": []})
    first = t.read(now=0.0)
    assert first["running"] and first["trusted"] and first["install"] == pwa.INSTALL and first["install_qr"]
    t.read(now=1.0)
    assert len(asked) == 1
    t.read(now=pwa.TAIL_S + 0.1)
    assert len(asked) == 2
    assert not pwa.Tailnet(L(), lambda: None).read(now=0.0)["running"]
