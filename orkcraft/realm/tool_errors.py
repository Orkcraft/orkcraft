"""When an AI tool fails: what kind of failure it is, in one plain line, and what the person can do.

    raise ToolError("claude", why, code=1)    # a run of a tool failed (str(): "claude exited with 1: …")
    tool_errors.classify(text, code)          # "missing" | "login" | "limit" | "network" | "other"
    tool_errors.report(err, enabled, main)    # what the failure says on the bus (core: Town.tool_failed)

A face shows the report as a toast: "<Tool> hit an error", the line, and Switch to another tool that is
installed, Retry, Details (the tool's own words, kept whole to copy). A service never shows it itself.
"""
from __future__ import annotations

import re
import shutil
import threading
from typing import Callable, Iterable

from orkcraft.realm import harnesses

MISSING, LOGIN, LIMIT, NETWORK, OTHER = "missing", "login", "limit", "network", "other"
KINDS = (MISSING, LOGIN, LIMIT, NETWORK, OTHER)
DETAIL_KEEP = 4000                   # the tool's own words kept for Details

# The first kind whose words are in the tool's output (lower case). Order matters: a 401 that says
# "connection" is a login.
_WORDS: tuple[tuple[str, re.Pattern], ...] = (
    (MISSING, re.compile(r"command not found|not found \(|cli not found|^\S+ not found$|no such file or directory"
                         r"|is not recognized as an internal|enoent")),
    (LOGIN, re.compile(r"not logged in|log ?in again|please (run )?/?log ?in|/login|logged out|unauthori[sz]ed"
                       r"|\b401\b|authenticat|invalid (x-)?api[ _-]?key|api key (is )?(missing|invalid|not set)"
                       r"|(token|session|credentials?|login) (has )?expired|expired (token|session|credentials?)"
                       r"|no credentials|oauth|sign ?in")),
    (LIMIT, re.compile(r"\b429\b|\b529\b|rate[ _-]?limit|too many requests|overloaded|usage limit|limit reached"
                       r"|hit your limit|quota|resource[ _-]exhausted|capacity|credit balance")),
    (NETWORK, re.compile(r"econnrefused|econnreset|enotfound|etimedout|eai_again|getaddrinfo|network"
                         r"|connection (refused|reset|error|timed out)|could not connect|unable to connect"
                         r"|failed to connect|could not resolve|name resolution|socket hang up|fetch failed|offline")),
)

# What happened, in one line; {tool} is its title.
LINES = {
    MISSING: "{tool} is not installed, or Orkcraft cannot find it on this computer.",
    LOGIN: "{tool} is not signed in, or its sign-in has expired.",
    LIMIT: "{tool} hit a usage limit or its service is overloaded.",
    NETWORK: "{tool} could not reach its service. Check the internet connection.",
    OTHER: "{tool} stopped with an error before it finished.",
}


class ToolError(RuntimeError):
    """A run of an AI tool failed. Its str() is the line logs always had ("codex exited with 1: …");
    `detail` keeps the tool's own words whole, `kind` says what kind of failure it is."""

    def __init__(self, harness: str, detail: str, code: int | None = None, kind: str = "") -> None:
        self.harness, self.code = harness, code
        self.detail = (detail or "").strip()[:DETAIL_KEEP]
        self.kind = kind if kind in KINDS else classify(self.detail, code)
        if code is None:
            said = self.detail[:300]
        else:
            said = f"{harness} exited with {code}: {self.detail[:300]}"
        super().__init__(said)
        _LAST.error = self


_LAST = threading.local()       # the newest ToolError made on each thread (`taken`)


def taken() -> ToolError | None:
    """The newest AI tool failure on this thread since the last call, even one a caller turned into an
    error string of its result (a face's job reads it to offer Switch and Retry)."""
    error = getattr(_LAST, "error", None)
    _LAST.error = None
    return error


def classify(text: str, code: int | None = None) -> str:
    """The kind of a tool's failure from its words (and exit code: 127 is a command not found)."""
    low = (text or "").lower()
    if code == 127:
        return MISSING
    for kind, words in _WORDS:
        if words.search(low):
            return kind
    return OTHER


def missing(harness: str, command: str) -> ToolError:
    """The tool's command is not on this computer."""
    return ToolError(harness, f"{command} not found", kind=MISSING)


def installed(harness_id: str, which: Callable[[str], str | None] | None = None) -> bool:
    h = harnesses.get(harness_id)
    return bool(h and (which or shutil.which)(h.bin))


def others(failed: str, enabled: Iterable[str], which: Callable[[str], str | None] | None = None,
           broken: Iterable[str] = ()) -> list[dict]:
    """The tools to switch to: installed here, not the one that failed nor one that failed to start or
    sign in (`broken`); the ones turned on in Settings first, in the registry's order."""
    on, broken, which = set(enabled), set(broken) | {failed}, which or shutil.which
    found = [h for h in harnesses.REGISTRY.values() if h.id not in broken and which(h.bin)]
    found.sort(key=lambda h: h.id not in on)
    return [{"id": h.id, "title": h.title, "mark": h.mark, "on": h.id in on} for h in found]


def install_hint(failed: str, which: Callable[[str], str | None] | None = None) -> str:
    """How to get a second tool to switch to, when there is none."""
    which = which or shutil.which
    for h in harnesses.REGISTRY.values():
        if h.id != failed and not which(h.bin):
            return f"No other AI tool is installed. To have one to switch to, install {h.title}: {h.install}"
    return "No other AI tool is installed."


def what_to_do(err: ToolError) -> str:
    """The step the person can take for this kind, beyond Switch and Retry ("" when none)."""
    h = harnesses.get(err.harness)
    if h is None:
        return ""
    if err.kind == MISSING:
        return f"Install it: {h.install}"
    if err.kind == LOGIN:
        return f"Sign in again in a terminal: {h.login}"
    if err.kind == LIMIT:
        return "Wait a few minutes, or switch to another tool."
    return ""


def report(err: ToolError, enabled: Iterable[str], main: str, where: str = "",
           which: Callable[[str], str | None] | None = None, broken: Iterable[str] = ()) -> dict:
    """What a tool's failure says on the bus (`bus.TOOL_ERROR`). `main`: the machine's main tool —
    Switch changes it, so it is offered only when the tool that failed was the main one."""
    title = harnesses.title(err.harness)
    is_main = err.harness == main
    switch = others(err.harness, enabled, which, broken) if is_main else []
    if not is_main:
        hint = f"This step is set to use {title}. Choose another tool in its building's settings."
    elif not switch:
        hint = install_hint(err.harness, which)
    else:
        hint = ""
    h = harnesses.get(err.harness)
    return {"harness": err.harness, "tool": title, "mark": h.mark if h else "", "kind": err.kind, "where": where,
            "title": f"{title} hit an error", "line": LINES[err.kind].format(tool=title),
            "action": what_to_do(err), "detail": err.detail or str(err), "code": err.code,
            "switch": switch, "hint": hint, "main": is_main}
