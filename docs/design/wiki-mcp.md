# Design — the Wiki as an MCP server

Status: built 2026-10-08, the step after [wiki-folders-rules.md](wiki-folders-rules.md) §3. The rules for
AI tools tell an agent where the wiki is; the MCP server gives it the wiki as tools, so it searches before
it answers instead of walking files.

## 1. The server

`python -m orkcraft.wiki_mcp --project <repo> --wiki <the wiki's folder>` (`orkcraft/wiki_mcp.py`): MCP over
stdio, standard library only, read-only, one wiki per server.

| Tool | What |
|---|---|
| `wiki_map` | the wiki's `index.md` and its `RULES.md`: read first |
| `wiki_search` | `query`, `limit`: the pages that match (titles, aliases, text; any script; no model), each with its path and the line that matched |
| `wiki_read` | `path`: one page (relative to the project as the rules cite it, or to the wiki) |

Nothing outside the wiki's folder is read, nor its `raw/` snapshots. An answer it has not says so:
*Nothing in the wiki matches … Say so rather than guess.*

## 2. Where each AI tool finds it

Written and removed together with the rules for AI tools (the same tools, the same folders, the same
*Write now* / *Remove*), as an entry of this Wiki's own, `orkcraft-wiki-<building id>`:

| Tool | File | |
|---|---|---|
| Claude Code | `.mcp.json` | `mcpServers` (Claude Code asks once before it uses a project's server) |
| Cursor | `.cursor/mcp.json` | `mcpServers` |
| Codex | `.codex/config.toml` | a `[mcp_servers.…]` table between two marker lines of ours |
| agy, Hermes | — | they read MCP servers only from their global settings: not written; the rules tell them where the wiki is |
| pi | — | no MCP; the rules |

- Only our entry is written or removed; a person's servers and settings stay. A file left with nothing
  else is deleted; a file that is not valid JSON is left alone.
- The entry names this machine's Python and paths, so it is **never committed** (the rules' blocks are).
- `wiki_mcp: false` in the building's settings keeps the rules and takes the server out.

## 3. Not now

- agy's and Hermes' global settings (they would need asking, as their hooks do).
- A note tool (`wiki_note`): an agent leaves a note in the inbox as the rules say.
- One server for every wiki of a town.
