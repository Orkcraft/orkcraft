"""A personal Google account: one sign-in for Gmail, Calendar and Drive (docs/design/google-account.md).

The person makes their own OAuth client in Google Cloud (a Desktop app, published "In production" and never
verified: Google lets an unverified app sign in the person who made it), pastes its id and secret here, and
signs in once in the browser. The sign-in comes back to this machine (`http://127.0.0.1:<port>`, PKCE), and
what it gives is kept as logins (realm/logins.py): the client as `google-client`, each account as
`google-<e-mail>` — the refresh token and the parts Google allowed, never in the project. Read-only for mail
and Drive; the calendar may add events:

    SCOPES["gmail"]     gmail.readonly    External listeners hear the inbox
    SCOPES["calendar"]  calendar.events   the Calendar shows the week and adds an event
    SCOPES["drive"]     drive.readonly    the Wiki reads Drive (Docs as Markdown, text files as they are)

    save_client("123-abc.apps.googleusercontent.com", "GOCSPX-…")
    c = Consent(parts=("gmail", "calendar", "drive")); c.start()   # c.url opens in the browser
    c.state == "done"; c.account == {"email": "ann@gmail.com", "parts": [...], "ref": "keychain:google-ann@gmail.com"}
    gmail_messages("keychain:google-ann@gmail.com", "in:inbox newer_than:2d")
    disconnect("ann@gmail.com")          # revoked at Google, forgotten here

Every failure is a `GoogleError` that says in plain words what happened and what to do, and which of three it
is (`kind`, as realm/feeds.py's): `login` (sign in again), `target` (turn an API on, pick another folder) or
`network`. No model, no bus, no face. Standard library only.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from orkcraft.realm import logins

SCOPES = {"gmail": "https://www.googleapis.com/auth/gmail.readonly",
          "calendar": "https://www.googleapis.com/auth/calendar.events",
          "drive": "https://www.googleapis.com/auth/drive.readonly"}
PARTS = tuple(SCOPES)
WHAT = {"gmail": "read your mail", "calendar": "see and add calendar events", "drive": "read your Drive"}
IDENTITY = ("openid", "email")          # the address the account is kept under
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
REVOKE = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com"
CLIENT = "google-client"                # the login that keeps the OAuth client
SERVICE = "google"                      # the logins' service of an account
CLIENT_ID = re.compile(r"^[0-9]{6,}-[a-z0-9]{8,}\.apps\.googleusercontent\.com$")
CLIENT_SECRET = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
TIMEOUT_S = 20
WAIT_S = 600                            # how long a sign-in waits for the browser to come back
APIS = {"gmail": "gmail.googleapis.com", "calendar": "calendar-json.googleapis.com", "drive": "drive.googleapis.com"}
CONSOLE = "https://console.cloud.google.com"
LINKS = {                                # the wizard's steps, straight to the console's pages
    "project": f"{CONSOLE}/projectcreate",
    "apis": f"{CONSOLE}/flows/enableapi?apiid=" + ",".join(APIS.values()),
    "branding": f"{CONSOLE}/auth/branding",
    "audience": f"{CONSOLE}/auth/audience",
    "client": f"{CONSOLE}/auth/clients/create",
    "access": "https://myaccount.google.com/connections",
}
FALLBACK = ("Without a Google sign-in: hear Gmail with an app password (External listeners → Add a source → "
            "Gmail), and show the calendar from its secret address in iCal format (Google Calendar → Settings → "
            "your calendar → Integrate calendar), read-only.")


class GoogleError(Exception):
    """What went wrong, said plainly, and which of the three failures it is (login, target, network)."""

    def __init__(self, text: str, kind: str = "network") -> None:
        super().__init__(text)
        self.kind = kind if kind in ("login", "target", "network") else "network"


# -- the client and the accounts (realm/logins.py) --------------------------------------------------------

def parse_client(text: str, secret: str = "") -> tuple[str, str]:
    """(id, secret) from what was pasted: the id and the secret, or the whole JSON file Google gives."""
    text = (text or "").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            raise GoogleError("That is not the client's JSON file: paste the file Google gave, or its id and "
                              "secret", "target") from None
        data = data if isinstance(data, dict) else {}
        if data.get("web"):
            raise GoogleError("That client is a Web application: make one of type Desktop app", "target")
        inner = data.get("installed") or data
        text, secret = str(inner.get("client_id") or ""), str(inner.get("client_secret") or "")
    cid, secret = text.strip(), (secret or "").strip()
    if not CLIENT_ID.match(cid):
        raise GoogleError("The client id ends in .apps.googleusercontent.com: copy it from Google Cloud → "
                          "Clients", "target")
    if not CLIENT_SECRET.match(secret):
        raise GoogleError("Paste the client secret too (it starts with GOCSPX-)", "target")
    return cid, secret


def save_client(client_id: str, secret: str = "") -> str:
    cid, sec = parse_client(client_id, secret)
    return logins.save(CLIENT, json.dumps({"id": cid, "secret": sec}), CLIENT, cid.split("-", 1)[0])


def client() -> dict:
    """{"id", "secret"} of the OAuth client kept here, or {}."""
    try:
        data = json.loads(logins.get(CLIENT) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) and data.get("id") and data.get("secret") else {}


def forget_client() -> bool:
    return logins.remove(CLIENT)


def login_name(email: str) -> str:
    return "google-" + re.sub(r"[^a-z0-9._@+-]", "-", (email or "").strip().lower())[:120]


def ref_of(email: str) -> str:
    return logins.PREFIX + login_name(email)


def _account(ref: str) -> dict:
    try:
        data = json.loads(logins.resolve(ref) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def accounts() -> list[dict]:
    """Every account signed in here: e-mail, the parts Google allowed, its login reference, when — no token."""
    out = []
    for entry in logins.listed(SERVICE):
        ref = logins.PREFIX + entry["name"]
        data = _account(ref)
        out.append({"email": entry["account"] or data.get("email", ""), "ref": ref, "saved": entry["saved"],
                    "parts": [p for p in PARTS if p in (data.get("parts") or [])], "where": entry["where"]})
    return out


def parts_of(ref: str) -> list[str]:
    return [p for p in PARTS if p in (_account(ref).get("parts") or [])]


# -- HTTP ---------------------------------------------------------------------------------------------------

def _post(url: str, form: dict, opener=None) -> dict:
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "orkcraft"})
    try:
        with opener(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", errors="replace") or "{}")
        except (ValueError, OSError):
            body = {}
        raise _token_error(str(body.get("error") or e.code), str(body.get("error_description") or "")) from None
    except (urllib.error.URLError, OSError) as e:
        raise GoogleError(f"Could not reach Google ({getattr(e, 'reason', e)}); it tries again later") from None


def _token_error(code: str, about: str) -> GoogleError:
    if code == "invalid_grant":
        return GoogleError("Google no longer accepts this sign-in: it was removed in your Google account, your "
                           "password changed, or it was not used for six months. Connect Google again", "login")
    if code in ("invalid_client", "unauthorized_client"):
        return GoogleError("Google does not know this client: check the client id and secret in Settings → "
                           "Accounts, or make the client again", "login")
    if code in ("admin_policy_enforced", "org_internal"):
        return GoogleError("This Google account's admin does not allow this app. " + FALLBACK, "login")
    if code == "invalid_scope":
        return GoogleError("Google refused one of the parts asked for. " + FALLBACK, "login")
    return GoogleError(f"Google refused the sign-in: {code}{f' ({about})' if about else ''}", "login")


_tokens: dict[str, tuple[str, float]] = {}       # ref → (access token, when it runs out), for the app's life
_lock = threading.Lock()


def access_token(ref: str, opener=None, fresh: bool = False) -> str:
    """A short-lived token for the account under `ref`, from its refresh token (one call an hour)."""
    with _lock:
        held = _tokens.get(ref)
    if held and not fresh and held[1] > time.time() + 60:
        return held[0]
    acc = _account(ref)
    if not acc.get("refresh"):
        name = ref[len(logins.PREFIX):] if logins.is_ref(ref) else ref
        raise GoogleError(f"The Google sign-in {name.removeprefix('google-')} is gone: connect Google again "
                          "(Settings → Accounts)", "login")
    c = client()
    if not c:
        raise GoogleError("The Google Cloud client is gone: add it again in Settings → Accounts", "login")
    got = _post(TOKEN, {"client_id": c["id"], "client_secret": c["secret"], "refresh_token": acc["refresh"],
                        "grant_type": "refresh_token"}, opener)
    token = str(got.get("access_token") or "")
    if not token:
        raise GoogleError("Google gave no token; it tries again later")
    with _lock:
        _tokens[ref] = (token, time.time() + float(got.get("expires_in") or 3600))
    return token


def _api_error(e: urllib.error.HTTPError, part: str) -> GoogleError:
    try:
        err = json.loads(e.read().decode("utf-8", errors="replace") or "{}").get("error") or {}
    except (ValueError, OSError, AttributeError):
        err = {}
    err = err if isinstance(err, dict) else {"message": str(err)}
    reasons = {str(x.get("reason", "")) for x in err.get("errors") or [] if isinstance(x, dict)}
    for d in err.get("details") or []:
        if isinstance(d, dict) and d.get("reason"):
            reasons.add(str(d["reason"]))
    text = str(err.get("message") or e.reason or "")
    name = {"gmail": "Gmail", "calendar": "Google Calendar", "drive": "Google Drive"}.get(part, "Google")
    if "accessNotConfigured" in reasons or "SERVICE_DISABLED" in reasons or "has not been used in project" in text:
        return GoogleError(f"The {name} API is off in your Google Cloud project: turn it on "
                           f"({CONSOLE}/apis/library/{APIS.get(part, '')}), then wait a minute", "target")
    if e.code == 401:
        return GoogleError(f"{name}: Google did not accept the sign-in; connect Google again", "login")
    if e.code == 403 and ({"insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"} & reasons
                          or "insufficient" in text.lower()):
        return GoogleError(f"This sign-in may not {WHAT.get(part, 'do that')}: connect Google again and leave "
                           f"{name} ticked", "login")
    if e.code == 404:
        return GoogleError(f"{name}: not found ({text[:120]})", "target")
    if e.code == 429 or "rateLimitExceeded" in reasons or "userRateLimitExceeded" in reasons:
        return GoogleError(f"{name}: too many requests; it tries again later")
    return GoogleError(f"{name}: {e.code} {text[:160]}", "login" if e.code == 403 else "network")


def call(ref: str, path: str, part: str, params: dict | None = None, body: dict | None = None,
         method: str = "", raw: bool = False, opener=None):
    """One call of a Google API as the account under `ref`: its JSON (or bytes when `raw`)."""
    opener = opener or urllib.request.urlopen
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params, doseq=True)}" if params else "")
    for attempt in (0, 1):
        head = {"Authorization": f"Bearer {access_token(ref, opener, fresh=attempt == 1)}", "User-Agent": "orkcraft",
                "Accept": "application/json" if not raw else "*/*"}
        data = None
        if body is not None:
            data, head["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(url, data=data, headers=head, method=method or ("POST" if body is not None else "GET"))
        try:
            with opener(req, timeout=TIMEOUT_S) as r:
                got = r.read()
            return got if raw else json.loads(got.decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:          # the hour's token ran out early: once more, fresh
                continue
            raise _api_error(e, part) from None
        except (urllib.error.URLError, OSError) as e:
            raise GoogleError(f"Could not reach Google ({getattr(e, 'reason', e)}); it tries again later") from None
    raise GoogleError("Google did not accept the sign-in; connect Google again", "login")


# -- signing in: the browser comes back to this machine ----------------------------------------------------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def email_of(id_token: str) -> str:
    """The address in the ID token Google's token endpoint just gave (over TLS, so not checked again)."""
    try:
        payload = id_token.split(".")[1]
        return str(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("email") or "")
    except (IndexError, ValueError):
        return ""


