# Anonymous usage stats

Orkcraft can share which of its features are used, so we know what to make better. It is **off until
you say yes**: the window asks once (or the installer, whose answer the window keeps), and Settings or
`orkcraft usage on|off|status` change it at any time.

## What is sent

Each event below, with only the properties listed. Numbers go as buckets (`0`, `1`, `2-5`, `6-10`,
`11+`), never as exact counts.

| Event | When | Properties |
|---|---|---|
| `app_opened` | the window opens | `face` (gui), `tools` (claude · agy · codex: the ones you turned on), `buildings`, `roads` (buckets) |
| `app_closed` | the window closes | `minutes` it was open (`<5` · `5-30` · `30-120` · `120+`) |
| `building_built` | you raise a building | `type`: its catalog type (lake, forge, …, custom) |
| `building_demolished` | you demolish one | — |
| `road_laid` | you lay a road | — |
| `session_opened` | you open an ork's CLI session | `harness`: claude · agy · codex |
| `deed_earned` | you earn a deed | `deed`: its id (town, road, reference, …) |
| `stage_reached` | your mascot grows | `stage`: 1–4 |
| `autonomy_set` | you change the orks' autonomy | `level`: chains · clock · free |
| `halted` | you press 🛑 Halt All | — |
| `install_started` | the installer starts ([install.md](install.md)) | `method` (sh), `arch` (x86_64 · arm64 · other), `upgrade` (already installed) |
| `install_step` | each of its steps ends | `step` (uv · python · package · version · window · agents), `ok`, `seconds` (`<10` · `10-60` · `60-300` · `300+`); when it failed `error`, a kind: disk_full · permission · tls · network · python_download · resolve_failed · build_failed · git_missing · unknown; and per step `found` (uv was there), `source` (git · archive · local), `window` (native · browser), `tools` (claude · codex · agy found) |
| `install_finished` | the installer ends | `ok`, `seconds`, `failed_step` |

Every batch also carries a random install id (drawn when you say yes, forgotten when you say no), when
this window was opened, the Orkcraft version, the OS (darwin · linux · windows) and the Python version.

**Never sent:** your code, prompts, what the orks or you wrote, file names, paths, project or building
names, git data, your settings' text, your email, your IP address.

The same answer covers [crash reports](crash-reports.md): where in Orkcraft's code something broke,
never what was in it.

## Where it goes

To Orkcraft's own proxy, a Cloudflare Worker (its code: [tools/usage-worker/](../tools/usage-worker/)),
which drops anything not in the table above and your IP address, and passes the rest to
[Amplitude](https://amplitude.com/) in its US data centre.

## When nothing is collected

Whatever you answered, nothing is collected while `DO_NOT_TRACK=1` or `ORKCRAFT_NO_USAGE=1` is set,
under CI (`CI=true`), or in the demo (`orkcraft --demo`).

## See it for yourself

`ORKCRAFT_USAGE_DEBUG=1 orkcraft` prints every batch to the terminal instead of sending it.
