"""One run of a unit, read from a Claude Code transcript (JSONL) — for the Unit Chronicles.

Transcript lines are JSON objects with `type` (`user` / `assistant` / `system` / `summary`),
`timestamp` (ISO 8601) and `message` (`role`, `content`, and `usage` on assistant messages).
`content` is a string (a human prompt) or a list of blocks: `text`, `thinking`,
`tool_use` (`id`, `name`, `input`), `tool_result` (`tool_use_id`, `content`, `is_error`).
One assistant message can span several lines that repeat the same `message.id` and `usage`, so
token usage is counted once per message id.

Read-only and bounded: at most `MAX_BYTES` of a transcript are parsed and every text is cut to
`DETAIL_CHARS`. The content is shown locally only (it can quote private nodes).
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.sources import pricing

MAX_BYTES = 20 * 1024 * 1024
DETAIL_CHARS = 2000
INTERRUPTED = "[Request interrupted by user"
EDIT_TOOLS = ("Edit", "MultiEdit", "Write", "NotebookEdit")

DONE, WAITING, HALTED, UNKNOWN = "✅", "❓", "🛑", "…"


@dataclass
class Step:
    kind: str                  # prompt | text | tool | result | error
    title: str                 # one line for the list
    detail: str = ""           # the expanded text
    ts: dt.datetime | None = None
    diff: str = ""             # for edit tools: a unified-style view of the change
    tool: str = ""             # for tool steps: the tool's name (`Bash`, `mcp__github__get_file`)


@dataclass
class Run:
    path: str
    steps: list[Step] = field(default_factory=list)
    started: dt.datetime | None = None
    ended: dt.datetime | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0                              # API-equivalent, priced models only
    models: set[str] = field(default_factory=set)
    unpriced: set[str] = field(default_factory=set)    # models with no published price
    last_context_tokens: int = 0                       # what the model read on its last turn
    outcome: str = UNKNOWN
    truncated: bool = False
    error: str = ""

    @property
    def duration_s(self) -> float | None:
        if self.started and self.ended:
            return (self.ended - self.started).total_seconds()
        return None

    @property
    def context_tokens(self) -> int:
        """🪵 — the context of the last turn (not the sum over turns: every turn re-reads it)."""
        return self.last_context_tokens

    @property
    def cost(self) -> float | None:
        """🪙 — None when nothing could be priced; partial when some models are unknown."""
        if self.unpriced and not self.cost_usd:
            return None
        return self.cost_usd

    @property
    def diffs(self) -> list[Step]:
        return [s for s in self.steps if s.diff]


def _ts(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cut(text: str) -> str:
    return text if len(text) <= DETAIL_CHARS else text[:DETAIL_CHARS] + " …"


def _first_line(text: str, width: int = 100) -> str:
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return line if len(line) <= width else line[: width - 1] + "…"


def _result_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _tool_title(name: str, inp: dict) -> str:
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description"):
        if isinstance(inp.get(key), str) and inp[key]:
            return f"{name} · {_first_line(inp[key], 80)}"
    return name


def _edit_diff(name: str, inp: dict) -> str:
    path = str(inp.get("file_path") or inp.get("notebook_path") or "")
    head = f"--- {path}\n+++ {path}\n"
    if name == "Write":
        return head + "\n".join("+" + l for l in str(inp.get("content", "")).splitlines())
    edits = inp.get("edits") if name == "MultiEdit" else [inp]
    out = []
    for e in edits if isinstance(edits, list) else []:
        if not isinstance(e, dict):
            continue
        out.append("@@")
        out += ["-" + l for l in str(e.get("old_string", "")).splitlines()]
        out += ["+" + l for l in str(e.get("new_string", e.get("new_source", ""))).splitlines()]
    return head + "\n".join(out)


def read_run(path: str | Path) -> Run:
    """Parse a transcript into steps and metrics; never raises (errors land in `Run.error`)."""
    run = Run(str(path))
    seen_usage: set[str] = set()
    pending: dict[str, Step] = {}
    last_kind = ""
    try:
        f = Path(path).open(encoding="utf-8", errors="replace")
    except OSError as e:
        run.error = str(e)
        return run
    read = 0
    with f:
        for line in f:
            read += len(line)
            if read > MAX_BYTES:
                run.truncated = True
                break
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or e.get("type") not in ("user", "assistant"):
                continue
            ts = _ts(e.get("timestamp"))
            if ts:
                run.started = run.started or ts
                run.ended = ts
            msg = e.get("message") if isinstance(e.get("message"), dict) else {}
            content = msg.get("content")
            if e["type"] == "user":
                if isinstance(content, str):
                    if content.startswith(INTERRUPTED):
                        run.steps.append(Step("error", "🛑 interrupted by the operator", "", ts))
                        last_kind = "interrupted"
                    else:
                        run.steps.append(Step("prompt", f"🗣 {_first_line(content)}", _cut(content), ts))
                        last_kind = "prompt"
                    continue
                for b in content if isinstance(content, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and str(b.get("text", "")).startswith(INTERRUPTED):
                        run.steps.append(Step("error", "🛑 interrupted by the operator", "", ts))
                        last_kind = "interrupted"
                    elif b.get("type") == "tool_result":
                        pending.pop(str(b.get("tool_use_id", "")), None)
                        text = _result_text(b.get("content"))
                        kind = "error" if b.get("is_error") else "result"
                        mark = "✗" if b.get("is_error") else "↳"
                        run.steps.append(Step(kind, f"{mark} {_first_line(text) or '(empty)'}", _cut(text), ts))
                        last_kind = kind
                    elif b.get("type") == "text":
                        text = str(b.get("text", ""))
                        run.steps.append(Step("prompt", f"🗣 {_first_line(text)}", _cut(text), ts))
                        last_kind = "prompt"
                continue
            # assistant
            mid = str(msg.get("id") or "")
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else None
            model = str(msg.get("model") or "")
            if usage and mid not in seen_usage:
                if mid:
                    seen_usage.add(mid)
                if model and not model.startswith("<"):   # "<synthetic>" messages cost nothing
                    run.models.add(model)
                    cost = pricing.usage_cost(model, usage)
                    if cost is None:
                        run.unpriced.add(model)
                    else:
                        run.cost_usd += cost
                run.last_context_tokens = pricing.context_of(usage)
                run.input_tokens += int(usage.get("input_tokens") or 0)
                run.output_tokens += int(usage.get("output_tokens") or 0)
                run.cache_read_tokens += int(usage.get("cache_read_input_tokens") or 0)
                run.cache_write_tokens += int(usage.get("cache_creation_input_tokens") or 0)
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and str(b.get("text", "")).strip():
                    text = str(b["text"])
                    run.steps.append(Step("text", f"💬 {_first_line(text)}", _cut(text), ts))
                    last_kind = "text"
                elif b.get("type") == "tool_use":
                    name = str(b.get("name") or "tool")
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    step = Step("tool", f"🔧 {_tool_title(name, inp)}",
                                _cut(json.dumps(inp, ensure_ascii=False, indent=2)), ts,
                                diff=_cut(_edit_diff(name, inp)) if name in EDIT_TOOLS else "", tool=name)
                    run.steps.append(step)
                    run.tool_calls += 1
                    pending[str(b.get("id", ""))] = step
                    last_kind = "tool"
    if last_kind == "interrupted":
        run.outcome = HALTED
    elif pending and last_kind == "tool":
        run.outcome = WAITING   # a tool call with no result yet: a permission prompt or still running
    elif last_kind == "text":
        run.outcome = DONE
    return run