PAGE = ("<!doctype html><meta charset=utf-8><title>Orkcraft</title><body style=\"font:16px system-ui;margin:3em;"
        "max-width:36em\"><h1>{title}</h1><p>{text}</p></body>")


class Consent:
    """One sign-in: a listener on 127.0.0.1 for Google's answer, the URL to open, and how it went.

    `state`: waiting → done (`account`) or failed (`error`, said plainly, with the way round it)."""

    def __init__(self, parts: tuple[str, ...] | list[str] = PARTS, opener=None,
                 wait_s: float = WAIT_S) -> None:
        self.parts = [p for p in PARTS if p in parts] or list(PARTS)
        self.opener, self.wait_s = opener, wait_s
        self.state, self.error, self.account = "waiting", "", {}
        c = client()
        if not c:
            raise GoogleError("Add your Google Cloud client first (its id and secret)", "target")
        self._client = c
        self._verifier = _b64(secrets.token_bytes(48))
        self._state = _b64(secrets.token_bytes(24))
        self._done = threading.Event()
        consent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:                       # noqa: N802 - http.server's name
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if q.get("state", [""])[0] != consent._state:
                    self._page(404, "Not this sign-in", "This page belongs to another sign-in. Start again in Orkcraft.")
                    return
                title, text = consent.answer(q.get("code", [""])[0], q.get("error", [""])[0])
                self._page(200, title, text)

            def _page(self, code: int, title: str, text: str) -> None:
                body = PAGE.format(title=_html(title), text=_html(text)).encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:           # nothing on the console
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.redirect = f"http://127.0.0.1:{self._server.server_address[1]}"
        scope = " ".join([*IDENTITY, *(SCOPES[p] for p in self.parts)])
        self.url = AUTH + "?" + urllib.parse.urlencode({
            "client_id": c["id"], "redirect_uri": self.redirect, "response_type": "code", "scope": scope,
            "code_challenge": _b64(hashlib.sha256(self._verifier.encode()).digest()), "code_challenge_method": "S256",
            "state": self._state, "access_type": "offline", "prompt": "consent"})

    def start(self) -> "Consent":
        threading.Thread(target=self._serve, name="google:consent", daemon=True).start()
        return self

    def _serve(self) -> None:
        deadline = time.monotonic() + self.wait_s
        self._server.timeout = 0.5
        try:
            while not self._done.is_set() and time.monotonic() < deadline:
                self._server.handle_request()
        finally:
            self._server.server_close()
        if self.state == "waiting":
            self._fail("No answer from Google in ten minutes. If Google said the app is blocked or not verified "
                       "and gave no way on, Google will not let this client read your mail or Drive. " + FALLBACK)

    def cancel(self) -> None:
        if self.state == "waiting":
            self._fail("Stopped.")

    def _fail(self, text: str) -> None:
        self.state, self.error = "failed", text
        self._done.set()

    def answer(self, code: str, error: str) -> tuple[str, str]:
        """Google's answer: the code is traded for the tokens at once. (title, text) for the browser tab."""
        if self.state != "waiting":
            return "Already done", "Go back to Orkcraft."
        if error or not code:
            why = ("You did not allow it, or Google blocked the app." if error == "access_denied"
                   else f"Google said: {error or 'no code'}.")
            self._fail(f"{why} Nothing was connected. To try again: Settings → Accounts → Connect Google. "
                       f"On Google's warning, click Advanced, then Go to … (unsafe): it is your own client. "
                       + FALLBACK)
            return "Not connected", self.error
        try:
            got = _post(TOKEN, {"client_id": self._client["id"], "client_secret": self._client["secret"],
                                "code": code, "code_verifier": self._verifier, "redirect_uri": self.redirect,
                                "grant_type": "authorization_code"}, self.opener)
            self.account = self._keep(got)
        except GoogleError as e:
            self._fail(str(e))
            return "Not connected", str(e)
        self.state = "done"
        self._done.set()
        names = ", ".join({"gmail": "Gmail", "calendar": "Calendar", "drive": "Drive"}[p] for p in self.account["parts"])
        return "Connected", f"{self.account['email']}: {names}. You can close this tab and go back to Orkcraft."

    def _keep(self, got: dict) -> dict:
        granted = set(str(got.get("scope") or "").split())
        parts = [p for p in self.parts if SCOPES[p] in granted]
        if not got.get("refresh_token"):
            raise GoogleError("Google gave no lasting sign-in. Remove Orkcraft's access in your Google account "
                              f"({LINKS['access']}) and connect again", "login")
        if not parts:
            raise GoogleError("Google allowed none of Gmail, Calendar or Drive (each has its own tick on Google's "
                              "page). Connect again and leave them ticked. " + FALLBACK, "login")
        email = email_of(str(got.get("id_token") or ""))
        if not email:
            raise GoogleError("Google did not say which account signed in; connect again", "login")
        ref = logins.save(login_name(email), json.dumps({"email": email, "refresh": got["refresh_token"], "parts": parts}),
                          SERVICE, email)
        with _lock:
            _tokens[ref] = (str(got.get("access_token") or ""), time.time() + float(got.get("expires_in") or 3600))
        return {"email": email, "parts": parts, "ref": ref,
                "missing": [p for p in self.parts if p not in parts]}

    def snapshot(self) -> dict:
        return {"state": self.state, "error": self.error, "account": self.account, "url": self.url}


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def disconnect(email: str, opener=None) -> bool:
    """Revoke the account's sign-in at Google (when it answers) and forget it here. False when none was kept."""
    ref = ref_of(email)
    refresh = _account(ref).get("refresh")
    if refresh:
        try:
            _post(REVOKE, {"token": refresh}, opener)
        except GoogleError:                     # already revoked, or offline: forgotten here all the same
            pass
    with _lock:
        _tokens.pop(ref, None)
    return logins.remove(login_name(email))


