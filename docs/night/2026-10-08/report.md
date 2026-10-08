# Night 2026-10-08 — report

(The final session F writes the morning summary at the top.)

## Sessions

### A1 — tech-debt audit (architect)
- Done: queue `tech-debt.md` (T01–T13, ordered); `test_mine` flake fixed at its cause — the Mine marked a research done before writing its report (a31c15f); dead code removed (`google.drive_folder_name`, `quickadd.origin_repo`, `wikimcp.SERVES`); new architecture test: a module that starts agents registers them in `halt` (1f5f164).
- Checked, not debt: every agent run goes through `realm/halt.py`; the HUD agent count does not double-count; the "unused" views/workers are loaded by name. T01 (rename `modes.py`), T05, T12 dropped with reasons.
- Left for A2/A3, best first: T08 (old spellings in GUI templates, S), T11 (find what reaches the network during tests), T02 (functions only tests call), T06 (split `steward.py` 979 lines), T04 stage 1, T13, T07. T09 (removing the TUI, 20k lines) is a plan for later, not for tonight.
- Full suite without the browser tests on 217948a: green, 1864 passed in 13 min; all of the 40 slowest tests are TUI tests (T10b).
- Question for the morning: may we remove the TUI after the GUI gap list (T09 step 1) is closed, and keep `orkcraft tui` as a deprecation note for one release?

### P1 — triage of unbuilt design docs (PM)
- Done: queue `design-docs.md` — every `docs/design/*.md` checked against the code (file:line in each item): 13 build items (B01–B14, best value first), 13 *not now* with reasons (live services, the phone app, generated audio/art, owner's calls), the fully built docs listed. Built myself: **B01** landscape stage 1 — the `landscape` flag on the 7 types, the Build list shows buildings first and the land as its own group, the term (b41a52c); **B02** a road rule's own model tier, picked in its Edit dialog (3a32d26). Status lines fixed: landscape.md, yards.md (merged with #131), steward-at-work.md, steward-listens.md.
- Left for P2–P4, in order: B05 (Lookout names the kind, S), B03+B04 (spend *by purpose*, the ledger simplify needs before any cut, M+S), B07/B08 (landscape stages 2–3), B09 (watchers without a model), B10 (Mine: the mind is the model that answered), B11–B14.
- May be broken: nothing known; the critical tests, the touched modules' tests and the browser tests of the Build list and road rules are green.
- Questions for the morning: (1) the Fast Path — today the GUI says *Review board's Fast Path* / *Review board rejected it* because `Council` → *Review board* in the lexicon, but simplify.md §3 calls it *Build check*: which word? (B06). (2) simplify §5 renames the type id `council` → `review` and its modules, against CLAUDE.md's "code keeps its names" — drop §5's code half? (N10). (3) simplify stage 2: should the steward (not the Elders) answer an agent's permission questions at night? (N07). (4) OpenAI prices for Codex are still empty: they must be read first-hand (N12).

