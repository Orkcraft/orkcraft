# Design — distribution through the marketplaces where the audience installs

Status: decided with the owner 2026-10-13: "we must spread through Claude Code's plugins, and preferably through
other marketplaces too, VS Code's as well; estimate how much of the product it changes". Answers
[open-questions.md](open-questions.md) Q22. Builds on [similar-products.md](similar-products.md) §2 (Pixel Agents:
126k marketplace installs against 9.7k stars), [launch-prep.md](launch-prep.md). Estimates are from reading the code,
not from building anything.

## 1. The rule

**A marketplace entry is a door, not a second face.** The GUI stays the one face (CLAUDE.md): a plugin or an
extension installs Orkline, connects its hooks, opens the town, and at most shows a count. Every building, card and
console stays in the GUI.

## 2. What the product already has (read 2026-10-13)

- **The GUI is a local server** (`gui/server.py`, websockets) drawn in a pywebview window or the browser
  (`gui/launch.py`), with a token (`GET /api/version` as the handshake). Anything that can show a web page can show
  the town.
- **The hooks exist for every AI tool** (`orkcraft hooks install`, `hooks/install.py`: Claude Code, Codex, agy,
  Cursor, pi, Hermes), and the session hook **already fails open** (`hooks/session.py`: errors swallowed, exit 0).
- **The installer** (`install.sh`) puts uv, a Python and Orkline in place on macOS and Linux; Windows through pipx.
  Orkline is installed from GitHub, **not from PyPI**.
- **Keeping the Mac awake** exists (`gui/awake.py`, `caffeinate -i -w`), which answers most of research R9.

## 3. The doors, with what each changes

| door | what it is | what changes in the product | effort | priority |
|---|---|---|---|---|
| **0. PyPI** | `orkcraft` published as a package; `uvx orkcraft gui` runs it with nothing installed by hand | a release workflow that publishes the wheel; the name checked free; `updates.json` and the installer read the version from the same place | **≈ 1 day** | **P0 before the launch**: every door below installs through it |
| **1. A Claude Code plugin**, in Orkline's own plugin marketplace (a repository with the marketplace file), then submitted to the public directories | **hooks** from the plugin (session log; the Warder opt-in), each a shim that exits 0 when Orkline is not there; **`/orkcraft`**: opens the town, or offers to install it (PyPI, uv) and says what it puts where | `orkcraft hooks install` sees the plugin's hooks and does not write them twice; the onboarding's hooks question ([open-questions.md](open-questions.md) Q16) is skipped when the plugin is in (installing it was the consent); the town shows sessions started outside it, with the plugin's hooks (Q21's first look comes almost free) | **≈ 2–4 days** | **P0 before the launch**: the audience's own tool, the smallest change |
| **2. A VS Code extension**, on the VS Code Marketplace **and Open VSX** (Cursor, Windsurf and VSCodium install from Open VSX) | a status bar item (🥩 2/8 · ❓ 1); "Open the town": the GUI in an editor panel or its own window; installs Orkline when missing, after asking | **a small read-only status call** for the counter (the server has the token and the routes); **the GUI at narrow widths** (a panel of 400–600 px: today panels have a 380 px minimum and the town assumes a window); finding the running town (its port and token in a file); **a TypeScript project to keep**, built and published by CI | **≈ 1–2 weeks** for a first version; upkeep after | **P1, after the testers**; sooner if the launch's channels show the editor is where people come from |
| **3. Other AI tools' marketplaces** (Codex, Cursor and the rest, where they have one) | the same door as 1, per tool | per tool, as its plugin format allows | unknown | **research R10**: which have a public marketplace, and what their format allows |
| **4. Homebrew core** | `brew install orkcraft` without the tap | the formula moved from `Formula/` to homebrew-core's rules (stars and age are asked for) | ≈ 1 day, when accepted | Later, when it qualifies |

**Built 2026-10-14** (doors 0 and 1, nothing published): `.github/workflows/pypi.yml` and `tools/pypi.py` (the
package `orkline` on PyPI, from a tag, by trusted publishing; from git it stays `orkcraft`), the plugin in
`plugins/claude-code/` with the repository's own `.claude-plugin/marketplace.json`, `hooks_install.plugin_in`. The
plugin brings the session log only; the Warder stays a per-project opt-in. The owner's steps:
[distribution-howto.md](../distribution-howto.md).

## 4. What stays the same

- The town, the buildings, the console, Camp and Office: nothing is drawn twice.
- Local-first and no API keys: every door runs the person's own Orkline and their own AI tools.
- The terms ([decisions-2026-10.md](decisions-2026-10.md) §5): a plugin runs the person's unmodified Claude Code;
  nothing touches its sign-in.

## 5. What it costs beyond the code

- **Upkeep:** each door follows its marketplace's format changes. Door 1 is a few files; door 2 is a second codebase
  and a release process. That is why door 2 waits.
- **The listing is a page to write:** a name, a line, screenshots, a GIF; the same materials as the README and the
  landing ([launch-prep.md](launch-prep.md) §2), in each marketplace's sizes.
- **Being accepted is not in our hands:** public directories review what they list. Orkline's own marketplace
  repository works the day it is made; the public listing is applied for beside it.

## 6. How it is measured

Installs from each door, and of those, **how many open the town and finish Mission 1** (the usage stats'
`install_*` events with the door as a property, [dogfood-logs.md](dogfood-logs.md)). A door that brings installs but no
Mission 1 is a poster, not a door.
