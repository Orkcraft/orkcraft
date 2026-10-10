# Design — the town in your pocket: a mobile client

Status: a plan, written 2026-10-06; stage 0 of §9 is built (`orkcraft/gui/mobile.py`,
`GET /api/version` in `orkcraft/gui/server.py`, `tests/test_mobile.py`); stage 1 and 2 are built on the
host's side (the listener `gui/phones.py`, pairing `gui/pairing.py`, the certificate `gui/phone_tls.py`,
Settings → Phones `gui/static/js/phones.js`, `mobile.chat`, the notifier `gui/notify.py`;
`tests/test_phones.py`), with `tools/phone.py` as a phone in a terminal. A first app is a prototype web app
the listener serves itself over Tailscale (`gui/pwa.py`, `gui/static/pwa/`, `tests/test_pwa.py`; §10); a
native app is not built (§8.1).
Builds on the GUI's host and socket ([gui-migration.md](gui-migration.md) §5) and the daemon it
leads to (§1 there).

## 1. What a phone is for

The orks work while the operator is away from the desk, and what stops them most is a question
nobody answers. A phone paired with the town (a 🐦‍⬛ **War Raven** in Camp, a **Phone** in Office:
`lexicon.TERMS` `war_raven`) is for the moments between: a glance, a tap, back in the pocket.

| On the phone | What it does | In the code |
|---|---|---|
| Glance at the town | the project, each building's title, type, state and whether its ork asks | `mobile.compact` over `state.buildings` |
| Orders (Office: Answers) | a question an ork waits on, its last lines, its answers, the Elders' advice; a tap answers | `orders.answer` → `Muster.answer`; `orders.follow` |
| Drop into The Pit (Office: Drop file here) | a link, a text, a photo or a file shared from the phone's share sheet | `act` → `gui/views/pit.py` `drop` / `drop_file` |
| Ask the Warchief (Office: Lead agent) | the Town Hall's chat, one question at a time | `act` → `gui/views/town_hall.py` `ask` |
| 🛑 Halt All (Office: Stop all) | every session interrupted, every agent process killed | `halt` → `Host._halt` |
| Spend and quotas | the HUD's spend against its limit and the tools' quotas | `state.hud` (`treasury.resources`, `treasury.quota`) |
| Push notifications | a question came, spend or a quota crossed into warn or over | `mobile.news` (§5) |

### What stays on the desktop

The phone never changes the shape of the town. It does not build or demolish, lay or take up
roads, move huts, recruit, edit a building's rules (the keeper), redesign a window, open the
Lake, revert a checkpoint or type into a terminal. Those need the room, the keyboard and the
person's full attention; a mistap on a bus must not demolish a building or send `rm -rf` to an
ork. A question's answer is the one keystroke a phone may send to a session, and only one the
question offers (`Muster.answer` refuses any other).

## 2. How it connects

The phone is one more face over the same host. It speaks the protocol the page already speaks
(`gui/server.py`): a snapshot when the town changes and `{"t": "cmd", "id", "name", "args"}`
answered by a `reply`. Nothing in `core/`, `realm/` or `design/` learns that phones exist.

```
phone ──TLS── phone listener (stage 1) ──┐
                                         ├── Host (gui/host.py) ── Town, bus, services
page  ──127.0.0.1── Server /ws ──────────┘
```

- **One host, one owner.** The phone reaches the town that `orkcraft gui` (or, later, the daemon of
  [gui-migration.md](gui-migration.md) §1) runs. A phone never runs a town of its own, so the
  one-owner rule holds: the same Halt All, the same budget, the same Town Scroll.
