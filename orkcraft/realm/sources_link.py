"""A pasted link (or an e-mail address) → the service to listen to, its site and the thing to tick.

The Watchtower's Add a source takes a link rather than an id: every service has links to what a
person wants to hear, and a link names the service, the site and the target at once
(docs/design/watchtower-quick-add.md §4.3).

    recognise("https://acme.slack.com/archives/C07SUPPORT")
        == Link("slack", "acme.slack.com", "C07SUPPORT", "the channel C07SUPPORT")
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    service: str        # github | gitlab | slack | discord | jira | confluence | figma | gmail | mail
    site: str = ""      # acme.slack.com, acme.atlassian.net, the mail address…
    target: str = ""    # owner/repo, a channel id, a project key, a space key, a file key
    says: str = ""      # what will be ticked, in words


EMAIL = re.compile(r"^[^@\s]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
GOOGLE_MAIL = ("gmail.com", "googlemail.com")


def recognise(text: str, gitlab_hosts=()) -> Link | None:
    """The service a link or an address points at, or None. `gitlab_hosts`: the self-hosted GitLabs
    this machine has a login for (their links are GitLab's too)."""
    text = (text or "").strip()
    if EMAIL.match(text):
        domain = text.rsplit("@", 1)[1].lower()
        return Link("gmail" if domain in GOOGLE_MAIL else "mail", text, "", f"the mailbox {text}")
    url = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
    host, parts = (url.hostname or "").lower(), [p for p in url.path.split("/") if p]
    if host in ("github.com", "www.github.com") and len(parts) >= 2:
        repo = f"{parts[0]}/{parts[1].removesuffix('.git')}"
        return Link("github", "github.com", repo, f"the repo {repo}")
    if (host == "gitlab.com" or host in {h.lower() for h in gitlab_hosts}) and len(parts) >= 2:
        path = "/".join(parts[:parts.index("-")] if "-" in parts else parts)
        return Link("gitlab", host, path, f"the project {path}")
    if host.endswith(".slack.com"):
        channel = parts[1] if len(parts) >= 2 and parts[0] == "archives" else ""
        return Link("slack", host, channel, f"the channel {channel}" if channel else "")
    if host in ("discord.com", "discordapp.com", "www.discord.com") and len(parts) >= 3 and parts[0] == "channels":
        if parts[1] == "@me" or not parts[2].isdigit():
            return Link("discord", "", "", "")       # a direct message: no bot hears those
        return Link("discord", parts[1], parts[2], f"the channel {parts[2]}")
    if host.endswith(".atlassian.net"):
        if parts[:1] == ["wiki"]:
            space = parts[2] if len(parts) >= 3 and parts[1] == "spaces" else ""
            return Link("confluence", host, space, f"the space {space}" if space else "")
        key = ""
        if len(parts) >= 2 and parts[0] == "browse":
            key = parts[1].split("-", 1)[0]
        elif "projects" in parts and parts.index("projects") + 1 < len(parts):
            key = parts[parts.index("projects") + 1]
        return Link("jira", host, key.upper(), f"the project {key.upper()}" if key else "")
    if host in ("figma.com", "www.figma.com") and len(parts) >= 2:
        if parts[0] in ("design", "file", "board", "proto", "make", "slides"):
            key = parts[3] if len(parts) >= 4 and parts[2] == "branch" else parts[1]
            return Link("figma", host, key, f"the file {key}")
        if parts[:2] == ["files", "team"] and len(parts) >= 3:
            return Link("figma", host, f"team:{parts[2]}", f"the team {parts[2]}")
    return None
