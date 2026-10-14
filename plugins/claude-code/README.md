# Orkline for Claude Code

The Claude Code plugin of [Orkline](https://github.com/Orkcraft/orkcraft): a door to the town, not a second face
([docs/design/distribution.md](../../docs/design/distribution.md)).

## Install

```text
/plugin marketplace add Orkcraft/orkcraft
/plugin install orkline@orkline
```

## What it brings

- **`/orkline`** (and `/orkline:orkcraft`, the old name): opens the town for the project you are in. When Orkline
  is not installed, it says what it would install (uv when missing, then `orkline` from PyPI with
  `uv tool install`) and installs only after you say yes.
- **The session log's hooks** (`SessionStart`, `UserPromptSubmit`): each session in a project Orkline keeps is
  written to that project's `.orkcraft/sessions.jsonl`, so the town shows sessions started outside it. They
  **fail open**: with Orkline missing or broken they exit 0 and say nothing. A project whose
  `.claude/settings.json` already has Orkline's session hook keeps it and the plugin stays quiet there, so a
  session is never logged twice; `orkline hooks install` writes only the Warder while the plugin is in.
- **Not the Warder** (the security hook before each tool): it stays an opt-in per project,
  `orkline hooks install` or the onboarding's question.

## Remove

`/plugin uninstall orkline@orkline`. Orkline itself, if the plugin installed it: `uv tool uninstall orkline`.

## Its version

`version` in `.claude-plugin/plugin.json` is the plugin's own, not Orkline's: installed plugins update only when it
is raised, so raise it in the commit that changes anything under `plugins/claude-code/`. Check with
`claude plugin validate . && claude plugin validate plugins/claude-code --strict`.
