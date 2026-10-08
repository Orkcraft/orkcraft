# Design — places: the phone tells the town where you are

Status: written 2026-10-08. Stage 1 (§8) is built: the rules and the history (`realm/places.py`), the
Watchtower's places (`core/workers/watchtower_places.py`, its Sources & intent: `buildings/watchtower_places.js`),
`POST /api/place` and `place.report` (`gui/phones.py`, `gui/places.py`), Tailscale (`gui/tailnet.py`) and the
Shortcuts / Tasker recipe (Settings → Phones); `tests/test_places.py`. Not built: the spend ceiling of §6
(the town's budget and the Agent pool's own `budget_usd` hold meanwhile) and stages 2–3.
Builds on the phone ([mobile.md](mobile.md): the listener, pairing, the device token), the
External listeners (the Watchtower: [watchtower-automation.md](watchtower-automation.md),
[watchtower-quick-add.md](watchtower-quick-add.md)), the roads ([roads-and-orcs.md](roads-and-orcs.md))
and the Night round ([night-round.md](night-round.md)). Wording: ork, orkestration (CLAUDE.md).

## 1. What and why

A **place** is a named area — *home*, *office*, *gym* — that a paired phone watches. When the phone
comes into a place or leaves it, the town hears one event and sends it down the roads, like any other
signal. The first use is the Agent pool's (Barracks'): *back home* lets its steward start the evening's
work; the Calendar, the Task board and the Gramophone (discussed apart) may listen later.

