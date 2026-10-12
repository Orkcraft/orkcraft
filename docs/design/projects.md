# Design — 📁 Projects: the folder an orkspace works in, and a way back in time

Status: design notes, written 2026-10-11; stages 0–5 are done. Builds on the orkspaces of the Town Scroll
(`scroll.py` `Orkspace`, `GitLink`), the orkspace worktrees (`realm/worktrees.py`), the camp's checkpoints
(`realm/checkpoint.py`) and the first commit the Agent pool makes (`realm/jobs.py` `ensure_repo`). Wording: ork,
orkestration (CLAUDE.md).

| stage | what | state |
|---|---|---|
| 0 | the word: **Project** for the folder, the Town Scroll becomes the **Town file** (§2) | done |
| 1 | projects in the Town Scroll, an orkspace picks one; git started with the person's yes (§3, §4) | done |
| 2 | **Copy to orkspace…** for a building (§5) | done |
| 3 | a map goes back as a whole: the orkspace's checkpoints (§6) | done |
| 4 | snapshots of a project's files before an ork works, and one **History** to go back (§7) | done |
| 5 | every worker that touches files works in its orkspace's project, not the town's root (§8) | done |

## 1. The problem

A town has one root today: the folder `orkcraft` opened in (`find_project_root`: up to `.orkcraft.json` or
`.git`), or `~/Orkcraft` outside any project. Every orkspace works in it. Two things are missing:

- **Several projects in one town.** A person with three repositories runs three towns. The War Map could be
  the switch between them.
- **A way back.** Orks change files. When a run goes wrong, the person wants the files as they were before it,
  and the map as it was before a change of the town. The camp's checkpoints give back one building; nothing
  gives back the files, and nothing gives back a whole map.

## 2. Decisions

1. **The word.** The folder an orkspace works in is a **Project** (`TERMS`: `_t("project", "Project",
   "Projects")`). The Town Scroll, called "Project file" until now, becomes the **Town file**
   (`_t("town_scroll", "Town file", "Town files", "Town Scroll", "Town Scrolls")`); the places that said
   "Project file" say "Town file" (docs/reference.md, script-first.md, phone-places.md, portrait.md).
   Code keeps its names: `town_scroll`, `.orkcraft.json`, `scroll.py`.
2. **N:1.** An orkspace points to a project; many orkspaces may point to the same one (Feat-OAuth,
   QA-Regression and Design-Review on one repository). The project is optional: an orkspace without one works
   in the town's root, as today.
3. **A building lives in one orkspace** (already so: `scroll_checks.py` refuses a building in two). A building
   wanted on another map is **copied** (§5): the copy is a building of its own, with its own history.
4. **Two histories, one view.** The project's files keep their history in the project's git, the map keeps
   its history in the camp's git (`.orkcraft/`). They are never one repository: going back in the code must not
   take a building away, and a change of the map must not land in the person's `git log`. The person sees both in
   one **History** (§7.3).

## 3. The model

```json
"projects": [
  {"id": "shop", "name": "Shop", "path": "~/code/shop", "git": {"managed": true}}
],
"orkspaces": [
  {"id": "feat_oauth", "project": "shop", "git": {"enabled": true, "mode": "worktree", "branch": "oauth"}},
  {"id": "qa", "project": "shop", "git": {"enabled": false, "mode": "root"}},
  {"id": "camp", "project": null}
]
```

- `projects[]` is the town's list: `id`, `name`, `path` (absolute, or `~/…`), `git.managed` (true when Orkcraft
  started its git, so it may say more, §4).
