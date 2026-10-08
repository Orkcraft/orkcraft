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
Their jobs, new names (Pacer, Treasurer, Alchemist, Peon) and stages are in
[design/simplify.md](design/simplify.md) §6.

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

## 🏕️ Agent pool: what is wanted decides the way — what is left

[design/barracks-flows.md](design/barracks-flows.md) stages 1–3 are built: the cart's kind of work, the pool's
order, the `reply` path in `read` mode held by the Review gate, the Reply check, the External listeners' per-source
kind. Its §14 *As built* says what was decided. These parts are not built yet.

### The `doc` path (§6, stage 4)

A document (a design, a decision, a brief) still takes the code change's way, and its ork still runs in `work`
mode.

- The `doc` path: one ork on the goal's planning tier, in `read` mode with write access to its one document only.
- With `debate` on, a Review board's members argue first.
- The document goes where the pool's `doc_to` says: the Review gate (default), the Wiki's inbox, or a docs pull
  request.
- Nothing it writes leaves the camp without the Review gate (`gate.HELD_WANTS` gains `doc`).
- Meet the design briefs the planning pool already leaves ([design/barracks-designs.md](design/barracks-designs.md))
  rather than duplicate them.

Done when a Calendar's *meeting soon* brief is written by a `doc` ork that cannot touch any other file, and waits
in the Review gate.

### Kinds set by a Router rule and a routing Review board (§4)

Today both pass on the kind their cart came with; neither sets one.

- A Router rule may name a kind: `match → route, want`.
- A Review board that routes names `WANT:` beside `ROUTE:`, and the kind goes on `team.routed`.

Neither may raise what the cart already carries, unless the person wrote the rule.

Done when the demo's Triage names *Reply* for a mail it gives an agent, so the tower need not.

### A reply that reads like code: the autonomy's say (§5)

The steward always leaves a to-do (*Looks like a code task — from …*). By the pool's autonomy it should instead
ask the person (🔥) when the autonomy is *Propose only*, and keep the to-do otherwise.

Done when, at *Propose only*, the question names the message and offers *Make it a code task*.

### The quick-add question through Claude

*What do you want done with these?* is asked on the token path of the External listeners' quick-add, not yet on
the *through Claude* path (`watchtower_add.what_claude`).

Done when a source added through Claude's connection keeps its kind in `wants`.

## ⛏️ The Mine: what its check rests on

The Mine is built and tested with fake tools ([design/mine.md](design/mine.md)). Before its "confirmed"
can be trusted: a smoke test on live Claude Code, Codex and Hermes (the JSON they answer, the cost against
the estimate), a finding's mind taken from the model that answered rather than the tool, and agy searching
the web or saying why it cannot. Then: sources that do not open, a page that retells another, a debate that
can change a claim, *Search more* queued, *+ Repeat* on the Calendar, a source added by hand; the usage
proxy deployed again and a release. All of it, with what "done" means, in
[design/mine-next.md](design/mine-next.md).
