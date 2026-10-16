"""The town in a phone's browser (gui/pwa.py): the app's files from the phone listener, a browser's socket that
names its token as a subprotocol, the pairing link on the tailnet, and Tailscale's state for the desktop."""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import subprocess
from pathlib import Path

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
    head, body = _split(pwa.serve("GET", "/app/fonts/titillium-web-latin-400-normal.woff2"))   # the desktop's faces
    assert "Content-Type: font/woff2" in head and body[:4] == b"wOF2"
    assert b"New Rocker" in _split(pwa.serve("GET", "/app/fonts/fonts.css"))[1]
    assert _split(pwa.serve("GET", "/app/fonts/OFL-Titillium-Web.txt"))[0].startswith("HTTP/1.1 404")
    head, body = _split(pwa.serve("HEAD", "/app/app.css"))
    assert head.startswith("HTTP/1.1 200") and body == b""


def test_every_import_of_a_served_module_is_a_served_module_with_the_names_it_takes():
    """The app's module graph, as the phone loads it (the owner's phone stuck on "Loading…" when the desktop's layout
    gained imports /app/ did not serve, and one name that resolved to the app's own ground.js): every relative import
    in a served .js resolves, under /app/, to a served .js that exports each name taken from it."""
    import posixpath
    import re
    served = pwa.files()
    imports = re.compile(r'import\s*\{([^}]*)\}\s*from\s*"(\.{1,2}/[^"]+)"|import\s*"(\.{1,2}/[^"]+)"')
    exports = re.compile(r"export\s+(?:async\s+)?(?:function\*?|const|let|var|class)\s+([\w$]+)|export\s*\{([^}]*)\}")
    for name, path in served.items():
        if not name.endswith(".js") or name == "sw.js":
            continue
        for names, rel, bare in imports.findall(path.read_text(encoding="utf-8")):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), rel or bare))
            assert target in served, f"{name} imports {rel or bare}: /app/{target} is not served"
            text = served[target].read_text(encoding="utf-8")
            has = {m[0] for m in exports.findall(text) if m[0]}
            has |= {x.split(" as ")[-1].strip() for m in exports.findall(text) if m[1] for x in m[1].split(",")}
            for one in filter(None, (x.split(" as ")[0].strip() for x in names.split(","))):
                assert one in has, f"{name} takes {one} from {target}, which does not export it"


def test_the_service_worker_keeps_every_module_the_app_loads():
    import re
    sw = (pwa.ROOT / "sw.js").read_text(encoding="utf-8")
    shell = set(re.findall(r'"([^"]+)"', sw[sw.index("SHELL"):sw.index("];")]))
    assert {k for k in pwa.files() if k.endswith(".js") and k != "sw.js"} <= shell


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
        assert status == 200 and b"Orkline" in body and "content-security-policy" in headers
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


@pytest.mark.asyncio
async def test_a_new_pairing_finds_a_tailnet_that_came_after_the_listener(fake_repo, tmp_path, monkeypatch):
    checkpoint.ensure(fake_repo)
    listener = phones.Listener(Host(fake_repo, auto_commit=False), cert_folder=tmp_path)
    monkeypatch.setattr(phones, "lan_ip", lambda: "127.0.0.1")               # the LAN, and no Tailscale yet
    listener.bind, listener.tail_find = None, lambda: None
    try:
        first = listener.pair()
        assert first["app_link"] == "" and listener.tail_server is None
        listener.tail_find = lambda: tailnet.Tail("127.0.0.2", "town.tail12.ts.net")   # Tailscale came
        listener.tail_cert = lambda tail: None                                # …without certificates
        assert listener.pair()["app_link"] == "" and listener.tail_server is not None
        listener.tail_cert = lambda tail: phone_tls.ensure(tmp_path)          # …and then they were turned on
        again = listener.pair()
        assert listener.tail_trusted and again["app_link"].startswith("https://town.tail12.ts.net:")
        assert listener.server is not None                                    # the LAN's listener stayed
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
    assert first["dns"] == pwa.DNS and first["dns_qr"] and "installed" in first
    t.read(now=1.0)
    assert len(asked) == 1
    t.read(now=pwa.TAIL_S + 0.1)
    assert len(asked) == 2
    assert not pwa.Tailnet(L(), lambda: None).read(now=0.0)["running"]