- **The page's socket stays as it is.** It listens on 127.0.0.1 only, takes the run's token from
  its address and an `Origin` of the server, and sends everything (the whole snapshot, `detail`,
  the terminals' binary frames). A phone needs none of the big parts and cannot send that Origin.
- **A listener for phones (stage 1)** beside it, on the same loop (`Server.run`): its own port on
  the LAN interface, TLS, a device token in `Authorization: Bearer`, no Origin. It sends compact
  snapshots only (`mobile.compact`, at most every few seconds, only when `rev` changed) and passes
  a command to `host.command` only when `mobile.allowed(host, name, args)` says so. It never sends
  `state`, `detail` or terminal frames, and takes no `watch`, `term.attach` or `term.replay`.

### Pairing

1. On the desktop, Settings → Pair a phone shows a QR code: the listener's address
   (`https://<lan ip>:<port>`), the certificate's SHA-256 fingerprint and a one-time pairing code
   (32 random bytes, good for 2 minutes, once).
2. The phone scans it, calls `GET /api/version` to check it speaks this `api`, then trades the
   pairing code for a **device token** (`POST /api/pair`, the code and a device name).
3. The host keeps only the token's hash, the device's name and when it was last seen, in the
   machine's settings (`settings.path()`, `$XDG_CONFIG_HOME/orkcraft/settings.json`), never in the
   Town Scroll: the scroll is committed to the project's git. Settings → Phones lists them, and
   Forget revokes one at once (its open socket is closed).

The page's own token (`Server.token`, new each run) is never shown to a phone: it would die with
the run, and it opens the full socket.

As built (stage 1): the QR code's text is `orkcraft://pair?v=1&addr=<address>&fp=<fingerprint, hex>&code=<code>`.
Before it pairs, the phone's `GET /api/version` shows the code it scanned as its Bearer token; a wrong
one counts as a pairing attempt. `POST /api/pair` takes only `Content-Type: application/json` and at
most 4 KB (a browser's simple POST cannot reach it), and answers `{"id", "token", "name"}` once. The
listener listens only while a phone is paired or a code is shown, on the LAN address the machine
reaches out by (`ORKCRAFT_PHONE_HOST` overrides it), and keeps its port in the settings (`phone_port`)
so a paired phone finds it next run. Only `settings.save_phones` writes the paired phones: a town that
loaded the settings before a phone was forgotten never brings it back when it saves its own.

### TLS

The listener makes a self-signed certificate on its first start (kept beside the settings, `0600`)
and the QR code carries its fingerprint, so the phone pins it instead of trusting a CA. On
127.0.0.1 the page keeps plain HTTP: nothing leaves the machine.

### Reaching a machine that is not on the same Wi-Fi (stage 3)

LAN pairing works at home and in the office; on the road the phone needs a relay. Two ways, in
order:

1. **The operator's own tunnel.** Tailscale (the phone joins the tailnet and reaches the LAN
   address as is) or the tunnels the Watchtower will supervise anyway
   ([watchtower-automation.md](watchtower-automation.md) §2 C). No server of ours.
2. **A relay.** The host dials out to a relay over a WebSocket, the phone dials in, and the relay
   only pipes bytes between the two. The phone and the host speak TLS end to end inside it (the
   pinned certificate), so the relay sees neither the town nor the token. It also carries pushes
   (§5).

## 3. The API, v1

Versioned in two numbers: `server.PROTOCOL` (the socket's messages) and `mobile.API` (what a phone
may read and send). A change that breaks a client raises one; a field added does not. The
handshake says both:

```
GET /api/version      (the token as ?t= or Authorization: Bearer; 403 without it)
← {"name": "orkcraft", "version": "0.1.0", "protocol": 1, "api": 1}
```

The commands a phone may send are a closed list, `mobile.COMMANDS`; `tests/test_mobile.py` checks
that each one is a command the host has, and that building, typing into a terminal and moving a hut
are not on it.

| Command | Args | Result | Already there |
|---|---|---|---|
| `mobile.hello` | — | name, version, `api`, the commands and the acts by type | new (stage 0) |
| `mobile.snapshot` | `since`: a `rev` the phone has | the compact snapshot, or `{"v", "rev", "same": true}` | new (stage 0) |
| `orders.answer` | `id`, `key` | `true`; an error when it was answered already or `key` is not its answer | yes |
| `orders.follow` | `id` | `true`: the Elders' advice sent as the person's answer | yes |
| `halt` | — | how many it stopped | yes |
| `act` | `id`, `act`, `args` | as the act; only `pit`: `drop`, `drop_file` and `town_hall`: `ask` | yes |
| `mobile.chat` | `limit` (at most 20) | the hall's last messages: `who`, `text` (plain), `ts`, `error`, `offer` | new (stage 2) |
| `place.report` | `id`, `place`, `change`, `at` | `{"outcome"}`: the phone came to a place or left it ([phone-places.md](phone-places.md)); also `POST /api/place` | new (places, stage 1) |

The Warchief's answer arrives in the Town Hall's `detail` (`chat`), which the phone listener does
not send; stage 2 adds `mobile.chat` (the last messages of the hall's chat, Markdown as plain text)
so the phone reads its answer.

### The compact snapshot

`mobile.compact(host.snapshot())`: derived from the page's snapshot, never from the town, so the
two never disagree. A town of one building is 0.5 KB against the page's 9 KB: no roads, huts, orkspaces, garrisons, cards, the
Lake's tabs, jobs or the glossary.

```json
{
  "v": 1, "rev": "3f1c0a9be2d47c15",
  "project": "orkcraft", "demo": false, "look": "office",
  "resources": {"quota": "Quota", "gold": "Spend", "lumber": "Context", "supply": "Agents"},
  "hud": {"gold": "$1.20 / $5.00", "gold_level": "ok", "show_gold": true, "quota": "…",
          "quota_level": "ok", "agents_working": 2, "agents": 5, "alerts": 1, "quiet": false,
          "hour_plain": "…"},
  "alerts": [{"id": "term:new:claude:1", "title": "Proceed?", "who": "…", "building": "barracks",
              "options": [["1", "Yes"], ["2", "No"]], "context": ["…", "…", "…"],
              "advice": null, "waited": 42.0}],
  "buildings": [{"id": "town_hall", "title": "Town Hall", "title_plain": "Control panel",
                 "type": "town_hall", "state": "", "alert": null}],
  "sessions_running": 1
}
```

- `rev` is a hash of the rest: the same town, the same `rev`. A hut dragged on the desktop does not
  change it; a question that came does.
- A question keeps its last three lines (`mobile.CONTEXT_LINES`), not twelve, and loses its
  terminal `ref`.

## 4. Office and Camp on the phone

The phone follows the snapshot's `look` (`camp` or `office`, the person's: portrait.md §3), as the page
does, and its `portrait` (the monogram and Do not disturb, which a phone may set with `you.dnd`); the
same rules hold ([CLAUDE.md](../../CLAUDE.md)): every text a person reads says **ork** / **orks** and
**orkestration**, and each concept its one word of `lexicon.TERMS`, in either look. The host already
sends what may carry emoji twice, as it is and `_plain` (`title_plain`, `hour_plain`; the toasts'
`message_plain`), and `resources` names the HUD's four in the look's words. The app's own labels
(Answers, Drop file here, Stop all, Lead agent) come from the glossary: `mobile.hello` will carry
`lexicon.glossary()` at stage 1, so an app built once says words added later. What people or
agents wrote (a question's lines, the Warchief's answer, a dropped file's name) keeps its words.

## 5. Push notifications

A phone in a pocket has no socket open, so what must wake it goes through the platform's push (APNs
on iOS, FCM on Android).

- **What wakes it** is `mobile.news(before, after)` between two compact snapshots: a question that
  came (each once, by its id), spend or a quota that crossed into `warn` or `over` (the levels of
  `telemetry.level`). Nothing on the first look: pairing wakes nobody for what already waited.
- **Why snapshots and not only the bus.** The questions are not a bus event: `Host.tick` reads
  the sessions' screens every second (`Host.refresh_roster` → `Muster.rebuild`) and the questions
  come out of that. Comparing snapshots catches them all, whatever found them. The bus adds what a
  snapshot does not keep: a `toast` of severity `error`, and `session` with `state: "exited"` (an
  ork that went home, with its report) — a notifier subscribes to them with
  `town.bus.subscribe(bus.ANY, …)`, as `Host._event` does.
- **The notifier** (`gui/notify.py`, stage 2) runs on the host's loop: after each flush it compacts
  the snapshot, asks `news`, and for each device with a push token sends one short line in the
  device's look ("Grunt asks: Proceed?" / "Worker asks: Proceed?"). The text of the push carries
  no code, no file contents and no secrets: only the title and who asks. Tapping it opens the
  question in the app, which fetches it through the socket.
- **Quiet hours** (`schedule.quiet_now`): pushes keep coming, unless the machine's autonomy lets the
  Elders answer (🕰 on the clock or ⛓️‍💥 unchained); then only an `over` spend wakes the phone. A device can mute each
  kind.
- **Where it is sent from.** APNs and FCM need the app's own credentials, which a laptop does not
  hold, so a push goes through the relay (§2): the host sends it the device's push token and the
  line, end to end encrypted to the device's key when the platform allows (a notification service
  extension decrypts it on iOS). Until the relay, a phone on the LAN gets its notices only while
  the app is open (a local notification from the socket).

