# Design — Homebrew bottles: `brew install` downloads, nothing builds

`brew install orkcraft/orkcraft/orkcraft` installs from the formula in this repository (docs/updates.md,
"The Homebrew formula"). Since 0.2.2 the formula takes every Python package as a wheel from PyPI, so
an install takes seconds of pip on top of the downloads. It still builds two things on the person's
machine: Orkcraft itself from the GitHub archive (setuptools, quick), and, on an Intel Mac,
cryptography from its sdist, which has brew install Rust first (minutes). A **bottle** is the
installed keg packed by brew: `brew install` pours it and builds nothing, on any platform it was
made for.

| stage | what | state |
|---|---|---|
| 1 | wheels instead of sdists in the formula (`tools/brew_formula.py`) | done |
| 2 | the `brew` workflow builds bottles for each platform and uploads them to a GitHub Release (§2) | |
| 3 | the formula gets its `bottle do` block in the same workflow, after the bottles are up (§3) | |
| 4 | `brew test` and `brew audit --strict` on every bottle build; the install time in the release notes (§4) | |

## 1. What is built where

| platform | runner | bottle tag (example) |
|---|---|---|
| macOS, Apple silicon | `macos-15` (arm64) | `arm64_sequoia` |
| macOS, Intel | the newest Intel runner GitHub still offers | `sequoia` |
| Linux, x86_64 | `ubuntu-latest` | `x86_64_linux` |
| Linux, arm64 | `ubuntu-24.04-arm` | `arm64_linux` |

A bottle for one macOS version is poured on that version and newer ones, so one per architecture is
enough. A platform with no bottle (an older macOS, a missing runner) still installs from the
formula as today: nothing is lost if a build fails.

## 2. The workflow

`.github/workflows/brew.yml` already runs when `__version__` changes on `main` and commits
`Formula: orkcraft <version>`. Two jobs follow it:

1. **bottle** (a matrix over §1): check out the formula commit, `brew tap orkcraft/orkcraft <the
   checkout>`, `brew install --build-bottle orkcraft/orkcraft/orkcraft`, `brew test`, then
   `brew bottle --json --root-url https://github.com/Orkcraft/orkcraft/releases/download/v<version>
   orkcraft/orkcraft/orkcraft`. Upload the `.tar.gz` to the release `v<version>` (created by the
   first job that gets there, with `notes` from `updates.json`) and keep the `.json` as an artifact.
2. **merge**: download every `.json`, `brew bottle --merge --write --no-commit *.json`, which writes
   the `bottle do` block (`root_url` and one `sha256` per tag) into `Formula/orkcraft.rb`, and commit
   `Formula: orkcraft <version> bottles` to `main`.

The workflow needs `contents: write` for the release and the commit (it has it already).

## 3. The formula and its generator

`tools/brew_formula.py` writes the formula from scratch, so on a release it drops the old version's
`bottle do` block. That is right (the old bottles are for the old version), and the merge job adds the
new one. When the generator runs by hand on the same version, it keeps a `bottle do` block it finds,
so a fix to the formula does not throw away bottles that still fit. `tests/test_brew_formula.py`
checks that a `bottle do` block's `root_url` names the formula's own version.

Between the formula commit and the bottle commit (the bottle builds take ~10 minutes) an install
builds from the formula as today: slower, still correct.

## 4. Checks

- Each bottle job runs `brew test` and `brew audit --strict --online orkcraft/orkcraft/orkcraft`; a
  failure leaves that platform without a bottle and the release goes on.
- A bottle has absolute paths in it (the venv's `bin/` scripts point at the Cellar); `brew bottle`
  replaces them with `@@HOMEBREW_CELLAR@@` and brew writes them back on pouring, so the bottle is
  made in the default prefix (`/opt/homebrew`, `/usr/local`, `/home/linuxbrew/.linuxbrew`), which
  GitHub's runners have.
- The updater needs no change: `brew upgrade orkcraft/orkcraft/orkcraft` pours a bottle when there
  is one.

## 5. Open questions

- Intel runners on GitHub are going away; when there is none, Intel Macs build from the formula
  (with cryptography from source) and the docs say so.
- Release assets are public and count against nothing for a public repository; a private fork would
  need a token for brew to download them (`HOMEBREW_GITHUB_API_TOKEN`).