- `orkspace.project` is a project id or `null` (the town's root). `GitLink` stays as it is and now means a branch
  or a worktree **inside the orkspace's project** (`.orkcraft/worktrees/<orkspace>` of that project).
- One function answers "where does this orkspace work": `projects.root_of(scroll, orkspace_id, town_root)`,
  and `worktrees.cwd_for` builds on it.
- `load()` migrates: a scroll without `projects` gets `[]` and every orkspace `project: null`, so every town
  works as before. The schema gets the two fields (`schemas/town-scroll.v3.json`, minor version).
- **Where the Town file lives.** While a town has no project of its own, nothing moves: `.orkcraft.json` stays in
  the root. A town with projects keeps its file and its `.orkcraft/` in the town's root; the projects are
  only paths. A project folder gets no Orkcraft files of its own except what its worktrees and snapshots
  need (§7).

## 4. A new orkspace picks its project

The War Map's fog (war-map.md §2.4) takes a name and a biome; under them, one more row:

**Works in:** *same as the open orkspace* (default) · *the town's folder* · *a folder…* · *a new project*

- **A new project** creates `~/Orkcraft/projects/<name>/`, starts
  git there and makes a first commit (`jobs.ensure_repo`: a `.gitignore` that leaves out `.env`, keys,
  caches and `.orkcraft/`). No question: the folder is Orkcraft's own.
- **A folder…** that is already a git repository is taken as it is.
- **A folder…** without git asks once, in one plain line: *"This folder has no history. Start git here, so
  Orkcraft can take you back to any earlier state? Your files stay as they are."* **Start git** · **Not now**.
  "Not now" still links the project; §7 is off for it and the History says why.
- **Refused:** `/`, the home folder, a folder inside another repository (`git rev-parse --show-toplevel` is a
  parent), and a first commit over 200 MB (it names the largest folders, so the person can ignore them).

The War Map shows the project's name in the open land's line and in every land's tooltip. A land's menu has
**Project…**, and the Warchief's line `/project`: both open the Project dialog of that orkspace (where it works now,
**Choose a folder…**, a path pasted, the town's other projects, the town's folder).

### As built (stage 1)

