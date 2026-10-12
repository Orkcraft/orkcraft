# Design — a personal Google account: Gmail, Calendar and Drive in one sign-in

Status: written 2026-10-08; phase 1 is built (`realm/google.py`, `realm/feeds_google.py`, `sources/ics.py`,
`sources/lore.py`, `gui/accounts.py`, `js/accounts.js`; tests/test_google.py). Not yet tried on a live Google
account: §8 is the first check. Wording: External listeners (Watchtower), Calendar (War Drum), Wiki (Scroll Dump).

## 1. What it is for

A person signs in to their own Google account once, and three buildings use it:

| Part | Scope | Building | What it does |
|---|---|---|---|
| Gmail | `gmail.readonly` | External listeners | new mail is a signal (`gmail: login=…`), a message addressed to you in To a mention |
| Calendar | `calendar.events` | Calendar | the week comes from Google Calendar; New event adds there |
| Drive | `drive.readonly` | Wiki | a source `gdrive:google-<e-mail>[/<folder>]`: Docs exported as Markdown, text files as they are, the rest skipped |

It is for **personal use**: one person, their own Gmail. A Workspace account whose admin blocks unknown apps gets
the plain refusal and the way round it (§6).

## 2. Why the person's own client, and what Google does with it

Weighed on 2026-10-08 (the discussion is in the session that wrote this):

- **An Orkcraft-owned OAuth client** is one click for the person, but makes Orkcraft a vendor: a verified app,
  a privacy policy, and for Gmail (a *restricted* scope) a security assessment (CASA) every year, ≈ $540–1 800
  through TAC Security and weeks of work. Not for a personal tool.
- **The person's own client** (chosen): a Desktop app in their own Google Cloud project, published **In
  production** and never verified. Google then shows "Google hasn't verified this app" once; the person, who made
  it, clicks Advanced → Go to … (unsafe). An unverified app may sign in up to 100 users in its whole life: one
  person never reaches it, and no assessment is asked.
- **Testing is not enough:** in Testing, Google ends a refresh token after 7 days. The wizard says so on the step
  that publishes the app.
- A refresh token In production lasts until it is revoked, the Google password changes (for Gmail scopes), or it
  is unused for six months. Each ends as a plain *Connect Google again* (§5).
- **Claude's connectors** (a look through `claude -p`, watchtower-quick-add.md §7) stay as they are: no setup,
  but a model run each look (≈ $0.04, ≈ $2 a day per source every 30 min). The Google sign-in is free per look.

### Why these scopes, and not more

- `gmail.readonly`, not `gmail.modify` or `mail.google.com`: the tower only listens. Nothing is sent, labelled,
  deleted or marked read. (IMAP with OAuth would need `mail.google.com`, the whole mailbox to write: so Gmail is
  read through the Gmail API instead.)
- `calendar.events`, not `calendar`: events are read and added; calendars themselves and their sharing are not
  touched.
- `drive.readonly`, not `drive`: mail is text from strangers and it reaches the orks' models. A prompt injection
  in a letter must never get a token that can change or delete Drive. Writing to Drive gets its own scope when a
  building needs it, asked then.
- `openid email`: the address the account is kept under, nothing else of the profile.

Each scope is a tick on Google's page; the person may leave one out. The parts Google allowed are kept with the
sign-in, and the wizard says which ones it did not (§6).

## 3. The wizard

Settings → Accounts → **Connect Google**, and the same from the onboarding's last card (over the map, beside
How free are your orks?: nothing waits on it). **Put away for now (2026-10-09):** the wizard is long and opened over
Town settings, so Connect Google shows only with `ORKCRAFT_GOOGLE=1` (the snapshot's `google`, `js/accounts.js`
`googleShown`): in Settings, the onboarding and the Calendar's import alike. An account already connected still
shows in Settings → Accounts, with Disconnect. Five steps, each with a link straight to its page of the console:

1. **Make a project** (`console.cloud.google.com/projectcreate`): any name; free, no billing.
2. **Turn on the APIs** (`flows/enableapi?apiid=gmail…,calendar-json…,drive…`): the three at once.
3. **Name the app and publish it**: Branding (a name, your e-mail), then Audience → External → **Publish app**.
4. **Make a Desktop client** (`auth/clients/create`) and paste its Client ID and secret, or the JSON file.
5. **Sign in**: Gmail, Calendar and Drive ticked; the browser opens Google's page; the answer comes back to
   `http://127.0.0.1:<port>` (PKCE, a state of its own). Then **Use it in the town**: each part with the building
   it goes to, and *(set up now: not in the town yet)* beside a building that is missing.

About 5–8 minutes, up to 12 the first time; once. With a client saved, steps 1–4 show ✓ and the wizard opens on 5.

`gcloud` is not used: it is one more install and one more sign-in, and most people have neither. A person who has
it may make the project and turn on the APIs with it; the client and the publishing are console pages anyway.

## 4. Where the sign-in lives, and what the person sees

- **The client** is the login `google-client` (realm/logins.py): the OS keychain when `keyring` is there, else
  `logins.json` with mode 0600. **An account** is the login `google-<e-mail>`: its refresh token and the parts
  Google allowed. A building names it, never holds it: `login=keychain:google-ann@gmail.com`,
  `"google": "keychain:google-ann@gmail.com"`, `gdrive:google-ann@gmail.com`. Nothing of it is in the project or
  its git.
