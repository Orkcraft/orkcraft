# Design — the Wiki: any folder, a folder picker, rules for AI tools

Status: agreed and built 2026-10-08. It grows the 🗑️ Scroll Dump (**Wiki**,
[wiki-librarian.md](wiki-librarian.md)) in three ways: any folder can be a source, whatever it holds;
a folder is connected with the system's own dialog, the recent folders or a drop; and once the
Review board has approved what the librarian wrote, every AI tool of the machine is told the wiki is
there, where it is and how to use it.

## 1. Any folder

Before: a source was a folder **inside the project** (`shelves.inside`) of Markdown (`docs`) or of
code (`code:src`), up to 500 files.

- **A new source, `dir:<folder>`**, reads everything it can in a folder, mixed: notes and text
  (`.md`, `.txt`, `.rst`…), code, `.docx` and `.pdf`. `docs` and `code:src` keep their meaning, so
  a town written before reads what it read. A folder connected from the window is a `dir:`.
- **Inside or outside the project.** A folder outside is read-only, always. The wiki itself stays
  in the project's `llm-wiki/<topic>/`; nothing is written into a folder that is not ours, unless the
  person allows it when connecting it (§3.4), and then only the rules' block.
- **What is read.** Text and code as they are. `.docx`: its text, taken out with the standard
  library (it is a zip of XML) into `raw/` (git-ignored), as a Confluence page is. `.pdf`: not
  converted — the AI tools read PDFs themselves; the librarian is told the file's path (in the
  project relative, outside absolute). Anything else (images, archives, binaries) is skipped.
- **What is skipped.** Hidden folders and `shelves.SKIP_DIRS`; what the folder's `.gitignore` ignores
  when it is in a git work tree (`git ls-files -co --exclude-standard`); secrets by their name
  (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `credentials*`, `secrets*`); a file over 10 MB.
- **Large folders.** `max_files` (default 2000) caps a source; the rest wait (the window says the
  source is cut). Taking in stays incremental, as today: the manifest's fingerprint of each file
  (outside the project its size and mtime, so a big folder is not read again on every look), and
  batches of `MAX_ITEMS` by module.

## 2. The folder picker

The GUI is the town in a pywebview window (or a browser with `--browser`) on 127.0.0.1. A browser's
`showDirectoryPicker` and a drop give a handle, not a path, so the picker is the server's.

- **Choose folder…** opens the system's dialog: pywebview's own `FOLDER_DIALOG` in the app's window;
  with `--browser`, `osascript` on macOS, `zenity` or `kdialog` on Linux, PowerShell on Windows. The
  dialog runs on a thread of its own (the socket never waits for it); the window asks for its answer.
- **Recent folders**: the last 8 connected on this machine (`MachineSettings.recent_folders`), one
  click each.
- **Browse**: a list of folders, from home, for a machine with no dialog (no toolkit, a remote
  desktop): open a folder, go up, pick it.
- **Drop a folder** on the dialog: the app's window gives its full path (pywebview's
  `pywebviewFullPath`); a browser gives one only from a file manager that sends a `file://` URL, else
  the dialog says to choose it instead.
- **A path by hand** stays, under *Type a path*.
- **Phones** get no picker: a folder belongs to the computer, and is connected there.

## 3. Rules for AI tools

### 3.1 What

`RULES.md` in the wiki's folder is the one source of truth; each AI tool gets a short block that
points to it:

| Tool | Where | How |
|---|---|---|
| Claude Code | `CLAUDE.md` of the project | a block that imports the file (`@llm-wiki/general/RULES.md`) |
| Codex, agy, Hermes, pi, Cursor | `AGENTS.md` of the project | a block that names the file and says to read it |
| Cursor | `.cursor/rules/orkcraft-wiki-<id>.mdc` | a file of ours, `alwaysApply: true` |

The tools are the ones on in Settings → AI tools (Claude Code alone when none is). agy's reading of
`AGENTS.md` is not verified yet: re-check it against agy before relying on it.

### 3.2 What RULES.md says

It is a layer about the wiki's **structure**, so an agent knows where to look and where a thing
belongs:

