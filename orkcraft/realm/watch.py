"""🗼 What the Watchtower listens to, besides the mailbox (realm/mailbox.py).

    github   `gh api repos/<owner/repo>/events` — events newer than the last one seen
    cron     a schedule: `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00`, a 5-field cron
    feeds    Slack, Jira, Confluence, Figma: comments and mentions (realm/feeds.py)
    webhook  an HTTP server on 127.0.0.1:<port> (never another interface); a POST is a signal.
             With `webhook_secret_env` set, a request must carry the secret: `X-Orkcraft-Token`,
             or GitHub's `X-Hub-Signature-256` HMAC of the body. /slack, /jira, /confluence and
             /figma are checked and answered the way those services sign (realm/inbound.py).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from orkcraft.realm import inbound, steward

GH_TIMEOUT_S = 15
MAX_BODY = 1024 * 1024
FEEDS = ("slack", "jira", "confluence", "figma")      # realm/feeds.py
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass
class Signal:
    at: str
    source: str            # mail | github | cron | webhook | slack | jira | confluence | figma
    title: str
    body: str = ""
    ref: str = ""          # mail uid, GitHub event id, webhook path, a feed item's link
    mention: bool = False  # a feed item about you

    @property
    def event(self) -> str:
        if self.source in FEEDS:
            return "watch.mention" if self.mention else "watch.comment"
        return {"mail": "mail.received", "github": "watch.github", "cron": "watch.cron"}.get(self.source,
                                                                                              "watch.webhook")


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# -- GitHub -------------------------------------------------------------------------------------------------

def describe(ev: dict) -> tuple[str, str]:
    """(title, body) of one GitHub event."""
    kind, p, who = ev.get("type", "Event"), ev.get("payload") or {}, (ev.get("actor") or {}).get("login", "?")
    if kind == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        title = f"PR #{pr.get('number', '?')} {p.get('action', '')}: {pr.get('title', '')}"
        return title.strip(), f"{who} · {pr.get('html_url', '')}"
    if kind == "IssuesEvent":
        it = p.get("issue") or {}
        return f"issue #{it.get('number', '?')} {p.get('action', '')}: {it.get('title', '')}", f"{who} · {it.get('html_url', '')}"
    if kind == "IssueCommentEvent":
        it, c = p.get("issue") or {}, p.get("comment") or {}
        return f"comment on #{it.get('number', '?')}", f"{who}: {(c.get('body') or '')[:500]}"
    if kind == "PushEvent":
        commits = p.get("commits") or []
        ref = str(p.get("ref", "")).removeprefix("refs/heads/")
        return f"push to {ref}: {len(commits)} commit{'s' if len(commits) != 1 else ''}", \
            "\n".join(f"- {c.get('message', '').splitlines()[0]}" for c in commits[:10] if c.get("message"))
    if kind == "ReleaseEvent":
        rel = p.get("release") or {}
        return f"release {rel.get('tag_name', '')} {p.get('action', '')}", rel.get("html_url", "")
    if kind == "WorkflowRunEvent":
        run = p.get("workflow_run") or {}
        return f"workflow {run.get('name', '')}: {run.get('conclusion') or run.get('status', '')}", run.get("html_url", "")
    return f"{kind.removesuffix('Event')} by {who}", ""


def github_events(repo: str, last_id: str, runner=subprocess.run) -> tuple[list[Signal], str, str]:
    """(new signals oldest first, the newest id, error). The first look (no last id) sends nothing."""
    if not REPO.match(repo or ""):
        return [], last_id, f"github: {repo!r} is not owner/repo"
    if runner is subprocess.run and shutil.which("gh") is None:
        return [], last_id, "github: install and log in to `gh`"
    try:
        out = runner(["gh", "api", f"repos/{repo}/events?per_page=30"], capture_output=True, text=True,
                     timeout=GH_TIMEOUT_S)
        if out.returncode != 0:
            return [], last_id, f"github: {(out.stderr or out.stdout).strip()[:150]}"
        events = json.loads(out.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return [], last_id, f"github: {e}"[:200]
    ids = [str(e.get("id", "")) for e in events if e.get("id")]
    newest = max(ids, key=lambda x: int(x) if x.isdigit() else 0, default=last_id)
    if not last_id:
        return [], newest, ""
    new = [e for e in events if str(e.get("id", "")).isdigit() and last_id.isdigit() and int(e["id"]) > int(last_id)]
    out_signals = []
    for e in sorted(new, key=lambda e: int(e["id"])):
        title, body = describe(e)
        out_signals.append(Signal(str(e.get("created_at") or now_iso()), "github", title, body, str(e["id"])))
    return out_signals, newest, ""


# -- the schedule ---------------------------------------------------------------------------------------

def to_schedule(expr: str) -> str:
    """`every 15m` / `every 2h` → a cron; the rest is what the steward reads."""
    m = re.fullmatch(r"every (\d{1,3})\s*(m|min|h)", expr.strip().lower())
    if m:
        n = max(1, int(m.group(1)))
        return f"*/{n} * * * *" if m.group(2) in ("m", "min") else f"0 */{n} * * *"
    return expr


def schedule_ok(expr: str) -> bool:
    return steward.to_cron(to_schedule(expr)) is not None


def cron_due(expr: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    return steward.due(to_schedule(expr), last, now)


# -- the webhook ----------------------------------------------------------------------------------------

def signed(secret: str, body: bytes, headers) -> bool:
    if not secret:
        return True
    token = headers.get("X-Orkcraft-Token", "")
    if token and hmac.compare_digest(token, secret):
        return True
    sig = headers.get("X-Hub-Signature-256", "")
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(sig) and hmac.compare_digest(sig, want)


class Webhook:
    """An HTTP listener on 127.0.0.1 only; every accepted POST calls `on_signal` (the whole body:
    the receiver parses a service's delivery, or cuts a raw one)."""

    def __init__(self, port: int, secret: str, on_signal: Callable[[Signal], None],
                 secrets: dict[str, str] | None = None) -> None:
        self.port, self.secret, self.on_signal = port, secret, on_signal
        self.secrets = dict(secrets or {})          # a service's own secret: Slack's signing secret, …
        self.server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        hook = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server's name)
                size = int(self.headers.get("Content-Length") or 0)
                if size > MAX_BODY:
                    self.send_response(413)
                    self.end_headers()
                    return
                body = self.rfile.read(size)
                service = inbound.service_of(self.path)
                ok = inbound.verify(service, hook.secrets.get(service) or hook.secret, body, self.headers) \
                    if service else signed(hook.secret, body, self.headers)
                if not ok:
                    self.send_response(401)
                    self.end_headers()
                    return
                reply = inbound.answer(service, body)
                if reply is not None:                 # Slack checks the URL: its challenge back, no signal
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(reply)
                    return
                text = body.decode("utf-8", errors="replace")
                event = self.headers.get("X-GitHub-Event", "")
                title = f"{self.path} {event}".strip() if event else f"POST {self.path}"
                hook.on_signal(Signal(now_iso(), "webhook", title, text, self.path))
                self.send_response(202)
                self.end_headers()
                self.wfile.write(b"accepted\n")

            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"orkcraft watchtower\n")

            def log_message(self, *a):        # quiet: the terminal belongs to the TUI
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True, name=f"watchtower-{self.port}").start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