@pytest.mark.asyncio
async def test_tailscale_that_comes_after_the_town_is_taken_within_a_minute_on_the_same_port(
        fake_repo, tmp_path, monkeypatch):
    checkpoint.ensure(fake_repo)
    listener = phones.Listener(Host(fake_repo, auto_commit=False), cert_folder=tmp_path)
    monkeypatch.setattr(phones, "lan_ip", lambda: "127.0.0.1")
    listener.bind, listener.tail_find = None, lambda: None
    watch = pwa.TailWatch(listener, every=60.0)
    assert not watch.wanted()                                               # no phone paired: nothing to look for
    listener.pairing.add("Phone")
    try:
        listener.start()                                                    # the town opens; Tailscale is not up yet
        port = listener.pairing.port()
        assert watch.wanted() and listener.tail_server is None
        asked = []
        listener.tail_find = lambda: asked.append(1) or tailnet.Tail("127.0.0.2", "town.tail12.ts.net")
        listener.tail_cert = lambda tail: phone_tls.ensure(tmp_path)
        watch.tick(now=watch._at + 30.0)
        assert not asked                                                    # not before a minute
        watch.tick(now=watch._at + 61.0)
        for _ in range(100):
            if not watch._busy:
                break
            await asyncio.sleep(0.02)
        assert asked and listener.tail_trusted and listener.tail_address == f"https://town.tail12.ts.net:{port}"
        assert not watch.wanted()                                           # done: it looks no more
        assert listener.server is not None                                  # the LAN's listener stayed
    finally:
        listener.stop()



def test_the_phone_draws_the_desktops_marks():
    """A building's mark on the phone is the desktop's: its line icon in Office (pwa/icons.js keeps js/icons.js's
    PATHS), its header sprite in Camp (served as sprites/<type>.png, for every type the app names)."""
    import re
    from pathlib import Path

    static = Path(pwa.__file__).parent / "static"
    paths = lambda t: dict(re.findall(r'^\s+(\w+): "([^"]+)"', t[t.index("PATHS = {"):t.index("};", t.index("PATHS = {"))], re.M))  # noqa: E731
    desk, phone = (static / "js" / "icons.js").read_text(), (static / "pwa" / "icons.js").read_text()
    assert paths(desk) and paths(phone) == paths(desk)
    named = set(re.findall(r'"(\w+)"', phone[phone.index("new Set(["):phone.index("]);", phone.index("new Set(["))]))
    assert named == {d.name for d in pwa.SPRITES.iterdir() if d.is_dir()}
    for name in named:
        for scale in ("", "@2x"):
            head, body = _split(pwa.serve("GET", f"/app/sprites/{name}{scale}.png"))
            assert head.startswith("HTTP/1.1 200") and "image/png" in head and body[:4] == b"\x89PNG", name
    assert _split(pwa.serve("GET", "/app/sprites/../tokens.css"))[0].startswith("HTTP/1.1 404")


def test_the_phone_wears_the_design_system_its_fence_and_its_resources():
    """The app's page loads the desktop's design system (tokens.css, components.css, the same files) and the
    sprites its windows and HUD draw: the fence round a window, the resources before the town's name."""
    import re

    from orkcraft.design import tokens

    head, body = _split(pwa.serve("GET", "/app/"))
    assert b'href="tokens.css"' in body and b'href="components.css"' in body
    for name in pwa.STYLES:
        head, body = _split(pwa.serve("GET", f"/app/{name}"))
        assert "text/css" in head and body == (tokens.SYSTEM / name).read_bytes(), name
    css = (pwa.ROOT / "app.css").read_text()
    for url in sorted(set(re.findall(r'url\("([^"]+)"\)', css))):
        assert _split(pwa.serve("GET", f"/app/{url}"))[0].startswith("HTTP/1.1 200"), url
    for res in ("quota", "gold", "meat"):
        for scale in ("", "@2x"):
            assert _split(pwa.serve("GET", f"/app/icons/res-{res}{scale}.png"))[0].startswith("HTTP/1.1 200"), res
    assert _split(pwa.serve("GET", "/app/icons/settings.png"))[0].startswith("HTTP/1.1 404")   # its resources only


