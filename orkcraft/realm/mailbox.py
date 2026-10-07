"""The Mail Watcher's mailbox: IMAP, read-only, standard library only.

Settings name the server and the environment variables that hold the login — never the password
itself (the Town Hall's Warder flags a spec that does):

    host  imap.example.com     user_env  MAIL_USER     password_env  MAIL_PASSWORD
    port  993 (SSL)            folder    INBOX

`host: gmail` (or `yandex`, `icloud`) names the provider's server; Gmail wants an app password
(Google account → Security → App passwords) and IMAP turned on.

The mailbox is opened read-only and bodies are fetched with PEEK, so watching never marks a
message as read.
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from orkcraft.realm import logins

LOOK_LIMIT = 20
PROVIDERS = {"gmail": "imap.gmail.com", "yandex": "imap.yandex.com", "icloud": "imap.mail.me.com"}
SNIPPET = 200


@dataclass
class Message:
    uid: int
    sender: str
    subject: str
    date: str = ""
    unread: bool = False
    snippet: str = ""

    def text(self) -> str:
        return f"From: {self.sender}\nSubject: {self.subject}\n\n{self.snippet}".rstrip()


@dataclass
class Look:
    unread: int = 0
    messages: list[Message] = field(default_factory=list)     # newest first
    error: str = ""


def credentials(cfg: dict) -> tuple[str, int, str, str, str]:
    host = str(cfg.get("host", "")).strip()
    host = PROVIDERS.get(host.lower(), host)
    if not host:
        raise ValueError("set `host` in the building's settings")
    user_env, pw_env = str(cfg.get("user_env", "")), str(cfg.get("password_env", ""))
    # the address is no secret: `user` holds it as written; `user_env` / `password_env` name a variable or a login
    user = str(cfg.get("user") or "").strip() or logins.resolve(user_env)
    password = logins.resolve(pw_env)
    for name, value in ((user_env or "user", user), (pw_env or "password_env", password)):
        if not value:
            raise ValueError(f"the login {name[len(logins.PREFIX):]} is gone — log in again" if logins.is_ref(name)
                             else f"set {name} in the environment")
    return host, int(cfg.get("port") or 993), user, password, str(cfg.get("folder") or "INBOX")


def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value or "")))
    except (ValueError, LookupError):
        return value or ""


def _sender(value: str) -> str:
    name, addr = parseaddr(_decode(value))
    return name or addr or "(unknown)"


def _snippet(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    keep = [ln for ln in text.splitlines()
            if ln.strip() and not ln.startswith(("--", "Content-", "content-")) and not re.match(r"^[A-Za-z0-9+/=]{60,}$", ln)]
    return re.sub(r"\s+", " ", " ".join(keep)).strip()[:SNIPPET]


def _open(cfg: dict, factory):
    host, port, user, password, folder = credentials(cfg)
    conn = factory(host, port)
    conn.login(user, password)
    typ, data = conn.select(f'"{folder}"' if " " in folder else folder, readonly=True)
    if typ != "OK":
        conn.logout()
        raise RuntimeError(f"cannot open {folder}")
    return conn


def look(cfg: dict, factory=imaplib.IMAP4_SSL, limit: int = LOOK_LIMIT) -> Look:
    try:
        conn = _open(cfg, factory)
    except (ValueError, RuntimeError) as e:
        return Look(error=str(e))
    except (imaplib.IMAP4.error, OSError) as e:
        return Look(error=f"IMAP: {e}"[:200])
    try:
        out = Look()
        _, unseen = conn.uid("search", None, "UNSEEN")
        unseen_uids = {int(x) for x in (unseen[0] or b"").split()}
        out.unread = len(unseen_uids)
        _, everything = conn.uid("search", None, "ALL")
        uids = [int(x) for x in (everything[0] or b"").split()][-limit:]
        for uid in reversed(uids):
            _, data = conn.uid("fetch", str(uid), "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            header = data[0][1] if data and isinstance(data[0], tuple) else b""
            msg = email.message_from_bytes(header or b"")
            unread = uid in unseen_uids
            date = ""
            try:
                date = parsedate_to_datetime(msg.get("Date", "")).strftime("%d %b %H:%M")
            except (TypeError, ValueError):
                pass
            snippet = ""
            if unread:
                _, body = conn.uid("fetch", str(uid), "(BODY.PEEK[TEXT]<0.1200>)")
                if body and isinstance(body[0], tuple):
                    snippet = _snippet(body[0][1] or b"")
            out.messages.append(Message(uid, _sender(msg.get("From", "")), _decode(msg.get("Subject", "")) or
                                        "(no subject)", date, unread, snippet))
        return out
    except (imaplib.IMAP4.error, OSError) as e:
        return Look(error=f"IMAP: {e}"[:200])
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def read(cfg: dict, uid: int, factory=imaplib.IMAP4_SSL) -> str:
    """The message as text (its plain part), without marking it read."""
    conn = _open(cfg, factory)
    try:
        _, data = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
        raw = data[0][1] if data and isinstance(data[0], tuple) else b""
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    msg = email.message_from_bytes(raw or b"", policy=email.policy.default)
    part = msg.get_body(preferencelist=("plain", "html")) if hasattr(msg, "get_body") else None
    body = part.get_content() if part is not None else ""
    if part is not None and part.get_content_type() == "text/html":
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"[ \t]+", " ", body)
    head = f"**{_decode(str(msg.get('Subject', '')))}**\n\nfrom {_decode(str(msg.get('From', '')))} · {msg.get('Date', '')}"
    return f"{head}\n\n---\n\n{body.strip()}"


def new_since(last_uid: int | None, look_: Look) -> list[Message]:
    """Messages above the last seen uid, oldest first (none on the first look)."""
    if last_uid is None:
        return []
    return sorted((m for m in look_.messages if m.uid > last_uid), key=lambda m: m.uid)
