# GitHub profile: what to paste

For the owner: the repository's settings that live on GitHub, not in the repository
([design/launch-prep.md](design/launch-prep.md) §2a). Paste them by hand. Repository → ⚙ next to **About** for the
first two; **Settings → General → Social preview** for the third.

## Description

> Build the factory that builds your side project: your coding agents as a town. Tasks go down roads, through a
> review gate, and the game is spending less per accepted result. Claude Code, Codex. Local-first.

(GitHub shows up to 350 characters; this is about 230.)

**Website:** `https://orkline.dev`, once it serves a page (below).

## Topics

```
claude-code  codex  coding-agents  ai-agents  multi-agent  agent-orchestration  developer-tools  local-first
pixel-art  gamification  side-project
```

`agent-orchestration` is the term people search for, so it stays spelt that way here. Everywhere else the product
says "orkestration" (CLAUDE.md, Wording).

## Social preview

1280×640 PNG, shown on every shared link. Not made yet: the Camp frame with one ❓ and a cart at the gate, the name
and the line. Until it exists, `docs/img/look-camp.png` cropped to 2:1 will do.

Text on it:

> **Orkline**
> Build the factory that builds your side project.

## When orkline.dev serves the same files: the URLs to switch

**Not switched yet**, on purpose: installed copies and the install line in people's notes must keep working.
Switch them only once `https://orkline.dev/install.sh` and `https://orkline.dev/install/<role>/<look>` return the
same files as on orkcraft.dev. Keep orkcraft.dev redirecting to orkline.dev for good after that.

| where | what | switch to |
|---|---|---|
| `README.md`, "Try it in a minute" | `curl -fsSL https://orkcraft.dev/install.sh \| sh` | `https://orkline.dev/install.sh` |
| `docs/install.md`, lines 6, 14 and 17 | the install line, the class and look picked "on orkcraft.dev", `…/install/engineer/camp` | `orkline.dev` |
| `install.sh`, its header comments (lines 4–5) and the comments at lines 30 and 263 | how it is fetched | `orkline.dev` (comments only: the script fetches nothing from the domain) |
| `orkcraft/cli.py`, the help of `--role` and `--look` | "as orkcraft.dev asked" | "as orkline.dev asked" (update `tests/test_cli.py`'s docstrings in the same commit) |
| `orkcraft/realm/intents.py`, comments at lines 743, 752 and 761 | "the classes of orkcraft.dev" | `orkline.dev` |
| `tools/usage-worker/worker.js` line 66 (comment) and `tools/usage-worker/wrangler.toml` line 9 (the commented-out route `usage.orkcraft.dev`) | the proxy's route | `usage.orkline.dev` when the proxy gets a domain |
| the landing page (not in this repository) | its own links and its `/install/<role>/<look>` redirects | `orkline.dev` |

**Never switched** (code keeps its names, CLAUDE.md): the schemas' `$id`s (`https://orkcraft.dev/schemas/…`, also
`SCHEMA_URL` in `orkcraft/scroll.py`). They name a format and are not fetched, and town files written before carry
them.

**Not on the domain, so separate:** `updates.json` is read from
`https://raw.githubusercontent.com/Orkcraft/orkcraft/main/updates.json` (`orkcraft/core/updates.py` `MANIFEST_URL`).
It moves with the GitHub repository, not with the domain. After a repository rename, GitHub redirects the old
address, so installed copies keep finding it. Still, switch `MANIFEST_URL`, `SOURCE`, `install.sh`'s `REPO`, the
Homebrew formula's URLs (`tools/brew_formula.py`, then regenerate `Formula/orkcraft.rb`), `pyproject.toml`'s
`[project.urls]` and the README's links to the new repository in one release.
