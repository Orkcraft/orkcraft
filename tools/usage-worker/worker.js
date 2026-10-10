// Orkcraft's usage proxy (docs/usage-stats.md): a Cloudflare Worker between the app and Amplitude.
// It holds the Amplitude key (a secret of the Worker, never in the repository), keeps only the events
// and properties listed below — the same list as orkcraft/core/usage.py `EVENTS` — limits how often
// one install may send, and passes the rest on. The person's IP address stays here: Amplitude only
// sees the Worker's request.
//
//   POST /v1/events  {install_id, session_id, app_version, os, python, events: [{event, time, props}]}
//   → 204 (kept or dropped quietly) · 400 (not a batch) · 413 (too big) · 429 (too often)
//   X-Amplitude-Status on a 204 that reached Amplitude: its own answer (200 ok, 400 a bad key or batch,
//   401 a key of the other data centre), so `curl -i` shows why nothing arrives.

const COUNTS = ["0", "1", "2-5", "6-10", "11+"];
const MINUTES = ["<5", "5-30", "30-120", "120+"];
const TOOLS = ["claude", "agy", "codex", "hermes", "pi", "cursor"];
const TYPES = ["pit", "watchtower", "signpost", "mill", "horn", "fields", "barracks", "council", "war_drum",
  "forest", "scrolls", "mine", "gramophone", "lab", "lake", "forge", "loot", "crag", "catapult", "town_hall", "workshop", "custom"];
const DEEDS = ["town", "road", "reference", "week", "learned", "mature", "trusted", "night"];

const oneOf = (list) => (v) => list.includes(v);
const EVENTS = {
  app_opened: { face: oneOf(["gui", "tui"]),
    tools: (v) => Array.isArray(v) && v.length <= TOOLS.length && v.every((t) => TOOLS.includes(t)),
    buildings: oneOf(COUNTS), roads: oneOf(COUNTS) },
  app_closed: { minutes: oneOf(MINUTES) },
  building_built: { type: oneOf(TYPES) },
  building_demolished: {},
  road_laid: {},
  session_opened: { harness: oneOf(TOOLS) },
  deed_earned: { deed: oneOf(DEEDS) },
  stage_reached: { stage: oneOf([1, 2, 3, 4]) },
  autonomy_set: { level: oneOf(["chains", "clock", "free"]) },
  halted: {},
};

const MAX_BODY = 64 * 1024;
const MAX_EVENTS = 100;
const HEX32 = /^[0-9a-f]{32}$/;
const VERSION = /^[0-9A-Za-z.+-]{1,32}$/;
const OS = ["darwin", "linux", "windows", "unknown"];
const AMPLITUDE = { eu: "https://api.eu.amplitude.com/2/httpapi", us: "https://api2.amplitude.com/2/httpapi" };

function clean(e, now) {
  if (!e || typeof e !== "object" || !Object.hasOwn(EVENTS, e.event)) return null;
  const allowed = EVENTS[e.event];
  const props = {};
  for (const [k, v] of Object.entries(e.props || {})) if (Object.hasOwn(allowed, k) && allowed[k](v)) props[k] = v;
  // A time from the last week, else now: a stuck queue or a wrong clock never rewrites history.
  const time = Number.isInteger(e.time) && e.time > now - 7 * 864e5 && e.time < now + 3e5 ? e.time : now;
  return { event: e.event, time, props };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/v1/events") return new Response(null, { status: 404 });
    if (!(request.headers.get("user-agent") || "").startsWith("orkcraft/")) return new Response(null, { status: 403 });
    if (Number(request.headers.get("content-length") || 0) > MAX_BODY) return new Response(null, { status: 413 });
    const text = await request.text();
    if (text.length > MAX_BODY) return new Response(null, { status: 413 });
    let body;
    try { body = JSON.parse(text); } catch { return new Response(null, { status: 400 }); }
    if (!body || !HEX32.test(body.install_id) || !Array.isArray(body.events)) return new Response(null, { status: 400 });

    if (env.LIMITER) {                        // the Rate Limiting binding of wrangler.toml, per install
      const { success } = await env.LIMITER.limit({ key: body.install_id });
      if (!success) return new Response(null, { status: 429 });
    }

    const now = Date.now();
    const sessionId = Number.isInteger(body.session_id) && body.session_id > 0 ? body.session_id : -1;
    const appVersion = VERSION.test(body.app_version || "") ? body.app_version : "unknown";
    const os = OS.includes(body.os) ? body.os : "unknown";
    const python = /^3\.\d{1,2}$/.test(body.python || "") ? body.python : "unknown";
    const country = env.SEND_COUNTRY === "true" && request.cf && request.cf.country ? request.cf.country : undefined;
    const events = body.events.slice(0, MAX_EVENTS).map((e) => clean(e, now)).filter(Boolean).map((e) => ({
      device_id: body.install_id,
      event_type: e.event,
      time: e.time,
      session_id: sessionId,
      event_properties: e.props,
      user_properties: { python },
      app_version: appVersion,
      os_name: os,
      platform: "Desktop",
      ...(country ? { country } : {}),
      ip: "$remote",                          // the request's address, which is the Worker's: never the person's
    }));
    if (!events.length) return new Response(null, { status: 204 });

    const res = await fetch(AMPLITUDE[env.AMPLITUDE_REGION] || AMPLITUDE.us, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: env.AMPLITUDE_API_KEY, events }),
    });
    // The app keeps a batch and tries again only when it is worth it: Amplitude down or busy.
    if (res.status === 429 || res.status >= 500) return new Response(null, { status: 503 });
    // Anything else is final for the app; the header says what Amplitude thought of the batch.
    return new Response(null, { status: 204, headers: { "X-Amplitude-Status": String(res.status) } });
  },
};
