"""The town in a phone's browser: a web app the phone listener serves itself (docs/design/mobile.md §8.1, a
prototype). No app store and no build: the phone opens the tailnet's address, pairs, and adds the page to its
Home Screen. It speaks the protocol the phone listener speaks (gui/phones.py), with what a browser can say.

    GET /app/                     the app's files (gui/static/pwa/): its page, script, style, manifest, worker, icons
    GET /app/manifest.webmanifest?k=<device token>    the same manifest, its start_url carrying the token (iOS, below)
    /ws  Sec-WebSocket-Protocol: orkcraft.v1, bearer.<device token>   a browser cannot set Authorization

Only on the tailnet with its *.ts.net certificate (gui/tailnet.py) is this an app: a browser trusts that
certificate as it is, and a service worker or a Home Screen app needs one it trusts. On the LAN the listener's
certificate is self-signed and pinned (gui/phone_tls.py), which a browser cannot pin; the files are served
there too, for a person who accepts the warning on purpose, but the desktop offers no link to them.

Setting up: no QR code can join a phone to a tailnet (Tailscale's phone apps take no key from a link), so the
desktop leads the person through it (`phones.tailnet`): while no phone of theirs is in the tailnet its QR code
is Tailscale's download, with the account to log in as; once one is, it is the app's pairing link.

Pairing: the desktop shows a second QR code, `https://<name>.ts.net:<port>/app/#pair=<code>`. The code rides
in the fragment, which the browser never sends; the page trades it for a device token (`POST /api/pair`, as
any phone does) and keeps the token in the browser's storage. On iOS, Safari and the app added to the Home
Screen do not share storage: the page names the token in its manifest's start_url (`?k=`), so the app the
person adds opens with it once, keeps it, and wipes it from its address.

The files are only the app's shell: what the town is comes over the socket, after the token. They are the
same for everyone and say nothing of this town.
"""
from __future__ import annotations

import json
import re
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlsplit

from orkcraft.gui import tailnet

ROOT = Path(__file__).resolve().parent / "static" / "pwa"
PREFIX = "/app/"
SUBPROTOCOL = "orkcraft.v1"
BEARER = "bearer."
TOKEN = re.compile(r"[A-Za-z0-9_-]{20,128}")   # a device token as pairing makes it (token_urlsafe)
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".svg": "image/svg+xml"}
# The app's page loads only its own files and talks only to its own listener.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' wss:; "
       "manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
       "form-action 'none'")


def files() -> dict[str, Path]:
    """The app's files by the name they are served at (under PREFIX)."""
    return {p.name: p for p in sorted(ROOT.iterdir()) if p.is_file() and p.suffix in TYPES}


def wants(path: str) -> bool:
    return path == PREFIX.rstrip("/") or path.startswith(PREFIX)


def _head(status: HTTPStatus, content_type: str, length: int, extra: str = "") -> bytes:
    return (f"HTTP/1.1 {status.value} {status.phrase}\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {length}\r\nCache-Control: no-cache\r\nX-Content-Type-Options: nosniff\r\n"
            f"Referrer-Policy: no-referrer\r\n{extra}Connection: close\r\n\r\n").encode("ascii")


