# AI tool glyphs

One glyph per AI tool the orks run on (`realm/harnesses.py` `REGISTRY`): they tell *which tool* a row is
about, beside its name. They follow the rules of the service glyphs
([../services/README.md](../services/README.md)): Simple Icons only (CC0-1.0, from the npm package, these
from simple-icons 16.34.0), a path only, under 2 KB, drawn as a mask in the town's gold, `aria-hidden` with
the name written next to it. One difference: no well. The row's checkbox beside it is one already, and two
in a row look odd. The file is named by the tool's id in orkcraft.

A tool without a glyph shows its harness `mark` (the one the terminal and the settings show) as a text
mark instead.

## The glyphs

| Tool | File | Note |
|---|---|---|
| Claude Code | `claude.svg` | Simple Icons `claudecode` |
| Cursor | `cursor.svg` | |
| pi | `pi.svg` | Simple Icons `pi` (source pi.dev) |
| Codex | — | OpenAI is not in Simple Icons: the mark `⌬` |
| Antigravity | — | not in Simple Icons (`googlegemini` is another product): the mark `✦` |
| Hermes Agent | — | Simple Icons `hermes` is the parcel service, not this: the mark `☤` |

## Adding one

1. `npm pack simple-icons`, copy `package/icons/<slug>.svg` here as `<tool id>.svg`; check the slug's
   `source` in `data/simple-icons.json` is the tool itself, not a namesake.
2. Check it as the service glyphs say (a path only, under 2 KB).
3. Add the id to `TOOL_GLYPHS` in `js/onboarding.js`, its `.gui-onb__svc--tool-<id>` line to
   `onboarding.css`, and its row here.
