# Night 2026-10-08 — report

(The final session F writes the morning summary at the top.)

## Sessions

### A1 — tech-debt audit (architect)
- Done: queue `tech-debt.md` (T01–T13, ordered); `test_mine` flake fixed at its cause — the Mine marked a research done before writing its report (a31c15f); dead code removed (`google.drive_folder_name`, `quickadd.origin_repo`, `wikimcp.SERVES`); new architecture test: a module that starts agents registers them in `halt` (1f5f164).
- Checked, not debt: every agent run goes through `realm/halt.py`; the HUD agent count does not double-count; the "unused" views/workers are loaded by name. T01 (rename `modes.py`), T05, T12 dropped with reasons.
- Left for A2/A3, best first: T08 (old spellings in GUI templates, S), T11 (find what reaches the network during tests), T02 (functions only tests call), T06 (split `steward.py` 979 lines), T04 stage 1, T13, T07. T09 (removing the TUI, 20k lines) is a plan for later, not for tonight.
- Question for the morning: may we remove the TUI after the GUI gap list (T09 step 1) is closed, and keep `orkcraft tui` as a deprecation note for one release?
