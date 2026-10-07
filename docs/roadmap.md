# Roadmap

What is planned and not built yet. Each item says why it matters and what "done" looks like; the
reference ([reference.md](reference.md)) describes only what works today.

## 🏰 Town Hall: the Council and the Elders

### Guarding agy as Claude Code is guarded

The 🛡 Warder is a `PreToolUse` hook for Claude Code and Codex (`orkcraft/hooks/warder.py`). agy has
one too: it reads `PreToolUse` from `.agents/hooks.json` and `~/.gemini/config/hooks.json`, and a
`deny` stops the call ([agy-guard](design/agy-guard.md) has the format, the tool names and what is
still unverified). orkcraft does not install it yet, so agy sessions run with only agy's own
`--sandbox` and permission prompts, and the onboarding's Warder step says so.

What remains:

- a Warder mode for agy (`python3 -m orkcraft.hooks.warder agy`): read `toolCall.name` /
  `toolCall.args` and `workspacePaths`, answer `{"decision": "deny" | "ask", "reason": …}`;
- `orkcraft hooks install` writing the hooks files: the Warder and the session hook into
  `.agents/hooks.json`, and the global `~/.gemini/config/hooks.json` where agy needs it;
- a smoke test on a live agy: a denied `rm -rf` and a denied `.env` read, in a print run and in a
  War Tent session, before the onboarding stops saying agy is unguarded.

### The Council's watchers

Drummer, Taskmaster, Alchemist and Keeper are still draft agents in `watchers/`; only the Warder
runs. Taskmaster's budget duty is covered by the 🪙 / 🪵 limits.
Their jobs, new names (Pacer, Treasurer, Alchemist, Peon) and stages are in
[design/simplify.md](design/simplify.md) §6.

## 🪙 Codex: its spend

Codex runs as a harness (`codex exec`) and in the War Tent, and its plan's windows show under
⏳ Limits, but the HUD does not know what it costs: `codex exec --json` reports tokens and no price,
so its runs count as unpriced (`+`). The research and the plan are in
[design/codex-limits.md](design/codex-limits.md) §4 and §5.2.

- Read OpenAI's per-token prices for the Codex models (`gpt-6-*`) first-hand and write them, with
  their date, into a second table in `sources/pricing.py`; the numbers in the note are unverified.
- Price `codex exec` runs and War Tent sessions from the model and the token counts (an
  API-equivalent estimate for a ChatGPT login, as for Claude Pro / Max).

Done when a Codex run on a known model shows 🪙 instead of `+`.
