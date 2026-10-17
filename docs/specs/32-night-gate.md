# Spec 32 — the night gate: `dev` tested every night, `main` by one press (decisions §39, §42, §45)

Branch `spec/32-night-gate` · **Builds:** Claude · **Review:** full · track 1, **P0** (§45 makes it so).

## Why
Every change lands on `dev` on its critical tests (§45). `main` is what users install, so it takes `dev` only after
deep checks and the owner's pass. The owner may not look every day, so the deep checks run by themselves every night,
and the morning shows one report and one press.

## What
1. **The night run** (`core/night_gate.py`, new, no face; scheduled by the host's clock as the Night round is):
   at `gate.night_hour` (default 3, local; a machine setting, cleaned) when `dev`'s head changed since the last run
   (else nothing): a worktree off `dev`'s head, then in order, each step recorded:
   1. the full suite (`python -m pytest -q`), 2. the browser tests (the `*_browser.py` files),
   3. **the daily check** (§39): one Claude session (tier from `gate.check_tier`, default warrior; budget
      `gate.night_budget_usd`, default 2.00, said in the report; stopped at the budget) reads the commits merged into
      `dev` since `main` (subjects, the ideas they came from: `.orkcraft/ideas/merged.jsonl`, the ideas' pages) and the
      failures of steps 1–2, and fixes what fails on a branch `night/<date>`; its fix lands on `dev` only through the
      same gate as a task (critical tests, then steps 1–2 again).
   The result: `.orkcraft/gate/night/<date>.json` `{"dev": sha, "main": sha, "commits": [{sha, subject, idea}],
   "steps": [{"name", "ok", "summary", "failed": [names]}], "fixed": [..], "not_fixed": [..], "cost", "green": bool,
   "started", "finished"}`. Repository lock shared with the board's runner (`realm/idea_git.py`).
2. **Pass to main** (`gate.pass_night {"date"}`): only for a green report whose `dev` sha is still `dev`'s head (else:
   *dev moved since the night; run again*); fast-forwards `main` to it (a merge commit only if `main` has commits of its
   own: a critical release), pushes, records `passed_by: "you"`, `passed_at`. `gate.run_night` runs it now (from the
   gate or the board).
3. **Where it shows:** the Review gate's window and **the board's Today** (focus mode shows only the board): one card
   **Night report · <date>**: green → *N changes ready for main* · the steps' one-line summaries · cost · **Pass to main**
   (a confirm naming the count) · *Details* (the commits, each with its idea, and the steps' failures); red → in **Needs
   you** with what failed and what the check could not fix. The phone shows the same card; Pass to main asks once.
   A push for the report only when red (green goes in the morning's digest, §44.4).
4. **Never:** the night run never touches `main`; a red step never lands anything; the check session never pushes to
   `main`; Stop all stops the night run.

## Tests
Unit (temp repo + bare origin, a stub `claude`, a tiny suite): a night with `dev` unchanged does nothing; green →
report, Pass to main fast-forwards and pushes; red step → no pass, Needs you; the check fixes a failing test on
`night/<date>` and it lands on `dev` through the gate; budget stop; `dev` moved after the night → Pass refused; Stop all.
Browser (desktop + 390 px, both looks): the green card and its confirm, the red card in Needs you. The critical tests,
`tests/test_gui_wording.py`, the touched modules' tests. Screenshots to `docs/design/img/night-gate/`.

Change nothing outside: `core/night_gate.py`, `realm/idea_git.py` (shared helpers only), `gui/ideas.py` (the card and
the two commands; or a new `gui/night_gate.py` wired in `gui/host.py`), `gui/mobile.py` (allowlist, news), `settings.py`
(the `gate.*` keys), the board's JS (`gui/static/js/board/*`, `gui/static/pwa/board.js`, `pwa/app.css`), the Review
gate's window only to show the same card, and the tests.
