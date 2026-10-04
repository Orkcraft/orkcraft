# Roadmap

What is planned and not built yet. Each item says why it matters and what "done" looks like; the
reference ([reference.md](reference.md)) describes only what works today.

## 🏰 Town Hall: the Council and the Elders

### Research: guarding agy as Claude Code is guarded

The 🛡 Warder is a Claude Code `PreToolUse` hook (`orkcraft/hooks/warder.py`); agy has no documented
pre-tool hook, so its sessions run unguarded — only `--sandbox` and its own modes stand between an
agy agent and the machine. The Elders read agy's permission menus too, but nothing denies a
dangerous command before it runs.

Find out, for the agy version orkcraft supports:

- whether agy has a hook, plugin or policy file that can veto a tool call (shell, file write, network)
  before it runs, and in what format it answers;
- if not: what its `--sandbox` and `--mode` actually confine (folders, network, shell), and whether a
  wrapper — a restricted `PATH`, a shell shim, the terminal stream orkcraft already reads — could stop
  what the Warder denies for Claude (`rm -rf` of the repository, `curl | sh`, force pushes, secrets);
- how agy's permission menus read on screen, so the Elders' option reading (`realm/elders.py`) stays
  right for it;
- how agy reports spend (`--output-format json`), so its runs stop being counted as unpriced 🪙.

Done when a short design note says which of these orkcraft can rely on, and the onboarding's Warder
step either guards agy or says plainly that it cannot.

### The Council's watchers

Drummer, Taskmaster, Alchemist and Keeper are still draft agents in `watchers/`; only the Warder
runs. Taskmaster's budget duty is covered by the 🪙 / 🪵 limits.

## 🪙 Codex: its limits and its spend

Codex runs as a harness (`codex exec`) and in the War Tent, but the HUD knows nothing of what it
costs: `codex exec --json` reports tokens and no price, so its runs count as unpriced (`+`), and
there is no Codex row under ⏳ Limits.

Find out, for the Codex version orkcraft supports:

- where its plan's windows can be read without spending quota (`/status` shows them in the TUI;
  older session files carried `rate_limits`, newer sessions live in an sqlite store);
- whether OpenAI publishes per-token prices for the Codex models (`gpt-6-*`), so an API-billed
  Codex can be priced like Claude in `sources/pricing.py`.

Done when the ⏳ Limits tab shows Codex next to claude and agy, or a note says why it cannot.
