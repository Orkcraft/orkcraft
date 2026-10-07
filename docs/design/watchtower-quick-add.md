# Design — adding a source to the Watchtower in a minute

Status: a plan, written 2026-10-07; nothing of it is built. Items marked *(check)* have not been
verified against the live services yet. It is the near, hand-held half of
[watchtower-automation.md](watchtower-automation.md): that plan removes the person from the loop
(OAuth apps, a background service, tunnels, webhooks registered for them); this one makes the
loop short today, with no server of ours and no OAuth app anyone has to own.

## 1. The problem

Today a source is a line of YAML that names environment variables:

```yaml
host: gmail
user_env: GMAIL_USER
password_env: GMAIL_APP_PASSWORD
feeds:
  - "slack: token=SLACK_TOKEN channels=C0123,D0456"
```

To add Slack a person has to: create a Slack app by hand, find the right scopes, install it, copy
the token, export it in the shell, **restart orkcraft**, find the channel ids, write the line
(or ask the steward to). Nothing tells them it worked until two minutes later, or that it did not
until a `✗ ERR` appears. GitLab and Discord are not there at all.

The goal: **from "+ Add a source" to the first signal in about a minute**, for the six tools
people ask for: GitHub, GitLab, Gmail, Slack, Discord, Jira (with Confluence) and Figma.

## 2. Principles

1. **One paste at most.** Where a login is already on the machine (`gh`, `glab`), use it: zero
   pastes. Otherwise a deep link opens the exact page where the token is made, prefilled where
   the service allows it; the person pastes one thing back.
2. **Paste a link, not an id.** Every service has links to the thing to listen to: a repo, a
   channel, a Jira issue, a Figma file. A link tells the service, the site and the id at once.
3. **Pick from a list, with a default.** After the login, the tower asks the service what there
   is (repos, channels, projects, files) and preselects the likely one (this project's repo, the
   channels the person wrote in lately).
4. **Check before Add.** The last step is a real first look, live: *connected as @ann · 14 items
   seen · the next new one will be a signal*. A failure says which step to redo, in plain words.
5. **Tokens never pass through a model.** The form posts straight to the worker; the steward and
   the Warchief never see a token, and a token never lands in the town scroll or the project file.
6. **Poll first.** Every quick-added source polls (2 min). Push (webhooks, sockets) is an upgrade
   offered later on the source's line, never a step of adding it.

## 3. Logins: where the token goes

A new concept, **Logins** (one word for it in `realm/lexicon.py` `TERMS`): the tokens the
Watchtower uses, kept on this machine, outside the project.

- Stored in the OS keychain through `keyring` (an optional extra); without it in
  `~/.config/orkcraft/logins.json`, mode 0600. One entry per login: `slack-acme`, `jira-acme`,
  `gmail-ann@example.com`.
- A spec refers to a login as `keychain:<name>` wherever it names an environment variable today:
  `token=keychain:slack-acme`, `password_env: keychain:gmail-ann`. Environment names keep working
  (`token=SLACK_TOKEN`), so every spec written before still loads.
- No restart: the worker reads the login at each look.
- The Town Hall's Warder still flags a spec that holds a value instead of a name.
- The Settings window lists Logins (service, account, which buildings use it, last used, last
  error) with **Log in again** and **Remove**.

## 4. The flow

### 4.1 Entry points

- The Watchtower with no source (state C0): its card says **+ Add a source** instead of "Open it
  and say what to listen to"; a click opens the window at the picker.
- The open window: a **+** chip at the end of the source chips.
- **Sources & intent**: an **Add** button above the list; each source's line gets **Edit**,
  **Log in again** (when it fails) and **Remove**.
- The Town Hall's Build: a preset that ends in a Watchtower opens the picker right after it is
  built.

### 4.2 The picker

```
 Add a source                                         ✕
 ┌──────────────────────────────────────────────────┐
 │ Paste a link to what you want to hear…           │   ← detects the service and the target
 └──────────────────────────────────────────────────┘
  GitHub ✓ gh   GitLab   Gmail   Slack   Discord
  Jira          Confluence       Figma
  ─────────
  Other mail (IMAP) · Schedule · Webhook
```