def manifest(raw: bytes, query: str) -> bytes:
    """The manifest as it is, or with `k` (a device token) in its start_url's fragment: what an iOS Home
    Screen app opens with. Anything but a token's characters leaves it as it is."""
    k = (parse_qs(query).get("k") or [""])[0]
    if not TOKEN.fullmatch(k):
        return raw
    data = json.loads(raw)
    data["start_url"] = "./#k=" + k
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def serve(method: str, target: str) -> bytes:
    """A whole response to a request for the app (`wants` its path)."""
    parts = urlsplit(target)
    if parts.path == PREFIX.rstrip("/"):
        return _head(HTTPStatus.MOVED_PERMANENTLY, "text/plain; charset=utf-8", 0, f"Location: {PREFIX}\r\n")
    if method not in ("GET", "HEAD"):
        return _head(HTTPStatus.METHOD_NOT_ALLOWED, "text/plain; charset=utf-8", 0, "Allow: GET, HEAD\r\n")
    name = parts.path[len(PREFIX):] or "index.html"
    path = files().get(name)
    if path is None:
        body = b"Not Found"
        return _head(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", len(body)) + body
    body = path.read_bytes()
    if name == "manifest.webmanifest":
        body = manifest(body, parts.query)
    extra = f"Content-Security-Policy: {CSP}\r\n" if path.suffix == ".html" else ""
    if name == "sw.js":
        extra += f"Service-Worker-Allowed: {PREFIX}\r\n"
    head = _head(HTTPStatus.OK, TYPES[path.suffix], len(body), extra)
    return head if method == "HEAD" else head + body


def ws_token(headers: dict[str, str]) -> str:
    """The device token a browser names among its subprotocols (`bearer.<token>`), or ""."""
    for item in headers.get("sec-websocket-protocol", "").split(","):
        item = item.strip()
        if item.startswith(BEARER) and TOKEN.fullmatch(item[len(BEARER):]):
            return item[len(BEARER):]
    return ""


def select(protocol, offered) -> str | None:
    """The subprotocol the listener answers with: a browser that offers some needs one of them back."""
    return SUBPROTOCOL if SUBPROTOCOL in offered else None


def link(address: str, code: str) -> str:
    """What the second QR code says: the app on the tailnet, with the pairing code in its fragment."""
    return f"{address}{PREFIX}#pair={quote(code, safe='')}"


INSTALL = "https://tailscale.com/download"
DNS = "https://login.tailscale.com/admin/dns"   # where a tailnet's HTTPS certificates are turned on
TAIL_S = 3.0             # `tailscale status` at most this often, while the desktop asks


class Tailnet:
    """`phones.tailnet` for the desktop: the account, the phones in the tailnet, and what its QR code says."""

    def __init__(self, listener, phones: Callable[[], dict | None] = tailnet.phones) -> None:
        self.listener, self.phones = listener, phones
        self._at, self._got = -TAIL_S, None

    def read(self, now: float | None = None) -> dict[str, Any]:
        now = time.monotonic() if now is None else now
        if now - self._at >= TAIL_S:
            self._at, self._got = now, self.phones()
        from orkcraft.gui.phones import qr_data_uri   # phones imports this module
        got = self._got
        return {"running": got is not None, "installed": bool(tailnet.command()) and not tailnet.off(),
                "account": (got or {}).get("account", ""),
                "phones": (got or {}).get("phones", []), "trusted": bool(self.listener.tail_trusted),
                "install": INSTALL, "install_qr": qr_data_uri(INSTALL), "dns": DNS, "dns_qr": qr_data_uri(DNS)}


def retry_tail(listener) -> None:
    """A new pairing on a listener that was already up looks for the tailnet again: Tailscale started, or its
    HTTPS certificates were turned on, since it came up. Without this the app's link waited for a restart."""
    if listener.bind or (listener.tail_server is not None and listener.tail_trusted):
        return
    tail = listener.tail_find()
    if tail is None or (listener.tail_server is not None and not tail.name):
        return                                   # no tailnet, or no name a certificate could be for
    if listener.tail_server is not None:         # on the tailnet without a certificate: ask for one again
        old, listener.tail_server, listener.tail_address = listener.tail_server, None, ""
        old.close()
    from orkcraft.gui import phone_tls
    cert, key = phone_tls.ensure(listener.cert_folder)
    listener._start_tail(tail, listener.pairing.port(), phone_tls.context(cert, key), True)


def commands(listener) -> dict[str, Callable[[dict], Any]]:
    t = Tailnet(listener)
    return {"phones.tailnet": lambda a: t.read()}
