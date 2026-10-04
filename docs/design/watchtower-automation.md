# Design — the Watchtower, fully automatic

Status: a plan, written 2026-10-04; nothing of it is built. API details marked *(check)* have not
been verified against the live services yet (see reference.md, Watchtower → Later).

## 1. The goal

The operator says two things once: **where to listen** (Gmail, Slack, Jira, Confluence, Figma,
GitHub) and **what for** (the intent). Everything else happens on its own and keeps working:

- the tower hears while the TUI is closed, and nothing is lost;
- logins are made by clicking through a browser, never by pasting tokens into the environment;
- each source is pushed to the tower when it can be, asked when it cannot, and both when in doubt;
- addresses, secrets and webhook registrations are created, renewed and repaired by the tower.

What the operator does today, and what replaces it:

| Today, by hand | Fully automatic |
|---|---|
| export `SLACK_TOKEN`, `ATL_TOKEN`, … | `orkcraft connect slack` — a browser login, the token in the OS keychain |
| run cloudflared, copy the address | the tower runs and supervises the tunnel itself |
| paste the address into Slack, Jira, Figma, GitHub | the tower registers its webhooks through their APIs |
| invent secrets, put them in the environment | generated, kept in the keychain, rotated |
| keep orkcraft open | a background service (`orkcraft watch`) |
| notice a dead webhook | the tower notices (polling finds what push missed) and re-registers |

## 2. The pieces

### A. Push without a tunnel first

The cheapest automation needs no public address at all. Prefer it wherever it exists:

- **Mail: IMAP IDLE.** The server tells the open connection when mail arrives; Gmail, Yandex,
  iCloud support it. Instant mail, no tunnel, no Google Cloud project (Gmail's own push needs
  Pub/Sub).
- **Slack: Socket Mode.** The tower opens a WebSocket to Slack with an app-level token
  (`xapp-…`); events come down it. No Request URL, no signing secret to check, no tunnel. Costs
  one dependency (`websockets`), as an optional extra.
- GitHub, Jira, Confluence and Figma have no such channel: they need an address (C, D).

### B. A tower that never sleeps: `orkcraft watch`

- One background process per project; `orkcraft watch install` makes it a user service (launchd
  on macOS, a systemd user unit on Linux, a scheduled task on Windows), the way `orkcraft hooks
  install` installs the Warder. `orkcraft watch status / stop / uninstall`.
- It runs every source of every Watchtower in the town: polling, IMAP IDLE, Socket Mode, the
  webhook listener, the tunnel, the Lookout's intent filter.