A tile shows what is already there: `✓ gh` when `gh auth status` says logged in, `✓ ann@acme` when
a Login exists for that service — those skip the login step.

The link box recognises:

| Link | Service and target |
|---|---|
| `github.com/<owner>/<repo>[/…]` | GitHub, that repo |
| `<host>/<group>/<project>[/-/…]` (gitlab.com or a host with a GitLab Login) | GitLab, that project |
| `<ws>.slack.com/archives/<C…>` | Slack, that workspace and channel |
| `discord.com/channels/<guild>/<channel>` | Discord, that server and channel |
| `<site>.atlassian.net/browse/<KEY-1>` or `/jira/…/projects/<KEY>` | Jira, that site, project `KEY` |
| `<site>.atlassian.net/wiki/spaces/<SPACE>/…` | Confluence, that site and space |
| `figma.com/(design\|file\|board)/<key>/…` | Figma, that file |
| `figma.com/files/team/<id>/…` | Figma, that team's projects to pick from |
| an e-mail address | Gmail when `@gmail.com` or Google Workspace *(check: MX lookup)*, else Other mail |

### 4.3 The three steps

Every service runs the same three steps in the same panel, over the feed (like a signal or the
settings, with ← back):

```
 Slack · acme                                   1 Log in  ›  2 What  ›  3 Check
```

1. **Log in** — skipped when a Login (or `gh` / `glab`) is there. Otherwise: a numbered list of
   at most three clicks, each with its link, and one field for what to paste. The field checks
   the shape at once (`xoxp-…`, `glpat-…`, `figd_…`, 16 letters for an app password) and the
   login itself on Continue (`/myself`, `auth.test`, an IMAP login).
2. **What** — a list from the service, the likely ones ticked; a search box over it. Optional:
   a narrower query (JQL, CQL) folded under *More*.
3. **Check** — the first look, live, then **Add**. Shows: as whom, what it will hear, how many
   items are there now (they are marked seen, not sent), and how often it looks. **Add** writes
   the spec line and the source's chip appears at once with `0`.

After Add: if the tower has no intent yet, one line under the chips offers it: *Say what to listen
for, or everything passes* (→ Sources & intent).

## 5. Per service

What each service needs, the shortest login, what step 2 lists, and what becomes a signal.
`watch.mention` is "about you" (a mention, a DM, a review asked of you, an assignment);
`watch.comment` is everything else new.

### GitHub — zero pastes when `gh` is there

- **Login:** `gh auth status`. Logged in → nothing to do. Not logged in → **Log in with GitHub**
  runs `gh auth login --web` in the GUI's terminal panel (a device code to type in the browser).
  No `gh` → a fine-grained token: link to `github.com/settings/personal-access-tokens/new`,
  read-only *Metadata, Issues, Pull requests* (+ *Notifications* for a classic token).
- **What:** two switches, both on by default:
  - **My notifications** — `gh api notifications?participating=true`: review requests,
    mentions, assignments, replies in threads I am in, across every repo. → `watch.mention`.
  - **Repos** — a list from `gh repo list` and the orgs, **this project's `origin` ticked**:
    their events as today (`repos/{repo}/events`). → `watch.github`.
- **Spec:** the `github:` key takes a list and notifications move into a feed line:
  `github: repos=owner/app,owner/api notifications=on` (gh's login; `token=keychain:github` when
  there is no gh). The old `github: owner/repo` key keeps loading as one repo.
- **Push later:** `gh api repos/{repo}/hooks` (needs admin; the automation plan §2 D).

### GitLab — new

- **Login:** `glab auth status` *(check)* → reuse it. Otherwise a personal access token: the link
  `https://<host>/-/user_settings/personal_access_tokens?name=orkcraft&scopes=read_api` opens the
  form prefilled; paste `glpat-…`. A self-hosted GitLab is asked for its host first (or comes
  from the pasted link).