- The hour's access token lives in memory only.
- **Settings → Accounts** lists each account: its e-mail, the parts (Gmail · Calendar · Drive), *Used by* each
  building and part, the Wiki's Drive (the whole Drive, or **Choose a folder** of My Drive), *Use … in the town*
  for a part no building uses yet, and **Disconnect**.
- The safety line says plainly: read-only for mail and Drive; the calendar may add the events you ask for; mail,
  events and documents the orks work on go to the AI tool that runs them, as any other text does.

## 5. Disconnect

One button per account, with a confirmation: Google takes back the access (`oauth2.googleapis.com/revoke`), the
sign-in is deleted from this machine, and the buildings that used it say **Connect Google again** until it is
back. **Also take it out of the buildings** (a tick) removes the Gmail line, the Calendar's `google` and the Drive
source as well. **Forget the Google Cloud client** removes the client once no account is left.

A sign-in Google stopped accepting (revoked in the Google account, a new password, six months unused) shows the
same way: the source burns `login` with *Connect Google again (Settings → Accounts)*.

## 6. When Google refuses

Every failure says what happened and what to do (`GoogleError`, with `login` / `target` / `network` as the
tower's failures):

| What | What the person reads |
|---|---|
| `access_denied` on the way back | You did not allow it, or Google blocked the app. To try again … click Advanced, then Go to … (unsafe). + the way round |
| no answer in ten minutes | If Google said the app is blocked and gave no way on, Google will not let this client read your mail or Drive. + the way round |
| a part left unticked | Google did not allow Drive. + the way round; the other parts work |
| `admin_policy_enforced`, `org_internal` | This Google account's admin does not allow this app. + the way round |
| an API off in the project | The Gmail API is off in your Google Cloud project: turn it on (its link), then wait a minute |
| `invalid_grant` | Google no longer accepts this sign-in … Connect Google again |

**The way round** (`google.FALLBACK`): Gmail with an app password (External listeners → Add a source → Gmail,
watchtower-quick-add.md §5) and the calendar from its secret iCal address, read-only (Calendar → settings).

**The open risk.** Whether Google lets an unverified personal client have the *restricted* scopes
(`gmail.readonly`, `drive.readonly`) was not found written down by Google: rclone, the Google Workspace CLI and
several MCP servers work this way, and the 100-user cap is the stated limit. §8 checks it on a live account. If
Google blocks it, the Calendar still works (`calendar.events` is only *sensitive*), and Gmail and Drive fall back
as above.

## 7. Not done, on purpose

- No Orkcraft-owned client, no server of ours, no relay.
- No `gmail.modify`, `gmail.send`, `mail.google.com`, full `drive` or full `calendar`.
- No reading of Claude's or agy's own Google tokens (watchtower-quick-add.md §7.1).
- No Testing-mode client handed to the person: tokens that die after a week look like a bug.
- No phone adds an account (mobile.md: a phone never changes a setting).
- No forwarding rules and no Pub/Sub push for Gmail: the tower asks every 2 minutes.
- No PDF or Office file read from Drive in phase 1; no shared drives beyond what `files.list` gives by default.

## 8. The first live check (after the merge)

1. `orkcraft gui` on a project → Settings (**Menu ▾** in the HUD) → **Connect Google**.
2. Steps 1–4 in Google Cloud with your personal Gmail; on step 3 press **Publish app** (Audience).
3. Step 5: **Sign in with Google** → *Google hasn't verified this app* → Advanced → Go to … (unsafe) → leave the
   three ticks → the tab says *Connected*.
4. **Use it** with all three ticked. Within two minutes: a mail sent to yourself from another address shows in
   External listeners; the Calendar shows this week; the Wiki's sources list *Google Drive · <e-mail>*.
5. Calendar → New event → it appears in Google Calendar.
6. Settings → Accounts → Disconnect → the account is gone from `myaccount.google.com/connections`.

What to send back if a step fails: the step's number, the text Orkcraft or Google showed (a screenshot is best),
and whether Google's warning page offered *Go to … (unsafe)*.

## 9. Where it lives

| Part | File |
|---|---|
| The client, the sign-in, the tokens, the three APIs | `orkcraft/realm/google.py` (no face) |
| Gmail as a feed of External listeners | `orkcraft/realm/feeds_google.py`, `realm/feeds.py` (`gmail:`) |
| The Calendar's Google source and New event | `orkcraft/sources/ics.py` (`read_google`), `core/workers/war_drum.py` (`google`) |
| Drive as a source of the Wiki | `orkcraft/sources/lore.py` (`GoogleDriveSource`) |
| Settings → Accounts, putting it in the town | `orkcraft/gui/accounts.py`, `gui/static/js/accounts.js` |
| The onboarding's card | `gui/static/js/onboarding.js` (`Connect Google`) |

## 10. Later

- The tower reads a whole message on Enter (`messages.get format=full`), as it does over IMAP.
- Gmail's `history.list` instead of a search each look (fewer calls; a mail older than two days that arrives late).
- PDFs and Office files from Drive (Drive's own text export for Office files).
- More than the primary calendar (a pick in the Calendar's settings).
- Other accounts the same way (Microsoft 365: Outlook, its calendar, OneDrive).
