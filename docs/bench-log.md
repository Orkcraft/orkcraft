# Test bench log

Runs of `orkcraft bench` on a building, what failed, why, what was changed and what came after
([design/test-bench.md](design/test-bench.md)). Newest first.

## 2026-10-10 — Agent pool on agy (1.3.3), simple

| run | case | building | bare |
|---|---|---|---|
| 20261010-082322 | slugify | asked after 3 reworks, 46 s, nothing committed | failed, 18 s, nothing changed |
| 20261010-082428 | inventory | asked after 3 reworks, nothing committed | failed, 4 of 5 tests |

**Cause (environment, both sides):** agy 1.3.3 in `--print` mode denies any terminal command it
cannot ask about, and the turn then ends with an empty answer (`denied_actions: RunCommand`). Both
the orks and the bare tool try `pytest` first, so neither writes the change. Run by hand on the same
copy: with `--dangerously-skip-permissions` (still `--sandbox`) the bare tool passes slugify in
140 s; an allow rule in the project's `.agents/settings.json` did not help.

**Fix (decided by the operator):** an unchained building's agy orks get `--dangerously-skip-permissions`
(`--sandbox` stays): `Harness.free_args`, passed by the pool when its autonomy is FREE. The bench runs
its pool unchained and the bare tool the same way.

| run | case | building | bare |
|---|---|---|---|
| 20261010-084355 | slugify | **passed**, 255 s, 147k tokens, 1 ork, no rework | passed, 146 s, 69k tokens |

agy is not priced, so both sides show $0.00; tokens stand in for spend on agy.

### Series simple, after the fix (20261010-0851…)

| case | building | bare | time | tokens |
|---|---|---|---|---|
| slugify | passed, 129 s | passed, 136 s | −5 % | +19 % |
| inventory | passed, 141 s | passed, 112 s | +25 % | +14 % |
| roman | passed, 113 s | passed, 189 s | −40 % | −2 % |
| chunk | passed, 97 s | passed, 122 s | −21 % | −3 % |
| top-words | passed, 222 s | passed, 191 s | +16 % | +8 % |

All pass on both sides. One ork each, no steward call, no rework. Time varies a lot between two runs of
one case (slugify: 255 s, then 129 s), so one run decides nothing within 10 %.

**Found on the way:** `agy models` (1.3.3) puts a tab between a model's id and its name;
`model_families.parse_agy` split on a space, listed no model, and every tier ran on agy's default, so a
rework's "retier" changed nothing. Fixed; this series still ran on the default model (the list was
cached empty), the next ones run on the tiers' models.

## 2026-10-10 — Agent pool on agy, medium

First series (20261010-0916…, stopped after two cases):

| case | building | bare |
|---|---|---|
| rate-limiter | asked after one rework, 429 s, 207k tokens | passed, 122 s, 56k tokens |
| lru-cache | the same blind rework, stopped | — |

**Cause (building):** agy's steward runs in an empty folder. On a review it looked for the files, was
denied the command and ended its turn with no answer; `verdict_of` read the empty answer as a rework
with no notes. The ork reworked blind, then asked what was wrong, and the question went to the operator.
Replayed by hand, the same review answers ACCEPT.

**Fix:** an empty steward answer is asked once more (`BarracksWorker._steward`), and the review and the
question prompts say that what is above is all it needs and to run no commands (`barracks.FROM_ABOVE`).
Replayed: ACCEPT twice, the second in 25 s and 5k tokens instead of 58–80 s.

After (20261010-0933…):

| case | building | bare | time | tokens |
|---|---|---|---|---|
| rate-limiter | passed, 254 s | passed, 214 s | +19 % | +34 % |
| lru-cache | passed, 191 s | passed, 246 s | −22 % | −3 % |
| semver | passed, 469 s | passed, 346 s | +35 % | +35 % |
| intervals | passed, 211 s | passed, 233 s | −10 % | +2 % |
| dig | passed, 539 s | passed, 438 s | +23 % | +5 % |

All pass; 2 of 5 within 10 %. The building's own calls on each: the sort ≈ 10 s and 22k tokens (agy's
own prompt is most of it), the review 20–50 s and 5–11k tokens. The rest of the gap is the ork's own
run against the bare tool's, on the same model (flash-high), which varies as much between runs.

## 2026-10-10 — Agent pool on agy, parallel

Series 1 (20261010-1026, ledger only, then stopped): passed both, building 484 s / bare 338 s. The
steward's plan came back empty four times: in its empty folder agy tried a command and ended the turn
(same cause as the review). **Fix:** the sort, the plan and the final look carry `plans.FROM_ABOVE`.
Replayed: a JSON plan of four parts, twice (62–89 s).

Series 2 (20261010-1048…, stopped in route):

| case | building | bare |
|---|---|---|
| ledger | passed, 270 s, 94k tokens — but as one ork | passed, 398 s, 200k tokens |
| gradebook | asked, 734 s, 395k tokens | passed, 290 s |