- **What:**
  - **My to-dos** (on by default) — `GET /api/v4/todos?state=pending`: mentions, assignments,
    review requests, failed pipelines of mine. → `watch.mention`.
  - **Projects** — `GET /api/v4/projects?membership=true&order_by=last_activity_at`, the
    project whose remote matches `origin` ticked; their events
    (`GET /projects/:id/events`). → `watch.comment` (`watch.gitlab` *(check: a new event or
    reuse `watch.github`'s shape)*).
- **Spec:** `gitlab: host=gitlab.com token=keychain:gitlab projects=group/app,group/api todos=on`
  (`projects=` takes paths with `/`, so `feeds.IDS` grows a path form).
- **Push later:** project webhooks with `X-Gitlab-Token`; `/gitlab` in `realm/inbound.py`.

### Gmail — one paste (an app password)

- **Login:** the e-mail address, then an app password: link to
  `myaccount.google.com/apppasswords` (needs 2-step verification — the panel says so and links
  it). Paste the 16 letters; Continue logs in over IMAP. IMAP is always on for personal Gmail
  since 2025 *(check)*.
  - A Workspace account whose admin forbids app passwords gets the plain fail: *Your
    organisation does not allow app passwords — Gmail needs a Google sign-in (not built yet)*,
    and the link to the automation plan's OAuth (§2 E, open question 1).
- **What:** the folder (`INBOX` ticked; the labels listed from IMAP `LIST`), and **Only unread**
  on. Optional: **From** and **Subject contains** — a cheap filter before the intent.
- **Spec:** as today, the password by Login: `host: gmail`, `user: ann@example.com`,
  `password_env: keychain:gmail-ann`.
- Yandex and iCloud are the same flow with their own app-password links (Other mail asks the
  host).

### Slack — one app from a manifest, one paste

Slack has no personal token without an app. The panel makes the app in two clicks:

1. **Create the app** — a link to `api.slack.com/apps?new_app=1&manifest_json=…` *(check: the
   manifest in the address)* carrying orkcraft's manifest: name *Orkcraft listener*, **user**
   scopes `search:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`,
   `channels:read`, `groups:read`, `users:read`. The person picks the workspace and confirms.
   If the address cannot carry it, the panel shows the manifest with **Copy** and the link to
   *From an app manifest*.
2. **Install to the workspace**, then copy the **User OAuth Token** (`xoxp-…`) from *OAuth &
   Permissions* — the panel says exactly where it is.
3. Paste it. Continue runs `auth.test` (as whom, which workspace).

- **What:**
  - **Mentions and DMs** (on by default) — as today, `search.messages` for `<@me>` and the D…
    channels. → `watch.mention`.
  - **Channels** — `users.conversations` (the ones I am in), sorted by my latest activity, none
    ticked; a pasted channel link ticks that one. → `watch.comment`.
- An app installed only in its own workspace is an internal app, outside Slack's 2025 history
  limits for unlisted apps *(check)*.
- **Spec:** `slack: token=keychain:slack-acme channels=C0123,C0456` (as today, the token by
  Login).
- **Push later:** Socket Mode (the automation plan §2 A) — the same manifest with
  `socket_mode_enabled` and an `xapp-` token; no tunnel.

### Discord — new; a bot, because a person's token is off limits

Discord forbids automating a user account, so the tower listens as a bot the person invites to
their server. It hears only the channels the bot can see, and tells a mention by the person's
user id (asked once in step 2).

1. **Create the bot** — link to `discord.com/developers/applications` → *New Application* →
   *Bot* → *Reset Token*, copy it; on the same page switch on **Message Content Intent**
   (privileged, a switch for bots in under 100 servers).
2. Paste the token. Continue runs `GET /users/@me` (the bot's name).
3. **Invite it** — the panel builds the link from the bot's id:
   `discord.com/oauth2/authorize?client_id=<id>&scope=bot&permissions=66560` (View Channels +
   Read Message History, nothing else); the person picks the server.

- **What:** the servers the bot is in (`GET /users/@me/guilds`) and their text channels
  (`GET /guilds/{id}/channels`), none ticked; a pasted channel link ticks that one. **Me** — the
  person's Discord user (from a pasted message link's author or typed `@name`), to tell mentions.
- **Signals:** new messages per channel (`GET /channels/{id}/messages?after=<last>`). A message
  that mentions **me** or the bot, or replies to me → `watch.mention`; others `watch.comment`.
- **Spec:** `discord: token=keychain:discord-bot channels=123,456 me=789`.
- **Push later:** the Gateway (a WebSocket, like Slack's Socket Mode) — no tunnel needed.

### Jira (and Confluence) — one paste, both from it

- **Login:** the site (from a pasted link, else typed: `acme` → `acme.atlassian.net`), the
  e-mail, and an API token: link to `id.atlassian.com/manage-profile/security/api-tokens` →
  *Create API token*. Continue runs `/rest/api/3/myself`.
- One Atlassian login serves both: after Jira the panel offers **Also Confluence on this site**
  (one click, the same Login); the Confluence tile does the same the other way.
- **What (Jira):**
  - **About me** (on by default) — the default JQL as today: issues I watch, am assigned or
    reported; @-mentions → `watch.mention`, other new comments → `watch.comment`.
  - **Projects** — `GET /rest/api/3/project/search`, none ticked; a ticked project adds
    `project in (…)` to the JQL. Status changes and new issues come in through a ticked project:
    *(check: the changelog in `search/jql` with `expand=changelog`)* — today only comments do.
  - *More:* the JQL itself.
- **What (Confluence):** **Mentions of me** on; spaces from `GET /wiki/api/v2/spaces`, none
  ticked; *More:* the CQL.
- **Spec:** as today, by Login: `jira: site=acme.atlassian.net user=keychain:atl-acme-user
  token=keychain:atl-acme` (the e-mail lives in the Login too, so `user=` can name it).

### Figma — one paste

- **Login:** link to `www.figma.com/settings` → *Security* → *Generate new token*, scopes
  **File content: read**, **Comments: read**, **current user: read**. Paste `figd_…`; Continue
  runs `/v1/me`.
- **What:** paste one or more file links (the main way — Figma has no "my recent files" API), or
  a team link → `GET /v1/teams/{id}/projects` → `GET /v1/projects/{id}/files`, sorted by last
  change, tick the files.
- **Signals:** as today — new comments; a reply to mine or an @-mention → `watch.mention`.
- **Spec:** `figma: token=keychain:figma files=AbC123,XyZ789`.
- **Push later:** Webhooks v2 `FILE_COMMENT` (needs a team with edit rights).

### Summary

| Service | Pastes | Login check | Step 2 lists | Default on | New code |
|---|---|---|---|---|---|
| GitHub | 0 with `gh`, else 1 | `gh auth status` | repos (`origin` ticked) | notifications + this repo | notifications feed, many repos |
| GitLab | 0 with `glab`, else 1 | `/user` | projects (`origin` ticked) | to-dos + this project | the whole service |
| Gmail | 1 | IMAP login | folders | INBOX, unread | the login by Login, folder list |
| Slack | 1 (after 2 clicks) | `auth.test` | my channels | mentions and DMs | the manifest, channel list |
| Discord | 1 (after 3 clicks) | `/users/@me` | servers → channels | — | the whole service |
| Jira / Confluence | 1 + site + e-mail | `/myself` | projects / spaces | about me / mentions | project and space lists |
| Figma | 1 | `/v1/me` | files from links or a team | — | team → files list |

## 6. The whole service, not a list of things

People ask to hear "all of Jira" or "all of Figma", not three channels. How far each service goes
without a list:

| Service | Everything, polled | Note |
|---|---|---|
| Jira / Confluence | yes: `jql=` / `cql=` can span the site (`updated > -1d`, `type = comment`) | loud; offered only with an intent, which keeps it calm |
| Slack | yes: `search.messages` with `after:<date>` sees every channel the person can, no channel list | search trails real time by seconds |
| GitHub / GitLab | yes: notifications and to-dos cover every repo and project | — |
| Discord | the channels the bot can see in the servers it was invited to | a server's every channel is one tick ("all channels") |
| Gmail | the whole mailbox: every folder, or `[Gmail]/All Mail` | — |
| Figma | **no**: there is no "my files" or "my notifications" API. A team → its projects → their files → each file's comments is many calls a look and meets the rate limit | the whole team comes with a team-level Webhook v2 `FILE_COMMENT` — push, so it needs a public address (watchtower-automation.md §2 C) |

So step 2 of every service but Figma gets **Everything** at the top of its list (off by default),
and turning it on with no intent asks for one: *Everything in Jira is a lot — say what you listen
for, or keep everything*. Figma's **Whole team** stays greyed out with *needs push — not built
yet* until the tunnel exists.

## 7. Through Claude or agy: the connectors people already have

Many people have Jira, Confluence, Slack, Figma or GitHub connected in Claude Code or agy already
(MCP servers, claude.ai connectors). The tower can use them without a single token of its own,
but not the way it uses a token.

### 7.1 What it cannot do

- **Borrow their logins.** Reading Claude Code's or agy's stored OAuth tokens would be posing as
  another app: fragile and against the services' terms. Never.
- **Log in to the same servers itself.** The hosted MCP servers admit their own lists of clients:
  Atlassian's (`mcp.atlassian.com`) does dynamic client registration but only for approved clients
  (custom redirect addresses are a feature request, ROVO-870); Slack's (`mcp.slack.com`) has no
  dynamic registration *(check, both)*; Figma's (`mcp.figma.com`, and the claude.ai Figma
  connector) serves design context for code and has **no tool for comments** (checked, §7.5) —
  Figma is heard by its token only (§5). claude.ai's connectors live on Anthropic's side: no token is on the
  machine at all.
- **Be told when something happens.** MCP is tools to call, not events: an MCP source is polled
  like any other, through tools shaped for a model.

### 7.2 What it can: ask the agent

The tower runs the agent headless with the person's own MCP servers (`claude -p`, agy's headless
mode) and asks it, in a fenced prompt, for what is new. The agent is an approved client, so its
logins work.

- **One run per look**, on the light model (the Fast Path's): *list the new comments and mentions
  in Jira since 2026-10-07T10:12*. The tower passes the last look's time and the ids it has seen;
  dedupe is by `id` like every feed.
- **The answer by schema, not by asking.** `--json-schema` with `{items: [{id, title, text, url,
  author, at, mention}]}` (at most N items); the answer is read from the result's
  `structured_output`. A model asked for "only JSON" in words wraps it in prose or fences — it
  did, every time (§7.5).
- **The tower owns the process.** `--output-format stream-json --verbose`, stdin from
  `/dev/null` (without it the run waited on the terminal and never ended), the `result` event read
  and the process ended there, a timeout (90 s) over it all. The `system:init` event also tells
  which servers this run sees and their state, so a look that finds its server `needs-auth`
  fails at once as *needs a login* instead of asking the model.
- **Read-only, enforced by the tower, not asked of the model.** At setup the tower lists the
  server's tools and keeps those that only read (`get…`, `search…`, `list…`, `read…`); the run
  allows exactly those (`--allowedTools`) and nothing else — no shell, no files, no write tool. A
  signal's text can tell the agent to do something; it has nothing to do it with.
- **Slow and paid.** A look took ~35 s and $0.04–0.05 on haiku (§7.5): every 15 min that is
  ≈ $4 a day per source, every 30 min ≈ $2. So every 30 min by default (10 at the fastest), the
  model's thinking off *(check: how, headless)* — it was half of each look's time. Each look's
  cost goes to Spend and shows on the source's line (`via Claude · every 30 min · ≈ $0.90 today`);
  a daily ceiling
  in the tower's settings, past it the source waits like the Lookout does out of 🪙. A
  subscription's turns count against its limits (⏳ Limits shows them).
- **The same path every time.** Left to itself the model takes 3 turns one run and 13 the next
  (§7.5). The prompt names the tools in order, and the ids a look learns once — the Atlassian
  cloud id, the person's Slack user id — are kept and passed to the next look, which saves two
  turns and most of the spread.
- **Halt All** stops a look in flight; the next one starts from the same time.
- **Spec:** `agent: tool=claude server=atlassian every=15m ask=new comments and mentions in Jira`
  (`ask=` takes the rest of the line; `tool=agy` for agy).

### 7.3 Where it fits in the flow

- **The picker.** The tower reads the **names** of the person's MCP servers — the `mcp_servers` of
  a headless run's `system:init` (each with `source`: `claudeai`, `plugin`, local, and `status`),
  and the server keys of agy's `~/.gemini/config/mcp_config.json`,
  `~/.gemini/antigravity/mcp_config.json` and `~/.gemini/config/plugins/*/mcp_config.json` —
  never their settings or tokens, and marks the tiles:
  `Jira ✓ in Claude`. Such a tile offers two ways, the token one first:
  - **Log in** (§5): free, every 2 min, exact.
  - **Use Claude's connection**: no token, every 30 min, costs a model run each look.
  - A server in `needs-auth` shows as `Jira · in Claude, needs a login` with *run `/mcp` in Claude
    Code*; the tower cannot log it in.
- **Step 2 without a token.** The agent lists what there is (projects, spaces, channels) in one
  turn, for the agent source's ticks.
- **From the intent.** Whatever way a source is added, the agent can turn *user feedback about the
  app* into a proposal — Jira project `SUP`, Slack `#feedback`, a JQL — in one turn
  (watchtower-automation.md §2 G).
- claude.ai connectors **are** seen by a headless `claude -p` of a logged-in Claude Code (§7.5):
  a person who connected Gmail on claude.ai hears their mail with no app password and no setup.
  Right after start a connector can read `needs-auth` for a moment before it connects: the
  picker asks twice before it says so.

### 7.4 Its states

| State | Its chip | Its line |
|---|---|---|
| listening | `jira 2` | via Claude · every 30 min · last look 10:12 · ≈ $0.90 today |
| looking | `jira …` | asking Claude… |
| waiting: the ceiling | `jira ⏸` | *Today's ceiling ($0.50) reached — looks again tomorrow* · **Raise it** |
| waiting: limits | `jira ⏸` | *Claude's limit is used up until 14:00* |
| failing: the connection | `jira ✗ ERR` | *Claude's Jira connection needs a login — run `/mcp` in Claude Code* (the tower cannot log it in) |
| failing: the answer | `jira ✗ ERR` | *Claude's answer was not the list asked for* — the look is retried once, then waits for the next |
| failing: too slow | `jira ✗ ERR` | *Claude did not answer in 90 s* — the process is ended, the next look tries again |

### 7.5 Checked on a live machine (2026-10-07)

Claude Code 2.1.291 on macOS, agy 1.3.1.

| What | Found |
|---|---|
| claude.ai connectors in `claude -p` | seen, `source: claudeai`; tools named `mcp__claude_ai_<Name>__<tool>` |
| Their state at init | Gmail, Figma, Calendar `connected`; one run earlier read `needs-auth` for Gmail while `claude mcp list` said connected |
| Plugin servers (Slack, Atlassian, Linear, Notion, Intercom) | `needs-auth` until logged in once with `/mcp` (a browser consent, one click when already signed in) |
| Atlassian's read tools | an allow-list by hand: `atlassianUserInfo`, `getAccessibleAtlassianResources`, `searchJiraIssuesUsingJql`, `getJiraIssue`, `searchConfluenceUsingCql` (a name filter misses `fetch`, `search`, `…UserInfo`) |
| One Jira look (JQL about me, last day) | 4 issues, the same ids twice (`KEY:updated`); 5–7 turns, 23–42 s, $0.029–0.076 |
| One Confluence look (CQL mentions of me) | 0 items both times; one run took 13 turns and tried a tool not allowed (refused) — the same ask, a different path |
| One Slack look (mentions and DMs) | 0 items both times *(check: with a mention made on purpose)*; 3–8 turns, 15–22 s, $0.011–0.043 |
| agy | its MCP config holds firebase and dart servers only: nothing to listen with there |
| Gmail's read tools | `search_threads`, `get_thread`, `get_message`, `list_labels`, `list_drafts`, `get_draft`; 20 more write (send, reply, forward, trash, label…) — the allow-list matters |
| Figma connector | design, Code Connect, FigJam, shaders; **no comments** |
| "Only JSON" asked in words | not JSON (prose or fences) |
| `--json-schema` | the answer in `structured_output`, valid, `subtype: success` |
| Without stdin from `/dev/null` | the run answered and did not exit; ended by hand |
| One Gmail look (`search_threads` once, 10 items) | 4 turns, ~35 s (half of it thinking), $0.036–0.050 |
| Twice in a row | the same 10 thread ids: dedupe by id works |
| Write tools refused | not tried yet (a write prompt with read tools only) |

## 8. The states of a source

The Watchtower's states (its card and window) stay as they are; a source adds its own:

```
 not set ──Add──► logging in ──ok──► picking ──► checking ──ok──► listening
                     │                              │               │  ▲
                     └─fail: says which step        └─fail──────────┘  │
                                                                     failing ──Log in again / Edit──┘
```

| State | Its chip | Its line in Sources & intent |
|---|---|---|
| listening | `slack 3` | as whom, what it hears, last look · Edit · Remove |
| failing: the login | `slack ✗ ERR` | *The token was refused — log in again* · **Log in again** (step 1, the rest kept) |
| failing: a target | `slack ✗ ERR` | *#support is gone or the app was removed from it* · **Edit** (step 2) |
| failing: the network | `slack ✗ ERR` | *Could not reach slack.com* · nothing to do, it retries |

A failure reads as which of the three it is, so the fix is one button. `feeds.Look.error` grows
a kind (`login` / `target` / `network`) from the HTTP status (401/403 → login, 404 → target,
others → network).

## 9. What changes in the code

- `realm/logins.py` (new, no face): the store, `keychain:` refs, `resolve(ref)`; `Feed.env` and
  `mailbox` resolve through it.
- `realm/feeds.py`: kinds `gitlab`, `discord`; GitHub notifications; `Look.error` kinds; the
  lists for step 2 (`channels(feed)`, `projects(feed)`, …) as plain functions, faked in tests
  like the looks.
- `realm/sources_link.py` (new): a link or an address → (service, site, target).
- `core/workers/watchtower.py`: acts `add_source(service, login, targets)` →
  check (a first look) → write the spec line; `remove_source`, `edit_source`; the login form goes
  to `logins` without the scroll, the steward or the bus seeing it.
- `gui/views/watchtower.py` + `js/buildings/watchtower.js`: the picker, the three steps, the `+`
  chip, Edit / Log in again / Remove per source. Every label through `say()`; the new word
  *Logins* in `lexicon.TERMS`.
- The manifest for Slack and the invite link for Discord: data in `realm/feeds.py`.
- `realm/feeds.py`: an `agent` kind whose look runs `claude -p` / agy headless with the read-only
  tools picked at setup (`core/workers` runs it in a thread like every look, faked in tests like
  `judge_runner`); its spend through the Fast Path's accounting.
- `tools.py`: the names of the MCP servers Claude Code and agy have, for the picker's marks.
- The TUI gets nothing (deprecated, calm-town.md §9); its view keeps reading the same spec.

## 10. Stages

| # | Stage | Done when |
|---|---|---|
| 1 | Logins + `keychain:` refs | a token pasted in the GUI works with no restart and no export; old specs load |
| 2 | The picker, the three steps, GitHub (gh), Gmail, Jira/Confluence, Figma | each is added in under a minute on a clean machine, the first look shown before Add |
| 3 | Slack's manifest | a person with no Slack app gets one and listens in two clicks and a paste |
| 4 | GitHub notifications; GitLab | review requests and mentions arrive from both |
| 5 | Discord | a bot invited by the panel hears the ticked channels; mentions of me are told |
| 6 | Paste a link | every link of §4.2 lands on the right service with its target ticked |
| 7 | Failure kinds + Log in again / Edit | a revoked token is fixed from the chip in one step |
| 8 | Everything (§6) | Jira, Slack, GitHub, GitLab, Discord and mail can be heard whole, with an intent asked for |
| 9 | Through Claude or agy (§7) | a person with Jira only in Claude hears it with no token, read-only, the cost shown |

## 11. Open questions

1. **Discord's "me".** Is asking the person's user id good enough, or should the bot learn it
   from the first message they write while it watches?
2. **Many accounts per service** (two Slack workspaces, work and personal Gmail): one line each
   already works; the picker shows the Logins it has — is "+ another account" enough?
3. **GitHub notifications vs repo events.** Notifications alone might be what most people want;
   should repo events be off by default to keep the feed calm?
4. **Who may see Logins.** The GUI is reachable from a phone (mobile.md): may a phone add a
   Login, or only the machine the town runs on?
5. **The keychain on Linux** without a running secret service: is the 0600 file acceptable as
   the default, or should the panel ask?
6. **The agent source's price.** Is 15 min and a light model the right default, and should it be
   offered at all on a subscription whose limits the orks also need?
7. **Figma's whole team** waits for push; is a slow poll of the team's recently changed files
   (`last_modified` from the projects' lists, only those asked for comments) good enough
   meanwhile?
