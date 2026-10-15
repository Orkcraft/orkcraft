"""📍 A phone's place report, from the phone listener to the Watchtower that knows the place
(docs/design/phone-places.md §3).

    POST /api/place  {"id", "place", "change", "at"}   (gui/phones.py: a device token, at most 1 KB)
    place.report     the same as a phone's command over its socket (gui/mobile.py COMMANDS)

The device it came from is the listener's to say (`mobile.guard`), never the report's. A place no tower
knows is refused with what the phone is told; a report every tower knows goes to each of them.
"""
from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from typing import Any

from orkcraft.realm import places

TOWER = "watchtower"
LIMIT = 1024             # POST /api/place's body
RATE = 6 / 60.0          # place reports a second a device may send (six a minute)…
BURST = 6.0              # …and at most this many at once


def towers(host) -> list:
    """The Watchtower workers of the town, each with its places."""
    out = []
    for b in (host.town.scroll.buildings if host.town.scroll is not None else []):
        if b.demolished or host.type_of(b.id) != TOWER:
            continue
        w = host.town.worker(b.id)
        if w is not None and getattr(w, "desk", None) is not None:
            out.append(w)
    return out


def names(host) -> list[str]:
    """Every place the town's towers know, each once (`mobile.hello` gives them to the app)."""
    return list(dict.fromkeys(n for w in towers(host) for n in w.desk.names))


def report(host, args: dict) -> dict[str, Any]:
    """A phone came to a place or left it: {"outcome": sent · asked · waiting · stale · no road · refused}."""
    from orkcraft.gui.host import CommandError          # host imports this module (through mobile)
    known = names(host)
    try:
        r = places.check(args, known, str(args.get("device") or ""), str(args.get("device_id") or ""))
    except places.PlaceError as e:
        raise CommandError(str(e)) from None
    outcomes = [w.report_place(r) for w in towers(host) if r.place in w.desk.names]
    order = ("sent", "waiting", "asked", "no road", "stale", "refused")
    return {"outcome": min(outcomes, key=lambda o: order.index(o) if o in order else len(order))}


async def post(listener, method: str, headers: dict[str, str], reader: asyncio.StreamReader) -> bytes:
    """`POST /api/place` on the phone listener (gui/phones.py): a report from a client that speaks no socket
    (Shortcuts, Tasker): a device token, JSON, 1 KB, six a minute a device."""
    from orkcraft.gui import mobile
    from orkcraft.gui.host import CommandError
    from orkcraft.gui.pairing import Bucket
    from orkcraft.gui.phones import HEAD_S, _bearer, _json, _response
    if method != "POST":
        return _response(HTTPStatus.METHOD_NOT_ALLOWED)
    device = listener.pairing.device(_bearer(headers.get("authorization", "")))
    if device is None:
        return _response(HTTPStatus.FORBIDDEN)
    if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return _response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
    try:
        length = int(headers.get("content-length", ""))
    except ValueError:
        return _response(HTTPStatus.LENGTH_REQUIRED)
    if not 0 < length <= LIMIT or "transfer-encoding" in headers:
        return _response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    bucket = listener._place_buckets.setdefault(device["id"], Bucket(RATE, BURST, BURST))
    if not bucket.take():
        return _json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Too many place reports: wait a minute"})
    try:
        body = json.loads(await asyncio.wait_for(reader.readexactly(length), HEAD_S))
    except (ValueError, asyncio.IncompleteReadError, TimeoutError):
        return _json(HTTPStatus.BAD_REQUEST, {"error": "Not a place report"})
    if not isinstance(body, dict):
        return _json(HTTPStatus.BAD_REQUEST, {"error": "Not a place report"})
    listener.pairing.seen(device["id"])
    try:
        result = listener.host.command("place.report", mobile.guard("place.report", body, device))
    except CommandError as e:
        return _json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
    return _json(HTTPStatus.OK, result)
