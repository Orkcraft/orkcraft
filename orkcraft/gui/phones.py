"""The listener for phones (docs/design/mobile.md §2, stage 1): one more face over the same host.

It runs beside the page's server, on the same loop (`Server.run`), on its own port of the LAN interface,
over TLS with a self-signed certificate the phone pins (gui/phone_tls.py). It listens only while a phone
is paired or a pairing code is shown: a machine with no phone opens no port on the LAN.

    GET  /api/version   Authorization: Bearer <device token, or the live pairing code>
         ← {"name": "orkcraft", "version": "0.1.0", "protocol": 1, "api": 1}
    POST /api/pair      {"code": "<pairing code>", "name": "Vadim's phone"}   (Content-Type: application/json)
         ← {"id": "<device id>", "token": "<device token>", "name": "Vadim's phone"}
    GET  /ws            Authorization: Bearer <device token>; a WebSocket:
         ← {"t": "state", "state": {...}}     the compact snapshot (gui/mobile.py), at most every PUSH_S
         → {"t": "cmd", "id": 7, "name": "orders.answer", "args": {"id": "…", "key": "1"}}
         ← {"t": "reply", "id": 7, "ok": true, "result": true}
         ← {"t": "news", "news": [...]}       what came, while the app is open (gui/notify.py)

A command reaches `host.command` only when `mobile.allowed` says so, at most a few a second per device
(`pairing.Bucket`); it never sends the page's `state`, `detail` or a terminal's frames and takes no
`watch`, `term.attach` or `term.replay`. Forget (Settings → Phones) closes the device's socket at once.

The page's commands for it (`commands`): `phones.list`, `phones.pair` (a new code, the QR code to scan),
`phones.pair_stop` and `phones.forget`.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import socket
import ssl
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlsplit

from websockets.frames import Frame, Opcode
from websockets.http11 import Request
from websockets.server import ServerProtocol

from orkcraft import env
from orkcraft.gui import mobile, phone_tls
from orkcraft.gui.host import CommandError
from orkcraft.gui.pairing import Bucket, PairError, Pairing, clean_name

PUSH_S = 2.0             # a phone gets the compact snapshot at most this often, and only when its rev changed
HEAD_LIMIT = 16 * 1024   # an HTTP request's head
HEAD_S = 10.0            # …and how long it may take to come
BODY_LIMIT = 4096        # POST /api/pair's body
MAX_FRAME = 8 * 2**20    # as the page's socket: a dropped file comes base64 in one frame
HOST_ENV = "PHONE_HOST"  # ORKCRAFT_PHONE_HOST: the address to listen on, when the LAN's own is not the one


class PhoneError(CommandError):
    """A page's request about phones that cannot be done here; its text is shown to the person."""


def lan_ip() -> str | None:
    """This machine's address on the network it reaches out by (no packet is sent), or None offline."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))            # TEST-NET-1: only picks the interface a route goes out of
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return None if ip.startswith("127.") or ip == "0.0.0.0" else ip


def pair_link(address: str, fingerprint: str, code: str) -> str:
    """What the QR code says: where the town is, the certificate to pin and the one-time code."""
    return (f"orkcraft://pair?v={mobile.API}&addr={quote(address, safe='')}"
            f"&fp={fingerprint.replace(':', '')}&code={quote(code, safe='')}")


def qr_data_uri(text: str) -> str | None:
    """The QR code as an SVG data: URI (shown as an image, never as markup); None without segno."""
    try:
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=6, border=2, dark="#000", light="#fff", xmldecl=False)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _response(status: HTTPStatus, body: bytes = b"", content_type: str = "text/plain; charset=utf-8") -> bytes:
    body = body or status.phrase.encode()
    head = (f"HTTP/1.1 {status.value} {status.phrase}\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            "Connection: close\r\n\r\n")
    return head.encode("ascii") + body


def _json(status: HTTPStatus, data: Any) -> bytes:
    return _response(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")


def _parse_head(head: bytes) -> tuple[str, str, dict[str, str]] | None:
    """(method, target, headers by lower-case name) of a request's head; None when it is not HTTP/1.1."""
    try:
        lines = head.decode("latin-1").split("\r\n")
        method, target, version = lines[0].split(" ")
    except ValueError:
        return None
    if version not in ("HTTP/1.1", "HTTP/1.0"):
        return None
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            return None
        headers.setdefault(name.strip().lower(), value.strip())
    return method, target, headers


def _bearer(value: str) -> str:
    return value[7:].strip() if value[:7].lower() == "bearer " else ""


