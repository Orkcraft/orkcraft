"""🔥 Where a day went wrong or cost the most, found in its logs by code — no model (docs/design/improve-buildings.md
§13): the first step of Improve, so the Mechanic and the Farseer read a few calls in full, never the whole day.

    hotspots.find(root, day, titles, decisions, dislikes)    [Hotspot], each with an id the review cites (H1, H2, …)
    hotspots.digest(spots)                                  what the council reads: each hotspot and its excerpts

The kinds, in the order they are listed:

    dislike     a 👎 on a building that day, with what the person said and what it made
    failed      a model call that ended with an error
    rework      an Agent pool's steward sent work back or again (follow-up, reuse, retier)
    repeated    the same opening of a prompt sent REPEAT_MIN times or more in one building's day: context sent again
    costly      the day's costliest calls, by tokens (COSTLY of them, each at least COSTLY_MIN)
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft.realm import analytics, call_log

COSTLY, COSTLY_MIN = 5, 5_000
REPEAT_MIN, REPEAT_HEAD = 3, 1500           # how many times, and how much of a prompt's opening is compared
HEAD, TAIL, OUT = 1200, 400, 800            # what of a call goes in the digest: its prompt's head and tail, its output
DIGEST_MAX = 40_000                         # characters the council reads at most


@dataclass
class Hotspot:
    id: str
    kind: str
    building: str
    title: str
    said: str                                # one line: what is wrong or costly, with its numbers
    calls: list[str] = field(default_factory=list)       # the calls it rests on: `<building>/calls/<file>`
    excerpt: str = ""


def _ref(bid: str, line: dict) -> str:
    return f"{bid}/calls/{str(line.get('raw') or '').removesuffix('.gz')}"


def _excerpt(folder: Path, line: dict) -> str:
    raw = call_log.raw(folder, line)
    prompt, out = str(raw.get("prompt") or ""), str(raw.get("stdout") or "")
    if len(prompt) > HEAD + TAIL:
        prompt = f"{prompt[:HEAD]}\n[… {len(prompt) - HEAD - TAIL:,} characters …]\n{prompt[-TAIL:]}"
    head = (f"{line.get('who') or 'the tool'} · {line.get('purpose') or 'work'} · {line.get('tool')}"
            f"{':' + line['model'] if line.get('model') else ''} · {float(line.get('seconds') or 0):.0f} s · "
            f"{int(line.get('tokens') or 0):,} tokens")
    err = str(raw.get("stderr") or "").strip()
    return (f"{head}\nPROMPT:\n{prompt}\nOUTPUT:\n{out[:OUT]}" + (f"\nERRORS:\n{err[-OUT:]}" if err else ""))


def find(root: Path, day: str, titles: dict[str, str], decisions: Callable[[str, str], list[dict]],
         dislikes: Callable[[str, str], list[dict]]) -> list[Hotspot]:
    found: dict[str, list[Hotspot]] = defaultdict(list)
    costly: list[tuple[int, str, dict]] = []
    for bid in analytics._buildings(root, day):
        folder = call_log.day_folder(root, day, bid)
        title = titles.get(bid, bid)
        lines = call_log.read(folder)
        for d in dislikes(bid, day):
            note = str(d.get("note") or "").strip()
            found["dislike"].append(Hotspot("", "dislike", bid, title,
                                            f"a 👎 on {title}" + (f": “{note[:300]}”" if note else " (no words)"),
                                            excerpt=f"What it made then:\n{str(d.get('output') or '')[:OUT]}"))
        for x in lines:
            if x.get("code"):
                found["failed"].append(Hotspot("", "failed", bid, title, f"a call of {title} failed (exit "
                                               f"{x.get('code')})", [_ref(bid, x)], _excerpt(folder, x)))
            if int(x.get("tokens") or 0) >= COSTLY_MIN:
                costly.append((int(x.get("tokens") or 0), bid, x))
        sent_back = [d for d in decisions(bid, day) if d.get("action") in analytics.REWORKS]
        if sent_back:
            found["rework"].append(Hotspot("", "rework", bid, title,
                                           f"{title} sent work back or again {len(sent_back)} time"
                                           f"{'' if len(sent_back) == 1 else 's'}",
                                           excerpt="\n".join(f"- {d.get('action')}: {d.get('orc') or 'the steward'} — "
                                                             f"{str(d.get('why') or '')[:300]}" for d in sent_back[:8])))
        same: dict[str, list[dict]] = defaultdict(list)
        for x in lines:
            prompt = str(call_log.raw(folder, x).get("prompt") or "")
            if len(prompt) >= REPEAT_HEAD:
                same[hashlib.sha1(prompt[:REPEAT_HEAD].encode()).hexdigest()].append(x)
        for group in same.values():
            if len(group) >= REPEAT_MIN:
                tokens = sum(int(x.get("tokens") or 0) for x in group)
                found["repeated"].append(Hotspot("", "repeated", bid, title,
                                                 f"{title} sent the same opening of a prompt {len(group)} times "
                                                 f"({tokens:,} tokens in all)", [_ref(bid, x) for x in group],
                                                 _excerpt(folder, group[0])))
    for tokens, bid, x in sorted(costly, key=lambda c: -c[0])[:COSTLY]:
        title = titles.get(bid, bid)
        found["costly"].append(Hotspot("", "costly", bid, title, f"a costly call of {title}: {tokens:,} tokens",
                                       [_ref(bid, x)], _excerpt(call_log.day_folder(root, day, bid), x)))
    spots = [h for kind in ("dislike", "failed", "rework", "repeated", "costly") for h in found[kind]]
    for n, h in enumerate(spots, 1):
        h.id = f"H{n}"
    return spots


def digest(spots: list[Hotspot]) -> str:
    """Each hotspot: its id, its building, what is wrong, then its excerpt; cut at DIGEST_MAX."""
    parts, size = [], 0
    for h in spots:
        part = f"### {h.id} · {h.kind} · {h.title} (`{h.building}`)\n{h.said}\n{h.excerpt}".rstrip() + "\n"
        if size + len(part) > DIGEST_MAX:
            parts.append(f"[{len(spots) - len(parts)} more hotspots left out: the digest is full]\n")
            break
        parts.append(part)
        size += len(part)
    return "\n".join(parts)