## 6. Offline and reconnect

- The app keeps the last compact snapshot and shows it greyed, with "as of 12:41", while it cannot
  reach the town. Nothing it shows is acted on from the cache: every button sends a command and
  waits for its `reply`.
- On reconnect it calls `mobile.snapshot` with `since` set to the `rev` it kept; an unchanged town
  answers `{"same": true}` in a few bytes. Then it waits for pushes on the socket as the page does.
- **Answers are idempotent by the question's id.** An answer sent twice, or for a question already
  answered at the desk, gets `That question was answered already` (`Host._answer`); the app says
  so and drops it. It never queues answers while offline: an ork's question may be stale by the time
  the phone is back.
- A drop into The Pit taken while offline is queued on the phone (it is the person's own content,
  never stale) and sent once with an id, so a retry after a lost `reply` does not drop it twice
  (stage 2: `drop` takes an optional client id the worker remembers for an hour).
- Back-off on reconnect: 1, 2, 4 … 60 s, and at once when the phone's network changes.

## 7. Security

- **The phone can do less than the page.** The listener checks every command against
  `mobile.allowed`; the page's socket is not reachable from the LAN at all (127.0.0.1, the run's
  token, its Origin).
- **Tokens.** The pairing code is one-time and short-lived; a device token is 32 random bytes,
  kept in the phone's keychain / keystore and only as a hash on the host, compared with
  `secrets.compare_digest` (as `Server._http` does the page's). Forget revokes it at once.
- **TLS with a pinned certificate** on the LAN; end to end inside the relay, which never holds a
  key that opens the town.
- **Halt All from a phone** is allowed on purpose (stopping is always safe) and asks once to
  confirm; it says on the desktop which device stopped it (a toast).
- **Files** from the phone go through the Pit's own limits (`views.pit.FILE_LIMIT`, 5 MB; the
  socket's 8 MB frame) and land where a dropped file always lands; a phone names no path. A text
  the desktop drops is read as paths when it names files (they are copied in); a phone's never is
  (`mobile.guard` sets `paths: false` on its `drop`), so a phone cannot pull a file of the machine into
  the project.
- **What a phone reads** is the compact snapshot: no Town Scroll, no file contents, no terminal
  output beyond a question's last three lines. Stage 2's `mobile.chat` is the Warchief's answers,
  which already avoid secrets as the hall's chat does.
- **Rate limits** on the listener: pairing attempts (5 a minute, then locked until the desktop
  shows a new code), commands (a few per second per device).
- **Spend.** A Warchief question costs a model call; it counts against the same budget
  (`Town.budget_ok`), and a spent budget refuses it on the phone as at the desk.

## 8. Not decided

1. Native apps (Swift and Kotlin) or one cross-platform app. The protocol does not care; the push
   extension and the share sheet favour native. Meanwhile a web app over Tailscale stands in (§10): it
   tells what a phone is used for before an app is written for it.
2. Who runs the relay: the project (a small service), or only the operator's own tunnel.
3. Whether the daemon ([gui-migration.md](gui-migration.md) §1) must come first, so a phone can
   reach a town whose window is closed; until then the town is `orkcraft gui --browser` left
   running.

## 9. Stages

| stage | scope | state |
|---|---|---|
| 0 | the surface, inside the host: `mobile.API`, `server.PROTOCOL`, `GET /api/version` (the run's token), `mobile.hello`, `mobile.snapshot` (compact, with `rev` / `since`), `mobile.COMMANDS` and `mobile.allowed`, `mobile.news`, the `war_raven` term; tests. No phone talks to it yet; the page could | done |
| 1 | LAN: the phone listener (TLS, a device token, `mobile.allowed`, compact snapshots only), pairing by QR code, Settings → Phones (list, forget), the glossary in `mobile.hello`; a first app: glance, Orders, Halt All, spend and quotas | done on the host; the app waits on §8.1 (`tools/phone.py` stands in) |
| 2 | the rest of v1: drop into The Pit (share sheet, offline queue, the drop's client id), Ask the Warchief with `mobile.chat`, the notifier (`gui/notify.py`) with local notifications while the app is open | done on the host (the client id, `mobile.chat`, the notifier's `news`); the share sheet and the offline queue are the app's |
| 3 | away from home: the relay (end to end TLS, push through APNs / FCM), or the operator's tunnel; per-kind mute and quiet hours | — |
| 4 | when the daemon comes: the phone reaches a town with no window open; a town picker for several projects | — |

## 10. The prototype: the town in the phone's browser (PWA)

No app store and no build: the phone listener serves a small web app itself (`gui/pwa.py`, its files in
`gui/static/pwa/`, plain JavaScript), and the phone adds it to its Home Screen. It does what stage 1 and 2
give a phone: the glance (spend, quotas, the buildings, what asks first), Answers with the Advisor's
suggestion, Stop all (two taps), the Warchief and Drop file here (a text, a link or a file up to 5 MB; on
Android also from the share sheet, through the manifest's `share_target`).

**Only over Tailscale.** A browser cannot pin a certificate, and a service worker or a Home Screen app needs
one it trusts. The tailnet's `*.ts.net` certificate (`tailscale cert`, phone-places.md §3) is that one, so
the app is offered only on the tailnet with HTTPS certificates on. The LAN listener serves the same files,
for a person who accepts the certificate warning on purpose; the desktop offers no link to them.

**Setting up from one QR code.** No link can join a phone to a tailnet: Tailscale's phone apps take no key
from outside (auth keys are for its command line; on iOS only a managed device logs in by one). So the
desktop leads the person through it, on the same QR code (`phones.tailnet`, Settings → Phones and the
portrait's menu), from `tailscale status`:

1. While no phone of the person's is online in the tailnet, the code is Tailscale's download, with the
   account to log in as (the one this machine is logged in with).
2. Once one is, the code turns by itself into the app's link, `https://<name>.ts.net:<port>/app/#pair=<code>`.
   The phone's camera opens it in the browser, and the page pairs at once (`/api/version`, `POST /api/pair`,
   as any phone) with the phone's kind as its name. The code rides in the fragment, which the browser never
   sends, and is wiped from the address when the page reads it.

**The socket from a browser.** A browser cannot set `Authorization` on a WebSocket, so it names the token as
a subprotocol: `Sec-WebSocket-Protocol: orkcraft.v1, bearer.<token>`; the listener answers `orkcraft.v1`
and never echoes the token. Everything after it is the phone's: `mobile.allowed`, the rate limit, Forget.

**iOS keeps a Home Screen app's storage apart from Safari's.** Paired in Safari, the page names the token
in its manifest's `start_url` (`manifest.webmanifest?k=<token>`, a token's characters only) and in its own
fragment, so the app the person adds opens with it once, keeps it and wipes it from its address. Until the
app is added that address holds the phone's key, and the page says so.

**What it cannot do yet.** No push while it is closed: news comes while it is open (`notify.py`), with a
system notification when the page is in the background and the person allowed it. iOS has no share
target for a web app. These two are what §8.1 weighs for a native app; the relay of stage 3 brings
Web Push too.

Not tried on a real phone yet: the iOS hand-over of the token, and the Android install prompt.

