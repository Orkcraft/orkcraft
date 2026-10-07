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

## 🪙 Codex: its prices

`codex exec` runs and War Tent sessions are priced from their model and token counts
(`pricing.codex_usage_cost`, [design/codex-limits.md](design/codex-limits.md) §5.2), but OpenAI's
table in `sources/pricing.py` (`OPENAI_PRICES`) is empty: openai.com could not be read from the
machine it was built on, and a price is never guessed. Until it is filled, Codex runs stay
unpriced (`+`).

- Read OpenAI's per-token prices for the Codex models (`gpt-6-*`) first-hand from
  <https://developers.openai.com/api/docs/pricing>. Write them into `OPENAI_PRICES` with
  `OPENAI_PRICES_AS_OF`. Include the long-context threshold and whether a cache write costs more
  than input. The numbers in the design note's §4 are unverified.

Done when a Codex run on a known model shows 🪙 instead of `+`.