- where the wiki is, and that `index.md` is read first, then a section's `index.md`, then the page;
- its sections, each with what it holds (from `WIKI.md` and `pages/`); a wiki with no structure of
  its own gets the usual one of LLM wikis: **goals**, **context**, **people**, **events**,
  **decisions**, **glossary**, **how-to**;
- how to use it: search it before answering about the project, cite a page by its path, say "not in
  the wiki" rather than guess, follow the pages of **decisions** as the project's rules;
- how to add to it: never edit its pages directly; leave a note in the inbox (`notes/inbox`), and a
  page whose owner is human stays theirs.

### 3.3 When

The building's setting **Rules for AI tools** (`agent_rules`):

- **After review** (`review`): written each time the Review board approves an ingest's spot-check.
- **Ask me** (`ask`, the default): an approved review shows a strip *Rules for AI tools are ready*
  with **Write them**; nothing is written until then.
- **Off** (`off`).

**Write now** writes them at any time, and **Remove** takes every block out. A review sent back
(`rework`) never writes. What is written in the project is committed by the librarian: `RULES.md`
always, a `CLAUDE.md` or `AGENTS.md` only when it had nothing of a person's waiting to be committed
(else it is left for them to commit).

### 3.4 Not touching what people wrote

- A block sits between `<!-- orkcraft:wiki:<building id> -->` and `<!-- /orkcraft:wiki:<building id> -->`;
  only that block is written or removed, the rest of the file stays as it was. Each Wiki of the
  town has its own block.
- A file that was not there is made with the block alone; removing the block of such a file, empty
  then, deletes it.
- **A folder outside the project** gets the block only when the person said so when connecting it
  (*Also tell AI tools working in this folder about the wiki*, off by default; `rules_in`). The block
  there names `RULES.md` by its absolute path. Nothing there is committed.

## 4. Wording

New in `TERMS`: `agent_rules` → **Rules for AI tools**. Labels: *Choose folder…*, *Recent*,
*Browse*, *Type a path*, *Write them*, *Write now*, *Remove*.

## 5. Settings

| Key | Default | What |
|---|---|---|
| `sources` | — | grows `dir:<folder>`: any folder, in the project or outside |
| `max_files` | 2000 | the files a `dir:` source reads at most |
| `agent_rules` | `ask` | `review`, `ask` or `off` (§3.3) |
| `rules_in` | `[]` | folders outside the project that get the block too (§3.4) |

## 6. Where the code goes

- `realm/extract.py` (new, pure): what a file is to the wiki (text, code, docx, pdf, skipped),
  secrets by name, `.docx` → text.
- `sources/lore.py`: `DirSource`; `realm/wiki.py`: fingerprints of a file outside the project, the
  ingest prompt's PDFs.
- `realm/wikirules.py` (new, pure): `RULES.md`, the blocks, merging and removing them.
- `core/workers/scrolls.py`: `add_folder` for any folder, the rules after an approved review, write,
  remove; `core/workers/scrolls_rules.py` a part of it.
- `gui/folders.py` (new): the dialog, browsing, recent folders, drops; `gui/launch.py` hands it the
  window. `gui/views/scrolls.py` and `js/buildings/scrolls.js`: the dialog, the Rules block.
- Tests: `tests/test_wiki_folders.py`, `tests/test_wiki_rules.py`, `tests/test_gui_folders.py`.

## 7. As built

- *Rules for AI tools are ready* is a strip of the window's head under the ones that say what runs,
  failed or waits to be taken in; the **Rules for AI tools** block (opened while they are ready) has
  *Write now* whatever the strip shows.
- The folder dialog asks the server for the system's dialog and polls for its answer every 400 ms
  (`pick`, `picked`); a machine with none falls back to *Browse* by itself.
- Tests: `test_wiki_folders.py`, `test_wiki_rules.py`, `test_gui_folders.py`, and the dialog and the
  block in `test_gui_browser.py`.

## 8. Not now

- An MCP server for the wiki (search and read as tools, for every AI tool): the next step.
- OCR of scanned PDFs; `.pptx`, `.xlsx`.
- Google Drive as a source: a remote source like Confluence, with the Google account's design.
- The TUI (deprecated).
