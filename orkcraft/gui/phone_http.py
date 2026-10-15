"""Keep-alive HTTP connection handling and response helpers for the phone listener
(gui/phones.py; decisions-2026-10.md §19).
"""
from __future__ import annotations

import asyncio
import json
import ssl
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

from orkcraft.gui import pwa

HEAD_LIMIT = 16 * 1024   # an HTTP request's head
HEAD_S = 10.0            # …and how long it may take to come
IDLE_S = 15.0            # keep-alive: how long to wait for the next request on an open connection
KEEP_ALIVE_MAX = 100     # at most this many requests on one connection
BODY_LIMIT = 4096        # POST /api/pair's body


def _response(status: HTTPStatus, body: bytes = b"", content_type: str = "text/plain; charset=utf-8",
              keep_alive: bool = False) -> bytes:
    body = body or status.phrase.encode()
    conn = "Connection: keep-alive" if keep_alive else "Connection: close"
    head = (f"HTTP/1.1 {status.value} {status.phrase}\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            f"{conn}\r\n\r\n")
    return head.encode("ascii") + body


def _json(status: HTTPStatus, data: Any, keep_alive: bool = False) -> bytes:
    return _response(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json",
                     keep_alive=keep_alive)


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


async def handle_conn(listener: Any, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle requests on a connection with keep-alive for body-less GETs."""
    try:
        from orkcraft.gui import phones
        max_reqs = getattr(phones, "KEEP_ALIVE_MAX", KEEP_ALIVE_MAX)
        idle_s = getattr(phones, "IDLE_S", IDLE_S)
        head_s = getattr(phones, "HEAD_S", HEAD_S)
        for req_count in range(max_reqs):
            timeout = head_s if req_count == 0 else idle_s
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError, ConnectionError,
                    ssl.SSLError, OSError):
                return
            parsed = _parse_head(head)
            if parsed is None:
                writer.write(_response(HTTPStatus.BAD_REQUEST, keep_alive=False))
                return
            method, target, headers = parsed
            path = urlsplit(target).path
            if path == "/ws":
                if method != "GET":
                    writer.write(_response(HTTPStatus.METHOD_NOT_ALLOWED, keep_alive=False))
                    return
                await listener._websocket(head, headers, reader, writer)
                return

            # Requests with a body close the connection: any request with a body or a Content-Length
            # header (including every early 403/413/415/429 answer in phones.py _pair and places.py
            # post) answers with Connection: close and ends the keep-alive loop. Only body-less GETs
            # are kept alive.
            has_body = (method != "GET") or ("content-length" in headers) or ("transfer-encoding" in headers)
            close_conn = headers.get("connection", "").lower() == "close"
            is_post_endpoint = path in ("/api/pair", "/api/place")
            is_last = (req_count == max_reqs - 1) or close_conn or has_body or is_post_endpoint
            keep = not is_last

            if path == "/api/version":
                writer.write(listener._version(method, headers, keep_alive=keep))
            elif path == "/api/pair":
                writer.write(await listener._pair(method, headers, reader))
            elif path == "/api/place":
                writer.write(await listener._place(method, headers, reader))
            elif pwa.wants(path):
                writer.write(pwa.serve(method, target, keep_alive=keep))
            else:
                writer.write(_response(HTTPStatus.NOT_FOUND, keep_alive=keep))

            if is_last:
                return
            await writer.drain()
    except Exception:                              # one phone's broken request never stops the listener
        pass
    finally:
        try:
            head_s = getattr(phones, "HEAD_S", HEAD_S)
            if not writer.is_closing():
                await asyncio.wait_for(writer.drain(), head_s)
            writer.close()
        except Exception:
            pass