# -- Gmail: External listeners (realm/feeds_google.py) ------------------------------------------------------

def gmail_messages(ref: str, query: str = "in:inbox newer_than:2d", limit: int = 20,
                   opener=None) -> list[dict]:
    """The newest messages that match `query`, newest first: id, thread, from, to, subject, date, snippet, labels."""
    listed = call(ref, "/gmail/v1/users/me/messages", "gmail", {"q": query, "maxResults": limit}, opener=opener)
    out = []
    for m in listed.get("messages") or []:
        got = call(ref, f"/gmail/v1/users/me/messages/{urllib.parse.quote(str(m.get('id', '')))}", "gmail",
                   {"format": "metadata", "metadataHeaders": ["From", "To", "Cc", "Subject", "Date"]}, opener=opener)
        head = {h.get("name", "").lower(): h.get("value", "") for h in (got.get("payload") or {}).get("headers") or []}
        out.append({"id": got.get("id", ""), "thread": got.get("threadId", ""), "from": head.get("from", ""),
                    "to": head.get("to", ""), "cc": head.get("cc", ""), "subject": head.get("subject", ""),
                    "date": head.get("date", ""), "snippet": got.get("snippet", ""),
                    "labels": list(got.get("labelIds") or []), "at": got.get("internalDate", "")})
    return out


