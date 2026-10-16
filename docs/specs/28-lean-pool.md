# Spec 28 — the lean Agent pool: fewer tokens for the same parallel work

Branch `spec/28-lean-pool` · design: decisions §39, the owner's ask of 16 October (fewer tokens on roles and on the
talk between the pool and its orks) · **Builds:** Claude · **Review:** full · track 1, P1 (a simplification)

## Why
Where the pool spends tokens today without need (facts, 16 October):
- each ork question is answered by a separate one-shot steward call with no session, up to 3 per run
  (`core/workers/barracks.py:531-545`, `_steward` 590);
- every card gets a steward review with a diff of up to 20 000 chars (`core/workers/barracks_review.py:95-150`),
  even when its tests pass;
- the planner writes new personas (up to 2000 chars each) that are never removed (`barracks_plan.py:330-359`,
  `realm/personas.py`);
- the cold prompt puts per-task lines (the ork's name, its branch) before the stable rules, so the tools' prompt
  cache matches less (`barracks.py:639-656`);
- 🪵 (`lumber_context_limit_tokens`) only warns; an ork's session rolls over only after 5 tasks.

## Do
1. **Stable first.** In `BarracksWorker._prompt` (cold path), put everything that is the same for every task of this
   pool first, in a fixed order: the line on parallel agents and worktrees (without the ork's name), the commit
   rule, `## <keeper>'s rules` (orders), the ask rule, `OUTSIDE_RULE`, `ANSWER_RULE`. Then everything per task: the
   ork's name, its persona, its branch, the task, designs, overlaps, decisions, the steward's feedback, `PART_RULE`,
   the closing line, recent work. Same words as today; only the order changes. The warm path is unchanged.
2. **Fewer steward answers.** `MAX_STEWARD_ANSWERS` becomes 1. The steward's answer call (`use="answer"`) runs on the
   light tier (`light=True`) and its prompt holds only the card, the decisions so far and the question (no diff, no
   repository reading asked). If it cannot answer from those, it says ASK and the question goes to the person (🔥)
   as today.
3. **Tests are the review of code.** A new pool setting `review`: `tests` (default) or `steward`. With `tests`, a
   card whose tests ran and passed is accepted without a steward review call; a card with no tests, failing tests,
   or `review: steward` gets the steward review as today. Trivial cards keep skipping review. Every result still stops
   at the Review gate for the person (nothing is merged by the pool).
4. **Roles stay few and short.** A persona's prompt is capped at 600 chars when written and when loaded (cut at a
   sentence end). The planner proposes new personas only when the pool setting `new_roles` is true (default false);
   otherwise it assigns from the existing ones. Add `personas.remove(state_dir, name)`, and a Remove action for a
   persona in the pool's settings; an ork holding a removed persona goes back to none.
5. **A full context rolls over.** When an ork's last run reports more context tokens than 60 % of 🪵
   (`lumber_context_limit_tokens`), its next task starts a fresh session with the short `recent` handoff, as the
   5-task rollover does now.
6. **Show where tokens went.** The waybill at the Review gate (docs/design/cart-waybill.md) gets one line per card:
   tokens and cost of the ork's work, and of the steward split by use (answers, review, planning), from what is
   already counted (`out.steward_cost`, `steward_tokens`, the telemetry purpose tags). Plain words; no new screen.

## Not in this spec
No change to Mission 1 (its drill runs without a model). No new building, no daily batch (that is §39's own spec).
No change to the warm path, claims, worktrees or budgets.

## Tests
Add `tests/test_lean_pool.py`: the cold prompt's stable part is byte-identical for two different orks and tasks and
comes first; a second ork question in one run goes to the person, not to the steward; the answer call is light and
holds no diff; with `review: tests` and green tests no steward review call is made, with failing tests one is; a
persona over 600 chars is cut; `new_roles` false keeps the planner from writing personas; `personas.remove` works and
frees its ork; a run over 60 % of 🪵 makes the next task cold; the waybill shows the split. Run the critical tests
(CLAUDE.md) and `tests/test_steward*.py tests/test_pool_*.py tests/test_typed_pool.py tests/test_gui_pool_clan.py`,
plus the test files of every module touched.
