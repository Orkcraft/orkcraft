# Design — External listeners through MCP: a look carried by a tool, then a path of its own

Status: written 2026-10-07. **Stages 1–3 (§9) set aside on 2026-10-08** — see §11. **§12 (2026-10-09): Claude's
connection is the first way, every 30–60 min, and every message is sorted.** Built instead:
the agent source in the quick-add's picker and the ids a look keeps for the next
(watchtower-quick-add.md §7.2, §7.3). It is the second half of
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

## 11. Set aside (2026-10-08)

Weighed against what the Watchtower already has, the three stages buy little now:

- **Direct is there already.** Jira (JQL), Confluence (CQL), Slack (`search.messages`,
  `conversations.history`) and Gmail (IMAP) are read by the tower itself with a token of the person's
  (quick-add §5): no model, every 2 min, 401/403 told as a login. A learned Direct path would be the
  same call, reached the long way round. The picker now offers the token first and Claude's connection
  second (quick-add §7.3), so a person who can make a token never needs a learned path.
- **Local fits almost no one.** The services heard through Claude are hosted servers or claude.ai
  connectors (quick-add §7.5); none was a local stdio server.
- **What is left is the Carrier held to one call** — still a model run each look, fewer turns.
  The cheap half of that is built: the ids a look looked up (a cloud id, a user id) go to the next
  look, which skips those turns (quick-add §7.2 *The same path every time*).
- The move of `catapult_mcp` to `mcp_paths` and `carry`'s read mode serve only stages 2–3; the agent
  source runs its own `claude -p` (`realm/feeds_agent.py`), checked by events as `carry` is.

Taken up again when carried looks prove costly in Spend (many sources, a short `every=`), starting with
the Carrier held to one learned call (§3, §4) and nothing of Direct or Local.

## 12. Taken up again (2026-10-09): Claude's connection first, every message sorted

Asked by the owner: the tower's agent sorts every message first — how important it is, and whether an agent can
answer it. With a model called on what comes in anyway, the owner chose to read through MCP first.

- **Through Claude (MCP) is the picker's first way** (`js/buildings/watchtower_add.js`): no token, Claude's
  connector, a look **every 30 to 60 minutes** (`feeds_agent.EVERY_MIN`, `EVERY_MAX`; a line written before with a
  shorter `every=` is read as 30). A token of your own stays the second way, and sources already set up keep working.
- **Every source is sorted by the Lookout** (`realm/lookout.py` `judge(..., triage=True)`): one call of the
  steward's model for up to 20 new messages, with the intent when one is asked (stages below). With no model (Fast Path
  off) or Spend at its limit, mail is never held back: it goes on unsorted; only an intent makes it wait, as before.
  `triage: false` on the tower turns the sort off.
- **The sort rides on the cart**: the text sent down a road ends with its line (`importance: high · answered by:
  you · asks: reply · answer today · risk if unanswered: high (client may leave) · tone: upset`),
  so the next building and its agent see it first; the tower's list shows *important* and *an agent can answer*,
  and a low one dimmed (`js/buildings/watchtower.js` `Sort`).
- **The sort is in three stages, code where it can** (`realm/mail_sort.py`, asked by the owner the same day):
  1. *Code:* a mailing or a machine's message — list headers (`List-Unsubscribe`, `List-Id`, `Precedence`,
     `Auto-Submitted`, read by IMAP; a service's labels such as Promotions, copied by the agent look), a robot
     sender (`noreply@`, `notifications@`, `newsletter@`…), an automatic reply — is sorted low with its reason and
     **never costs a model call** (unless an intent asks the model about it anyway).
  2. *The model,* one call for the batch, the steward's `judge` (thrift laborer, balance and quality **warrior**,
     never elder): what is asked (nothing, info, reply, action, decision), how fast (now, today, week, none), the
     risk if no one answers (and what), the tone, and whether an agent could answer it alone.
  3. *Code:* importance and who answers, by rules a person can read: high on a high risk, an answer due today or
     an angry or upset sender; low when it only informs at no risk; **a decision, a high risk or an angry sender
     always goes to the person**; nothing to answer when it asks nothing.
  The MCP look stays on the light model and only copies (the sender, the labels): it judges nothing.
- Not built: routing by the sort (a road for *an agent can answer* only). A road's rule can already read the line.
