---
name: orkline
description: Open the Orkline town (the window where your coding agents work as orks), or offer to install Orkline when it is missing. Use when the person asks to open Orkline, the town, or Orkcraft.
argument-hint: "[install]"
---

# Open the Orkline town

1. Run `sh "${CLAUDE_PLUGIN_ROOT}/scripts/town.sh" status` from the project folder.

2. If it says `installed: …`, run `sh "${CLAUDE_PLUGIN_ROOT}/scripts/town.sh" open` from the project folder and
   tell the person, in one line, that the town is opening in its own window (or the browser) for this project.
   Nothing else: every building and card lives in the town, not here.

3. If it says `missing`, do **not** install anything yet. Tell the person plainly what installing would do,
   then ask, and wait for a clear yes:
   - **uv**, Astral's Python package manager, only if the status said `uv: missing`: downloaded from
     `https://astral.sh/uv/install.sh` and run; it puts `uv` in `~/.local/bin`.
   - **Orkline** from PyPI: `uv tool install "orkline[gui]"`, into its own environment under uv's tools folder,
     with the `orkline` and `orkcraft` commands in `~/.local/bin`.
   - Nothing else changes: no settings are written, no hooks are added (this plugin already brings them), and
     `uv tool uninstall orkline` takes it back.

4. Only after a yes, run `sh "${CLAUDE_PLUGIN_ROOT}/scripts/town.sh" install`, say what it printed, and if it
   installed, open the town as in step 2. If the person says no, stop and leave everything as it was.

If the argument is `install` and Orkline is already installed, say so and open the town instead.
