# Updates

Orkcraft looks for a newer version of itself and installs it. A **critical update** — a fix for
something that loses work or lets harm in — installs by itself the next time the town opens, before
anything else loads. Any other update is offered: the window asks once per version, and
`orkcraft update` installs it from the terminal.

## What installs by itself

One setting per machine (Settings → *Updates that install by themselves*, or `orkcraft update <policy>`):

| Policy | When the town opens | In the window |
|---|---|---|
| `critical` (default) | a critical update installs, then Orkcraft restarts on it | other updates are offered |
| `auto` | every update installs, then Orkcraft restarts on it | — |
| `ask` | nothing installs by itself | every update is offered, a critical one loudly |

An install that fails never stops the town from opening: Orkcraft says why in the terminal, opens on
the version it has, and tries again after a day (or now, with `orkcraft update`).

The window reads the list when it opens and every 6 hours. When it finds a newer version it asks
once; **Update and restart** installs it, and the window closes and opens again on the new code.
Restarting stops what runs, as closing the window does. *Later* hides an ordinary update until the
next version, and a critical one until the window opens again (where, under `critical`, it installs).

## From the terminal

```bash
orkcraft update            # install the latest version now
orkcraft update check      # only say what is out and what it changes
orkcraft update critical   # which updates install by themselves: auto | critical | ask
```

## How it installs

With the tool that installed this copy, so its records stay right:

| Installed with | Updates with |
|---|---|
| `brew install orkcraft/orkcraft/orkcraft` (the tap below) | `brew update && brew upgrade orkcraft/orkcraft/orkcraft` |
| `pipx install "orkcraft[gui] @ git+…"` | `pipx upgrade orkcraft` |
| `uv tool install …`, or the installer (`install.sh`, [install.md](install.md)) | `uv tool upgrade orkcraft` |
| `pip install "orkcraft @ git+…"` | `python -m pip install --upgrade "orkcraft @ git+…"` (the same URL) |
| a git checkout (`bin/orkcraft`, `pip install -e`) | `git pull --ff-only` (then `uv pip install -e .` when `uv` is there) |

A brew copy is told by its path: it runs from `<HOMEBREW_PREFIX>/Cellar/orkcraft/<version>/libexec`.
`brew update` comes first because `brew upgrade` alone reads the tap only once a day; after the
upgrade brew removes the old version, so Orkcraft restarts on `<HOMEBREW_PREFIX>/opt/orkcraft`, which
points at the new one.

A git checkout updates itself only on `main` and only with no changes of its own: a working copy
with edits or on another branch is yours, so Orkcraft says what is out and leaves it alone.

## When nothing is read

`ORKCRAFT_NO_UPDATE=1` turns updates off: the list is never read and nothing installs. Under CI
(`CI=true`) and in the demo (`orkcraft --demo`) nothing is read either. Reading the list sends
nothing about you: it is a plain download of a public file, with `orkcraft/<version>` as its user
agent. `ORKCRAFT_UPDATE_URL` reads it from elsewhere (a fork, a mirror, a `file://` path).

## Publishing a release

The list is [`updates.json`](../updates.json) at the root of the repository, read from `main` at
`https://raw.githubusercontent.com/Orkcraft/orkcraft/main/updates.json`. A release is one commit to
`main` that:

1. raises `__version__` in `orkcraft/__init__.py` (the package's only version: `pyproject.toml`
   reads it);
2. adds the release at the top of `updates.json`:

   ```json
   {"version": "0.2.1", "date": "2026-10-08", "critical": true,
    "notes": "The Warder let a shell command through when …"}
   ```

3. after it lands, the `brew` workflow ([`.github/workflows/brew.yml`](../.github/workflows/brew.yml))
   sees the new `__version__` and commits the Homebrew formula for it (below).

Mark a release `critical` only for a security fix or a bug that loses work: it installs on every
machine with the default policy, with no question asked. `notes` is what the person reads before
it installs: one plain sentence on what it fixes. An installed copy sees the release as soon as the
commit is on `main` (raw.githubusercontent.com caches for a few minutes). `tests/test_updates.py`
checks that the newest release in `updates.json` is `__version__`.

## The Homebrew formula

The repository is its own tap: [`Formula/orkcraft.rb`](../Formula/orkcraft.rb) at its root.

```bash
brew tap orkcraft/orkcraft https://github.com/Orkcraft/orkcraft
brew install orkcraft/orkcraft/orkcraft
```

The full name `orkcraft/orkcraft/orkcraft` matters: since Homebrew 6 a formula from a tap that is not
Homebrew's own loads only once it is trusted, and installing it by its full name trusts that one
formula (not the rest of the tap). By the short name brew stops with "refusing to load formula from
untrusted tap"; `brew trust --formula orkcraft/orkcraft/orkcraft` fixes a copy installed that way.

The formula installs `orkcraft[gui]` in a virtualenv on Homebrew's Python, from the GitHub archive of
one commit, with every Python package pinned with its sha256 as the wheel `uv.lock` has for each of
macOS and Linux on arm and on Intel (the pyobjc ones, for the window's WebKit, only on macOS). Wheels
install in seconds, where brew building every sdist took minutes; a package with no wheel for a
platform comes as its sdist and is built there (cryptography on an Intel Mac, with Rust). Next:
bottles, so nothing is built at all ([design/brew-bottles.md](design/brew-bottles.md)). It is
written, never edited, by
[`tools/brew_formula.py`](../tools/brew_formula.py): it reads `__version__` and `uv.lock` at that
commit and hashes the archive.

On a release the `brew` workflow runs it for the commit that raised `__version__` and pushes
`Formula: orkcraft <version>` to `main`; `brew upgrade` sees the release from then on (until
then the window may offer an update that brew does not have yet: the install says the version did
not change, and it is tried again a day later). To write it by hand, from a commit already on GitHub:

```bash
python tools/brew_formula.py --commit <sha>   # needs `packaging`; downloads the archive to hash it
```

A copy installed before 0.2.0 cannot update itself: install it once more by hand
(`pipx install --force "orkcraft[gui] @ git+https://github.com/Orkcraft/orkcraft"`).
