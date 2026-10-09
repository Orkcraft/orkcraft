"""🗼 The tower's first sort of a message, in stages: code where it can, the model only where it must.

    automated(sender, title, tags)   stage 1, code: a mailing, a notification, an auto-reply? Its reason, or ""
    verdict(read)                    stage 3, code: importance and who answers, from what the model read
    line(sort, importance, answer)   the sort in one line, for the cart and the tower's list

Stage 2 is the model's (realm/lookout.py `judge(..., triage=True)`, the steward's `judge`, warrior at most): for
each message that is not automated, one structured read in the same call for the whole batch —

- `asks`: what is asked of us: nothing | info (it tells us something) | reply (an answer) | action (something to
  do) | decision (a choice only the operator can make);
- `urgency`: how fast: now | today | week | none;
- `risk`: what happens if no one answers: high | medium | low | none, and in a few words what;
- `tone`: angry | upset | urgent | neutral | friendly;
- `agent`: whether an AI agent could answer it well with no decision of the operator's.

Stage 3 turns that into the two words the tower shows and sends on, by rules a person can read here, never by the
model's say-so: a high risk, an angry or upset sender, or a decision always goes to the person.
(docs/design/watchtower-mcp-paths.md §12.)
"""
from __future__ import annotations

import re

ASKS = ("nothing", "info", "reply", "action", "decision")
URGENCY = ("now", "today", "week", "none")
RISK = ("high", "medium", "low", "none")
TONE = ("angry", "upset", "urgent", "neutral", "friendly")

# Who sends mail no one answers: the local part of the address.
_ROBOT = re.compile(r"^(?:no-?reply|do-?not-?reply|donotreply|notifications?|notify|mailer-daemon|postmaster|bounces?|"
                    r"newsletters?|news|digest|updates?|alerts?|marketing|promo(?:tions?)?)"
                    r"(?:[+._-].*)?$", re.I)
# What a mail's headers or a service's labels say of a mailing (realm/mailbox.py, realm/feeds_agent.py copy them).
_BULK_TAGS = {"list-unsubscribe": "has an unsubscribe link", "list-id": "comes from a mailing list",
              "precedence:bulk": "is a bulk mailing", "precedence:list": "comes from a mailing list",
              "precedence:junk": "is marked junk", "auto-submitted": "was sent automatically",
              "category_promotions": "is in Promotions", "category_social": "is in Social",
              "category_updates": "is in Updates", "category_forums": "is in Forums"}
_AUTO_SUBJECT = re.compile(r"^(?:auto(?:matic)?[- ]?reply|out of (?:the )?office|undeliverable|delivery status notification)\b", re.I)


def address(sender: str) -> str:
    """The e-mail address in a From line ("Ann <ann@x.io>" → "ann@x.io"); "" when there is none."""
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", sender or "")
    return m.group(0).lower() if m else ""


def automated(sender: str, title: str = "", tags=()) -> str:
    """Stage 1: why the message is a mailing or a machine's, in plain words; "" when a person may have written it."""
    for tag in tags or ():
        word = str(tag).strip().lower()
        if word.startswith("auto-submitted") and word.endswith(":no"):
            continue
        for key, why in _BULK_TAGS.items():
            if word == key or word.startswith(key + ":") or word == key.replace("category_", ""):
                return why
    local = address(sender).split("@")[0]
    if local and _ROBOT.match(local):
        return f"comes from {address(sender)}"
    if _AUTO_SUBJECT.match((title or "").strip()):
        return "is an automatic reply"
    return ""


def _one(value, words: tuple[str, ...], default: str) -> str:
    word = str(value or "").strip().lower()
    return word if word in words else default


def read(raw: dict) -> dict:
    """The model's stage-2 answer for one message, held to its words (anything else falls to the careful side)."""
    return {"asks": _one(raw.get("asks"), ASKS, "reply"), "urgency": _one(raw.get("urgency"), URGENCY, "week"),
            "risk": _one(raw.get("risk"), RISK, "medium"), "risk_why": str(raw.get("risk_why") or "")[:120],
            "tone": _one(raw.get("tone"), TONE, "neutral"), "agent": raw.get("agent") is True}


def verdict(r: dict) -> tuple[str, str]:
    """Stage 3: (importance high | normal | low, answer agent | person | "" when nothing is asked)."""
    hot = r["tone"] in ("angry", "upset")
    if r["risk"] == "high" or r["urgency"] in ("now", "today") or hot:
        importance = "high"
    elif r["asks"] in ("nothing", "info") and r["risk"] in ("none", "low"):
        importance = "low"
    else:
        importance = "normal"
    if r["asks"] in ("nothing", "info"):             # it asks no answer: nobody needs to write one
        answer = ""
    elif r["asks"] == "decision" or r["risk"] == "high" or hot or not r["agent"]:
        answer = "person"
    else:
        answer = "agent"
    return importance, answer


def line(sort: dict, importance: str, answer: str) -> str:
    """The sort in one line, for the cart and the list: what the next building and the person read first."""
    if sort.get("auto"):
        return f"automated: it {sort['auto']} · importance: low"
    parts = [f"importance: {importance}" if importance else "",
             {"agent": "answered by: an agent", "person": "answered by: you"}.get(answer, "no answer needed" if sort else ""),
             f"asks: {sort['asks']}" if sort.get("asks") else "",
             f"answer {'now' if sort.get('urgency') == 'now' else 'today' if sort.get('urgency') == 'today' else 'this week'}"
             if sort.get("urgency") in ("now", "today", "week") else "",
             f"risk if unanswered: {sort['risk']}" + (f" ({sort['risk_why']})" if sort.get("risk_why") else "")
             if sort.get("risk") not in (None, "", "none") else "",
             f"tone: {sort['tone']}" if sort.get("tone") not in (None, "", "neutral") else ""]
    return " · ".join(p for p in parts if p)
