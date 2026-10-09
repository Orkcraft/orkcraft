# The usage proxy

A Cloudflare Worker between Orkcraft and Amplitude (usage stats, [docs/usage-stats.md](../../docs/usage-stats.md)) and Sentry (crash reports, [docs/crash-reports.md](../../docs/crash-reports.md)).

```
orkcraft ──POST /v1/events──▶ Worker ──▶ Amplitude HTTP API v2 (US)
            User-Agent: orkcraft/x.y   · holds AMPLITUDE_API_KEY (a Worker secret)
                                       · keeps only the listed events and properties
                                       · at most 30 batches a minute per install
                                       · drops the person's IP address
```

The repository holds only the proxy's address (`orkcraft/core/usage.py` `ENDPOINT`), never a key.
Whoever runs the proxy can change the analytics behind it without a release of Orkcraft.

## Set it up

1. **Amplitude.** Create a project (US data centre, `app.amplitude.com`; for one in the EU data centre,
   `analytics.eu.amplitude.com`, set `AMPLITUDE_REGION = "eu"` in `wrangler.toml`). Project settings →
   General: copy the **API Key**.
   The **Secret Key** is not needed and stays in Amplitude. In the project's settings, turn off IP
   address and location tracking if offered: the only address Amplitude ever sees is Cloudflare's.
2. **Cloudflare.** An account (the free plan is enough), and Node 20+ for `wrangler`.
3. **Deploy** from this folder:

   ```bash
   cd tools/usage-worker
   npx wrangler login
   npx wrangler secret put AMPLITUDE_API_KEY     # paste the API Key: it is stored encrypted in Cloudflare
   npx wrangler deploy                           # → https://orkcraft-usage.<account>.workers.dev
   ```

   For a domain of your own, uncomment `routes` in `wrangler.toml` (the domain must be on Cloudflare).
4. **Check it** with an event of your own:

   ```bash
   curl -i https://orkcraft-usage.<account>.workers.dev/v1/events \
     -H 'User-Agent: orkcraft/0.1.0' -H 'Content-Type: application/json' \
     -d '{"install_id":"0123456789abcdef0123456789abcdef","session_id":1,"app_version":"0.1.0","os":"linux","python":"3.12","events":[{"event":"road_laid","time":0,"props":{}}]}'
   # HTTP/2 204; the event shows in Amplitude → User lookup → device 0123…cdef within a minute
   ```

   Nothing in Amplitude?
   - `npx wrangler secret list` must show `"name": "AMPLITUDE_API_KEY"`. A secret named after the key
     itself means `secret put` got the key where the name goes: delete it and put it again.
   - Send one event to Amplitude itself, without the Worker: `curl -i https://api2.amplitude.com/2/httpapi
     -H 'Content-Type: application/json' -d '{"api_key":"…","events":[{"device_id":"0123456789abcdef0123456789abcdef","event_type":"road_laid"}]}'`.
     `"invalid api_key"` means a wrong key, or a project in the EU data centre (`api.eu.amplitude.com`,
     `AMPLITUDE_REGION = "eu"`).
   - `npx wrangler tail --format pretty` shows the Worker's requests live while you send one.
   - The Worker's answer may carry `x-amplitude-status` (Amplitude's own answer), but Cloudflare's edge
     does not always pass it on: its absence proves nothing.
   - A change to `wrangler.toml` counts only after `npx wrangler deploy`.

5. **Point Orkcraft at it**: set `ENDPOINT = "https://…/v1/events"` in `orkcraft/core/usage.py` and
   release. Until then, try it on your own machine with
   `ORKCRAFT_USAGE_URL=https://…/v1/events orkcraft usage on && orkcraft`.

## Change the events

The list lives twice, and both must change together: `EVENTS` in `orkcraft/core/usage.py` and
`EVENTS` in `worker.js` (`tests/test_usage.py` checks that they name the same events, building types
and deeds). Add the event to [docs/usage-stats.md](../../docs/usage-stats.md) as well, then
`npx wrangler deploy` before the release that sends it: an event the Worker does not know is dropped.

## Crash reports → Sentry

`POST /v1/crash` takes the app's crash reports and run sessions ([docs/crash-reports.md](../../docs/crash-reports.md)),
checks each field again (file paths only of Orkcraft, a library or `<other>`; identifiers only) and
sends them to Sentry as one envelope. Without the `SENTRY_DSN` secret it answers 204 and drops them.

1. **Sentry.** An account (the free Developer plan is enough; open-source projects can ask for the
   sponsored plan). Create a project, platform **Python**. Project settings → Client Keys (DSN): copy
   the DSN, `https://<key>@o….ingest.us.sentry.io/<project>`.
2. In the project's **Security & Privacy**: turn on *Prevent Storing of IP Addresses* and keep
   *Data Scrubber* on. Sentry sees only the Worker's address anyway.
3. Put the DSN in the Worker and deploy:

   ```bash
   cd tools/usage-worker
   npx wrangler secret put SENTRY_DSN       # paste the DSN
   npx wrangler deploy
   ```
4. **Check it** with a report of your own (it shows in Sentry → Issues within a minute):

   ```bash
   curl -i https://orkcraft-usage.<account>.workers.dev/v1/crash \
     -H 'User-Agent: orkcraft/0.0.0' -H 'Content-Type: application/json' \
     -d '{"install_id":"0123456789abcdef0123456789abcdef","app_version":"0.0.0","os":"linux","python":"3.12","items":[{"type":"event","event_id":"0123456789abcdef0123456789abcdef","where":"command","handled":true,"exceptions":[{"type":"TestError","value":"a test from curl","frames":[{"file":"orkcraft/cli.py","function":"main","line":1,"in_app":true}]}]}]}'
   # HTTP/2 204; x-sentry-status: 200 when Sentry took it
   ```

   Or from the app: `ORKCRAFT_USAGE_DEBUG=1` prints what would be sent; with stats on, an error in
   the window's console (`throw new Error("test")`) is reported.

Releases are `orkcraft@<version>`, so Sentry → Releases shows the crash-free sessions of each
version. A git checkout reports as environment `checkout`, an installed copy as `production`.

## The installer

The Worker also serves [`install.sh`](../../install.sh) at `GET /install.sh`, read from `main` and
cached 5 minutes, so the install line can be `curl -fsSL https://orkcraft-usage.<account>.workers.dev/install.sh | sh`
(and later a domain of your own, through `routes`). Cloudflare's dashboard (Workers → this Worker →
Metrics) counts its requests: how many fetched the installer, with no data about who. The installer's
events (`install_started`, `install_step`, `install_finished`, [docs/install.md](../../docs/install.md))
reach Amplitude only once a Worker that knows them is deployed: `npx wrangler deploy` after a change
to `worker.js`.

## Rotate the key

In Amplitude, create a new API key, then `npx wrangler secret put AMPLITUDE_API_KEY` again. No release of
Orkcraft is needed.
