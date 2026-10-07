# AI tools: one registry, a main tool

Orkcraft leads six AI tools: **Claude Code**, **Antigravity (agy)**, **Codex**, **Hermes Agent**,
**pi** and **Cursor** (`cursor-agent`). Nothing outside `orkcraft/realm/harnesses.py` names how one
is called: every ork, building and decision goes through that registry.

## 1. The registry

`harnesses.REGISTRY` holds one `Harness` per tool, in the order a main tool is picked when none is
chosen (claude, agy, codex, hermes, pi, cursor). Each says:

| what | used by |
|---|---|
| `ask(prompt, folder, model)`: a one-shot answer in an empty folder, no edits | decisions (`builders.ask`) |
| `read(prompt, workdir, model, web)`: an agent that only reads | road agents, the Council, Scrolls, the Mill (`roads.run_agent`) |
| `work(prompt, workdir, model, resume)`: an agent that edits its worktree | the Barracks (`jobs.run_work`) |
| `result(stdout)` → text, cost, tokens, session | every run |
| `env(mode, workdir)`: variables a run needs | Hermes' write root, its hooks headless |
| `interactive(prompt, resume)`: a War Tent session | `sources/sessions.py`, `core/sessions.py` |
| `models` (tier → model), `default_model`, `task_models` | `realm/tiers.py`, the Barracks |
| `in_repo`, `resumable`, `stdin_prompt`, `deploys`, `web`, `priced`, `fits` | the callers above |
| `mark`, `color` | `realm/looks.py`, design tokens `harness-<id>` |

Every list of tools (`settings.TOOLS`, `scroll.HARNESSES`, `limits.PROVIDERS`, `tools.TOOLS`, the
catalog's and masonry's enums, `tiers.MODELS`) is read from it. A new tool is one `register(…)`
plus its login (`tools.py`), its hooks (`hooks/`) and its quota (`quota/`), when it has them.

## 2. The main tool

`MachineSettings.main_tool` (Settings → AI tools → Main tool in the GUI) names the tool decisions
run on; empty means the first tool that is on. A chosen tool that is off gives way to the first one
on; with none on it is Claude Code, as before there was a choice (`builders.main_tool`).

- **Decisions** — the Warchief, the Town Builder, the Foreman and the Builder, the road planner, the
  Recruiter, the Council's fast path, stewards and keepers, retros, the Catapult's web planner, the
  Workshop — call `builders.main_runner` (or `main_runner_of(machine)` in a face).
- **Steps** name a tool or `main`. `main` is resolved when the step runs (`roads.resolve`,
  `tiers.tool_of`), so a town follows the machine it opens on. New orks, Barracks providers, Council
  members and moderators, Scrolls librarians and the Mill's agent default to `main`; an older town
  keeps the tool its steps name.
- **Override**: a steward whose first step names a tool thinks with it (`steward.harness_for`); an
  ork's step keeps its own tool.
- **Models** move between tools by tier: `harnesses.model_on("codex", "haiku")` is Codex's laborer.
  A tool with no tier table (Hermes, pi, Cursor) runs its own default for a tier.

## 3. The new tools (checked against their sources, 2026-10)

### Hermes Agent (Nous Research, `hermes`)

- One-shot: `hermes chat --query-file - --oneshot --format stream-json --toolsets <set>`, the prompt
  on stdin. JSONL; the `result` line has `text`, `tokens.total`, `session_id`. No price there.
- `-z` is never used: it approves every command (`HERMES_YOLO_MODE=1`).
- Toolsets per mode: ask `todo`; read `file,search` (+`web`); work `file,terminal,search`. `file` can
  write, so a reading run gets `HERMES_WRITE_SAFE_ROOT=/dev/null/orkcraft` (no file can be made there)
  and a working run its worktree. Dangerous commands are refused in one-shot runs
  (`approvals.single_query_mode: deny`, its default).
- Resume: `--resume <id>`. Interactive: `hermes`, a first prompt `hermes chat -q <prompt>`.
- Hooks: only in `$HERMES_HOME/config.yaml` (no project file). Orkcraft adds a block between two
  marker comments after asking (`orkcraft hooks install --hermes-global`), never beside a `hooks:`
  key of the person's own. Headless runs get `HERMES_ACCEPT_HOOKS=1`.
- Spend: `estimated_cost_usd` per session in `$HERMES_HOME/state.db` (read-only). Limits:
  `hermes usage --json`.
- Login: `auth.json` (OAuth: a subscription) or a provider key in `.env` / the environment (API).

### pi (`@earendil-works/pi-coding-agent`, formerly `@mariozechner/…`)

- `pi --mode json -e <orkcraft.ts> --tools <list> [--no-session] -- <prompt>`. JSONL; the first line
  is the session header (its id); each assistant `message_end` carries the text and `usage.cost.total`
  in USD, summed.
- pi has **no approvals and no sandbox**: what it may do is the tools it is given — ask `--no-tools`,
  read `read,grep,find,ls`, work those plus `edit,write,bash`.
- Hooks: TypeScript extensions only. `hooks/pi_extension.py` writes one (this Python baked in) that
  every pi orkcraft starts loads with `-e`; `orkcraft hooks install` also copies it to
  `.pi/extensions/orkcraft.ts` for the person's own sessions (loaded once the folder is trusted). Its
  `tool_call` handler refuses a deny, asks on an ask (refuses with no UI), never throws.
- Resume: `--session <id>`. Spend: its session JSONL (the extension passes the file). No limits.
- Login: `~/.pi/agent/auth.json` (`type: oauth` a subscription, `api_key` an API key).

### Cursor (`cursor-agent`)

- `cursor-agent -p --output-format stream-json --trust …`, the prompt on stdin (`--resume` takes an
  optional value and would swallow a positional one). Read: `--mode ask`. Work:
  `--force --sandbox enabled`. The `result` line has the text, `session_id` and camelCase `usage`. No
  price: the plan pays (unpriced in 🪙, never $0).
- Hooks: `.cursor/hooks.json` (`preToolUse` with `Shell|Read|Write|Grep|Delete`, `sessionStart`,
  `beforeSubmitPrompt`). The CLI is reported to fire only some events: test before relying on it.
- Limits: the plan's month, from `DashboardService/GetCurrentPeriodUsage` on api2.cursor.sh with the
  stored login (Linux/Windows `auth.json`; macOS keeps it in the Keychain, not read). Undocumented: an
  answer it does not expect is a plain row.
- Login: `CURSOR_API_KEY`, or the stored `accessToken`.
- The Cursor editor is still asked about as an *other* tool in onboarding only when the CLI is not
  found.

Unverified (cursor.com was unreachable when this was written): `--mode ask`, the hook event list and
field names, the web toggle. Re-check against `cursor-agent --help` before relying on them.

## 4. The Warder and the session log

`hooks/warder.py` judges every tool with the same rules: each payload is mapped to the Claude Code
tool it is (`from_agy`, `from_named`: Hermes `terminal`/`write_file`/`patch`…, Cursor
`Shell`/`Read`/`Write`…, pi `bash`/`read`/`edit`…), and `answer` says the verdict the way each
reads it (Hermes hands an ask to its own approval gate; Codex and a headless pi refuse an ask).
`hooks/session.py` records Cursor's `workspace_roots`, Hermes' `extra.user_message` and pi's
transcript path.

## 5. Autonomy

`autonomy.guide` says per tool what a level changes: Hermes `approvals.mode` / `--yolo`, pi never
asks (the Warder is its only guard), Cursor's `.cursor/cli.json` permissions / `--force`.
