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


### D1 — GUI audit + quick fixes (designer)
- Done: queue `ui.md` (U01–U23) with screenshots in `ui/` — the demo sandbox at 1440×900 and 390×844, Camp and Office (light and dark), every building type's window, Settings, the portrait's menu, Answers. Fixed myself: the phone HUD ran off the right edge — it wraps now (U01); Office's phone rows were 240 px wide (U09); the phone's "Asks you 0" while the HUD said "Answers (3)" — the chip counts what Answers counts (U06); Answers cut each question at 40 characters with no "…" (U12); Camp's text actions were sentence case beside uppercase buttons (U13); a building's window showed another number than its card (34 vs 5) (U17); git's "fatal: not a git repository …" was the whole message on Branches & PRs, Review gate and File tree — now said plainly with what to do (`realm/gitinfo.py` `plain_error`, U18).
- Left for D2/D3, best first: U02 road labels drawn over card text (M), U24 a wake toast that says "it says ERROR" (S), U03 scroll cue for Settings and the War Map (S/M), U07 the Warchief's line squeezed by an open panel, U10/U11 an open card covering its neighbours and repeating its window's actions, U14, U16, U19–U23 (all S). Onboarding was not audited: another session works on it tonight.
- May be broken: nothing known; the critical tests, `test_gui.py` and `test_gui_browser.py` are green on these changes. CSS, `pocket.js` (the chip), `orders.js` (the list), `windows.js` (the number), `forge.js`, and `gitinfo.py` + the Review gate's and File tree's workers (the plain git error, with a test).
- Questions for the morning: (1) the HUD shows "Spend $— / $5.00" until an agent reports — keep the dash (it never claims a $0.00 not measured) or say "$0.00"? (U05) (2) one word for the questions: the HUD says *Answers*, the dialog *Awaiting an answer*, the phone *Asks you* — make all three *Answers*? (U15)

### A2 — tech debt from the queue (architect)
- Done: **T08** — the last 11 old spellings in GUI templates written in today's word (Lake → Inspector, keeper → steward, Halt All → Stop all); the page's runtime rewrite of every template (`todayStrings`) removed; `tests/test_gui_wording.py` reads all ~1.9k `html` templates and fails on an old spelling; CLAUDE.md → Wording updated (0b5daa7). **T02** — removed 7 functions only tests called (e7aa9db). **T11** — tests ran the machine's **real** `claude -p` and `gh` (Claude Code is installed in these containers): the Mine test's research went on the web. `tests/conftest.py` hides every agent CLI and `gh` from `$PATH`; a guard test checks it.
- Left: T06 (split `steward.py`), T04 stage 1, T13, T07; T10b now means fixing the load flakes, not adding xdist.
- May be broken: nothing known. Full suite `-n 8` on the T11 commit: 1925 passed, 1 load flake that passes alone (a different test each run, also before my change).
- Question for the morning: the night sessions' containers have a logged-in Claude Code — did earlier test runs (before T11) spend on your account? Worth a look at the usage page.

