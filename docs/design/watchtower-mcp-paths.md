# Design — External listeners through MCP: a look carried by a tool, then a path of its own

Status: written 2026-10-07; nothing built yet. It is the second half of
[watchtower-quick-add.md](watchtower-quick-add.md) §7 (*Through Claude or agy*: a look made by an agent
that has the person's MCP servers, not built yet either) and the reading twin of
[catapult-mcp.md](catapult-mcp.md) (a shot carried by a tool, then a learned path; built). §7 there stays
the rules of a carried look; this document adds what the Catapult has and the listener lacks: **learning a
path from the looks, so the next looks need no model.**

## 1. Why

A look through an agent (§7.2 there) costs a model run each time: 15–40 s and $0.01–0.08 on the light
model, measured (§7.5 there). A listener looks every 30 minutes by default: ≈ $2 a day per source, ≈ $4
every 15 minutes, and its turns count against a subscription's limits. A Catapult pays a model call per
shot; a listener pays one per look, all day, so a learned path saves far more here.

The looks also showed what a path fixes by itself: the ids the model composed drifted between looks
(the same 9 Confluence pages came back with two spellings of their time), the same ask took 3 turns one
run and 13 the next, and a refused query came back as "nothing new". A path the tower runs itself has
none of that: the call and the id are code.

## 2. Tracks, most deterministic first

The same three as the Catapult's (catapult-mcp.md §2), for reading:

| track | what makes a look | model | when it exists |
|---|---|---|---|
| **Direct** | the tower itself, with a token of your own: the service's API read through a recipe | none | a recipe knows the service and you named the env var (or logged in, quick-add §3) |
| **Local MCP** | the tower's own MCP client: `tools/call` of the learned read tool with the learned arguments on a **local (stdio) server** you allowed it to start | none | the server is local and you allowed it |
| **Carrier** | the AI tool that has the server, headless, allowed **only the learned read tool**, given its arguments as JSON | one call of the light model, short | a hosted server or a claude.ai connector |

Before a path is learned, a look is a carried look of quick-add §7.2: the agent may use the server's
read tools, answers by schema. After it, the track is chosen per look: Direct if its route is proven and
its token set, else Local if allowed, else the Carrier held to one call.

## 3. What a look teaches

A carried look's events (`--output-format stream-json`) show every `tool_use` and its `tool_result`.
After a look that succeeded with items, the Lookout (the tower's ork) reads them back:

1. **The call.** The read tool the run used to list what is new (`searchJiraIssuesUsingJql`,
   `slack_search`, `search_threads`) and its arguments. The arguments become a template
   (`catapult_mcp/templates.py`): constants (`cloudId`, a channel, the person's user id) stay constants;
   **the time of the last look** becomes a slot `{"$since": "<format>"}` — the format traced from the value
   the run put there (`updated >= "2026-10-07 10:12"` → the JQL's format) — and nothing else from the run
   becomes a slot. One call is learned, the listing one; a run that needed a second call per item
   (`getJiraIssue` for each) learns that as `each` with the item's key as its slot.
2. **The mapping.** How an item of the tool's result becomes a signal: which field is the service's
   `key`, its `version`, the title, the text, the url, the author, the time, and whether it is a
   mention — paths in the result (`issues[].key`, `issues[].fields.updated`, …). The run's own structured
   answer is the proof of the mapping: its `key` and `version` (copied verbatim, quick-add §7.2) are found
   in the result and their paths taken. A field the answer has and the result does not show (a summary
   the model wrote) is not learned; the signal's text is then the item's own text, cut.
3. **The id** is composed by code from `key` and `version`, as the tower does already: never the model's.

No model is needed for these steps. When the result is too big or nested to trace by rules, the Lookout
asks the light model once for the mapping (its cost in the ledger, like the Catapult's *Map fields*), and
the proof (§4) decides.

The template and the mapping live in `.orkcraft/watchtower/<id>/paths/<source>.json`, in the camp's git:
every lesson is a commit you can revert.

## 4. Proof before use

A learned path is used only after it gave **the same items** as the carried looks:

- The next **two** looks run both ways: the carried look as before (its items are what the listener sends)
  and the learned path beside it (its items are only compared). Same ids, same titles → proven.
- The window shows the comparison as a strip: *Learned a path for Jira: no model, every 2 min. Same 4
  items as Claude's last two looks. Use it · Keep Claude.* It is never switched on by itself the first time
  (the autonomy levels may later say otherwise).
- After it is on, the look's interval may drop to the direct interval (2 min) for Direct and Local; a
  Carrier held to one call keeps its interval (it still costs), shown with its smaller cost.

## 5. When a path breaks

- **Direct**: 401/403 → the source burns *token expired or lacks a scope*, as a logged-in source does;
  other errors → one carried look, and the path is learned again from it.
- **Local / Carrier**: the tool is gone or renamed, an argument refused, the mapping finds no `key` →
  one carried look, relearn. A relearn that gives a different call or mapping goes through the proof again.
- A look that returns zero items where the carried look found some is a break, not "nothing new"
  (quick-add §7.2's lesson): the path is set aside until relearned.

## 6. One kit, both directions

The Catapult's MCP code becomes shared, the Catapult writing through it and the listener reading:

- `realm/catapult_mcp/` → `realm/mcp_paths/` (`carrier.py`, `local.py`, `templates.py`, `routes.py`,
  `recipes/`), with `realm/catapult_mcp` kept as a thin import so nothing that imports it breaks.
- `carrier.carry` gains a read mode: allowed the server's read tools (quick-add §7.2's list), or exactly
  the learned one; the check by events stays (exactly the allowed calls, no write tool, a denial is news).
- Recipes gain a `read` part per service beside `write`: the API call that lists what is new and the
  mapping of its answer (Jira `search` with JQL, Slack `search.messages` / `conversations.history`,
  Gmail `users.threads.list`, Confluence CQL search). A service without a `read` part has no Direct track.
- `local.call` is used as it is.

## 7. Safety and money

- Read-only everywhere: a carried look is allowed only read tools; a learned path names one read tool;
  a Direct route is a GET (or the service's search POST) — a recipe's `read` part may not name a write.
- A signal's text is data in every track; in Direct and Local it never reaches a model at all.
- Never: another app's OAuth tokens, a hosted server called by the tower itself, a token written to a
  file or a look's history (catapult-mcp.md §6).
- Each carried look's cost shows on the source's line and in Spend; the line says what the path saves
  (*via Claude · ≈ $0.90 today* → *no model · every 2 min*).
- The sandbox never calls a carrier: its looks are recorded ones.

## 8. What the person sees

- A source's line names its track: `Jira · via Claude · every 30 min · ≈ $0.90 today` before, the strip of
  §4 when a path is learned, then `Jira · no model · every 2 min`.
- The source's detail shows the learned call and mapping (read-only), *Forget the path* (back to carried
  looks) and *Learn again*.

## 9. Stages

1. **Carried looks** (quick-add §7.2–7.4) on the shared kit: the move of `catapult_mcp` to `mcp_paths`,
   `carry` in read mode, the agent source in the quick-add's picker. (The night's Watchtower work may
   have started §7; build on what is merged.)
2. **Learning**: the call and the mapping from a carried look (§3), the double looks and the strip (§4),
   Local MCP for allowed stdio servers.
3. **Direct**: `read` parts of the recipes for Jira, Slack, Gmail, Confluence; the env var asked once;
   the break handling (§5).

## 10. Open questions

- After the proof, switch to the learned path by itself on 🕰 / ⛓️‍💥 autonomy, or always ask? This text
  asks the first time.
- A Slack search lags behind new messages *(check, quick-add §7.5)*: is `search.messages` the right
  listing call, or `conversations.history` per channel?
