# The Catapult through MCP: a shot carried by a tool, then a path of its own

*Status: design, not built.* The 🎯 Catapult sends out over HTTP with a token, or fills a site's forms
in a browser. People already have **Slack, Jira, Confluence, email, Notion and Discord** connected in
their AI tools as MCP servers or claude.ai connectors. This design lets a Catapult send through them —
and, after a shot went out that way, lets its ork (the Loader) build a **deterministic path** so the
next shots need no model at all.

The rule: **a model call is the last resort, and a lesson.** A shot takes the most deterministic path
that exists; when only a model can carry it, the run is read back and turned into a path.

## 1. What is there today

- `realm/mcp.py` finds the MCP servers of every tool by name only (never commands, env or URLs) and
  merges them: `Server(id, title, tools, glyph)`, `tools` naming the AI tools that have it. The
  onboarding saves only the ids (`profile["mcp"]`): which tool has which server is lost. claude.ai's
  connectors are not in any file and are not found at all.
- The Catapult's ork thinks (scout, map, repair) on the main tool: `builders.main_runner` →
  `claude -p` in an empty folder, with no `--mcp-config` and no allow-list — the project's
  `.mcp.json` servers are not loaded there.
- The Barracks is the only egress through an agent's connections (`PUBLISH:` draft → your yes →
  `publish_prompt`), and it has no MCP allow-list (`gui-onboarding.md` keeps it as a to-do).
- `watchtower-quick-add.md` §7 fixed the boundary for the other direction, and it holds here too:
  **never borrow another app's logins** (stored OAuth tokens of Claude Code, agy, claude.ai);
  hosted MCP servers admit only their own clients; asking the agent that is an approved client is
  allowed.

## 2. Three tracks, most deterministic first

| track | what runs a shot | model | when it exists |
|---|---|---|---|
| **API** | the Catapult itself: a request built from a `route` (method, address, headers, body template), a token from the environment | none | the service has an API and you gave a token (env var) |
| **Local MCP** | the Catapult's own MCP client: `tools/call` of the learned tool with the learned arguments on a **local (stdio) server** you named | none | the server is local and you allowed the Catapult to start it |
| **Carrier** | the AI tool that has the server, headless, allowed **exactly one** MCP tool, given the arguments as JSON | one call, the light model | a hosted server or a claude.ai connector — nothing else reaches it |

A Catapult in `mode: mcp` names *what* it sends to; the track is chosen per shot: API if its route
is learned and its token is set, else Local MCP if allowed, else Carrier. The window says which, in
plain words: `Slack API · $SLACK_BOT_TOKEN`, `slack (local server)`, `slack via Codex — a model call
per shot`.

## 3. Carrier: when the MCP is on one tool and the ork on another

**Who carries is chosen by the server, not by the ork.** The Loader keeps thinking on its tool; a
shot is carried by a tool that has the server.

- `realm/mcp.py` keeps what it found as it is (server → tools) in the machine settings, not only the
  ids: `MachineSettings.mcp = {"slack": ["codex"], "atlassian": ["claude", "agy"]}`, refreshed when
  Settings → AI tools opens and when a Catapult in `mode: mcp` starts.
- `via` (optional) picks the carrier; else the first tool that has the server **and is on**, the
  cheaper by billing first (`ToolChoice.billing`). A server whose only tool is off: the card says so
  — `slack is connected in Codex — Codex is off` — and the shot waits like a login (🔥), it is not
  failed.
- The same name in two tools can be two accounts. The first shot through a carrier asks (§6) and
  says which tool carries it; a changed carrier asks again.
- claude.ai connectors are found by the carrier itself: a Claude Code run's `system:init` event lists
  its MCP servers (`watchtower-quick-add.md` §7.2). A server picked by name that no file lists is
  looked up that way once.

**The harness side** (`realm/harnesses.py`): a new `call(prompt, workdir, allow, model)` per tool —
an agent allowed exactly the MCP tools in `allow` and nothing else (no shell, no edits, no web).

- Claude Code: `claude -p … --allowedTools mcp__slack__post_message --output-format stream-json
  --verbose`, run in the project (so `.mcp.json` servers load), stdin from `/dev/null`, a timeout.
- The other tools carry only where their headless mode can be held to one tool *(check each: Codex
  `exec`, agy, Cursor, pi, Hermes)*; a tool that cannot is never a carrier — the card says why.

**The prompt is a call, not a task.** The tool name and the arguments go in as JSON, fenced; the
cart's text is data, never instructions. *Call `mcp__slack__post_message` once with exactly these
arguments; do nothing else.* After the run the Catapult reads the `tool_use` blocks of the stream:
**exactly one call, to that tool, with those arguments** — else the shot failed (`the carrier did
something else`), whatever the model said. The `tool_result` is the shot's answer.

## 4. Learning a path after a carried shot

After a carried shot went out (✓), the Loader turns it into a path; no model is needed for the
first two steps.

1. **The arguments template.** Each argument of the recorded `tool_use` is traced back to the cart:
   a value equal to a leaf of the body (`catapult_web.leaves`) becomes that path (`text ← notes`), the
   rest stays a constant (`channel = "C0123"`). The template is `route.json` beside the building's
   scripts (`.orkcraft/scripts/<id>/route.json`, in the camp's git like `fill.py`: every lesson is a
   commit you can revert). From now on a carried shot is fully decided: the carrier only executes
   it, and the check of §3 compares against the template.
