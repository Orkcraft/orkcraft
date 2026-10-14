"""❓ The way to ask and to mark (docs/design/ork-console.md §4, §20; research R2 in docs/design/asking-r2.md): an
ork ends its run with a short block — its questions for the person, each with its answers to pick from, and the
assumptions it made — and the town reads it, so a question is pinned on top of the ork's answer and never lost in
its text.

    ```asks
    GIST: The dev server moved behind the proxy; its tests pass.
    QUESTION: Which port should the dev server use?
    - 8080
    - 3000
    ASSUMED: The API keeps its v1 paths.
    ```

    found = asking.parse(text)       # Asks(questions, assumptions, body, gist): `body` is the text without the block
    asking.gist_of(found)            # (the gist, "block") — or its last paragraph, "last paragraph", when it gave none
    asking.rule("Ugluk")             # what the ork's prompt says about it (Claude Code first; others keep `QUESTION:`)
    asking.rule("Ugluk", "19:00")    # … in the person's working hours: assume and mark unless a wrong guess costs a day
    asking.question_line(found)      # the questions as one paragraph, as a pool keeps its task's question

An ork asks only when it cannot go on without the person (a costly or irreversible choice); a choice that can be
undone it makes and marks (`ASSUMED:`), and the person reads the marks when they want. The older single line
`QUESTION: …` at the end of a run still reads as one question with no options. Pure module, no face.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TAG = "asks"
MAX_QUESTIONS, MAX_OPTIONS, MAX_ASSUMPTIONS, TEXT_MAX = 3, 6, 12, 500
GIST_LINES = 3                 # the gist is three lines at most (ork-console.md §20)
# The last fenced block tagged `asks`: three or more backticks or tildes, closed by the same, or by the end.
_BLOCK = re.compile(r"(^|\n)[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*" + TAG + r"[ \t]*\n(?P<body>.*?)(\n[ \t]*(?P=fence)[ \t]*(?=\n|$)|\Z)",
                    re.I | re.S)
_QUESTION = re.compile(r"^\s*\**\s*(?:QUESTION|Q)\s*\**\s*:\s*(.+)$", re.I)
_GIST = re.compile(r"^\s*\**\s*GIST\s*\**\s*:\s*(.+)$", re.I)
_ASSUMED = re.compile(r"^\s*\**\s*(?:ASSUMED|ASSUMPTION)\s*\**\s*:\s*(.+)$", re.I)
_OPTION = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$")
_LINE = re.compile(r"^\s*\**\s*QUESTION\b\s*:?\s*(.+)", re.I | re.S | re.M)   # the older single line


@dataclass
class Question:
    text: str
    options: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"text": self.text, "options": list(self.options)}


@dataclass
class Asks:
    questions: list[Question] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    body: str = ""
    via: str = ""          # "block" | "line" | "" (nothing asked or marked)
    gist: list[str] = field(default_factory=list)   # what was done or found, three lines at most (§20)


def _clip(text: str) -> str:
    return " ".join(text.split())[:TEXT_MAX]


def parse(text: str) -> Asks:
    """The questions and assumptions of a run's answer: its last `asks` block, else an older `QUESTION:` line."""
    text = text or ""
    blocks = list(_BLOCK.finditer(text))
    if not blocks:
        m = _LINE.search(text)
        if not m:
            return Asks(body=text)
        return Asks([Question(m.group(1).strip()[:TEXT_MAX * 4])], body=text[:m.start()].rstrip(), via="line")
    last = blocks[-1]
    found = Asks(body=(text[:last.start()] + text[last.end():]).strip(), via="block")
    current: Question | None = None
    for raw in last.group("body").splitlines():
        if m := _GIST.match(raw):
            current = None
            found.gist.append(_clip(m.group(1)))
        elif m := _QUESTION.match(raw):
            current = Question(_clip(m.group(1)))
            found.questions.append(current)
        elif m := _ASSUMED.match(raw):
            current = None
            found.assumptions.append(_clip(m.group(1)))
        elif (m := _OPTION.match(raw)) and current is not None:
            current.options.append(_clip(m.group(1)))
        elif raw.strip() and current is not None and not current.options:
            current.text = _clip(f"{current.text} {raw}")          # a question that runs on to a second line
    found.questions = [Question(q.text, q.options[:MAX_OPTIONS]) for q in found.questions if q.text][:MAX_QUESTIONS]
    found.assumptions = [a for a in found.assumptions if a][:MAX_ASSUMPTIONS]
    found.gist = [g for g in found.gist if g][:GIST_LINES]
    return found


def last_paragraph(text: str) -> str:
    """The last paragraph of an answer, clipped: the gist of an ork whose AI tool gave none (§20)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip() and not p.strip().startswith("```")]
    return _clip(paras[-1]) if paras else ""


def gist_of(found: Asks) -> tuple[str, str]:
    """(the gist, where it came from): the ork's own `GIST:` lines ("block"), else the answer's last paragraph
    ("last paragraph"), else ("", "")."""
    if found.gist:
        return "\n".join(found.gist), "block"
    last = last_paragraph(found.body)
    return (last, "last paragraph") if last else ("", "")


def question_line(found: Asks) -> str:
    """The questions as one paragraph (no blank line: a pool reads a question's first paragraph as the question)."""
    return "\n".join(q.text for q in found.questions)


def at_work(until: str) -> str:
    """What the rule adds in the person's working hours (audience.md §2a): an ork must not stand all day on one
    question, so it waits only where a wrong guess costs more than a day."""
    return (f"The person is at work until {until} and will not answer before then. Do not stop for a question "
            "unless a wrong guess would cost more than a day's work to undo, or cannot be undone at all; otherwise "
            "make the likeliest choice, mark it as an assumption, and go on.\n\n")


def rule(steward: str = "", work_until: str = "") -> str:
    """What an ork's prompt says about asking and marking (Claude Code first, decisions §8); `work_until`: the
    person's working hours hold until then (schedule.py `work_ends`)."""
    who = f"{steward}, the steward, or the person" if steward else "the person"
    return (
        "## Questions and assumptions\n\n"
        + (at_work(work_until) if work_until else "") +
        "When you are unsure, do one of three things:\n"
        "- a costly or irreversible choice you cannot make without the person: stop and ask;\n"
        "- a choice that can be undone but is not obvious: make it, go on, and mark it as an assumption;\n"
        "- a routine choice: decide quietly.\n\n"
        f"End your answer with this block ({who} reads it): the gist first, what was done or found in three lines "
        "at most; then your questions, if any, at most three, each with the answers to pick from when there are a "
        "few; then your assumptions, if any:\n\n"
        "```asks\nGIST: <what was done or found, one line>\nQUESTION: <one question>\n- <an answer to pick>\n"
        "- <another>\nASSUMED: <one assumption, one line>\n```\n\n"
        "Do not ask anything in your text outside the block: a question there is not seen.")
