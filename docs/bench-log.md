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