- **Durable:** a delivery is appended (and fsync'ed) to `signals.jsonl` *before* the 2xx goes back;
  the dedupe keys live beside it. A crash loses nothing the sender thinks it delivered.
- The TUI becomes a reader: it tails `signals.jsonl`, shows the hut counts, marks read. A lock file
  makes sure one process owns the listeners; without the service the TUI keeps doing it all itself
  (today's behaviour).
- Carts down the roads: phase 1 — the service only collects, the TUI sends the carts when it opens
  (with a "12 came while you were away" note). Phase 2 — the service runs the roads headless too,
  within the autonomy slider's limits (open question 5.3).

### C. The address: a supervised tunnel

- The tower picks what is installed, in this order:
  1. **cloudflared, named tunnel** — a stable hostname on the operator's Cloudflare domain;
  2. **tailscale funnel** — a stable `*.ts.net` address;
  3. **ngrok** with its one free static domain;
  4. **cloudflared quick tunnel** — a new random address each start (then D re-registers every time).
- It starts the tunnel as a child process, reads the public URL from its output, checks it end to
  end (`GET https://…/` must answer `orkcraft watchtower`), restarts it on exit with backoff, and
  stores the address in `.orkcraft/watchtower/<id>/tunnel.json`.
- The hut and the head show it: `🌐 tower.example.com` or `🌐 no tunnel — polling`.
- Only the service paths (`/slack`, `/jira`, `/confluence`, `/figma`, `/github`) are exposed; a
  secret is required on every one of them (reference.md, Later 3).

### D. Webhooks registered by the tower

On start, on a new address and once a day, for every source with a login, the tower makes sure a
webhook exists, points at the current address and carries the current secret. Each one is tagged
(name or description `orkcraft:<project>:<building>`) so it finds and updates its own and never
touches others.

| Service | How | Needs |
|---|---|---|
| GitHub | `gh api repos/{repo}/hooks` — create or update, events `issues`, `issue_comment`, `pull_request`, `pull_request_review_comment`, `workflow_run` | admin on the repo; `gh` already logged in |
| Figma | `POST /v2/webhooks` (`FILE_COMMENT`, endpoint, passcode) for the team or project *(check: the v2 context fields)* | edit rights on the team |
| Jira | admin webhooks `POST /rest/webhooks/1.0/webhook` with a secret; for a non-admin, dynamic webhooks `POST /rest/api/3/webhook` via an OAuth app, which expire after 30 days — refreshed with `PUT /rest/api/3/webhook/refresh` *(check)* | Jira admin, or an OAuth app (E) |
| Confluence | no public webhook API for users: the tower writes the Automation rule's JSON for the operator to import once *(check: the Automation REST API)*; until then, polling | a space admin, once |
| Slack | Socket Mode (A) — nothing to register. Without it: `apps.manifest.update` sets `event_subscriptions.request_url`, with an app configuration token rotated by `tooling.tokens.rotate` | the app's collaborator |

When registration is not allowed (no admin rights), the tower says exactly which click the
operator, or their admin, has to make — and polls meanwhile.

### E. Logins: `orkcraft connect <service>`

- A browser OAuth flow with a redirect to `http://127.0.0.1:<port>/callback` (the device flow where
  a service has one; GitHub through `gh auth login`).
- Tokens and refresh tokens go to the OS keychain (`keyring`, optional extra); without a keychain,
  `~/.config/orkcraft/secrets.json` with mode 0600. Specs keep naming references, never values —
  `token=keychain:slack` beside today's `token=SLACK_TOKEN`.
- Refresh before expiry; a refused refresh turns the source's hut line into `slack  ERR` and the
  Town Hall's audit into a finding: "Slack: log in again — `orkcraft connect slack`".
- Gmail and Microsoft 365 through OAuth here too (Later 4): IMAP with XOAUTH2, so IDLE (A) keeps
  working.

### F. Push and poll, arbitrated

- Each source has a state: `push` (webhook or socket healthy), `poll` (no push possible) or
  `both` (just registered, or in doubt).
- While push is healthy, polling drops to a slow safety net (every 15–30 min). If the safety net
  finds an item push never delivered, push is marked doubtful: re-register (D), poll fast again.
- Silence is not proof: a heartbeat where the service offers one (Slack's socket pings, a GitHub
  `ping` after re-registration).
- Dedupe stays as it is (one key per item, however it came), so arbitration can be generous.

### G. The intent, set up for you

- From the intent alone the tower proposes sources and filters: "user feedback about the app" →
  Gmail (support@), Slack `#feedback`, Jira project `SUP`, App Store / Google Play reviews (new
  sources), a Signpost route to Barracks for a summary.
- A cheap prefilter before the model (keywords the model proposes once from the intent) cuts the
  cost; the model sees only what passes.
- 👍 / 👎 on what the Lookout let through (realm/feedback.py already records ratings) become
  examples in its prompt — the filter learns the operator's taste.
- The Crag shows the filter's spend per day; a ceiling in the tower's settings.

## 3. Stages

Each stage is useful alone, in this order:

| # | Stage | Done when |
|---|---|---|
| 1 | IMAP IDLE; Slack Socket Mode | mail and Slack arrive within seconds with no tunnel and no public address |
| 2 | `orkcraft watch` + durable spool | signals arrive while the TUI is closed; killing the process mid-delivery loses nothing |
| 3 | `orkcraft connect` + keychain + refresh | no token is ever exported by hand; an expired login shows as ERR with the fix |
| 4 | the tunnel manager | a stable public address, checked end to end, restarted on failure |
| 5 | webhook registration: GitHub, Figma, Jira; Confluence's rule export | adding a source needs no visit to the service's settings (admin rights aside) |
| 6 | push / poll arbitration, self-healing | a deleted webhook is noticed and recreated within one safety-net round |
| 7 | intent-driven setup, prefilter, learning from 👍 / 👎 | an intent alone yields a working tower; the filter's misses fall week to week |

## 4. Open questions

1. **Whose OAuth apps?** Slack, Atlassian, Figma, Google and Microsoft OAuth needs registered client
   ids. Orkcraft-owned apps (one click for users, but orkcraft becomes a vendor they trust, with
   app reviews — Google's restricted Gmail scopes need a security assessment) or each team's own
   (no vendor, but a setup step per service)?
2. **A relay?** A small orkcraft-run relay would give every user a stable address and survive the
   laptop sleeping — but orkcraft promises "no servers, sends nothing anywhere". Self-hosted relay
   as an option?
3. **Headless roads.** May the service run agents while nobody watches? Tie it to the autonomy
   slider and the quiet hours, and to the prompt-injection rules (Later 2).
4. **A sleeping laptop.** Webhook senders retry for minutes to hours; Slack's socket reconnects.
   Is a sleeping machine acceptable, or is "always on" a reason for the relay (2) or a small VPS?
5. **Admin rights.** GitHub and Jira webhooks need admin; most operators are not. Is polling plus a
   ready-made request for the admin good enough?
6. **Windows** for the service and the tunnel — supported at stage 2, or later?
7. **Cost.** The intent filter calls a model for every signal batch; at 99+ Slack messages an hour,
   is the prefilter enough, or is a per-day ceiling with "everything passes after it" the rule?
