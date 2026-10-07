"""A direct path for what a carrier sent: the service's own API (or SMTP) with a token of your own.

    derive("slack", "mcp__slack__post_message", template)   → [route, …] the recipes that fit, best first
    needs(route)                                             → the environment variables it reads
    send(route, cart)                                        → (Shot, kind): kind "" ok, "auth", "path", "other"
    preview(route, cart)                                     → the request as text, its secrets masked

A route is plain JSON: `method`, `url` (with `{@arg}` from the cart and `{$ENV}` from the environment)
or `url_env` (the whole address is the secret, a webhook), `auth`, `headers`, `body` — a template over
the cart (templates.py) — and `ok`, a path of the answer that must be true (Slack answers 200 with
`"ok": false`). `transport: smtp` sends a mail instead. Recipes (recipes/<service>.json) are data: a
seventh service is one file. A token is read when a shot fires and never written anywhere.
"""
from __future__ import annotations

import base64
import copy
import datetime as dt
import json
import os
import re
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from orkcraft.realm import catapult as cp
from orkcraft.realm.catapult_mcp import templates as tp

RECIPES = Path(__file__).parent / "recipes"
SEND_TIMEOUT_S = 20
_DROP = object()
AUTH_ERRORS = ("invalid_auth", "not_authed", "token_revoked", "token_expired", "missing_scope", "account_inactive")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def recipes() -> list[dict]:
    out = []
    for f in sorted(RECIPES.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("tools"):
            out.append(data)
    return out


def short_tool(tool: str) -> str:
    """`mcp__slack__post_message` → `post_message`."""
    parts = tool.split("__")
    return parts[-1] if len(parts) >= 3 and parts[0] == "mcp" else tool


def services_of(server: str, tool: str) -> list[dict]:
    key, name = _norm(server), _norm(short_tool(tool))
    return [r for r in recipes() if any(_norm(m) in key or _norm(m) in name for m in r.get("match") or [])]


def _arg_map(spec: dict, args: dict) -> dict[str, str]:
    """The recipe's names → the recorded call's argument names, by the recipe's aliases."""
    actual = {_norm(a): a for a in args}
    out = {}
    for name, aliases in (spec.get("args") or {}).items():
        for alias in aliases:
            if _norm(alias) in actual:
                out[name] = actual[_norm(alias)]
                break
    return out


def _fill(node, slots: dict):
    """A recipe's body with `@name` / `@name?` replaced by the call's template nodes."""
    if isinstance(node, str) and node.startswith("@"):
        name, optional = node[1:].rstrip("?"), node.endswith("?")
        if name in slots:
            return copy.deepcopy(slots[name])
        if optional:
            return _DROP
        raise KeyError(name)
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            filled = _fill(v, slots)
            if filled is not _DROP:
                out[k] = filled
        return out
    if isinstance(node, list):
        out = []
        for v in node:
            filled = _fill(v, slots)
            if filled is not _DROP and not _holds_drop(v, slots):
                out.append(filled)
        return out
    return node


def _holds_drop(node, slots: dict) -> bool:
    """An optional slot that is missing anywhere inside a list item drops the whole item."""
    if isinstance(node, str) and node.startswith("@") and node.endswith("?"):
        return node[1:-1] not in slots
    if isinstance(node, dict):
        return any(_holds_drop(v, slots) for v in node.values())
    if isinstance(node, list):
        return any(_holds_drop(v, slots) for v in node)
    return False


def _routes_of(recipe: dict, spec: dict, args: dict, names: dict[str, str]) -> list[dict]:
    given = {k: args[a] for k, a in names.items()}
    if any(n not in given for n in spec.get("need") or []):
        return []
    out = []
    for r in spec.get("routes") or []:
        slots = {**(spec.get("defaults") or {}), **(r.get("defaults") or {}), **given}
        route = {k: v for k, v in r.items() if k not in ("body", "message", "defaults")}
        try:
            if "body" in r:
                route["body"] = _fill(r["body"], slots)
            if "message" in r:
                route["message"] = _fill(r["message"], slots)
            route["url_args"] = {m: copy.deepcopy(slots[m]) for m in re.findall(r"\{@(\w+)\}", str(r.get("url") or ""))}
        except KeyError:
            continue
        route.update(service=recipe["service"], what=spec.get("what", ""))
        out.append(route)
    return out


MAPPER = """You match the arguments of a tool call to a service's API. Say which of the API's actions the
tool call is, and which argument fills each of the API's names. Use only argument names that are listed.

The tool: {tool}
Its arguments: {args}

The API's actions (index: what — its names):
{specs}

Answer with JSON only: {{"action": <index or null>, "args": {{"<API name>": "<argument name>", …}}}}"""


def derive(server: str, tool: str, args, runner: Callable | None = None) -> tuple[list[dict], float]:
    """The direct routes a recipe gives for a recorded call (its arguments as a template), best
    first; with `runner`, a model matches the names once when the recipe's own names do not fit
    (it sees the tool's and the arguments' names, never their values). Returns (routes, cost)."""
    if not isinstance(args, dict):
        return [], 0.0
    name = _norm(short_tool(tool))
    found, cost = [], 0.0
    for recipe in services_of(server, tool):
        specs = recipe["tools"]
        for spec in specs:
            if any(_norm(m) in name for m in spec.get("match") or []):
                found += _routes_of(recipe, spec, args, _arg_map(spec, args))
        if found or runner is None:
            continue
        listing = "\n".join(f"{i}: {s.get('what', '')} — {', '.join(s.get('args') or {})}" for i, s in enumerate(specs))
        try:
            text, c = runner(MAPPER.format(tool=short_tool(tool), args=", ".join(args), specs=listing), "haiku")
            cost += c or 0.0
        except Exception:
            continue
        from orkcraft.realm.builders import extract_json
        answer = extract_json(text) or {}
        i = answer.get("action")
        names = answer.get("args") if isinstance(answer.get("args"), dict) else {}
        if isinstance(i, int) and 0 <= i < len(specs):
            spec = specs[i]
            names = {k: v for k, v in names.items() if k in (spec.get("args") or {}) and v in args}
            found += _routes_of(recipe, spec, args, names)
    return found, cost


def needs(route: dict) -> list[str]:
    """Every environment variable the route reads, in order."""
    out = []
    auth = route.get("auth") or {}
    for key in ("url_env",):
        if route.get(key):
            out.append(route[key])
    out += re.findall(r"\{\$(\w+)\}", str(route.get("url") or ""))
    out += [auth[k] for k in ("user_env", "env") if auth.get(k)]
    out += list((route.get("env") or {}).values()) + list((route.get("body_env") or {}).values())
    return list(dict.fromkeys(out))


def missing(route: dict, environ=None) -> list[str]:
    environ = os.environ if environ is None else environ
    return [n for n in needs(route) if not environ.get(n)]


def title(route: dict) -> str:
    return str(route.get("title") or route.get("service") or "direct")


def _url(route: dict, cart, environ, masked: bool) -> str:
    if route.get("url_env"):
        return f"${route['url_env']}" if masked else str(environ.get(route["url_env"], ""))
    url = str(route.get("url") or "")
    url = re.sub(r"\{\$(\w+)\}", lambda m: str(environ.get(m.group(1), f"${m.group(1)}")).rstrip("/"), url)
    for name, node in (route.get("url_args") or {}).items():
        url = url.replace("{@" + name + "}", urllib.parse.quote(str(tp.render(node, cart)), safe=""))
    return url


def _body(route: dict, cart, environ) -> dict:
    body = tp.render(route.get("body") or {}, cart)
    for key, env in (route.get("body_env") or {}).items():
        body[key] = environ.get(env, "")
    return body


def _headers(route: dict, environ, masked: bool) -> dict[str, str]:
    out = {"Content-Type": "application/json", "User-Agent": "orkcraft-catapult", **(route.get("headers") or {})}
    auth = route.get("auth") or {}
    secret = "…" if masked else environ.get(str(auth.get("env") or ""), "")
    kind = auth.get("kind")
    if kind == "bearer":
        out["Authorization"] = f"Bearer {secret}"
    elif kind == "basic":
        user = environ.get(str(auth.get("user_env") or ""), "")
        out["Authorization"] = "Basic …" if masked else "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()
    elif kind == "header":
        out[str(auth.get("header") or "Authorization")] = f"{auth.get('prefix', '')}{secret}"
    return out


def preview(route: dict, cart, environ=None) -> str:
    """What a shot would send, as text: the address, the headers and the body; secrets masked."""
    environ = os.environ if environ is None else environ
    if route.get("transport") == "smtp":
        msg = tp.render(route.get("message") or {}, cart)
        return f"SMTP ${(route.get('env') or {}).get('host', 'SMTP_HOST')}\n" + json.dumps(msg, ensure_ascii=False, indent=2)
    head = "\n".join(f"{k}: {v}" for k, v in _headers(route, environ, True).items())
    return (f"{route.get('method') or 'POST'} {_url(route, cart, environ, True)}\n{head}\n\n"
            + json.dumps(_body(route, cart, environ), ensure_ascii=False, indent=2))


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _answer_ok(route: dict, answer: str) -> tuple[bool, str]:
    path = route.get("ok")
    if not path:
        return True, ""
    try:
        data = json.loads(answer)
        value = tp.pick(data, path)
    except (ValueError, tp.Missing):
        return False, f"the answer has no {path}"
    if value:
        return True, ""
    return False, str(data.get("error") or f"{path} is false") if isinstance(data, dict) else f"{path} is false"


def send(route: dict, cart, environ=None, opener=urllib.request.urlopen, smtp: Callable | None = None) -> tuple[cp.Shot, str]:
    """Fire the route with this cart: (the shot, why it failed — "" ok, "auth" the token is refused,
    "path" the service refused what was sent, "other" the network or the service itself)."""
    environ = os.environ if environ is None else environ
    gone = missing(route, environ)
    try:
        if route.get("transport") == "smtp":
            if gone:
                return cp.Shot(_now(), False, 0, "SMTP", "", error="not set: " + ", ".join(gone)), "auth"
            return _send_smtp(route, cart, environ, smtp or _smtp)
        url, shown = _url(route, cart, environ, False), _url(route, cart, environ, True)
        body = _body(route, cart, environ)
    except tp.Missing as e:
        return cp.Shot(_now(), False, 0, str(route.get("url") or route.get("url_env") or ""), "", error=str(e)), "path"
    sent = json.dumps(body, ensure_ascii=False)[:cp.ANSWER_KEEP]
    if gone:
        return cp.Shot(_now(), False, 0, shown, sent, error="not set: " + ", ".join(gone)), "auth"
    if not url.startswith(("http://", "https://")):
        return cp.Shot(_now(), False, 0, shown, sent, error="the address is not http or https"), "other"
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), method=route.get("method") or "POST",
                                 headers=_headers(route, environ, False))
    try:
        with opener(req, timeout=SEND_TIMEOUT_S) as resp:
            status = getattr(resp, "status", 200)
            answer = resp.read(cp.ANSWER_KEEP).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        answer = e.read(cp.ANSWER_KEEP).decode("utf-8", errors="replace")
        kind = "auth" if e.code in (401, 403) else "path" if e.code in (400, 404, 409, 422) else "other"
        return cp.Shot(_now(), False, e.code, shown, sent, answer, f"HTTP {e.code}"), kind
    except Exception as e:  # the network and bad addresses, of every kind
        return cp.Shot(_now(), False, 0, shown, sent, error=str(e)[:300]), "other"
    ok, why = _answer_ok(route, answer)
    if not ok:
        return cp.Shot(_now(), False, status, shown, sent, answer, why), "auth" if why in AUTH_ERRORS else "path"
    return cp.Shot(_now(), 200 <= status < 300, status, shown, sent, answer), "" if 200 <= status < 300 else "other"


