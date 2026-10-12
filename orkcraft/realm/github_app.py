"""GitHub for the Improve buildings (docs/design/improve-buildings.md §4): signed in once through the Orkcraft
Improve GitHub App's device flow, and a change a Test bench tried sent to Orkcraft as a pull request.

The sign-in: GitHub shows the person a code (`start`), they type it at github.com/login/device, `poll` gets the token
— no client secret ships, the device flow needs none. The token is kept as a login on this machine (realm/logins.py,
the keychain when there is one). The app acts only where it is installed: on `orkcraft/orkcraft` by its owner, and
on the person's own account (for their fork), which `installed` checks and `INSTALL` opens.

A pull request is made with the API only, no clone: the person's fork (made when missing), a branch from Orkcraft's
`main` with the changed files (each merged three ways when `main` changed it since the installed version, refused
when that conflicts; a picture, given as bytes, is refused when `main` changed it to anything else), and the pull
request into `main`. The Test bench sends code and a type's defaults, the UX bench pictures, cards and windows.

    d = github_app.start(); github_app.poll(d) → "" while waiting, the login once signed in
    github_app.send(changes, title, body) → the pull request's URL
"""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import logins

CLIENT_ID = "Iv23ligmdXetPjrWsh4J"        # the Orkcraft Improve app's: not a secret (the device flow needs none)
SLUG = "orkcraft-improve"
UPSTREAM = "orkcraft/orkcraft"
BASE = "main"
LABEL = "from-orkcraft"
LOGIN = "github-improve"                  # the login it is kept under (realm/logins.py)
INSTALL = f"https://github.com/apps/{SLUG}/installations/new"
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API = "https://api.github.com"
TIMEOUT_S = 20
FORK_WAIT_S = 30


class GithubError(Exception):
    """What GitHub refused or could not be reached for; its text is shown to the person."""


@dataclass
class Device:
    device_code: str
    user_code: str
    uri: str
    interval: int
    expires_at: float


# -- HTTP ------------------------------------------------------------------------------------------------------------

def _call(method: str, url: str, body: dict | None = None, token: str = "", form: bool = False, opener=None):
    opener = opener or urllib.request.urlopen
    head = {"Accept": "application/json" if form else "application/vnd.github+json", "User-Agent": "orkcraft",
            "X-GitHub-Api-Version": "2022-11-28"}
    data = None
    if body is not None:
        data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
        head["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        head["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=head, method=method)
    try:
        with opener(req, timeout=TIMEOUT_S) as r:
            text = r.read().decode("utf-8", errors="replace")
            return getattr(r, "status", 200), (json.loads(text) if text.strip() else {})
    except urllib.error.HTTPError as e:
        try:
            got = json.loads(e.read().decode("utf-8", errors="replace") or "{}")
        except (ValueError, OSError):
            got = {}
        return e.code, got
    except (urllib.error.URLError, OSError) as e:
        raise GithubError(f"Could not reach GitHub ({getattr(e, 'reason', e)})") from None


def _api(method: str, path: str, body: dict | None = None, token: str = "", ok=(200, 201), opener=None) -> dict:
    code, got = _call(method, f"{API}{path}", body, token, opener=opener)
    if code not in ok:
        raise GithubError(f"GitHub said no ({code}): {got.get('message') if isinstance(got, dict) else got}"[:300])
    return got


# -- the sign-in -------------------------------------------------------------------------------------------------------

def start(opener=None) -> Device:
    code, got = _call("POST", DEVICE_URL, {"client_id": CLIENT_ID}, form=True, opener=opener)
    if code != 200 or "device_code" not in got:
        raise GithubError(f"GitHub did not give a code: {got.get('error_description') or got.get('error') or code}")
    return Device(got["device_code"], got["user_code"], got.get("verification_uri") or "https://github.com/login/device",
                  int(got.get("interval") or 5), time.time() + int(got.get("expires_in") or 900))