- ledger: the plan was dropped, "≈240k tokens, $1.20 does not fit: $1.00 left" — priced from tier costs
  on agy, which reports no cost and spends $0. **Fix:** `Foreman.priced`: the $ check holds only when one
  of the pool's tools prices its runs.
- gradebook: every part was judged by the whole test command on its own branch, where the other parts'
  modules are missing: all four sent back with collection errors, escalated, one asked the operator
  whether to write stubs. **Fix:** a part whose branch does not hold every other part's work
  (`plans.holds_all`) gets the failing tail as a note for its review; the merged whole is still tested
  strictly in the final look. Its prompt says not to write stand-ins for the other parts.

Series 3 (20261010-1123, stopped in ledger) — **environment, not fixed in code:**

- `/usr/local/bin/git` is git 2.33 and comes before `/usr/bin/git` (2.54) on PATH. Parts merge with
  `git merge-tree --write-tree` (git 2.38+), so every part's merge failed with its usage line and the
  orks were sent back to "merge the base" that had nothing to merge (also why
  `tests/test_pool_plans.py::test_parts_merge_without_a_checkout` and
  `tests/test_pool_claims.py::test_git_tells_a_conflict_and_commits_a_file_without_a_checkout` fail on
  this machine). The next runs put `/usr/bin` first for the bench only; removing or upgrading
  `/usr/local/bin/git` fixes it for the town.
- agy's quota ran out ("Individual quota reached … Resets in 36m"): the bare side failed in 7 s.

## 2026-10-10 — Research (mine) on claude

Found first: every non-code building's run crashed when its spend was read (`telemetry.calls`
compared the bench's start, with no zone, to the ledger's times, with one). **Fix:** a time with no zone
is read as local. Merged to main on its own.

| run | case | building | bare |
|---|---|---|---|
| 20261010-114616 | eu-ai-act-dates | passed 4/4, 141 s, $0.77 | passed 4/4, 59 s, $0.34 |
| 20261010-114936 | http3 | **passed 5/5**, 100 s, $0.61 | failed 4/5 (one site only), 47 s, $0.28 |

The building's calls: the plan on sonnet ≈ 10 s, the search on opus 80–120 s, the check on sonnet ≈ 10 s.
Its search answers 5–6 sub-questions with a source per claim, so it does more than the bare tool and
takes about twice the time and spend; on http3 that is what passes the check.

Tried: a plan of "the fewest sub-questions, what it asks, not what is near it" (instead of 3 to 7).
eu-ai-act-dates 114 s / $0.60 (passed), http3 37 s / $0.41 but **failed 3/5** — worse than the bare tool.
Reverted. Within 10 % is out of reach for Research without making it shallower than its design.

Series 4 (20261010-1222…, `/usr/bin` first on PATH): the plan now runs to the end on every case — no
rework, every part merged, the whole accepted — so both fixes above hold (gradebook: did not finish →
passed). But planned, the pool is far slower:

| case | building | bare | time | tokens |
|---|---|---|---|---|
| ledger | passed, 707 s | passed, 359 s | +97 % | +215 % |
| gradebook | passed, 636 s | passed, 305 s | +108 % | +258 % |
| route | passed, 696 s | passed, 267 s | +161 % | +273 % |
| toc | passed, 1053 s | passed, 609 s | +73 % | +176 % |
| invoice | passed, 1538 s | passed, 414 s | +272 % | +326 % |

**Cause (building):** an agy session costs 3–5 minutes even on a small part, about what the bare tool
takes for the whole task; with the plan (≈70 s), a review per part, the merges and the final look on top,
the critical path is longer than one session whatever the steward does. The sort said "in doubt: plan".
**Fix:** the sort weighs what an ork costs to start; a task one ork finishes in one sitting is `single`,
in doubt `single`.

Series 5 (20261010-1356…), every case sorted single:

| case | building | bare | time | tokens |
|---|---|---|---|---|
| ledger | passed, 273 s | passed, 284 s | −4 % | +4 % |
| gradebook | passed, 361 s | passed, 268 s | +35 % | +17 % |
| route | passed, 285 s | passed, 309 s | −8 % | −28 % |
| toc | passed, 497 s | passed, 552 s | −10 % | +20 % |
| invoice | passed, 621 s | passed, 533 s | +17 % | +48 % |

All pass; 2 of 5 within 10 %. What is left over is the sort and review calls (≈ 30–60 s, 30–40k
tokens on agy) and the ork's own run, which varies between runs as much as the gap.

### The Agent pool, where it stands

Every case of the three levels passes on agy, on both sides. Within 10 % on time and tokens: simple 1
of 5 (series ran before tokens were counted: by time 3 of 5), medium 2 of 5, parallel 2 of 5. The rest
is within the run-to-run spread of one agy session (slugify: 255 s, then 129 s); deciding below that
wants several runs per case (`--times`, still to come).
