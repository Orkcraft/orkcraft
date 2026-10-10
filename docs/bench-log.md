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