A schedule (the Watchtower's Schedule source) covers a fixed day already. A place is worth its
code where the day is not fixed: the work starts when you are home, not at 19:00.

### Not a building

Places are a **source of the External listeners**, not a building of their own:

- The Watchtower already turns what happens outside into signals, keeps them once (dedupe), keeps
  their history and sends them down roads with filters. A place is one more outside thing.
- A building for one sensor of a phone would add a hut to a town that is getting calmer
  ([calm-town.md](calm-town.md)).
- What is new is only the direction: the phone **pushes** the event; no source of the tower looks.

## 2. Principles

1. **Only you and your town.** The place is worked out on the phone. Coordinates never leave it: the
   town knows a place's name, never where it is. No server of ours, no third-party SDK in the app.
2. **Nothing about a place reaches a model.** A cart from a place tells a steward *that* it may start,
   never where you are or when you came.
3. **The building decides how freely.** Each place has its Autonomy and a spend ceiling, set in the
   Watchtower; the town's budget holds above both.
4. **Kept a short while, outside git.** The history of places is kept 7 days by default (configurable),
   in the machine's settings, never in the Project file or the camp's git.

## 3. How the event travels

```
phone (works out the place) ──HTTPS over the tailnet── phone listener ── Watchtower: Places ── roads
                                                         (home computer)    watch.place
```

### The town lives at home; the phone reaches it through Tailscale

The town runs on a computer at home (`orkcraft gui --browser` left running, later the daemon). On the
road the phone reaches it through **the operator's own Tailscale** — this settles mobile.md §8.2 for
places: no relay.

- **Found, not embedded.** The town looks for a running Tailscale on its machine (`tailscale status
  --json`) and, when there is one, listens on its tailnet address too, and puts that address in the
  pairing QR code beside the LAN one. Settings → Phones says when Tailscale is missing, with the
  link to install it on both machines.
- **A real certificate.** `tailscale cert` gives the machine's `*.ts.net` name a certificate a phone
  trusts as it is. The listener serves it on the tailnet address, so a client that cannot pin a
  certificate (Shortcuts, Tasker) can still speak HTTPS to the town. On the LAN the pinned
  self-signed certificate stays.
- **Never Funnel.** Funnel makes the address public; places need the tailnet only.
- **Said plainly** in Settings → Phones: the traffic is encrypted end to end, and Tailscale's
  coordination server knows which of your devices exist, not what they say.
- **One VPN at a time on iOS.** Tailscale is the phone's VPN; a work VPN would fight it. Not a case
  today; said in the setup when it is.

### The call

`POST /api/place` on the phone listener, the device token as `Authorization: Bearer`, at most 1 KB:

```json
{"id": "b1c4…", "place": "home", "change": "arrived", "at": "2026-10-08T19:42:10+02:00"}
```

- `place` must be one of the places the town knows (§5); `change` is `arrived` or `left`; `id` is the
  phone's, so a retry is heard once.
- It is a command of `mobile.COMMANDS` (`place.report`) for the app, and the same thing as a plain
  POST for Shortcuts and Tasker, which speak no socket.
- Rate limit: a few a minute per device; more is refused and shown on the device's line.

### Late events

The phone keeps an event it could not send (the home computer asleep, no network) and sends it later
with its own `at`. An event older than its **shelf life** (2 h by default, per place) is written to the
history but sends no cart: *left home* three hours late is not news.

## 4. The event: `watch.place`

The Places source of a Watchtower emits one event, `watch.place`:

| field | |
|---|---|
| `place` | the place's name: `home` |
| `change` | `arrived` · `left` |
| `at` | when the phone saw it (not when the town heard it) |
| `device` | the paired phone's name |

A road filters it as any other (`match`: `place=home, change=arrived`). The Lookout's intent filter
never sees it (no model call). The cart's text, the one a steward's ork reads, carries neither the place
nor the time: it says what the road was made for (*you may start the evening's work*), written when the
road is laid.

## 5. Places: named in the building, drawn on the phone

- **Names live in the Watchtower** (its Places source), so roads can name them. A place can be made
  in the building (a name) or on the phone (a name and its circle); each side shows the other's.
  The tower keeps a line per place, as it keeps its feeds: `home autonomy=clock shelf=2 say=You may start
  the evening's work.` (`config.places`, at most ten; `places_keep_days` beside it).
- **Circles live on the phone only:** the centre and the radius (150 m at least) are drawn on a map in
  the app and never sent. A place named on the desktop shows on the phone as *not on the map yet*.
- The app gets the names through `mobile.hello` (and a change through the snapshot's `rev`).

### Against false alarms

- A radius of 150–200 m at least; GPS drifts at the edge.
- `left` counts after a few minutes outside (5 by default); coming back within them cancels it.
- Later: the home Wi-Fi as a second sign (§8, stage 3).

## 6. In the building

The Watchtower's Places source, per place:

| setting | default | |
|---|---|---|
| **Autonomy** | Propose only | Propose only: the event asks in Answers before a road's work starts. Apply if unanswered: it starts after a while unless refused. Apply at once: it starts |
| **Spend ceiling** | $1 per event | what the work an event starts may spend; the town's budget holds above it. *Not built yet:* a cart carries no budget to the building that takes it; meanwhile the Agent pool's own `budget_usd` and the town's budget hold |
| **Shelf life** | 2 h | older events are kept but send no cart |
| **History** | 7 days | how long the events are kept on this machine; *Clear* empties it |

Forgetting a phone (Settings → Phones → Forget) deletes its events too. The history is a file per project
beside the machine's settings (`<settings folder>/places/<project>.jsonl`, 0600), never under the project.

**Roads.** A place's cart takes the route `<place>-<change>`, so a road laid on `watch.place#home-arrived`
takes only that; each arrived and left no road takes yet is a stub on the map to pull a road from (the
Watchtower's `loose_ends`). A report no road takes is kept as *no road* and sends nothing.

### The Agent pool's steward decides

The first road goes from Places to the Agent pool: `watch.place` `home` `arrived` → the pool's steward.
The steward decides what to start (no fixed list), within the place's Autonomy and ceiling. It may
simply start the Night round's work early; it never learns the place or the time.

## 7. The phone side

### Stage 1: no app — Shortcuts and Tasker

Until the app exists, Settings → Phones shows a ready recipe:

- **iOS Shortcuts:** an Arrive / Leave automation per place that runs *Get contents of URL* —
  `POST https://<machine>.ts.net:<port>/api/place` with the device token. *(check: whether a location
  automation runs without a tap on today's iOS.)*
- **Android Tasker** (or MacroDroid): a Location profile, an HTTP Request action, the same call.

The token for a recipe is a device token like the app's (one per paired recipe), revoked by Forget:
**Places through Shortcuts or Tasker** in Settings → Phones makes one (`phones.recipe`) and shows it once, with
the URL, the headers and the body. Shortcuts trusts only a real certificate, so the recipe needs Tailscale with
HTTPS certificates on; on the LAN's self-signed one the panel says so.

### Stage 2: the app (Capacitor)

One app for iOS and Android, wrapped in Capacitor — this settles mobile.md §8.1. Places need a native
plugin of our own, small and with no third-party SDK:

- **iOS:** region monitoring (`CLLocationManager`, at most 20 regions), which wakes the app even when
  it was closed.
- **Android:** the Geofencing API (`GeofencingClient`), with a dwell for `left`.
- Both are cheap on the battery (cell and Wi-Fi, no steady GPS). The app keeps no track, only the last
  change per place, and the queue of events not yet sent.
- **The stores:** both ask for background location (*Always*). Google Play wants a declaration and a
  video of the feature; the App Store a reason in plain words. Weeks, not days: planned in.

## 8. Stages

| stage | scope | done when |
|---|---|---|
| 1 ✓ | Tailscale found and used (the tailnet address in the QR, `tailscale cert`); `POST /api/place`; the Places source with its settings (§6) and `watch.place`; the history outside git; the Shortcuts / Tasker recipe | *back home* on a phone starts the Agent pool's steward, asked first in Answers |
| 2 | the app's own geofence plugin (iOS, Android); places drawn on the phone; the queue and shelf life on the phone | the same without Shortcuts or Tasker, on both phones |
| 3 | more signs of the phone: the home Wi-Fi joined or left, a car's Bluetooth / CarPlay (*in the car*) | the Gramophone can make an episode for the road |

## 9. Risks, said plainly

- **Privacy.** The history of places is a history of where you were. It stays on the home computer,
  7 days, never in git, never to a model.
- **Money.** A place starts paid work. Propose only and a ceiling by default; a forged event needs a
  device token, and a token is revoked by Forget.
- **False alarms.** GPS at the edge, a late iOS wake-up (minutes). The dwell and the shelf life keep a
  wrong event from doing harm.
- **Battery.** Native geofences only; no steady GPS.

## 10. Not decided

1. The Wi-Fi and the car as signs of their own (stage 3): the same `watch.place`, or a `watch.phone`
   event beside it?
2. Whether Apply if unanswered may wait for an answer on the phone (a push needs the relay, which
   places do without), or only in Answers on the desktop.
3. Places of several phones in one town (two people at home): one event per phone, or *first in /
   last out*?
