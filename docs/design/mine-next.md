# Design — the Mine, what is left

Status: written 2026-10-08, after the Mine was built ([mine.md](mine.md) §15). Nothing here is built. The
Mine works and is tested with fake tools; this is what stands between it and research a person can trust
without reading every source.

## 1. Why

The Mine's promise is the check: a finding is confirmed only when two different minds found it on two
different sites. Three things weaken that promise today:

- **Fewer minds than there could be.** Only Claude Code, Codex and Hermes search the web. agy could be a
  fourth, from another family (Google), but its reading run drops the `web` flag.
- **A mind is guessed from the tool.** A run's model is the tier asked for, not the model that answered.
  Hermes or pi on a Claude model count as their own mind, so Claude can "confirm" Claude.
- **Nobody has run it on live tools.** The prompts, the JSON the tools answer, the cost estimate and the
  rounds are tuned on fakes.

The rest (§3) makes it easier to use and cheaper, and nothing in §3 matters before §2 is done.

## 2. First: what the check rests on

### 2.1 agy searches the web

`harnesses.REGISTRY["agy"]` has `web=False`, and its `read` ignores `web`. Find out from agy's own
documentation and `agy --help` whether a reading run can search and open pages, and with which flag.

- If it can: pass the flag in its `read`, set `web=True`, add `google` to the families agy runs on
  (`research._TOOL_FAMILY` has it already), and add agy to the default `tools`.
- If it cannot: say so in [harnesses.md](harnesses.md) and in the Mine's window (*agy cannot search the
  web*), so nobody wonders why it is missing.

**Done:** a research on a machine with agy on shows four columns, or the window says why it shows three.

### 2.2 The mind is the model that answered

`roads.run_agent` returns text, cost and tokens (`result_of(...)[:3]`); each tool's result also says the
model (`Harness.result` → its fourth part, or the session's own record: Hermes' `state.db`, pi's session
JSONL). Keep it, and set the finding's `mind` from it (`research.mind(tool, model)`), not from the tier.

- Hermes and pi say which provider served the run: read it there when the model name alone is ambiguous.
- A tool that does not say: `mind` stays the tool, and the window marks that column *model not known*.
- Two tools on one family in `tools`: the window says *Claude Code and Hermes both run Claude: they count
  as one* before Start, so the person can drop one and save the money ([mine.md](mine.md) §14).

**Done:** `tests/test_mine.py` has a fake Hermes that reports a Claude model; its findings never confirm
Claude Code's.

### 2.3 A live smoke test

On a machine with Claude Code, Codex and Hermes logged in, run three researches (a product price, a law's
date, a technical fact with old and new answers) and note for each tool:

- whether its answer is the JSON the prompt asks for, and what it does instead when not;
- how many findings and sources, and how many sources do not open;
- what each round costs, against `research.estimate`;
- whether a debate changes anything, or only costs.

Then fix the prompts, set `SEARCH_USD` and `PLAN_USD` from what was measured, and write the numbers into
[mine.md](mine.md) §15. **Done:** the three reports are kept with the design note's numbers, and the
estimate before Start is within the range of what the runs cost.

## 3. Then

### 3.1 Sources that do not open

[mine.md](mine.md) §5 drops a source that does not open; the build does not check. Check each source once,
after a search round, from the worker's thread: a GET with a short timeout, through the machine's proxy
settings, a size cap, no cookies. A page that does not answer, or answers 4xx/5xx, is dropped from the
finding and named in the report (*2 sources did not open*). The quoted line is looked for in the page's
text: a quote not found makes that source count for nothing, with the reason shown. Off in the demo and in
tests (a fake fetcher). This is the first request the Mine itself sends out: `EFFECTS` and the reference
say so.

### 3.2 One text copied, harder cases

The check counts a quote copied on two sites once. It does not see a page that cites another (a news item
retelling a press release). With §3.1 the page text is at hand: a source whose text links to another
source of the same finding, or names it as its source, counts with it as one.

### 3.3 The debate can change a claim

A debate's verdict is *hold* or *withdraw*. Add *change*: the tool states the claim the pages do support,
which becomes a finding of its own and is grouped again. Today a half-right claim can only be withdrawn.

### 3.4 Search more waits its turn

*Search more* in Answers is refused while another research runs. Queue it instead: a queued item that
names the research and the dispute, run after the current one, with its own line in the queue.

### 3.5 A repeat from the Calendar

[mine.md](mine.md) §8 says a repeat is set in the Mine's window or as *+ Repeat* on the Calendar. Only the
Mine's window does it. Add *+ Repeat* to the Calendar's window when the town has a Mine: the question, the
schedule, the limit; it writes the Mine's `repeats` line.

### 3.6 A page added by hand

A source behind a login or a paywall cannot be read by a tool. In a dispute, let the person paste a link
or a file (*Add a source*): it counts as the person's, like *Accept*, and the report says so.

## 4. Outside the code

- **Usage statistics.** `tools/usage-worker/worker.js` knows the type `mine` in the repository; the proxy it
  is deployed as does not until it is deployed again. Until then the Mine's usage events are refused.
- **A release.** The Mine is in `main` without a version of its own. When §2.1–§2.3 are done, raise
  `__version__` and add the release to `updates.json` ([updates.md](../updates.md)), not critical.

## 5. Order

1. §2.3 the smoke test — it decides whether §2.1 and §2.2 change the numbers enough to matter.
2. §2.2 the mind from the model.
3. §2.1 agy.
4. §4 the usage proxy and the release.
5. §3.1–§3.6, each on its own, by what the smoke test showed hurts most.
