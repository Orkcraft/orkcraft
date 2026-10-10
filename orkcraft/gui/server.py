"""The GUI's server: the page, the design system and one WebSocket, on 127.0.0.1 only.

One asyncio loop runs it and the host (`gui/host.py`): the town lives on this loop's thread. The
page gets a snapshot of the town whenever it changes (at most every `FLUSH_S`, and only when it
differs from the last one), toasts as they come, and sends commands back:

    → {"t": "cmd", "id": 7, "name": "hut.move", "args": {"id": "lake", "x": 0.4, "y": 0.2}}
    ← {"t": "reply", "id": 7, "ok": true, "result": null}      (or "ok": false, "error": "...")
    ← {"t": "state", "state": {...}}                             (gui/state.py)
    ← {"t": "toast", "message": "...", "title": "...", "severity": "information", "timeout": null}
    → {"t": "cmd", "id": 8, "name": "watch", "args": {"ids": ["lake"]}}   (the buildings open in the page)
    ← {"t": "detail", "detail": {"id": "lake", "type": "lake", "ui": {...}, "data": {...}}}

A building's own state (`detail`, gui/views/) goes only to the pages that have it open, when its
worker says it changed.

A session's bytes go as binary frames, only to the pages that show it (`term.attach`):

    → {"t": "cmd", "id": 9, "name": "term.attach", "args": {"keys": ["new:claude:1"]}}   (all it shows)
    → {"t": "cmd", "id": 10, "name": "term.replay", "args": {"key": "new:claude:1"}}      (a terminal opened)
    ← [kind: 1 byte][key length: 1 byte][key, UTF-8][bytes]    kind 0: output, 1: all of it again (replay)

The socket takes only the page this server gave out: a random token in its address and an Origin
of this server, so another page open in a browser cannot drive the town.

`GET /api/version` (the same token, as `?t=` or `Authorization: Bearer`) is the handshake a client
other than the page makes first (docs/design/mobile.md): what this server speaks, as JSON.

    ← {"name": "orkcraft", "version": "0.1.0", "protocol": 1, "api": 1}

`GET /api/audio/<building>/<episode>` (the same token) is an Audio briefing's episode, to play (`<audio>`) or,
with `?dl=1`, to download (docs/design/audio-briefing.md §7): only a finished episode of that building,
named by its id, never a path.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import secrets
import threading
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from orkcraft import __version__
from orkcraft.design import tokens
from orkcraft.gui import mobile, notify, phones, pwa
from orkcraft.gui.host import CommandError, Host

STATIC = Path(__file__).with_name("static")
TICK_S = 1.0
FLUSH_S = 0.05
ROUTES = {"/static/": STATIC, "/ds/": tokens.SYSTEM}
PROTOCOL = 1            # the socket's messages above: a change that breaks a client raises it
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("font/woff2", ".woff2")


def _response(status: HTTPStatus, body: bytes, content_type: str = "text/plain; charset=utf-8") -> Response:
    headers = Headers([("Content-Type", content_type), ("Content-Length", str(len(body))),
                       ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")])
    return Response(status.value, status.phrase, headers, body)


def resolve(path: str) -> Path | None:
    """The file a static path names, never one outside its folder."""
    for prefix, root in ROUTES.items():
        if path.startswith(prefix):
            root = root.resolve()
            target = (root / path[len(prefix):]).resolve()
            if target.is_file() and target.is_relative_to(root):
                return target
    return None


class Server:
    def __init__(self, host: Host, port: int = 0) -> None:
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe(24)
        self.clients: set[ServerConnection] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.ready = threading.Event()
        self._stop: asyncio.Event | None = None
        self._last = ""
        self._dirty = False
        self.watching: dict[ServerConnection, set[str]] = {}
        self._details: set[str] = set()             # buildings whose detail waits to be sent
        self._sent: dict[tuple[int, str], str] = {}  # (page, building) → the detail it has
        self.attached: dict[ServerConnection, set[str]] = {}
        host.on_change = self._changed
        host.on_detail = self._detail_changed
        host.sessions.on_output = self._output
        host.on_toast = lambda data: self._send_all({"t": "toast", **data})
        # The listener for phones (gui/phones.py): on the LAN, TLS, a device token; only while one is paired.
        self.phones = phones.Listener(host)
        host.commands.update(self.phones.commands())
        host.commands.update(pwa.commands(self.phones))   # the app in a phone's browser: Tailscale's state
        self.notifier = notify.Notifier(host, self.phones)   # what came, to the phones that are open

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def url(self) -> str:
        return f"{self.origin}/?t={self.token}"

    # -- HTTP ----------------------------------------------------------------------------------

    def _token_ok(self, request: Request) -> bool:
        """The server's token, from the address (`?t=`) or an `Authorization: Bearer` header."""
        token = parse_qs(urlsplit(request.path).query).get("t", [""])[0]
        auth = request.headers.get("Authorization", "")
        if not token and auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
        return bool(token) and secrets.compare_digest(token, self.token)

    def version(self) -> dict:
        return {"name": "orkcraft", "version": __version__, "protocol": PROTOCOL, "api": mobile.API}

    def _http(self, connection: ServerConnection, request: Request) -> Response | None:
        parts = urlsplit(request.path)
        if parts.path == "/ws":
            token = parse_qs(parts.query).get("t", [""])[0]
            origin = request.headers.get("Origin", "")
            if not secrets.compare_digest(token, self.token) or origin != self.origin:
                return _response(HTTPStatus.FORBIDDEN, b"Forbidden")
            return None                                   # go on with the WebSocket handshake
        if parts.path == "/api/version":
            if not self._token_ok(request):
                return _response(HTTPStatus.FORBIDDEN, b"Forbidden")
            return _response(HTTPStatus.OK, json.dumps(self.version()).encode(), "application/json")
        if parts.path.startswith("/api/audio/"):
            if not self._token_ok(request):
                return _response(HTTPStatus.FORBIDDEN, b"Forbidden")
            return self._audio(parts.path.removeprefix("/api/audio/"), "dl=1" in parts.query.split("&"))
        if parts.path in ("/", "/index.html"):
            return _response(HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if parts.path == "/favicon.ico":                  # the ork mark (design-system/logo)
            return _response(HTTPStatus.OK, (tokens.SYSTEM / "logo" / "favicon.ico").read_bytes(), "image/x-icon")
        if parts.path == "/roles.css":
            return _response(HTTPStatus.OK, tokens.roles_css().encode(), "text/css; charset=utf-8")
        target = resolve(parts.path)
        if target is None:
            return _response(HTTPStatus.NOT_FOUND, b"Not found")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith(("javascript", "json")):
            kind += "; charset=utf-8"
        return _response(HTTPStatus.OK, target.read_bytes(), kind)

    def _audio(self, rest: str, download: bool) -> Response:
        bid, _, eid = rest.partition("/")
        bs = self.host.town.scroll.building(bid) if bid else None
        if bs is None or bs.demolished or self.host.type_of(bid) != "gramophone":
            return _response(HTTPStatus.NOT_FOUND, b"Not found")
        worker = self.host.town.worker(bid)
        path = worker.file_of(eid) if worker is not None else None
        if path is None:
            return _response(HTTPStatus.NOT_FOUND, b"Not found")
        from orkcraft.realm import gramophone
        resp = _response(HTTPStatus.OK, path.read_bytes(), gramophone.MIME.get(path.suffix, "application/octet-stream"))
        e = worker.get(eid) or {}
        name = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(e.get("title") or eid))[:80].strip() or eid
        plain = name.encode("ascii", "ignore").decode().strip() or eid
        resp.headers["Content-Disposition"] = (f'{"attachment" if download else "inline"}; filename="{plain}{path.suffix}"; '
                                               f"filename*=UTF-8''{quote(name + path.suffix)}")
        return resp

    # -- the socket ----------------------------------------------------------------------------

    async def _client(self, ws: ServerConnection) -> None:
        self.clients.add(ws)
        try:
            await ws.send(json.dumps({"t": "state", "state": self.host.snapshot()}, ensure_ascii=False))
            async for raw in ws:
                await ws.send(json.dumps(self._handle(raw, ws), ensure_ascii=False))
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            self.watching.pop(ws, None)
            self.attached.pop(ws, None)
            self._sent = {k: v for k, v in self._sent.items() if k[0] != id(ws)}

    def _watch(self, ws: ServerConnection | None, args: dict) -> list[str]:
        """The buildings this page has open: each one's detail now, and again when it changes."""
        ids = [str(x) for x in (args.get("ids") or [])][:50]
        if ws is not None:
            self.watching[ws] = set(ids)
            for bid in ids:
                self._send_detail(ws, bid, force=True)
        return ids

    @staticmethod
    def frame(kind: int, key: str, data: bytes) -> bytes:
        k = key.encode("utf-8")[:255]
        return bytes([kind, len(k)]) + k + data

    def _attach(self, ws: ServerConnection | None, args: dict) -> list[str]:
        """The sessions this page shows: their bytes as they come."""
        keys = [str(x) for x in (args.get("keys") or [])][:20]
        if ws is not None:
            self.attached[ws] = set(keys)
        return keys

    def _replay(self, ws: ServerConnection | None, args: dict) -> bool:
        """A terminal opened on the page: the session as it stands now, then its bytes as they come."""
        key = str(args.get("key") or "")
        s = self.host.sessions.get(key)
        if ws is None or s is None:
            return False
        self.attached.setdefault(ws, set()).add(key)
        asyncio.ensure_future(self._send(ws, self.frame(1, key, s.replay())))
        return True

    def _output(self, key: str, data: bytes) -> None:
        frame = None
        for ws, keys in list(self.attached.items()):
            if key in keys:
                frame = frame or self.frame(0, key, data)
                asyncio.ensure_future(self._send(ws, frame))

    def _send_detail(self, ws: ServerConnection, bid: str, force: bool = False) -> None:
        detail = self.host.detail(bid)
        if detail is None:
            return
        text = json.dumps({"t": "detail", "detail": detail}, ensure_ascii=False)
        key = (id(ws), bid)
        if force or self._sent.get(key) != text:
            self._sent[key] = text
            asyncio.ensure_future(self._send(ws, text))

    def _detail_changed(self, bid: str) -> None:
        if self.loop is None or not any(bid in ids for ids in self.watching.values()):
            return
        if not self._details:
            self.loop.call_later(FLUSH_S, self._flush_details)
        self._details.add(bid)

    def _flush_details(self) -> None:
        bids, self._details = self._details, set()
        for ws, ids in list(self.watching.items()):
            for bid in bids & ids:
                self._send_detail(ws, bid)

    def _handle(self, raw: str | bytes, ws: ServerConnection | None = None) -> dict:
        try:
            msg = json.loads(raw)
            cid = msg.get("id")
        except (ValueError, AttributeError):
            return {"t": "reply", "id": None, "ok": False, "error": "Not a command"}
        if msg.get("t") != "cmd":
            return {"t": "reply", "id": cid, "ok": False, "error": "Not a command"}
        try:
            name, args = str(msg.get("name", "")), msg.get("args") or {}
            if not isinstance(args, dict):
                raise CommandError("Arguments are an object")
            if name == "watch":
                result = self._watch(ws, args)
            elif name == "term.attach":
                result = self._attach(ws, args)
            elif name == "term.replay":
                result = self._replay(ws, args)
            else:
                result = self.host.command(name, args)
            return {"t": "reply", "id": cid, "ok": True, "result": result}
        except CommandError as e:
            return {"t": "reply", "id": cid, "ok": False, "error": str(e)}
        except Exception as e:                            # a broken command never closes the page
            return {"t": "reply", "id": cid, "ok": False, "error": f"{type(e).__name__}: {e}"}

    def _send_all(self, msg: dict) -> None:
        text = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            asyncio.ensure_future(self._send(ws, text))

    @staticmethod
    async def _send(ws: ServerConnection, text: str | bytes) -> None:
        try:
            await ws.send(text)
        except ConnectionClosed:
            pass

    def _changed(self) -> None:
        """The town changed: flush a snapshot soon (many changes in one moment make one send)."""
        if self._dirty or self.loop is None:
            return
        self._dirty = True
        self.loop.call_later(FLUSH_S, self._flush)

    def _flush(self) -> None:
        self._dirty = False
        if not self.clients:
            return
        text = json.dumps({"t": "state", "state": self.host.snapshot()}, ensure_ascii=False)
        if text != self._last:
            self._last = text
            for ws in list(self.clients):
                asyncio.ensure_future(self._send(ws, text))

    # -- its life ------------------------------------------------------------------------------

    async def _ticker(self) -> None:
        while True:
            await asyncio.sleep(TICK_S)
            try:
                self.host.tick()
                self.phones.tick()
            except Exception as e:
                self.host.town.toast(f"{type(e).__name__}: {e}", title="Town clock", severity="error")

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        self.host.town.call = lambda fn, *a: self.loop.call_soon_threadsafe(fn, *a)
        async with serve(self._client, "127.0.0.1", self.port, process_request=self._http,
                         max_size=8 * 2**20) as server:
            self.port = server.sockets[0].getsockname()[1]
            ticker = asyncio.create_task(self._ticker())
            self._phones_start()
            self.ready.set()
            await self._stop.wait()
            ticker.cancel()
            self.phones.stop()
        self.host.close()

    def _phones_start(self) -> None:
        """A machine with a paired phone listens for it from the start."""
        try:
            if self.phones.wanted():
                self.phones.start()
        except phones.PhoneError as e:
            self.host.town.toast(str(e), title="Phones", severity="warning")

    def stop(self) -> None:
        if self.loop is not None and self._stop is not None:
            self.loop.call_soon_threadsafe(self._stop.set)

    def start_thread(self) -> threading.Thread:
        """Serve on a thread of its own (the window takes the main thread); returns once it listens."""
        t = threading.Thread(target=lambda: asyncio.run(self.run()), name="orkcraft-gui", daemon=True)
        t.start()
        self.ready.wait(10)
        return t