class Phone:
    """One phone's open socket."""

    def __init__(self, device: dict, protocol: ServerProtocol, writer: asyncio.StreamWriter) -> None:
        self.id, self.name = device["id"], device["name"]
        self.protocol, self.writer = protocol, writer
        self.bucket = Bucket()
        self.rev = ""

    def flush(self) -> None:
        for data in self.protocol.data_to_send():
            if data:
                self.writer.write(data)
            else:                                  # the protocol's EOF: TLS cannot half-close, so close
                self.writer.close()

    def send(self, msg: dict) -> None:
        if self.writer.is_closing():
            return
        self.protocol.send_text(json.dumps(msg, ensure_ascii=False).encode("utf-8"))
        self.flush()

    def close(self, code: int = 1008, reason: str = "") -> None:
        if self.writer.is_closing():
            return
        try:
            self.protocol.send_close(code, reason)
            self.flush()
        except Exception:                          # already closing: the socket goes either way
            pass
        self.writer.close()


class Listener:
    def __init__(self, host, pairing: Pairing | None = None, bind: str | None = None,
                 cert_folder: Path | None = None) -> None:
        self.host = host
        self.pairing = pairing or Pairing()
        self.bind = bind or env.getenv(HOST_ENV) or None   # None: the LAN's address (lan_ip)
        self.cert_folder = cert_folder
        self.server: asyncio.AbstractServer | None = None
        self.address = ""                          # https://<ip>:<port> while it listens
        self.fingerprint = ""
        self.phones: set[Phone] = set()
        self.on_open: Callable[[Phone], None] = lambda phone: None   # gui/notify.py: what came while away
        self._pushed = 0.0
        self._snap: dict | None = None             # the last compact snapshot, while one is open
        self._said_locked = False                  # the desktop was told pairing locked (once a code)

    # -- its life ------------------------------------------------------------------------------------

    @property
    def listening(self) -> bool:
        return self.server is not None

    def wanted(self) -> bool:
        """It listens while a phone is paired or a pairing code is live, and only then."""
        return bool(self.pairing.devices()) or self.pairing.code_live()

    def _socket(self, ip: str, port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((ip, port))
            sock.listen(16)
        except OSError:
            sock.close()
            raise
        sock.setblocking(False)
        return sock

    def start(self, move: bool = False) -> None:
        """Listen on the LAN (on the loop that runs now). The port is the one phones were given; a
        `move` (a new pairing) takes another when that one is taken."""
        if self.server is not None:
            return
        ip = self.bind or lan_ip()
        if not ip:
            raise PhoneError("No network found: connect this machine to the Wi-Fi the phone is on")
        try:
            cert, key = phone_tls.ensure(self.cert_folder)
            ctx = phone_tls.context(cert, key)
        except (phone_tls.TlsError, OSError, ssl.SSLError) as e:
            raise PhoneError(str(e)) from None
        port = self.pairing.port()
        try:
            sock = self._socket(ip, port)
        except OSError as e:
            if not (move and port):
                raise PhoneError(f"Cannot listen for phones on {ip}:{port}: {e.strerror or e}") from None
            sock = self._socket(ip, 0)
        new = sock.getsockname()[1]
        if new != port:
            self.pairing.save_port(new)
        self.fingerprint = phone_tls.fingerprint(cert)
        self.address = f"https://{ip}:{new}"
        future = asyncio.ensure_future(asyncio.start_server(self._conn, sock=sock, ssl=ctx, limit=HEAD_LIMIT,
                                                            ssl_handshake_timeout=HEAD_S))
        self.server = _Pending(future, sock)
        future.add_done_callback(self._started)

    def _started(self, future: asyncio.Future) -> None:
        if future.cancelled() or future.exception() is not None:
            self.server, self.address = None, ""
            return
        if isinstance(self.server, _Pending):
            self.server = future.result()

    def stop(self) -> None:
        for phone in list(self.phones):
            phone.close(1001, "The town stopped listening")
        self.phones.clear()
        server, self.server, self.address = self.server, None, ""
        if server is not None:
            server.close()

    def tick(self, now: float | None = None) -> None:
        """Once a second from the server's clock: the snapshot to the phones that are open (every PUSH_S,
        only when it changed), and the listener stops when nothing is paired and no code is live."""
        now = time.monotonic() if now is None else now
        if self.server is not None and not self.wanted():
            self.stop()
            return
        if self.phones and now - self._pushed >= PUSH_S:
            self._pushed = now
            self.push()

    def compact(self) -> dict:
        return mobile.compact(self.host.snapshot())

    def push(self, snap: dict | None = None) -> dict:
        snap = snap or self.compact()
        self._snap = snap
        for phone in list(self.phones):
            if phone.rev != snap["rev"]:
                phone.rev = snap["rev"]
                phone.send({"t": "state", "state": snap})
        return snap

    def broadcast(self, msg: dict) -> None:
        for phone in list(self.phones):
            phone.send(msg)

    def close_device(self, device_id: str) -> None:
        for phone in [p for p in self.phones if p.id == device_id]:
            phone.close(1008, "This phone was forgotten")
            self.phones.discard(phone)

    # -- HTTP ----------------------------------------------------------------------------------------

    async def _conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), HEAD_S)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError, ConnectionError,
                    ssl.SSLError, OSError):
                return
            parsed = _parse_head(head)
            if parsed is None:
                writer.write(_response(HTTPStatus.BAD_REQUEST))
                return
            method, target, headers = parsed
            path = urlsplit(target).path
            if path == "/ws":
                if method != "GET":
                    writer.write(_response(HTTPStatus.METHOD_NOT_ALLOWED))
                    return
                await self._websocket(head, headers, reader, writer)
            elif path == "/api/version":
                writer.write(self._version(method, headers))
            elif path == "/api/pair":
                writer.write(await self._pair(method, headers, reader))
            else:
                writer.write(_response(HTTPStatus.NOT_FOUND))
        except Exception:                          # one phone's broken request never stops the listener
            pass
        finally:
            try:
                if not writer.is_closing():
                    await asyncio.wait_for(writer.drain(), HEAD_S)
                writer.close()
            except Exception:
                pass

    def _version(self, method: str, headers: dict[str, str]) -> bytes:
        if method != "GET":
            return _response(HTTPStatus.METHOD_NOT_ALLOWED)
        token = _bearer(headers.get("authorization", ""))
        if self.pairing.device(token) is None:
            # Before pairing a phone shows the code it scanned; a wrong one counts as an attempt.
            if not token or not self.pairing.attempt() or not self.pairing.code_ok(token):
                return _response(HTTPStatus.FORBIDDEN)
        from orkcraft import __version__
        from orkcraft.gui.server import PROTOCOL
        return _json(HTTPStatus.OK, {"name": "orkcraft", "version": __version__, "protocol": PROTOCOL,
                                     "api": mobile.API})

    async def _pair(self, method: str, headers: dict[str, str], reader: asyncio.StreamReader) -> bytes:
        if method != "POST":
            return _response(HTTPStatus.METHOD_NOT_ALLOWED)
        if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return _response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            length = int(headers.get("content-length", ""))
        except ValueError:
            return _response(HTTPStatus.LENGTH_REQUIRED)
        if not 0 < length <= BODY_LIMIT or "transfer-encoding" in headers:
            return _response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        if not self.pairing.attempt():
            self._locked()
            return _json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Pairing is locked: show a new code on the desktop"})
        try:
            body = json.loads(await asyncio.wait_for(reader.readexactly(length), HEAD_S))
        except (ValueError, asyncio.IncompleteReadError, TimeoutError):
            return _json(HTTPStatus.BAD_REQUEST, {"error": "Not a pairing request"})
        if not isinstance(body, dict):
            return _json(HTTPStatus.BAD_REQUEST, {"error": "Not a pairing request"})
        try:
            device_id, token, name = self.pairing.pair(body.get("code"), clean_name(body.get("name")))
        except PairError as e:
            return _json(HTTPStatus.FORBIDDEN, {"error": str(e)})
        self.host.town.toast(f"{name} is paired: it can answer the orks' questions and stop all",
                             title="Phone paired")
        return _json(HTTPStatus.OK, {"id": device_id, "token": token, "name": name})

    def _locked(self) -> None:
        if not self._said_locked:
            self._said_locked = True
            self.host.town.toast("Too many pairing attempts: the code is void. Show a new one to pair a phone.",
                                 title="Phones", severity="warning")

    # -- the socket ----------------------------------------------------------------------------------

    async def _websocket(self, head: bytes, headers: dict[str, str], reader: asyncio.StreamReader,
                         writer: asyncio.StreamWriter) -> None:
        protocol = ServerProtocol(max_size=MAX_FRAME)
        protocol.receive_data(head)
        events = protocol.events_received()
        request = events[0] if events and isinstance(events[0], Request) else None
        device = self.pairing.device(_bearer(headers.get("authorization", ""))) if request else None
        if request is None or device is None:
            protocol.send_response(protocol.reject(HTTPStatus.FORBIDDEN, "Forbidden"))
            for data in protocol.data_to_send():
                writer.write(data)
            return
        response = protocol.accept(request)
        protocol.send_response(response)
        phone = Phone(device, protocol, writer)
        phone.flush()
        if response.status_code != 101:
            return
        self.phones.add(phone)
        self.pairing.seen(phone.id)
        try:
            phone.rev = ""
            snap = self._snap if self._snap is not None and time.monotonic() - self._pushed < PUSH_S else self.compact()
            phone.rev = snap["rev"]
            phone.send({"t": "state", "state": snap})
            self.on_open(phone)
            while not writer.is_closing():
                data = await reader.read(65536)
                if not data:
                    protocol.receive_eof()
                    phone.flush()
                    break
                protocol.receive_data(data)
                for event in protocol.events_received():
                    self._frame(phone, event)
                phone.flush()
                await writer.drain()
                if protocol.close_expected():
                    break
        except (ConnectionError, ssl.SSLError, OSError):
            pass
        finally:
            self.phones.discard(phone)

    def _frame(self, phone: Phone, frame: Frame) -> None:
        if frame.opcode in (Opcode.PING, Opcode.PONG, Opcode.CLOSE):
            return
        if frame.opcode is not Opcode.TEXT or not frame.fin:
            phone.protocol.fail(1003, "One text frame a command")
            return
        try:
            text = frame.data.decode("utf-8")
        except UnicodeDecodeError:
            phone.protocol.fail(1007, "Not UTF-8")
            return
        phone.send(self.handle(phone, text))

    def handle(self, phone: Phone, raw: str) -> dict:
        """One command from a phone, as `Server._handle` does the page's, but only what a phone may send."""
        try:
            msg = json.loads(raw)
            cid = msg.get("id")
        except (ValueError, AttributeError):
            return {"t": "reply", "id": None, "ok": False, "error": "Not a command"}
        if msg.get("t") != "cmd":
            return {"t": "reply", "id": cid, "ok": False, "error": "Not a command"}
        name, args = str(msg.get("name", "")), msg.get("args") or {}
        if not self.pairing.known(phone.id):         # forgotten meanwhile (by another town on this machine)
            phone.close(1008, "This phone was forgotten")
            return {"t": "reply", "id": cid, "ok": False, "error": "This phone was forgotten"}
        if not phone.bucket.take():
            return {"t": "reply", "id": cid, "ok": False, "error": "Too many commands: wait a moment"}
        if not isinstance(args, dict):
            return {"t": "reply", "id": cid, "ok": False, "error": "Arguments are an object"}
        if not mobile.allowed(self.host, name, args):
            return {"t": "reply", "id": cid, "ok": False, "error": f"Not from a phone: {name}"}
        self.pairing.seen(phone.id)
        try:
            result = self.host.command(name, mobile.guard(name, args))
        except CommandError as e:
            return {"t": "reply", "id": cid, "ok": False, "error": str(e)}
        except Exception as e:                       # a broken command never closes the phone
            return {"t": "reply", "id": cid, "ok": False, "error": f"{type(e).__name__}: {e}"}
        if name == "halt":
            self.host.town.toast(f"Stop all came from the phone {phone.name}", title="Stop all", severity="warning")
        return {"t": "reply", "id": cid, "ok": True, "result": result}

    # -- the page's commands (Settings → Phones) -----------------------------------------------------

    def read(self) -> dict[str, Any]:
        return {"phones": self.pairing.public(), "listening": self.listening, "address": self.address,
                "fingerprint": self.fingerprint, "open": sorted({p.id for p in self.phones}),
                "pairing": self.pairing.expires_in()}

    def pair(self) -> dict[str, Any]:
        """A new one-time code and the QR code that carries it, the address and the fingerprint."""
        code = self.pairing.new_code()
        self._said_locked = False
        try:
            self.start(move=True)
        except PhoneError:
            self.pairing.void()
            raise
        link = pair_link(self.address, self.fingerprint, code)
        return {**self.read(), "link": link, "qr": qr_data_uri(link), "code": code}

    def pair_stop(self) -> dict[str, Any]:
        self.pairing.void()
        if not self.wanted():
            self.stop()
        return self.read()

    def forget(self, device_id: str) -> dict[str, Any]:
        if not self.pairing.forget(device_id):
            raise PhoneError("No such phone")
        self.close_device(device_id)
        if not self.wanted():
            self.stop()
        return self.read()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"phones.list": lambda a: self.read(), "phones.pair": lambda a: self.pair(),
                "phones.pair_stop": lambda a: self.pair_stop(),
                "phones.forget": lambda a: self.forget(str(a.get("id") or ""))}


class _Pending:
    """The listener while `start_server` comes up: closing it then closes the socket it was given."""

    def __init__(self, future: asyncio.Future, sock: socket.socket) -> None:
        self.future, self.sock = future, sock

    def close(self) -> None:
        if self.future.done() and not self.future.cancelled() and self.future.exception() is None:
            self.future.result().close()
        else:
            self.future.cancel()
            self.sock.close()
