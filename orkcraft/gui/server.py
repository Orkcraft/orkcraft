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

The socket takes only the page this server gave out: a random token in its address and an Origin
of this server, so another page open in a browser cannot drive the town.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import secrets
import threading
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from orkcraft.design import tokens
from orkcraft.gui.host import CommandError, Host

STATIC = Path(__file__).with_name("static")
TICK_S = 1.0
FLUSH_S = 0.05
ROUTES = {"/static/": STATIC, "/ds/": tokens.SYSTEM}
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
        host.on_change = self._changed
        host.on_detail = self._detail_changed
        host.on_toast = lambda data: self._send_all({"t": "toast", **data})

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def url(self) -> str:
        return f"{self.origin}/?t={self.token}"

    # -- HTTP ----------------------------------------------------------------------------------

    def _http(self, connection: ServerConnection, request: Request) -> Response | None:
        parts = urlsplit(request.path)
        if parts.path == "/ws":
            token = parse_qs(parts.query).get("t", [""])[0]
            origin = request.headers.get("Origin", "")
            if not secrets.compare_digest(token, self.token) or origin != self.origin:
                return _response(HTTPStatus.FORBIDDEN, b"Forbidden")
            return None                                   # go on with the WebSocket handshake
        if parts.path in ("/", "/index.html"):
            return _response(HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if parts.path == "/favicon.ico":
            return _response(HTTPStatus.NO_CONTENT, b"")
        if parts.path == "/roles.css":
            return _response(HTTPStatus.OK, tokens.roles_css().encode(), "text/css; charset=utf-8")
        target = resolve(parts.path)
        if target is None:
            return _response(HTTPStatus.NOT_FOUND, b"Not found")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith(("javascript", "json")):
            kind += "; charset=utf-8"
        return _response(HTTPStatus.OK, target.read_bytes(), kind)

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
            self._sent = {k: v for k, v in self._sent.items() if k[0] != id(ws)}

    def _watch(self, ws: ServerConnection | None, args: dict) -> list[str]:
        """The buildings this page has open: each one's detail now, and again when it changes."""
        ids = [str(x) for x in (args.get("ids") or [])][:50]
        if ws is not None:
            self.watching[ws] = set(ids)
            for bid in ids:
                self._send_detail(ws, bid, force=True)
        return ids

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
            result = self._watch(ws, args) if name == "watch" else self.host.command(name, args)
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
    async def _send(ws: ServerConnection, text: str) -> None:
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
            self.ready.set()
            await self._stop.wait()
            ticker.cancel()
        self.host.close()

    def stop(self) -> None:
        if self.loop is not None and self._stop is not None:
            self.loop.call_soon_threadsafe(self._stop.set)

    def start_thread(self) -> threading.Thread:
        """Serve on a thread of its own (the window takes the main thread); returns once it listens."""
        t = threading.Thread(target=lambda: asyncio.run(self.run()), name="orkcraft-gui", daemon=True)
        t.start()
        self.ready.wait(10)
        return t
