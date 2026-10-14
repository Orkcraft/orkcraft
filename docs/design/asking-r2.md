# Research R2 — how an ork's run asks the person and marks an assumption

Status: written 2026-10-14 for phase 1, lane 3 (A1). Answers [open-questions.md](open-questions.md) R2 for Claude Code;
Codex and agy follow the same way later. Feeds [ork-console.md](ork-console.md) §4 and §20 and
[decisions-2026-10.md](decisions-2026-10.md) §8 (the no-logs path).

## 1. How a run starts today (R1, as far as R2 needs it)

- **An ork's work is one headless call per run**, never a live terminal: `claude -p <prompt> --output-format json
  --permission-mode acceptEdits [--resume <session>]` (`realm/harnesses.py` `_claude_work`, run by `realm/jobs.py`
  `run_work`). The run ends; its JSON envelope gives the answer (`result`) and the `session_id`.
- **The Agent pool resumes the ork's session** for a follow-up, a rework or an answer (`core/workers/barracks.py`):
  so "ask, stop, get the answer, go on" is already one more `--resume` run with the answer as its prompt.
- **It already has a way to ask:** an ork that cannot go on ends with one line `QUESTION: …`; the steward answers it
  from its rules or hands it to the person (🔥, the task's status `asked`); the person's answer goes back by
  `--resume`. Nothing marks an assumption, a question has no answers to pick from, and nothing counts any of it.
- **A live terminal exists only when the person opens one** (an ork's terminal, "take over"): there Claude Code's own
  menus are seen by the roster (`realm/orcs.py` `detect_prompt`) and answered by typing a digit. Out of scope here.
- **The hooks** (`orkcraft/hooks/`, written by `orkcraft hooks install`): a session log (`session.py`) and the Warder
  (`warder.py`, PreToolUse). Since Q16 they are asked for once before quest 4, so a run can count on them only after.

## 2. The three ways

| | how | what it costs | what it gives |
|---|---|---|---|
| **a. Claude Code's own question form** (`AskUserQuestion`) | In `-p` it is offered only when the run has a *permission host* (an SDK `canUseTool`, or `--permission-prompt-tool`); a bare `claude -p` has none. A PreToolUse hook can return `permissionDecision: "defer"`: the run ends with `stop_reason: "tool_deferred"` and the questions (`questions[].question`, `options[].label`, `multiSelect`); the answer goes back by `--resume`, the hook then returns `allow` with `updatedInput.answers`. | A hook on every ork's run, i.e. in the person's project (Q16) or a `--settings` per run; `defer` holds only when the turn makes a single tool call; a protocol tied to this one tool and its version; **nothing for assumptions**. About 2 days. | The model's own, well-trained form: questions with options, no prompt to teach. |
| **b. A tool Orkcraft gives every ork over MCP** (`ask`, `assume`) | `--mcp-config` with a small stdio server, `--allowedTools mcp__orkcraft__ask,…`. To *wait* for the person the call must block (idle limit 30 min on stdio unless it sends progress, wall clock about 28 h), holding the process and the worktree; or it returns "asked, end your run", which is the block of c. by another road. | A server process per run; merging with the Test bench's own `--mcp-config` / `--strict-mcp-config` (`_claude_mcp`); a channel from the server back to the town; every tool's MCP flags (Codex, agy differ). About 3 days. | Structured calls, mid-run; the same tool for every AI tool that takes MCP — the way for Codex and agy later. |
| **c. A block at the end of the run** | The ork's prompt says: when you ask or assumed anything, end with a fenced block `asks` of `QUESTION:` lines (each with `- ` answers to pick) and `ASSUMED:` lines. The town takes the block off the answer and reads it (`realm/asking.py`). | About 150 prompt tokens a run; the model may forget or bend the format (the parser is lenient; the older `QUESTION:` line still reads; the counts show how often); a question comes only at the run's end — which is what "ask and wait" means anyway (ork-console §4). Half a day on top of what the pool has. | Questions with answers, assumptions, in **every** AI tool that returns text; no new process, no hook, no new flag; the pool's `--resume` does the rest. |

Also looked at: **`--json-schema`** (`-p` only; the envelope gets a validated `structured_output` at the end of an
agentic run). It makes c. strict for Claude Code, but it forces the whole answer into JSON, other tools have no such
flag, and whether a `--resume` run applies it again is not documented. **The Stop hook** sees
`last_assistant_message` and can send the ork back ("you asked in your text; put it in the block"); a cheap guard for
later, once the hooks are installed.

## 3. Recommendation: c., the block at the end — built (A2)

It is the cheapest thing that works (decisions §1 rule 5), it needs nothing installed before quest 4, and it is the
same for every AI tool, so Codex and agy only need the rule in their prompt. It also gives the gist of §20 the same
road later (a `GIST:` line in the same block, P1).

What it costs, said plainly: the format rests on the model following the prompt. The local event log counts every
question, assumption, answer and stop (A0), so a week of use shows whether runs bend it; if they do, the next steps,
in order, are the Stop hook's guard (the hooks are there by then), `--json-schema` for Claude Code, and b. (an MCP
`ask` tool) when an ork must ask **mid-run** without ending — the only thing c. cannot do.

## 4. What A2 built

- `realm/asking.py`: the block's format, its parser (the last `asks` block; the older line still reads), the rule an
  ork's prompt gets.
- `core/workers/barracks_asks.py`: an Agent pool ork on Claude Code is told the block (others keep the line); its
  questions go to the steward, then to the person **pinned on top of the task with their answers as buttons**; its
  assumptions are kept on the task and named on its result ("**2 assumptions**", before the report); every question,
  assumption, answer (by whom, after how long) and stop is counted into `.orkcraft/usage/events.jsonl`.
- `orkcraft usage local` prints a week's counts: the log check of ork-console §1a, done by the owner's own use.