def poll(d: Device, opener=None) -> str:
    """"" while the person has not typed the code yet; their login once they have (the token kept)."""
    if time.time() > d.expires_at:
        raise GithubError("The code expired: connect again")
    _code, got = _call("POST", TOKEN_URL, {"client_id": CLIENT_ID, "device_code": d.device_code,
                                           "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
                       form=True, opener=opener)
    error = got.get("error")
    if error == "authorization_pending":
        return ""
    if error == "slow_down":
        d.interval = int(got.get("interval") or d.interval + 5)
        return ""
    if error:
        raise GithubError({"expired_token": "The code expired: connect again",
                           "access_denied": "GitHub was told no: nothing connected"}.get(error, f"GitHub: {error}"))
    token = str(got.get("access_token") or "")
    if not token:
        raise GithubError("GitHub gave no token")
    me = _api("GET", "/user", token=token, opener=opener)
    login = str(me.get("login") or "")
    logins.save(LOGIN, json.dumps({"login": login, "token": token}), account=login)
    return login


def account() -> dict | None:
    """{login, token} of the account connected here, or None."""
    try:
        data = json.loads(logins.get(LOGIN))
    except (KeyError, ValueError, OSError, RuntimeError):
        return None
    return data if isinstance(data, dict) and data.get("token") and data.get("login") else None


def disconnect() -> bool:
    return logins.remove(LOGIN)


def installed(acct: dict, opener=None) -> bool:
    """Whether the app is installed on the person's own account (it pushes to their fork there)."""
    got = _api("GET", "/user/installations", token=acct["token"], opener=opener)
    return any(str((i.get("account") or {}).get("login") or "").lower() == acct["login"].lower()
               for i in got.get("installations") or [])


# -- a pull request ----------------------------------------------------------------------------------------------------

def merged(base: str, mine: str, theirs: str) -> str | None:
    """`mine` (base → mine, the bench's change) on top of `theirs` (base → theirs, Orkcraft's main since); None when
    the two change the same lines."""
    if theirs == base:
        return mine
    with tempfile.TemporaryDirectory(prefix="orkcraft-merge-") as tmp:
        paths = []
        for name, text in (("mine", mine), ("base", base), ("theirs", theirs)):
            p = Path(tmp) / name
            p.write_text(text, encoding="utf-8")
            paths.append(str(p))
        out = subprocess.run(["git", "merge-file", "-p", *paths], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def _fork(acct: dict, opener=None) -> str:
    """The person's fork of Orkcraft, made when missing; its full name."""
    name = f"{acct['login']}/{UPSTREAM.split('/')[1]}"
    code, _got = _call("GET", f"{API}/repos/{name}", token=acct["token"], opener=opener)
    if code == 200:
        return name
    _api("POST", f"/repos/{UPSTREAM}/forks", {"default_branch_only": True}, acct["token"], ok=(200, 202), opener=opener)
    end = time.time() + FORK_WAIT_S
    while time.time() < end:                      # GitHub makes a fork a moment after it says so
        if _call("GET", f"{API}/repos/{name}", token=acct["token"], opener=opener)[0] == 200:
            return name
        time.sleep(1.5)
    raise GithubError("GitHub is still making your fork of Orkcraft: try again in a minute")


def send(changes: dict[str, tuple[str, str] | tuple[bytes, bytes]], title: str, body: str, branch: str,
         acct: dict | None = None, opener=None) -> str:
    """The changed files ({path: (as installed, as changed)}, text or bytes) as a pull request into Orkcraft's main;
    its URL."""
    acct = acct or account()
    if acct is None:
        raise GithubError("Connect GitHub first (the mascot's menu → GitHub)")
    if not installed(acct, opener):
        raise GithubError(f"Install the Orkcraft Improve app on your account first: {INSTALL}")
    token = acct["token"]
    fork = _fork(acct, opener)
    head = _api("GET", f"/repos/{UPSTREAM}/git/ref/heads/{BASE}", token=token, opener=opener)["object"]["sha"]
    tree = _api("GET", f"/repos/{UPSTREAM}/git/commits/{head}", token=token, opener=opener)["tree"]["sha"]
    entries = []
    for path, (base, mine) in sorted(changes.items()):
        code, got = _call("GET", f"{API}/repos/{UPSTREAM}/contents/{urllib.parse.quote(path)}?ref={head}",
                          token=token, opener=opener)
        if isinstance(mine, bytes):                   # a picture: no lines to merge, so main must not have moved it
            theirs_b = base64.b64decode(got.get("content") or "") if code == 200 else None
            if theirs_b is not None and theirs_b not in (base, mine):
                raise GithubError(f"{path} changed in Orkcraft's main since this version: update Orkcraft and draw it "
                                  "again")
            blob = _api("POST", f"/repos/{fork}/git/blobs", {"content": base64.b64encode(mine).decode(),
                                                             "encoding": "base64"}, token, opener=opener)
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
            continue
        theirs = base64.b64decode(got.get("content") or "").decode("utf-8") if code == 200 else ""
        text = merged(base, mine, theirs) if code == 200 else mine
        if text is None:
            raise GithubError(f"{path} changed in Orkcraft's main where this change does: update Orkcraft and try "
                              "the change again")
        blob = _api("POST", f"/repos/{fork}/git/blobs", {"content": text, "encoding": "utf-8"}, token, opener=opener)
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = _api("POST", f"/repos/{fork}/git/trees", {"base_tree": tree, "tree": entries}, token, opener=opener)
    commit = _api("POST", f"/repos/{fork}/git/commits", {"message": title, "tree": new_tree["sha"], "parents": [head]},
                  token, opener=opener)
    _api("POST", f"/repos/{fork}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}, token,
         opener=opener)
    pr = _api("POST", f"/repos/{UPSTREAM}/pulls", {"title": title, "head": f"{acct['login']}:{branch}", "base": BASE,
                                                   "body": body, "maintainer_can_modify": True}, token, opener=opener)
    _call("POST", f"{API}/repos/{UPSTREAM}/issues/{pr['number']}/labels", {"labels": [LABEL]}, token, opener=opener)
    return str(pr.get("html_url") or "")