def test_the_phone_stands_on_the_desktops_ground():
    """A biome's ground on the phone is the desktop's: the colour (js/icons.js BIOMES) and the glyphs (js/terrain.js)."""
    import re
    from pathlib import Path

    static = Path(pwa.__file__).parent / "static"
    desk_biomes = dict(re.findall(r'^\s+(\w+): \{ ground: "(#\w+)"', (static / "js" / "icons.js").read_text(), re.M))
    phone = (static / "pwa" / "ground.js").read_text()
    assert desk_biomes and dict(re.findall(r'(\w+): "(#\w+)"', phone[:phone.index("};")])) == desk_biomes
    glyphs = lambda t: re.findall(r'^\s+(\w+): \{ glyphs: (\[[^\]]*\]), ink: "([^"]*)" \}', t, re.M)  # noqa: E731
    assert glyphs(phone) and glyphs(phone) == glyphs((static / "js" / "terrain.js").read_text())


def test_assets_json_lists_every_cache_first_file_with_a_hash():
    pwa.assets()                                     # the listener's warm-up
    head, body = _split(pwa.serve("GET", "/app/assets.json"))
    assert head.startswith("HTTP/1.1 200") and "application/json" in head
    assert "public, max-age=" not in head
    data = json.loads(body)
    cf_files = {k: v for k, v in pwa.files().items() if pwa.is_cache_first(k)}
    assert set(data.keys()) == set(cf_files.keys())
    for path, h in data.items():
        assert len(h) == 10 and all(c in "0123456789abcdef" for c in h)
        real_hash = hashlib.sha1(cf_files[path].read_bytes()).hexdigest()[:10]
        assert h == real_hash


def test_a_changed_file_changes_its_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(pwa, "_ASSETS", pwa._ASSETS)  # the map this test warms up goes with it
    dummy = tmp_path / "custom.png"
    dummy.write_bytes(b"content_version_one")
    real_files = pwa.files()
    monkeypatch.setattr(pwa, "files", lambda: {**real_files, "sprites/custom.png": dummy})
    h1 = pwa.assets()["sprites/custom.png"]
    assert h1 == hashlib.sha1(b"content_version_one").hexdigest()[:10]

    dummy.write_bytes(b"content_version_two_changed")
    h2 = pwa.assets()["sprites/custom.png"]
    assert h2 == hashlib.sha1(b"content_version_two_changed").hexdigest()[:10]
    assert h1 != h2
    _, body = _split(pwa.serve("GET", "/app/assets.json"))
    assert json.loads(body)["sprites/custom.png"] == h2


def test_a_request_only_reads_the_map_the_warm_up_hashed(tmp_path, monkeypatch):
    """Only the warm-up hashes: a request for assets.json reads the map it kept and touches no file."""
    monkeypatch.setattr(pwa, "_ASSETS", None)
    head, _ = _split(pwa.serve("GET", "/app/assets.json"))
    assert head.startswith("HTTP/1.1 503")             # not warmed yet: no map rather than a wrong one
    dummy = tmp_path / "custom.png"
    dummy.write_bytes(b"one")
    real_files = pwa.files()
    monkeypatch.setattr(pwa, "files", lambda: {**real_files, "sprites/custom.png": dummy})
    h1 = pwa.assets()["sprites/custom.png"]
    dummy.write_bytes(b"two")
    with monkeypatch.context() as m:
        m.setattr(pwa.hashlib, "sha1", lambda *a: pytest.fail("a request hashed"))
        m.setattr(Path, "stat", lambda *a, **k: pytest.fail("a request looked at a file"))
        _, body = _split(pwa.serve("GET", "/app/assets.json"))
    assert json.loads(body)["sprites/custom.png"] == h1


def test_service_worker_names_cache_version_and_cache_first_prefixes():
    sw = (pwa.ROOT / "sw.js").read_text(encoding="utf-8")
    assert "orkcraft-app-v11" in sw
    for prefix in ("v3/", "sprites/", "icons/", "fence/", "fonts/"):
        assert prefix in sw


def test_cache_control_headers_for_cache_first_and_shell():
    head_cf, _ = _split(pwa.serve("GET", "/app/camp/ork-walk.png"))
    assert "Cache-Control: public, max-age=31536000, immutable" in head_cf
    head_shell, _ = _split(pwa.serve("GET", "/app/app.js"))
    assert "Cache-Control: no-cache" in head_shell
    head_html, _ = _split(pwa.serve("GET", "/app/"))
    assert "Cache-Control: no-cache" in head_html
    head_assets, _ = _split(pwa.serve("GET", "/app/assets.json"))
    assert "Cache-Control: no-cache" in head_assets
