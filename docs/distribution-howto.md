# The doors: what the owner does to open them

For the owner: the steps that happen outside the repository, on PyPI, GitHub and Claude's directory. Everything
inside it is built and tested already ([design/distribution.md](design/distribution.md) doors 0 and 1). Nothing
here has been published yet.

## 1. PyPI: `orkline`

**What is in place.** [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml) builds the wheel and the sdist
on every push and checks them (`twine check --strict`, then [`tools/pypi.py`](../tools/pypi.py) `check`: the name
`orkline`, the version, both commands `orkline` and `orkcraft`, and none of what is meant for readers: the design
system's previews and notes, the docs, the generated reference sheets). It installs the wheel and runs both
commands. **Only a tag `v<version>` publishes**, through PyPI's trusted publishing: no token is stored in the
repository or in GitHub's secrets.

From git the distribution keeps its name `orkcraft`: copies installed from GitHub upgrade by that name
(`orkcraft/core/updates.py`), and pip refuses a URL whose package is named otherwise. The workflow renames it to
`orkline` in its own checkout just before building (`tools/pypi.py rename`). The import package stays `orkcraft`.
A copy installed from PyPI upgrades with `uv tool upgrade orkline`, `pipx upgrade orkline` or
`pip install --upgrade orkline`, whichever installed it ([updates.md](updates.md)).

### Once: claim the name and trust the workflow

1. **Check the name is still free:** <https://pypi.org/project/orkline/> should say *Not Found* (it did on
   2026-10-14; so did `orkcraft`).
2. **A PyPI account** with two-factor authentication on: <https://pypi.org/account/register/>.
3. **Add a pending trusted publisher** (this creates the project on the first upload, so no token is ever made):
   pypi.org → *Your account* → **Publishing** → *Add a new pending publisher* → **GitHub**, and fill in exactly:

   | field | value |
   |---|---|
   | PyPI Project Name | `orkline` |
   | Owner | `Orkcraft` |
   | Repository name | `orkcraft` |
   | Workflow name | `pypi.yml` |
   | Environment name | `pypi` |

   A pending publisher **does not reserve the name**: until the first upload, anyone can still take it. Cut the
   first release soon after.
4. **The `pypi` environment on GitHub:** the repository → **Settings → Environments → New environment** → `pypi`.
   Recommended: *Required reviewers* = you (each publish waits for your click), and *Deployment branches and
   tags* → *Selected* → add the tag rule `v*`.
5. Optional, to rehearse: the same pending publisher on <https://test.pypi.org> and a throwaway tag on a fork. Not
   needed: every push already builds and checks what a tag would publish.

### Each release: cut the tag

1. The release commit lands on `main` as always ([updates.md](updates.md), *Publishing a release*):
   `__version__` raised in `orkcraft/__init__.py` and the release at the top of `updates.json`.
2. Check the `pypi` workflow is green on that commit (Actions → **pypi**).
3. Tag that commit with the same version and push the tag:

   ```bash
   git fetch origin main
   git tag v0.3.0 origin/main          # v + the new __version__, on the release commit
   git push origin v0.3.0
   ```

   The workflow refuses a tag that is not `v` + `__version__`. With a required reviewer, approve the run under
   Actions → **pypi** → *Review deployments*.
4. Check it: <https://pypi.org/project/orkline/> shows the version, and on any machine with uv:

   ```bash
   uvx orkline --version
   uvx orkline gui            # the town, in the browser; uvx "orkline[gui]" gui for its own window
   ```

Push the tag right after the release commit: copies installed from PyPI read `updates.json` from `main`, and until
PyPI has the version their update says *the install finished, and the version is still …* and tries again a day
later.

**A release that went wrong** cannot be re-uploaded under the same version: *yank* it on PyPI (project →
*Manage* → *Releases* → *Options* → *Yank*) and release the next version.

## 2. The Claude Code plugin

**What is in place.** The repository is its own plugin marketplace:
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) (marketplace `orkline`) lists one plugin,
[`plugins/claude-code/`](../plugins/claude-code/README.md) (plugin `orkline`). It brings `/orkline` (and
`/orkline:orkcraft`, the old name), which opens the town or, when Orkline is missing, says what it would install
(uv when missing, then `orkline` from PyPI) and installs only after a yes; and the session log's hooks, which exit
0 and say nothing when Orkline is not there. While it is enabled, `orkline hooks install` writes only the Warder
for Claude Code, and Mission 1's hooks question is skipped. Both files pass `claude plugin validate`
(`tests/test_doors.py` checks them against Claude Code's documented formats, and runs the validator when Claude
Code is installed).

**Publish PyPI first:** `/orkline` installs Orkline from PyPI, so until `orkline` is there the plugin works only
for people who already have Orkline.

### Anyone can install it the day it is on `main`

```text
/plugin marketplace add Orkcraft/orkcraft
/plugin install orkline@orkline
```

(or from a shell: `claude plugin marketplace add Orkcraft/orkcraft && claude plugin install orkline@orkline`).
Installed plugins update when `version` in `plugins/claude-code/.claude-plugin/plugin.json` is raised: raise it
in every commit that changes the plugin.

## 3. Listing the plugin in the public directories

Being accepted is not in our hands ([design/distribution.md](design/distribution.md) §5); our own marketplace
above works meanwhile.

1. **Validate strictly first:** `claude plugin validate . && claude plugin validate plugins/claude-code --strict`,
   and go through Claude's pre-submission checklist:
   <https://claude.com/docs/plugins/pre-submission-checklist>.
2. **Fill the listing fields** the directory reads from `plugin.json` (Claude Code ignores them when loading):
   `icon`, `documentationUrl` (the plugin's README on GitHub until orkline.dev serves a page), `supportUrl` (the
   Issues page), `privacyPolicyUrl` (a page saying the plugin sends nothing anywhere, and Orkline's usage stats are
   asked for and off unless allowed: [usage-stats.md](usage-stats.md)). Raise the plugin's `version` in the same
   commit.
3. **Submit to Claude's plugin directory** (<https://claude.ai/directory>) from the developer portal,
   <https://claude.ai/directory/manage>. It needs a paid claude.ai plan (on Team or Enterprise, an owner, or a member
   given the Directory permission). The walkthrough: <https://claude.com/docs/plugins/submit>. Point it at the
   repository `Orkcraft/orkcraft`, plugin `orkline`. The listing page reuses the README's and the landing's
   materials: the line, screenshots of both looks, the GIF ([design/launch-prep.md](design/launch-prep.md) §2).
4. **Anthropic's official marketplace** (`claude-plugins-official`) does not take directory submissions; it is
   curated through Anthropic's partner contacts. Not a step for now.
5. **Community lists:** no documented submission process was found for community marketplaces (checked
   2026-10-14). Where a community list takes pull requests, the entry is the line above and the two install
   commands.

When the repository or the domain moves ([github-profile.md](github-profile.md)), switch the URLs in
`marketplace.json`, `plugin.json` and the plugin's README in the same release, and raise the plugin's `version`.
GitHub redirects a renamed repository, so `/plugin marketplace add Orkcraft/orkcraft` keeps working meanwhile.
