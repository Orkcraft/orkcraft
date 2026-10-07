"""A phone in a terminal: the reference client for the phone listener (docs/design/mobile.md, stage 1).

There is no phone app yet; this speaks the same protocol one will, so pairing, the compact town and
what a phone may send can be tried from another machine on the same Wi-Fi (or this one):

    python tools/phone.py pair 'orkcraft://pair?v=1&addr=…&fp=…&code=…' --name "My laptop"
    python tools/phone.py glance             # the town, small: spend, quotas, the questions that wait
    python tools/phone.py answer <id> <key>  # answer a question (one of its own answers only)
    python tools/phone.py follow <id>        # send the Elders' advice as your answer
    python tools/phone.py halt               # stop all (asks first)
    python tools/phone.py send <command> '<json args>'   # anything else: the listener refuses what a phone may not

Settings → Phones → Pair a phone shows the QR code; its text is the link `pair` takes (any QR reader
shows it). The client pins the certificate's fingerprint from that link, as an app does: it trusts no
CA and refuses a town whose certificate differs. What pairing gives it (the address, the fingerprint
and the device token) is kept in `~/.orkcraft-phone.json` (0600), or `--keep FILE`.

Needs `pip install websockets`.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.client
import json
import os
import ssl
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.client import connect

API = 1


def pinned() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE   # no CA: the fingerprint below decides
    return ctx


def fingerprint(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest().upper()


def https(addr: str, fp: str, method: str, path: str, token: str = "", body: dict | None = None) -> tuple[int, dict]:
    parts = urlsplit(addr)
    conn = http.client.HTTPSConnection(parts.hostname, parts.port, context=pinned(), timeout=10)
    try:
        conn.connect()
        if fingerprint(conn.sock.getpeercert(binary_form=True)) != fp.upper():
            sys.exit("The town's certificate is not the one the QR code named: not sending anything.")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        raw = r.read()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, {"error": raw.decode(errors="replace")}
    finally:
        conn.close()


def pair(args) -> None:
    q = parse_qs(urlsplit(args.link).query)
    addr, fp, code = q.get("addr", [""])[0], q.get("fp", [""])[0], q.get("code", [""])[0]
    if not (addr and fp and code):
        sys.exit("That is not a pairing link: it needs addr, fp and code")
    status, version = https(addr, fp, "GET", "/api/version", token=code)
    if status != 200:
        sys.exit(f"The town said {status} to the version check: show a new code and try again")
    if version.get("api") != API:
        sys.exit(f"This client speaks api {API}, the town {version.get('api')}")
    status, body = https(addr, fp, "POST", "/api/pair", body={"code": code, "name": args.name})
    if status != 200:
        sys.exit(f"Not paired ({status}): {body.get('error', '')}")
    keep = Path(args.keep).expanduser()
    fd = os.open(keep, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"addr": addr, "fp": fp, "token": body["token"], "id": body["id"], "name": body["name"]}, f)
    print(f"Paired as {body['name']!r} with Orkcraft {version['version']} at {addr}")


def kept(args) -> dict:
    try:
        return json.loads(Path(args.keep).expanduser().read_text())
    except (OSError, ValueError):
        sys.exit("Not paired: run `phone.py pair <link>` first")


async def session(args, name: str, cmd_args: dict) -> None:
    k = kept(args)
    url = k["addr"].replace("https://", "wss://") + "/ws"
    async with connect(url, ssl=pinned(), additional_headers={"Authorization": f"Bearer {k['token']}"},
                       max_size=8 * 2**20) as ws:
        sock = ws.transport.get_extra_info("ssl_object")
        if fingerprint(sock.getpeercert(binary_form=True)) != k["fp"].upper():
            sys.exit("The town's certificate changed since pairing: not sending anything.")
        state = json.loads(await ws.recv())["state"]
        if name == "glance":
            show(state)
            return
        await ws.send(json.dumps({"t": "cmd", "id": 1, "name": name, "args": cmd_args}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("t") == "reply" and msg.get("id") == 1:
                print(json.dumps(msg["result"], indent=2, ensure_ascii=False) if msg["ok"] else f"Refused: {msg['error']}")
                return


def show(s: dict) -> None:
    hud, words = s["hud"], s.get("resources") or {}
    print(f"{s['project']}{' (demo)' if s['demo'] else ''} · {words.get('gold', 'Spend')} {hud.get('gold')} "
          f"[{hud.get('gold_level')}] · {words.get('quota', 'Quota')} {hud.get('quota')} [{hud.get('quota_level')}] · "
          f"{hud.get('agents_working')}/{hud.get('agents')} working")
    for b in s["buildings"]:
        print(f"  {b['title_plain']:<28} {b['type']:<12} {b['state']}{'  ← asks' if b['alert'] else ''}")
    for a in s["alerts"]:
        print(f"\n? {a['who']}: {a['title']}   (id {a['id']}, waited {int(a['waited'])} s)")
        for line in a["context"]:
            print(f"    {line}")
        print("    answers: " + ", ".join(f"{k} = {v}" for k, v in a["options"]))
        if a["advice"]:
            print(f"    the Elders advise {a['advice']['key']}: {a['advice']['why']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="~/.orkcraft-phone.json", help="where the pairing is kept")
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("pair")
    p.add_argument("link")
    p.add_argument("--name", default="Terminal phone")
    sub.add_parser("glance")
    a = sub.add_parser("answer")
    a.add_argument("id")
    a.add_argument("key")
    f = sub.add_parser("follow")
    f.add_argument("id")
    sub.add_parser("halt")
    s = sub.add_parser("send")
    s.add_argument("command")
    s.add_argument("json", nargs="?", default="{}")
    args = ap.parse_args()
    if args.what == "pair":
        pair(args)
    elif args.what == "glance":
        asyncio.run(session(args, "glance", {}))
    elif args.what == "answer":
        asyncio.run(session(args, "orders.answer", {"id": args.id, "key": args.key}))
    elif args.what == "follow":
        asyncio.run(session(args, "orders.follow", {"id": args.id}))
    elif args.what == "halt":
        if input("Stop every ork in the town? [y/N] ").strip().lower() == "y":
            asyncio.run(session(args, "halt", {}))
    else:
        asyncio.run(session(args, args.command, json.loads(args.json)))


if __name__ == "__main__":
    main()
