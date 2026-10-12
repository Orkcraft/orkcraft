# The installer

For macOS and Linux, one line puts everything in place:

```bash
curl -fsSL https://orkcraft.dev/install.sh | sh
```

[`install.sh`](../install.sh) at the root of the repository is the whole installer: read it before you
run it. It needs only `sh` and `curl`. In a terminal it opens with the Warchief, drawn from his sprite in 12×5 cells
(`tools/install_banner.py`; his words beside him only when the terminal is 48 columns or wider; not
with `NO_COLOR` or outside a terminal).

At the end it opens the town. orkcraft.dev hands it the class and look picked there, in the address:

```bash
curl -fsSL https://orkcraft.dev/install/engineer/camp | sh
```

That address redirects to the usage proxy, which writes the two words into the script's `ROLE=""` and
`LOOK=""` lines (only words it knows the shape of; anything else leaves them empty). The same file is
also at `https://raw.githubusercontent.com/Orkcraft/orkcraft/main/install.sh`, with options instead:
`… | sh -s -- --role engineer --look camp`.

| Option | |
|---|---|
| `--role ROLE`, `--look camp\|office` | passed to `orkcraft` when the town opens (`orkcraft --help`) |
| `--no-open` | install only; with no terminal (a script, CI) it never opens |
| `--report`, `--no-report` | the question below, answered beforehand |

On Linux without GTK or Qt for Python the town opens in the browser.

## What it does

| Step | What happens |
|---|---|
| `uv` | uses the [uv](https://docs.astral.sh/uv/) that is there and answers, or puts the pinned version in `~/.local/bin` |
| `python` | `uv python install 3.12`: a Python of its own, whatever the system has |
| `package` | `uv tool install "orkcraft[gui] @ git+https://github.com/Orkcraft/orkcraft"` (GitHub's archive of `main` when git does not work, e.g. a Mac without the developer tools) |
| `version` | `orkcraft --version` runs |
| `window` | whether the town gets a window of its own or opens in the browser |
| `agents` | which AI tools are on the PATH: `claude`, `codex`, `agy` |

Each step's command and everything it printed go to `~/.orkcraft/install.log`. When a step fails the
installer stops, says which step, and gives a link to open an issue: attach that file.

It updates like any uv tool: `orkcraft update`, or `uv tool upgrade orkcraft` ([updates.md](updates.md)).
Run it again to reinstall.

## The question it asks

In a terminal it asks once whether you send an anonymous report of how the install goes. The answer
is also the answer to [usage stats](usage-stats.md): the window does not ask again, and a yes keeps
the same random install id, so the install and the first days of use are one install. With no
terminal to ask in (a script, `curl | sh` without a tty) nothing is sent and the window asks later.

- `sh install.sh --report` or `ORKCRAFT_REPORT=1`: yes, without the question.
- `sh install.sh --no-report` or `ORKCRAFT_REPORT=0`: no.
- `DO_NOT_TRACK`, `ORKCRAFT_NO_USAGE` or `CI` set: nothing is sent, whatever was said.
- `ORKCRAFT_USAGE_DEBUG=1` prints each event instead of sending it.

## What is sent after a yes

One event at the start, one per step and one at the end (`install_started`, `install_step`,
`install_finished`, listed with their properties in [usage-stats.md](usage-stats.md)): the step,
ok or failed, how long it took as a bucket, and the kind of error as a word from a closed list. They
go to the same proxy as the usage stats (`tools/usage-worker/`), which keeps only those properties
and drops your IP address. **Never sent:** paths, user or project names, the error's own text, the
log.

## For the maintainers

- `ORKCRAFT_INSTALL_FROM=<folder>` installs that checkout instead of `main`; the `installer` job of
  `.github/workflows/tests.yml` runs it on Linux and macOS for every change.
- The steps and error kinds live three times: `install.sh`, `orkcraft/core/usage.py`
  (`INSTALL_STEPS`, `INSTALL_ERRORS`, `EVENTS`) and `tools/usage-worker/worker.js`;
  `tests/test_installer.py` checks they agree. Deploy the Worker before a release that sends a new one.
- The Worker also serves the script at `/install.sh` (from `main`, cached 5 minutes), so
  `curl -fsSL https://orkcraft-usage.<account>.workers.dev/install.sh | sh` works too, and
  Cloudflare's request counts for that path say how many fetched it.