2. **Local MCP.** If the server is local (stdio) and you allowed it, the template is all the Catapult
   needs: its own MCP client starts the server from your tool's config and calls the tool. It reads
   that one server's launch entry only when you allow it, keeps nothing of it, and never for a hosted
   server.
3. **API.** If the service has a recipe (§5), the Loader writes an API route from the template —
   the MCP tool's arguments mapped to the service's request — and asks for **one thing: the name of
   the env var** that holds a token of your own (`SLACK_BOT_TOKEN — not set`). The token is never
   written anywhere (as `token_env` today). The model is used here only when the recipe does not
   cover the tool (one call, like Map fields; its cost in the ledger).
4. **Proof before use.** A learned route is used only after a 🧪 dry run of it shows the same
   request the carried shot made (the window shows both side by side) **and** your yes on its first
   real shot. Until then the shot goes the old track.

The window offers it as a strip, never by itself: *Learned a direct path: Slack API with
$SLACK_BOT_TOKEN. Use it · Keep the carrier.*

**When a path breaks** (the API answers 401/403, 404 for the channel, 400 for an argument), it is
handled like a broken form: 401/403 → the hut burns (`token expired or lacks a scope`) and the
queue holds; anything else → one carried shot (if a carrier exists and `repair` is on, within the
budget), and the route is learned again from it. A failed relearn keeps the old route and sends
`catapult.failed`; a good one sends `catapult.repaired` with what changed.

## 5. The six services

| service | usual MCP (carrier) | API track: request · auth | local MCP |
|---|---|---|---|
| **Slack** | Slack's hosted server, claude.ai connector | `chat.postMessage` · Bearer bot token; or an incoming webhook (the address is the secret: `url_env`) | community servers |
| **Discord** | community servers | a channel webhook · the address is the secret (`url_env`), no token | community servers |
| **Jira** | Atlassian's hosted server (approved clients only) | REST v3 `issue` / `comment` · Basic `email:API token` | community servers |
| **Confluence** | Atlassian's hosted server | REST v2 `pages` · Basic `email:API token`; the body in storage format | community servers |
| **Notion** | Notion's hosted server, claude.ai connector | `pages` / `blocks` · Bearer integration token + `Notion-Version` header | official local server |
| **Email** | Gmail connector (claude.ai), others | **SMTP** · host, user, password from env (an app password); a provider API (Resend, SendGrid) as an HTTP route | community servers |

What the API track needs beyond today's `mode: api`:

- **auth kinds**: `bearer` (today), `basic` (two env vars), `header` (a named header from env),
  `url_env` (the whole address is the secret);
- **headers** a route sets (`Notion-Version`), never from the cart;
- **a body template** (paths and constants, the same as §4.1) instead of the whole cart;
- **SMTP** as a second transport beside HTTP — the only one that is not a request.

Every recipe is data (`realm/catapult_routes/<service>.json`: the MCP tool names it knows → the
request), so a seventh service is one file.

## 6. Safety and money

- `mode: mcp` starts with `confirm` on; the first shot of every new track or carrier asks even when
  you turned it off. The 🔍 Audit flags a Catapult in `mode: mcp` that carries with confirm off.
- A carrier is allowed one tool and gets no shell, no edits, no web; the run's stream is the proof
  (§3), not its words.
- Carried shots spend: the light model, one call, in the ledger and under the 🪙 budget; past the
  budget a carried shot waits, an API or local shot does not.
- The sandbox never sends: every track is a dry run there.
- Never: another app's OAuth tokens, a hosted server called by the Catapult itself, a token written
  to a file or a shot's history.

## 7. The building

- Config: `mode: mcp`, `to` (a server id), `tool` (optional: the Loader picks it from the server's
  tools and asks once), `via` (optional carrier), `args` (like `fields`: `channel = "C0123"`,
  `text = notes`), `route_token_env` / the auth of a learned route.
- Card: `slack · post_message`, under it the track (`via Codex — a model call per shot` in the wait
  tone until a path is learned, then `Slack API`), the last shot.
- Window, head: the track with what it costs (`a model call per shot` / `no model`); a strip when a
  path was learned (§4); the carrier's question when the carrier changed.
- New events: none — `catapult.sent` / `failed` / `repaired` say it, with the track in the title.

## 8. Phases

1. **Carrier**: server → tools kept, `harnesses.call` with an allow-list for Claude Code, the stream
   check, `mode: mcp` with `to` / `tool` / `args`, the card and the window. Slack and Jira first.
2. **Learning**: `route.json` from a carried shot, API recipes for the six services, auth kinds and
   headers, SMTP, the proof and the strip, repair by a carried shot.
3. **Local MCP**: the Catapult's own MCP client for stdio servers you allow.
4. Carriers beyond Claude Code, tool by tool, as each headless mode is checked.

## 9. Open questions

- Is a stdio server's `env` in your tool's config (a token you wrote there) yours to start the
  server with, or borrowing (§1)? This design says yours, only with a yes per server.
- Which carrier is cheaper is known for billing, not for the call itself: is billing enough to pick?
- Email: SMTP passwords are the weakest secret here — offer only provider APIs, or both?
