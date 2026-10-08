# Design — guarding agy as Claude Code is guarded

Status: research note, written 2026-10-06, for the roadmap item *Research: guarding agy as Claude
Code is guarded*. §7 is built (`warder.py agy`, `hooks install`, the version gate) but stays
unclaimed in onboarding until the smoke test of §8 passes on a live agy. Since 2026-10-07 the
window's onboarding says so too (`hooks/install.py` `agy_warder_line`, shared with the terminal's).
The smoke test is still open. agy could not be installed here (its installer and docs at
antigravity.google are blocked by this machine's network), so nothing below was tried on a live agy.
Each claim is marked **[v]** verified, with its source, or **[u]** unverified.

Sources:

- **CL** — agy's changelog, `CHANGELOG.md` of https://github.com/google-antigravity/antigravity-cli
  (commit `274d81b`, 2026-10-05, newest release 1.2.17).
- **ENG** — the hook contract embedded as documentation in Google's shared agent engine
  (`google/antigravity/bin/localharness` in the `google-antigravity` 0.1.20 wheel,
  https://pypi.org/project/google-antigravity/). agy's README says the CLI and Antigravity 2.0 run
  on the same core engine. This is the engine's text, read from the binary, not agy's own docs.
- **#1053** — https://github.com/google-antigravity/antigravity-cli/issues/1053 (agy 1.2.7, open).
- **SDK** — https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/hooks/README.md

## 1. What orkcraft runs today

- Headless steps (`realm/roads.py` `_harness_cmd`, `realm/jobs.py` `work_cmd`):
  `agy --print <prompt> --model <m> --mode accept-edits --sandbox --add-dir <dir> --output-format json`,
  in an empty temp folder (roads) or a worktree (Barracks).
- War Tent sessions: plain `agy`, `agy --conversation <id>` (`sources/sessions.py`).
- `agy -p /usage --output-format json` for ⏳ Limits (`quota/agy_quota.py`).
- The session hook already speaks agy's hook format (`hooks/session.py agy`, `.agents/hooks.json`,
  `PreInvocation` / `Stop`, prints `{}`); `orkcraft hooks install` writes it since §8.
- No agy version is pinned. These flags need **1.1.12 or later**: `--mode` was ignored in `-p`
  runs before 1.1.12, `--output-format` arrived in 1.1.8, and `--sandbox` in print mode was fixed
  in 1.0.6 and 1.1.18 [v CL].

## 2. agy has a pre-tool hook that can veto a call

The premise of the roadmap item, "agy has no documented pre-tool hook", is out of date.

- `hooks.json` supports `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation` and `Stop`
  [v ENG]. The CLI has honoured pre-tool hook decisions since at least 1.0.16 ("empty decision
  strings returned by pre-tool hooks") [v CL]. Since 1.1.28 an approval prompt shows a `Reason:`
  line when "a hook flagging the action" asks for approval [v CL].
- Where agy looks: `<workspace>/.agents/hooks.json`, read once the folder is trusted (fixed in 1.1.1),
  and from every `.agents/` between the working directory and the project root (1.2.16). The global
  file is `~/.gemini/config/hooks.json` (since 1.0.8). Plugins can bring their own `hooks.json`
  [v CL]. `docs/reference.md` says "agy 1.1.x reads only `~/.gemini/config/hooks.json`", which
  contradicts the 1.1.1 entry [u, probably stale].
- File format [v ENG]: each top-level key names a hook, and the events sit under it. Tool events
  wrap their handlers in a `matcher` regex group (`"run_command"`, `"run_command|view_file"`, `"*"`).
  The command runs through `sh -c`, in the folder that holds `hooks.json`, with a timeout in seconds
  (30 by default).

  ```json
  {"orkcraft-warder": {"PreToolUse": [{"matcher": "run_command|write_to_file|…",
      "hooks": [{"type": "command", "command": "… -m orkcraft.hooks.warder agy", "timeout": 10}]}]}}
  ```

- Input on stdin, camelCase [v ENG]: `toolCall.name` (e.g. `run_command`), `toolCall.args`
  (`CommandLine` for a shell command), `stepIdx`, and on every event `conversationId`,
  `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`. There is **no `cwd`**:
  take `toolCall.args.Cwd` if it is present [u], else `workspacePaths[0]`.
- Output on stdout [v ENG]: `{"decision": "allow" | "deny" | "ask" | "force_ask", "reason": "…"}`,
  plus optional `permissionOverrides` and `overwrite` (rewrites the call's arguments).
- `deny` blocks the call, and so does `overwrite`. `allow` does **not** grant a permission
  (in headless runs at least) [v #1053]. The hook works as a restriction layer, which is all the
  Warder needs.
- In `-p` runs a tool that needs approval is soft-denied, and the run reports it under
  `denied_actions` in the JSON (1.1.3, 1.1.27) [v CL]. So an `ask` in a headless run turns into a
  deny, as it does for Codex today [u that hooks follow the same path, but likely].
- Tool names: the engine knows `run_command`, `write_to_file`, `replace_file_content`,
  `multi_replace_file_content`, `edit_file`, `view_file`, `read_url_content`, `search_web`,
  `list_dir`, `grep_search` [v ENG strings]. Which of them agy 1.2.x exposes, and the argument key
  for each file path (`TargetFile`, `AbsolutePath`, …), are [u].
- Exit codes: a third-party guide says a non-zero exit counts as a hook failure and a search
  summary says it counts as a deny [u, conflicting]. The Warder already exits 0 every time.
- The same gist claims the output is `{"allow_tool": …, "deny_reason": …}` and puts the global file
  under `~/.gemini/antigravity-cli/`. That contradicts ENG, #1053 and CL 1.0.8 [u, treat as wrong].
  The SDK has its own Python `PreToolCallDecideHook` with the same deny-wins design
  [v SDK], but that API is the SDK's, not the CLI's `hooks.json`.

## 3. What `--sandbox` and `--mode` confine (without a hook)

- `--mode` (`default` = request-review, `accept-edits`, `plan`) decides only whether **file edits**
  wait for review. `accept-edits` approves edits and new files inside the workspace [v CL 1.1.0].
- `--sandbox` turns on the **terminal sandbox**, which applies to `run_command` and not to file
  tools [v CL; ENG `RunCommandToolConfig.EnableTerminalSandbox`]. Inside it, `.git` is read-only
  (1.1.10), `.git` is on the "dangerous paths" list (1.0.9), network requests go through a proxy that
  records blocked ones (1.1.10), and the artifact and scratch folders are writable (1.2.10). The agent
  can ask to run a command outside the sandbox (`BypassSandbox`), which needs your approval [v CL, ENG].
  Whether the network is closed by default is [u]; a `sandboxAllowNetwork` setting exists [v ENG].
- Reads of the workspace are approved automatically under the default mode (1.1.20) [v CL]. Nothing
  stops agy reading a `.env` inside the workspace.

Against the Warder's list, without a hook:

| Warder denies | agy `--sandbox`, headless | agy interactive session |
|---|---|---|
| `rm -rf` of the repository / `.git` | `.git` is read-only; the working files can still be deleted [v] | as the user's approvals and allow rules decide |
| `curl … \| sh` | the network goes through the sandbox proxy; blocked by default [u] | as approved |
| `git push --force` | needs the network and a writable `.git`: most likely fails [u] | as approved |
| reading or staging secrets | **not stopped**: workspace reads are auto-approved | not stopped |

Wrappers are a weaker substitute. A restricted `PATH` or shell shims for `rm`, `git` and `curl` are
bypassed by absolute paths, `sh -c`, `python -c`, and by the file tools, which never run a shell.
The terminal stream orkcraft reads only shows commands after a menu appears, and an allow rule or
an auto-approved call shows none; headless runs have no stream at all. None of the three can veto a
call before it runs.

## 4. The permission menus on screen

- Prompt titles name the action: `Run this command?`, `Allow access to this URL?`,
  `Allow calling this tool?`. A `Reason:` line follows when the cause is not obvious (1.1.28) [v CL].
- Under a command confirmation the footer reads `↑/↓ Navigate · tab Amend · e edit command`
  [v screenshot `examples/statusline/images/statusline-tool.png` in the repository]. File writes
  in `default` mode open a diff review instead of a menu (1.1.0) [v CL].
- Approving offers always-allow rules ("Always Approve", subcommand-scoped suggestions), and since
  1.1.10 a pattern approved at a prompt is "recorded for the rest of the conversation" [v CL].
- The option labels and whether a digit picks an option are [u]: no screenshot or doc reachable
  from here shows them. `tui/roster.py` sends agy a bare digit, which assumes it does.

Fit with `realm/elders.py`: the title ends in `?`, so `detect_prompt` finds the question, and
`_YES` / `_NO` catch "Yes", "Allow", "Approve" and "Deny". `_WIDENS` catches "always" and
"for this session / project / …", but **not "for this conversation"**. If agy labels its
conversation-wide grant that way, the Elders could advise it as a one-time yes. Add `conversation`
to `_WIDENS` (a one-word change) before trusting the Elders' answers on agy.

## 5. Spend

- `--output-format json` and `stream-json` carry a usage object with token counts, including
  `cache_read_tokens` (1.1.8) [v CL]. No price field is documented for print mode [v CL, by absence].
  The status line's payload has had a `cost` field ("unrounded estimated cost of the current
  session") since 1.1.21 [v CL]. The engine holds per-model prices and `estimated_cost_usd`
  [v ENG strings]; whether print mode outputs it is [u].
- `harnesses.json_result` reads `total_cost_usd`, and its token reader uses Claude's key names, so agy runs
  come out unpriced and probably without tokens [u: the exact JSON keys of agy's result].
- A subscription (Google sign-in) is paid in quota, not dollars. Its windows are already read from
  `agy -p /usage`, so "unpriced" is the honest 🪙 answer there. Only a `GEMINI_API_KEY` run has a
  per-token price, and Google's Gemini price page (ai.google.dev) was unreachable from here, so no
  prices for the `gemini-3.x` models used in `realm/tiers.py` are verified.

## 6. What orkcraft can rely on

| Can rely on | Cannot rely on |
|---|---|
| a `PreToolUse` hook in `.agents/hooks.json` / `~/.gemini/config/hooks.json` whose `deny` blocks the call | `allow` from a hook (ignored, #1053) |
| `toolCall.name` + `toolCall.args.CommandLine` for shell commands | a `cwd` in the payload; argument keys of file tools until checked on a live agy |
| `--sandbox`: shell commands contained, `.git` read-only inside | `--sandbox` stopping secret reads or file-tool writes |
| `--mode` gating file edits | `--mode` gating shell or network |
| `denied_actions` and token counts in `-p` JSON | a dollar price in `-p` JSON |
| prompt titles ending in `?` | agy's option labels and digit keys |

## 7. Recommendation for the onboarding's Warder step

Guard agy with the same Warder through agy's own hook. Nothing new needs inventing:

1. `hooks/warder.py agy`: read `toolCall.name` / `toolCall.args`. Treat `run_command` as `Bash`
   (`CommandLine`), the file tools as Read / Write by their path argument, and take the folder from
   `Cwd` or `workspacePaths[0]`. Answer `{"decision": "deny" | "ask", "reason": "🛡️ Warder: …"}`,
   or `{}` when there is nothing to say. Never answer `allow`, and keep exiting 0.
2. `hooks/install.py`: when agy is on `PATH`, merge an `orkcraft` entry into the project's
   `.agents/hooks.json` (the Warder on `PreToolUse`, the session hook on `PreInvocation` / `Stop`).
   Headless road steps run in an empty temp folder outside the project, so their hooks have to live
   in `~/.gemini/config/hooks.json`. The step says so and asks before writing there. Add both files
   to the Warder's `SELF` list. Like Codex, agy runs workspace hooks only once the folder is trusted.
3. Require agy ≥ 1.1.12 (the flags above, and project hooks after trust) and check it in onboarding's
   tool step (`tools.py` already runs `--version`).
4. Before shipping, one smoke test on a live agy: `agy -p "run rm -rf .git" --output-format json`
   with the hook installed must show the deny in `denied_actions`. Read the file tools' argument
   keys from a hook that only logs its stdin.

Until step 4 passes, the Warder checkbox keeps its Claude / Codex wording. When agy is among the
chosen tools, the step adds this plain sentence:

> The 🛡 Warder does not guard agy yet: agy sessions run with only agy's own sandbox and permission
> prompts, so start agy with `--sandbox` and keep secrets out of the project folder.

Also, outside this item: add `conversation` to `elders._WIDENS`, and correct the hook lines in
`docs/reference.md` and `warder.py`'s docstring ("agy has no documented pre-tool hook").

## 8. Smoke test on a live agy

Built: `python -m orkcraft.hooks.warder agy`, the `orkcraft` entry `hooks install` merges into
`.agents/hooks.json` (and, after asking, into `~/.gemini/config/hooks.json`), and the 1.1.12 gate.
Rechecked before building, 2026-10-06: agy's changelog at `274d81b` (1.2.17) still says what §1–§2
quote. Issue #1053, the docs at antigravity.google and the engine wheel were not reachable from
the build machine either, so the payload and answer format still rest on ENG and #1053 as read
for this note. Onboarding keeps saying "does not guard agy yet" until someone runs these steps on a
machine with agy 1.1.12 or later and a Google sign-in or `GEMINI_API_KEY`:

1. `agy --version` says 1.1.12 or later.
2. In a scratch git repository: `orkcraft hooks install --agy-global`. `.agents/hooks.json` and
   `~/.gemini/config/hooks.json` each hold an `orkcraft` entry beside whatever was there; `agy -p /hooks`
   lists its `PreToolUse`, `PreInvocation` and `Stop` hooks (the last two list their handlers without
   a `matcher` group, as ENG describes for events that are not tool calls: if agy drops them, wrap
   them as `PreToolUse` is). Open `agy` there once and trust the folder; one prompt adds a line to
   `.orkcraft/sessions.jsonl`.
3. Payload: add a second entry that only logs, `{"probe": {"PreToolUse": [{"matcher": "*", "hooks":
   [{"type": "command", "command": "cat >> /tmp/agy-hook.jsonl; echo {}"}]}]}}`, then
   `agy -p "list the files here, then read README.md" --output-format json`. `/tmp/agy-hook.jsonl`
   shows `toolCall.name`, `toolCall.args` (the path keys of `view_file` / `list_dir`) and
   `workspacePaths`. If a file tool's path key has no "path", "file" or "dir" in it, add it to
   `warder._agy_paths`. Remove the probe.
4. Deny, headless: `agy -p "run: rm -rf .git" --mode accept-edits --sandbox --output-format json`.
   The JSON lists the call under `denied_actions`, `.git` is still there, and
   `.orkcraft/warder.jsonl` has a `deny` line with `"tool": "Bash"`.
5. Deny, a file tool: `echo X=1 > .env`, then `agy -p "show me what .env holds" --output-format json`.
   The read is denied and logged.
6. Ask, interactive: in `agy`, ask it to run `git reset --hard`. agy shows its `Run this command?`
   menu with a `Reason:` line naming the 🛡️ Warder; answering no leaves the work as it was.
7. Headless step outside the project: from an empty temp folder,
   `agy -p "run: git push --force" --output-format json`: denied by the global entry.
8. `orkcraft hooks uninstall`: both files keep every entry but `orkcraft`.

All eight pass → set `"agy_warder_checked": true` in the machine settings, `~/.config/orkcraft/settings.json` (the onboarding then says
the Warder guards agy and installs its hook while raising a town), note the agy version tested
here, and change the default once a second machine agrees.
