"""🗼 GitHub and GitLab as Watchtower feeds (realm/feeds.py): notifications and to-dos, and the events of
the repos and projects listed.

    github: repos=owner/app,owner/api notifications=on
        `notifications=on`: GET /notifications?participating=true — review requests, mentions,
        assignments, replies in threads you are in, across every repo; each is about you (a mention).
        `repos=`: GET /repos/{repo}/events, as the old `github: owner/repo` setting heard one repo.
        Asked through `gh api` (its login: nothing to paste), or with `token=` over HTTPS.
    gitlab: host=gitlab.com token=GITLAB_TOKEN projects=group/app,group/api todos=on
        `todos=on`: GET /api/v4/todos?state=pending — mentions, assignments, review requests,
        failed pipelines of yours; each is about you. `projects=`: GET /projects/:id/events, your own
        left out; a note that @-mentions you is a mention. Asked with `token=` (a `glpat-…`), or
        through `glab api` when there is none *(check: glab's flags)*.

A thread or a to-do that changes again is new again: its key carries its `updated_at`.
No face, no bus: the worker looks in a thread and turns the items into signals.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from orkcraft.realm import feeds
from orkcraft.realm.feeds import Failed, Feed, Item, Look, _iso, _short

GH_API = "https://api.github.com"
REASON = {"review_requested": "review asked", "mention": "mentioned", "team_mention": "team mentioned",
          "assign": "assigned", "author": "your thread", "comment": "a reply", "state_change": "state changed",
          "ci_activity": "CI", "manual": "subscribed", "subscribed": "watching", "security_alert": "security alert",
          "approval_requested": "approval asked"}
TODO = {"mentioned": "mentioned", "directly_addressed": "mentioned", "assigned": "assigned",
        "review_requested": "review asked", "approval_required": "approval asked", "build_failed": "pipeline failed",
        "unmergeable": "cannot merge", "marked": "a to-do", "member_access_requested": "access asked"}


def cli_kind(text: str) -> str:
    """What a `gh` / `glab` failure is, from what it printed."""
    t = (text or "").lower()
    if re.search(r"\b(401|403)\b|auth login|bad credentials|unauthori[sz]ed|not logged|requires authentication", t):
        return "login"
    if re.search(r"\b(404|410)\b|not found", t):
        return "target"
    return "network"


def cli(runner, cmd: list[str], kind: str):
    """`gh api …` / `glab api …` as JSON; a failure raised as the kind it is."""
    if runner is None or runner is subprocess.run:
        runner = subprocess.run
        if shutil.which(cmd[0]) is None:
            raise Failed(f"{kind}: install and log in to `{cmd[0]}`, or log in with a token", "login")
    try:
        out = runner(cmd, capture_output=True, text=True, timeout=feeds.TIMEOUT_S)
    except FileNotFoundError:
        raise Failed(f"{kind}: install and log in to `{cmd[0]}`, or log in with a token", "login") from None
    except (OSError, subprocess.SubprocessError) as e:
        raise Failed(f"{kind}: {e}"[:200], "network") from None
    if out.returncode != 0:
        said = (out.stderr or out.stdout or "").strip()
        raise Failed(f"{kind}: {said[:150]}", cli_kind(said))
    try:
        return json.loads(out.stdout or "null")
    except ValueError:
        raise Failed(f"{kind}: `{cmd[0]}` answered something that is not JSON", "network") from None


def _token(feed: Feed, what: str) -> str:
    """The token a line names; "" when it names none (the CLI's login); a named one that is gone fails."""
    if not feed.opts.get("token"):
        return ""
    token = feed.env("token")
    if not token:
        raise Failed(feed.missing("token", what), "login")
    return token


def _target(e: urllib.error.HTTPError, text: str) -> Exception:
    """A repo's or project's own 404 (or 403) is that target out of reach, not the login."""
    return Failed(text, "target") if e.code in (403, 404, 410) else e


# -- GitHub -----------------------------------------------------------------------------------------------

def html_url(api_url: str, fallback: str = "") -> str:
    """A notification's API link as the page a person opens: …/repos/o/r/pulls/3 → github.com/o/r/pull/3."""
    m = re.match(r"^https://api\.github\.com/repos/([^/]+/[^/]+)/(pulls|issues|commits|releases)/(.+)$", api_url or "")
    if not m:
        return fallback
    part = {"pulls": "pull", "issues": "issues", "commits": "commit", "releases": "releases"}[m.group(2)]
    return f"https://github.com/{m.group(1)}/{part}/{m.group(3)}"


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


def github(feed: Feed, opener=urllib.request.urlopen, runner=None) -> Look:
    token = _token(feed, "a GitHub token")

    def api(path: str):
        if token:
            return feeds.get_json(f"{GH_API}/{path}", {"Authorization": f"Bearer {token}",
                                                       "Accept": "application/vnd.github+json"}, opener)
        return cli(runner, ["gh", "api", path], "github")

    items: list[Item] = []
    if feed.on("notifications"):
        for n in api(f"notifications?participating=true&per_page={feeds.LOOK}") or []:
            subject, repo = n.get("subject") or {}, (n.get("repository") or {})
            name, why = repo.get("full_name", "?"), REASON.get(n.get("reason", ""), n.get("reason", ""))
            title = subject.get("title", "")
            items.append(Item(f"n:{n.get('id', '')}:{n.get('updated_at', '')}",
                              f"@ {why} · {name}: {_short(title, 60)}",
                              f"{name} · {subject.get('type', '')} · {why}\n\n{title}"[:feeds.BODY],
                              html_url(subject.get("url", ""), repo.get("html_url", "")), _iso(n.get("updated_at")),
                              mention=True))
    for repo in feed.ids("repos"):
        try:
            events = api(f"repos/{repo}/events?per_page=30") or []
        except urllib.error.HTTPError as e:
            raise _target(e, f"github: {repo} is gone or this login may not read it") from None
        except Failed as e:
            if e.kind == "target":
                raise Failed(f"github: {repo} is gone or this login may not read it", "target") from None
            raise
        for ev in events:
            if not ev.get("id"):
                continue
            title, body = describe(ev)
            items.append(Item(f"{repo}:{ev['id']}", f"{repo} · {title}", body[:feeds.BODY], "",
                              _iso(ev.get("created_at"))))
    return Look(sorted(items, key=lambda i: i.at))


# -- GitLab -----------------------------------------------------------------------------------------------

def gitlab_event(ev: dict, host: str, path: str) -> tuple[str, str, str]:
    """(title, body, link) of one GitLab project event."""
    who = (ev.get("author") or {}).get("username") or ev.get("author_username") or "?"
    action, target = ev.get("action_name", ""), ev.get("target_type") or ""
    web = f"https://{host}/{path}"
    if ev.get("push_data"):
        push = ev["push_data"]
        n = int(push.get("commit_count") or 0)
        return (f"{who} pushed to {push.get('ref', '')}: {n} commit{'s' if n != 1 else ''}",
                push.get("commit_title") or "", f"{web}/-/commits/{push.get('ref', '')}")
    note = ev.get("note") or {}
    if note:
        kind, iid = note.get("noteable_type", ""), note.get("noteable_iid")
        part = {"MergeRequest": "merge_requests", "Issue": "issues"}.get(kind, "")
        link = f"{web}/-/{part}/{iid}#note_{note.get('id', '')}" if part and iid else web
        return f"{who} commented on {ev.get('target_title') or kind}", note.get("body") or "", link
    part = {"MergeRequest": "merge_requests", "Issue": "issues", "Milestone": "milestones"}.get(target, "")
    link = f"{web}/-/{part}/{ev.get('target_iid')}" if part and ev.get("target_iid") else web
    what = re.sub(r"(?<!^)([A-Z])", r" \1", target).lower() if target else ""
    return f"{who} {action} {what} {ev.get('target_title') or ''}".replace("  ", " ").strip(), "", link


def gitlab(feed: Feed, opener=urllib.request.urlopen, runner=None) -> Look:
    host = feed.host
    token = _token(feed, "a personal access token, glpat-…")

    def api(path: str):
        if token:
            return feeds.get_json(f"https://{host}/api/v4/{path}", {"PRIVATE-TOKEN": token}, opener)
        return cli(runner, ["glab", "api", "--hostname", host, path], "gitlab")

    me = api("user") or {}
    uid, name = me.get("id"), str(me.get("username") or "")
    items: list[Item] = []
    if feed.on("todos"):
        for t in api(f"todos?state=pending&per_page={feeds.LOOK}") or []:
            target, project = t.get("target") or {}, (t.get("project") or {}).get("path_with_namespace", "?")
            why = TODO.get(t.get("action_name", ""), t.get("action_name", ""))
            who = (t.get("author") or {}).get("username", "?")
            title = target.get("title") or t.get("body") or ""
            items.append(Item(f"todo:{t.get('id', '')}", f"@ {why} · {project}: {_short(title, 60)}",
                              f"{project} · {t.get('target_type', '')} · {why} by {who}\n\n{t.get('body') or title}"[:feeds.BODY],
                              t.get("target_url", ""), _iso(t.get("created_at")), mention=True))
    for path in feed.ids("projects"):
        try:
            events = api(f"projects/{urllib.parse.quote(path, safe='')}/events?per_page={feeds.LOOK}") or []
        except urllib.error.HTTPError as e:
            raise _target(e, f"gitlab: {path} is gone or this login may not read it") from None
        except Failed as e:
            if e.kind == "target":
                raise Failed(f"gitlab: {path} is gone or this login may not read it", "target") from None
            raise
        for ev in events:
            if not ev.get("id") or (uid is not None and ev.get("author_id") == uid):
                continue
            title, body, link = gitlab_event(ev, host, path)
            mention = bool(name) and f"@{name}".lower() in body.lower()
            items.append(Item(f"{path}:{ev['id']}", f"{'@ ' if mention else ''}{path} · {_short(title, 70)}",
                              f"{title}\n\n{body}".strip()[:feeds.BODY], link, _iso(ev.get("created_at")), mention))
    return Look(sorted(items, key=lambda i: i.at), me={"id": uid, "username": name})