- `realm/projects.py`: `root_of`, `add`, `link`, `refusal`, `new_folder`, `start_git`; `scroll.Project`,
  `TownScroll.projects`, `Orkspace.project` (the schema's `projects` and `project`, checked in `scroll_checks.py`).
- `gui/projects.py`: `project.link` (`{state: "ask_git"}` for a folder with no git until `git` is given),
  `project.use`, `project.pick` / `project.picked`; `orkspace.new` takes `project`: `""` · `town` · `new` · an id.
  `js/project.js` is the dialog, `js/warmap.js` the fog's **Works in** row.
- A project inside Orkcraft's own `~/Orkcraft` repository is put in that repository's local exclude
  (`.git/info/exclude`), so the town's git never takes it in.
- Changing an orkspace's project drops its worktree link: a worktree belongs to the repository it was made of.
- Already in their project: War Tent sessions (`worktrees.cwd_for`) and the Agent pool (`code_root`: its own folder,
  else its orkspace's project, else the town's).

## 5. Copy a building to another orkspace

A building's menu gets **Copy to orkspace…** (next to the move the map already has, `move_building`).

- The copy gets a new id (`<id>_2`, as `new_orkspace` makes ids), its spec, its orks with their instructions,
  its scripts and blueprints (the reviewed flag stays only while the file is the same), its settings.
- **Roads:** its incoming roads come along only when their source is on the target map too; the rest are listed
  in the toast ("2 roads stayed behind: from Mail, from Calendar"). Outgoing roads belong to the receivers and
  are not copied.
- **Not copied:** its history, its renown and level, its spend, its sessions, its carts and what it keeps in
  `.orkcraft/` (a board's cards, a Loot queue). A copy starts at level 1, as a new building does.
- It is one checkpoint: `create(<new id>): copied from <id> (<orkspace>)`.
- Pure part in `scroll_garrisons.py` (`copy_building`), the files in `core/buildings.py` (`copy_to`); the GUI
  (`building.copy`, `js/build.js` `CopyAsked`, the hut's menu) only asks where to and shows the toast.
- As built: an ork's own script (`.orkcraft/scripts/<id>-<ork>.py`) is copied under the copy's name with the same
  bytes, so its review stays true; a script it shares with others keeps its path. `.orkcraft/scripts/<id>/` and
  `.orkcraft/blueprints/<id>/` are copied whole, and the spec's mentions of them follow. A copy of a copy is
  numbered from the original (`pool_2` copied gives `pool_3`). Its chronicle starts with `building_copied`.

## 6. A map goes back as a whole

A checkpoint (`realm/checkpoint.py`) names its building in a trailer. It also names its orkspace:
`Orkcraft-Orkspace: <id>`. Then:

- `history(root, orkspace=…)` lists one map's changes.
- `revert_orkspace(root, orkspace_id, sha)` puts back the orkspace's entry in the scroll (its buildings,
  their order, its biome and git link) and every file of its buildings as they were at `sha`, then commits that
  (`revert(<orkspace>): back to <time>`). Buildings that did not exist then are demolished (kept in history, as
  any removal); buildings removed since come back. Other orkspaces are untouched; §2.3 makes that safe.
- A road from a building of another map into this one stays only if its source still exists.

### As built (stage 3)

- `realm/checkpoint.py`: the `Orkcraft-Orkspace` trailer (`Town.checkpoint` names the building's orkspace unless
  one is given), `history(root, orkspace=…)`, `orkspace_at`, `at_of`; the kind `orkspace` for the map's own
  changes: made, renamed, a biome, a project.
- `core/maps.py` `revert`: the map's buildings get back their spec, scripts, blueprints and scroll entry (orks,
  roads from buildings that still exist, settings, place); their level stays theirs. Raised since: demolished.
  Moved to another map since: left there and said so. The Town Hall stands as it is. Going back is a checkpoint
  too, so it is undone the same way.
- `gui/history.py` (`history.list`, `history.revert`) and `js/history.js`: a land's menu **History…** and
  `/history`. Each row is the map right after that change: **Back to this**, then **Go back**.

## 7. Snapshots of a project's files

### 7.1 When

Before an ork works in a project's root (not in a worktree: a worktree is already its own branch) the town takes a
snapshot: before a War Tent session starts, before an Agent pool ork works in the project itself (its worktrees
off). And after, so "what did this run change" is one diff. (Loot writes no project file on accept: committing is
the Forge's job, so it takes none.)

### 7.2 How, without touching the person's history

```
GIT_INDEX_FILE=<tmp> git add -A          # the working tree as it is, untracked files too, .gitignore kept
git write-tree                          → tree
git commit-tree <tree> -p HEAD -m "…"   → sha
git update-ref refs/orkcraft/snapshots/<orkspace>/<utc time> <sha>
```

The person's branch, index, stash and `git log` stay as they were; the snapshots are not branches, so `git branch`,
pushes and clones never carry them (only `git log --all` would show them). A snapshot that equals the last one is not taken. Snapshots older than
30 days, beyond the last 200 of an orkspace, are dropped (`update-ref -d`, git's own gc cleans the objects).

**Going back** takes a snapshot first (so going back can be undone), then
`git checkout <sha> -- .` and removes the files the snapshot did not have and git does not ignore. It refuses
while an ork of that project runs. Pure module: `realm/snapshots.py`; the service that calls it publishes
`project.snapshot` / `project.restored` on the bus.

### 7.3 One History

A window of the Town Hall (and `/history`): one timeline per orkspace, newest first, made of both:

```
 14:32  ork Grom finished "Login form"        files: 6 changed     [Back to before] [Diff]
 14:05  Mail building: instructions changed   map                  [Back to before]
 13:50  ork Grom started "Login form"         files: snapshot
```

A map row knows the project's snapshot of its moment (the newest one not after it), so **Back to this** on it
offers: *the map* · *the files* · *both*; a files row offers *Files back*. The words say plainly what happens and what is
kept ("Your current files are saved first; you can come back to them").

### As built (stage 4)

- `realm/snapshots.py`: `take`, `listed`, `restore`, `changed`, `prune`. A snapshot's time is its ref's name, and a
  checkpoint's its `Orkcraft-At` trailer, both to the microsecond (git keeps seconds), so a change and the snapshot
  taken just before it sort right even within one second.
- `.orkcraft/` is never in a snapshot and never touched by going back, whatever the project's `.gitignore` says:
  when the project is the town's own folder, the camp's git and the worktrees live there.
- `core/timeline.py`: where and when (`folder_for`, `take`, `later`); War Tent sessions (`core/sessions.py`: before
  on open, after on exit, off the window's thread) and the Agent pool (`_work`, worktrees off). `bus.SNAPSHOT`.
- `gui/history.py`: `history.list` gives `{rows, files}`; `history.revert` takes `what`: `map` · `files` · `both`.
  The files go back only while no ork is at work (no agent running, no session open in that folder).
- `js/history.js`: rows tagged *map* and *files*; a files row says how many files changed (their names on hover).

## 8. Stage 5: workers in their project

The town's root stays the home of the Town file, `.orkcraft/` (checkpoints, spend, telemetry) and the quota.
What touches project files moves to `projects.root_of` one worker at a time, each with its tests: War Tent
sessions and the Agent pool did in stage 1; then the Forge, the codebase wiki,
Loot's file carts, and the Warder hook (`orkcraft hooks install` per project: `.claude/settings.json` lives in
each project). `repo_root` stays the town's root everywhere else; there is no rename across the code.

A worker asks `Worker.project_root` (its building's orkspace's project, else the town's root); `repo_root` and
`state_dir` stay the town's.

- **5.1 the Forge** — done: its branches, diffs, PR comments, tests and merges are the project's; its window says
  *in <project>* after the base.
- **5.2 the codebase wiki** — done: a Scroll Dump whose topic is `codebase` keeps its wiki and reads its sources in
  the project (`ScrollsWorker.work_root`); its wiki MCP server is the project's. A team, design or general wiki
  stays the town's. A codebase wiki made before the orkspace had a project stays where it was; the next ingest
  starts one in the project.
- **5.3 Loot** — done: the changed files it reviews (accept, reject, restore), the worktrees and branches of its
  carts and their previews are the project's; the vault, drafts and 👍 / 👎 stay in the town. A War Tent session in a
  project's worktree names that worktree relative to the project, so Loot finds it there.
- **5.4 the Security reviewer (Warder)** — done: when the town is guarded (its `.claude/settings.json` carries our
  hooks), a project it links or makes is guarded too (a new project's hooks are in its first commit); the Project
  dialog says *the Security reviewer guards it*, or offers **Guard it with the Security reviewer**.
  `orkcraft hooks install` / `uninstall` in the town also guard / unguard each of its projects.

## 9. What stays as it is

- A town without projects works exactly as today, and its Town file loads unchanged.
- Orkcraft never commits to the person's branches for a snapshot, never rewrites their history, never pushes.
- `core/`, `realm/`, `design/` stay faceless (`tests/test_architecture.py`).

## 10. Tests

- `tests/test_scroll.py`: migration (no `projects` → `[]`, `project: null`), an unknown project id is an error,
  a project shared by two orkspaces is fine.
- `tests/test_projects.py`: `root_of`, the refusals of §4, `ensure_repo` on a new folder.
- `tests/test_checkpoint*.py`: the orkspace trailer, `revert_orkspace` leaves other maps alone.
- `tests/test_snapshots.py`: a snapshot does not move `HEAD`, the index or the branch; untracked files are in it;
  going back restores, removes added files, keeps ignored ones and `.orkcraft/`, and can be undone; a session in
  the project is snapshotted before and after; one History lists both and takes the files back.
- `tests/test_maps.py`: the orkspace trailer, a map goes back and other maps stay, a building moved away stays.
- `tests/test_copy_building.py`, `tests/test_projects.py`, and the War Map, copy and History in `tests/test_gui_browser.py`.
- `copy_building`: new id, roads from the target map kept, the rest listed, no history copied.