def _smtp(host: str, port: int):
    return smtplib.SMTP_SSL(host, port, timeout=SEND_TIMEOUT_S) if port == 465 else smtplib.SMTP(host, port, timeout=SEND_TIMEOUT_S)


def _send_smtp(route: dict, cart, environ, factory) -> tuple[cp.Shot, str]:
    env = route.get("env") or {}
    msg_t = tp.render(route.get("message") or {}, cart)
    host, port = environ[env["host"]], int(environ.get(str(route.get("port_env") or ""), "") or 587)
    to = msg_t.get("to")
    to = [str(x) for x in to] if isinstance(to, list) else [s.strip() for s in str(to or "").split(",") if s.strip()]
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = environ[env["from"]], ", ".join(to), str(msg_t.get("subject") or "")
    if msg_t.get("cc"):
        cc = msg_t["cc"]
        msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else str(cc)
    msg.set_content(str(msg_t.get("text") or ""))
    sent = json.dumps(msg_t, ensure_ascii=False)[:cp.ANSWER_KEEP]
    shown = f"SMTP {host}:{port}"
    try:
        with factory(host, port) as s:
            if port != 465:
                s.starttls()
            s.login(environ[env["user"]], environ[env["password"]])
            refused = s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        return cp.Shot(_now(), False, e.smtp_code, shown, sent, error="the mail server refused the login"), "auth"
    except smtplib.SMTPRecipientsRefused as e:
        return cp.Shot(_now(), False, 550, shown, sent, error=f"refused: {', '.join(e.recipients)}"), "path"
    except Exception as e:
        return cp.Shot(_now(), False, 0, shown, sent, error=str(e)[:300]), "other"
    if refused:
        return cp.Shot(_now(), False, 550, shown, sent, error=f"refused: {', '.join(refused)}"), "path"
    return cp.Shot(_now(), True, 250, shown, sent, f"sent to {', '.join(to)}"), ""
