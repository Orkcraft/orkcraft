# Roadmap

What is planned and not built yet. Each item says why it matters and what "done" looks like; the
reference ([reference.md](reference.md)) describes only what works today.

## 🏰 Town Hall: the Council and the Elders

### Guarding agy as Claude Code is guarded: the live check

The 🛡 Warder guards agy through agy's own `PreToolUse` hook. Two pieces are built and covered by
tests written from the documented format: `python3 -m orkcraft.hooks.warder agy`, and
`orkcraft hooks install`, which writes `.agents/hooks.json` and, after asking,
`~/.gemini/config/hooks.json` (agy 1.1.12 or later). [agy-guard](design/agy-guard.md) has the
format and what is still unverified. Nobody has run it on a live agy yet, so the onboarding (the
window's and the terminal's) still says agy is unguarded, and a town is raised without agy's hook.

What remains is the smoke test of [agy-guard §8](design/agy-guard.md#8-smoke-test-on-a-live-agy)
on a machine with agy:

- a denied `rm -rf .git` and a denied `.env` read, in a print run and in a War Tent session, with
  the file tools' argument keys read from a probe hook;
- then `"agy_warder_checked": true` in the machine settings, and the agy version tested noted in
  the design note.

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