def gmail_profile(ref: str, opener=None) -> str:
    return str(call(ref, "/gmail/v1/users/me/profile", "gmail", opener=opener).get("emailAddress") or "")


# -- Calendar: the War Drum ---------------------------------------------------------------------------------

def _local(day: dt.date) -> str:
    return dt.datetime.combine(day, dt.time()).astimezone().isoformat()


def calendar_events(ref: str, start: dt.date, end: dt.date, calendar: str = "primary",
                    opener=None) -> list[dict]:
    """The events from `start` to `end` (inclusive), repeats expanded, as Google gives them."""
    out, token = [], ""
    while len(out) < 2000:
        params = {"timeMin": _local(start), "timeMax": _local(end + dt.timedelta(days=1)), "singleEvents": "true",
                  "orderBy": "startTime", "maxResults": 250}
        if token:
            params["pageToken"] = token
        got = call(ref, f"/calendar/v3/calendars/{urllib.parse.quote(calendar)}/events", "calendar", params,
                   opener=opener)
        out += got.get("items") or []
        token = got.get("nextPageToken") or ""
        if not token:
            break
    return out


def calendar_add(ref: str, summary: str, start: dt.datetime, minutes: int = 30, location: str = "",
                 calendar: str = "primary", opener=None) -> dict:
    """Add one event; a start without a zone is this machine's local time."""
    summary = " ".join((summary or "").split())
    if not summary:
        raise ValueError("an event needs a title")
    start = start if start.tzinfo else start.astimezone()
    end = start + dt.timedelta(minutes=max(1, int(minutes or 30)))
    body = {"summary": summary, "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}}
    if location:
        body["location"] = location
    return call(ref, f"/calendar/v3/calendars/{urllib.parse.quote(calendar)}/events", "calendar", body=body,
                opener=opener)


# -- Drive: the Wiki (sources/lore.py GoogleDriveSource) ----------------------------------------------------

DOC = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
TEXT_TYPES = ("text/plain", "text/markdown", "text/x-markdown")
TEXT_EXT = (".md", ".markdown", ".txt", ".rst")
MAX_BYTES = 1_000_000                   # a text file bigger than this is skipped
FIELDS = "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,size,parents)"


def readable(f: dict) -> bool:
    """A Google Doc (exported as Markdown) or a text file of a sane size; the rest is skipped."""
    if f.get("mimeType") == DOC:
        return True
    text = f.get("mimeType") in TEXT_TYPES or str(f.get("name", "")).lower().endswith(TEXT_EXT)
    return text and int(f.get("size") or 0) <= MAX_BYTES


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _list(ref: str, q: str, limit: int, opener) -> list[dict]:
    out, token = [], ""
    while len(out) < limit:
        params = {"q": q, "fields": FIELDS, "pageSize": min(100, max(1, limit - len(out))), "orderBy": "modifiedTime desc"}
        if token:
            params["pageToken"] = token
        got = call(ref, "/drive/v3/files", "drive", params, opener=opener)
        out += got.get("files") or []
        token = got.get("nextPageToken") or ""
        if not token:
            break
    return out[:limit]


READABLE_Q = (f"trashed = false and (mimeType = '{DOC}' or " + " or ".join(f"mimeType = '{t}'" for t in TEXT_TYPES)
              + " or " + " or ".join(f"name contains '{e}'" for e in TEXT_EXT) + ")")


def drive_files(ref: str, folder: str = "", limit: int = 500, opener=None) -> list[dict]:
    """The Docs and text files of the whole Drive, or of `folder` and the folders inside it; newest first."""
    if not folder:
        return [f for f in _list(ref, READABLE_Q, limit, opener) if readable(f)]
    out, todo, seen = [], [folder], set()
    while todo and len(out) < limit and len(seen) < 200:
        here = todo.pop(0)
        if here in seen:
            continue
        seen.add(here)
        inside = _list(ref, f"'{_q(here)}' in parents and trashed = false", limit, opener)
        todo += [f["id"] for f in inside if f.get("mimeType") == FOLDER]
        out += [f for f in inside if readable(f)]
    return out[:limit]


def drive_folders(ref: str, parent: str = "root", opener=None) -> list[dict]:
    """The folders in `parent` (`root`: My Drive), by name: [{"id", "name"}]."""
    got = _list(ref, f"'{_q(parent)}' in parents and mimeType = '{FOLDER}' and trashed = false", 200, opener)
    return sorted(({"id": f["id"], "name": f.get("name", "")} for f in got), key=lambda f: f["name"].lower())


def drive_text(ref: str, f: dict, opener=None) -> str:
    """A Doc as Markdown (plain text when Markdown is refused); a text file as it is."""
    fid = urllib.parse.quote(str(f.get("id", "")))
    if f.get("mimeType") == DOC:
        try:
            raw = call(ref, f"/drive/v3/files/{fid}/export", "drive", {"mimeType": "text/markdown"}, raw=True, opener=opener)
        except GoogleError as e:
            if e.kind == "login":
                raise
            raw = call(ref, f"/drive/v3/files/{fid}/export", "drive", {"mimeType": "text/plain"}, raw=True, opener=opener)
    else:
        raw = call(ref, f"/drive/v3/files/{fid}", "drive", {"alt": "media"}, raw=True, opener=opener)
    return raw.decode("utf-8", errors="replace")
