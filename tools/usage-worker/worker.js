// Orkcraft's usage proxy (docs/usage-stats.md): a Cloudflare Worker between the app and Amplitude.
// It holds the Amplitude key (a secret of the Worker, never in the repository), keeps only the events
// and properties listed below — the same list as orkcraft/core/usage.py `EVENTS` — limits how often
// one install may send, and passes the rest on. The person's IP address stays here: Amplitude only
// sees the Worker's request.
//
//   POST /v1/events  {install_id, session_id, app_version, os, python, events: [{event, time, props}]}
//   POST /v1/crash   {install_id, app_version, os, python, items: [{type: "event" | "session", …}]} → Sentry
//   GET  /install.sh the installer, from main
//   → 204 (kept or dropped quietly) · 400 (not a batch) · 413 (too big) · 429 (too often)
//   X-Amplitude-Status on a 204 that reached Amplitude: its own answer (200 ok, 400 a bad key or batch,
//   401 a key of the other data centre), so `curl -i` shows why nothing arrives.

const COUNTS = ["0", "1", "2-5", "6-10", "11+"];
const MINUTES = ["<5", "5-30", "30-120", "120+"];
const TOOLS = ["claude", "agy", "codex", "hermes", "pi", "cursor"];
const TYPES = ["pit", "watchtower", "signpost", "mill", "horn", "fields", "barracks", "council", "war_drum",
  "forest", "scrolls", "mine", "gramophone", "lake", "forge", "loot", "crag", "catapult", "town_hall", "workshop", "custom"];
const DEEDS = ["town", "road", "reference", "week", "learned", "mature", "trusted", "night"];
// The installer's (install.sh, docs/install.md): its steps, a time bucket, the kind of error.
const STEPS = ["uv", "python", "package", "version", "window", "agents"];
const SECONDS = ["<10", "10-60", "60-300", "300+"];
const ERRORS = ["disk_full", "permission", "tls", "network", "python_download", "resolve_failed",
  "build_failed", "git_missing", "unknown"];
const bool = (v) => typeof v === "boolean";

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
  install_started: { method: oneOf(["sh"]), arch: oneOf(["x86_64", "arm64", "other"]), upgrade: bool },
  install_step: { step: oneOf(STEPS), ok: bool, seconds: oneOf(SECONDS), error: oneOf(ERRORS), found: bool,
    source: oneOf(["git", "archive", "local"]), window: oneOf(["native", "browser"]),
    tools: (v) => Array.isArray(v) && v.length <= TOOLS.length && v.every((t) => TOOLS.includes(t)) },
  install_finished: { ok: bool, seconds: oneOf(SECONDS), failed_step: (v) => v === "none" || STEPS.includes(v) },
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

// The installer, as `main` has it: `curl -fsSL https://<this worker>/install.sh | sh`. Cloudflare's own
// request counts for this path are how many fetched it; nothing about the person is kept or sent.
const INSTALLER = "https://raw.githubusercontent.com/Orkcraft/orkcraft/main/install.sh";

async function installer() {
  const res = await fetch(INSTALLER, { cf: { cacheTtl: 300, cacheEverything: true } });
  if (!res.ok) return new Response("echo 'orkcraft: the installer could not be fetched; try again in a minute' >&2; exit 1\n",
    { status: 502, headers: { "Content-Type": "text/x-shellscript; charset=utf-8" } });
  return new Response(res.body, { headers: { "Content-Type": "text/x-shellscript; charset=utf-8",
    "Cache-Control": "public, max-age=300" } });
}

/** A request from the app, checked before anything else: its User-Agent, its size, JSON with an install
 *  id, and how often this install sends (the Rate Limiting binding of wrangler.toml). The body, or the
 *  Response that refuses it. */
async function batch(request, env) {
  if (!(request.headers.get("user-agent") || "").startsWith("orkcraft/")) return new Response(null, { status: 403 });
  if (Number(request.headers.get("content-length") || 0) > MAX_BODY) return new Response(null, { status: 413 });
  const text = await request.text();
  if (text.length > MAX_BODY) return new Response(null, { status: 413 });
  let body;
  try { body = JSON.parse(text); } catch { return new Response(null, { status: 400 }); }
  if (!body || !HEX32.test(body.install_id)) return new Response(null, { status: 400 });
  if (env.LIMITER) {
    const { success } = await env.LIMITER.limit({ key: body.install_id });
    if (!success) return new Response(null, { status: 429 });
  }
  return body;
}

// -- crash reports (docs/crash-reports.md): the app's own small form, checked field by field, then
// written as a Sentry envelope with the key this Worker holds (the secret SENTRY_DSN) ---------------

const WHERE = ["unhandled", "thread", "asyncio", "command", "clock", "window"];
const STATUSES = ["ok", "exited", "crashed", "abnormal"];
const ENVIRONMENTS = ["production", "checkout"];
const IDENT = /^[A-Za-z_$<>?][\w.$<>]{0,99}$/;
const FILE = /^(orkcraft\/[\w./-]{1,200}\.py|<stdlib>\/[\w./-]{1,200}|[\w.-]{1,80}\/[\w./-]{1,200}|<other>|<frozen [\w.]{1,80}>|static\/[\w./-]{1,200}\.js)$/;
const MAX_TEXT = 300;

function frames(list) {
  if (!Array.isArray(list)) return [];
  return list.slice(-40).filter((f) => f && FILE.test(f.file) && IDENT.test(f.function)).map((f) => ({
    filename: f.file, module: f.file.endsWith(".py") ? f.file.replace(/\.py$/, "").replaceAll("/", ".") : undefined,
    function: f.function, lineno: Number.isInteger(f.line) && f.line > 0 ? f.line : undefined, in_app: f.in_app === true,
  }));
}

function crashEvent(e, base) {
  if (!e || !/^[0-9a-f]{32}$/.test(e.event_id) || !WHERE.includes(e.where) || !Array.isArray(e.exceptions)) return null;
  const values = e.exceptions.slice(-3).filter((x) => x && IDENT.test(x.type)).map((x) => ({
    type: x.type, value: typeof x.value === "string" ? x.value.slice(0, MAX_TEXT) : "",
    mechanism: { type: e.where, handled: e.handled === true },
    stacktrace: { frames: frames(x.frames) },
  }));
  if (!values.length) return null;
  const now = Date.now();
  const time = Number.isInteger(e.time) && e.time > now - 7 * 864e5 && e.time < now + 3e5 ? e.time : now;
  return {
    event_id: e.event_id, timestamp: time / 1000, platform: e.platform === "javascript" ? "javascript" : "python",
    level: e.level === "fatal" ? "fatal" : "error", release: base.release,
    environment: ENVIRONMENTS.includes(e.environment) ? e.environment : "production",
    user: { id: base.install_id, ip_address: null }, server_name: "",
    tags: { where: e.where, os: base.os, python: base.python, face: e.face === "gui" ? "gui" : "cli",
      ...(typeof e.command === "string" && /^[a-z][a-z0-9_.]{0,60}$/.test(e.command) ? { command: e.command } : {}) },
    contexts: { os: { name: base.os }, runtime: { name: "CPython", version: base.python } },
    exception: { values },
  };
}

function crashSession(s, base) {
  if (!s || !/^[0-9a-f]{32}$/.test(s.sid) || !STATUSES.includes(s.status) || !Number.isInteger(s.started)) return null;
  const now = Date.now();
  return {
    sid: s.sid, did: base.install_id, init: s.init === true, status: s.status,
    started: new Date(s.started).toISOString(), timestamp: new Date(now).toISOString(),
    duration: Number.isInteger(s.duration) && s.duration >= 0 ? s.duration : 0,
    errors: Number.isInteger(s.errors) && s.errors >= 0 ? Math.min(s.errors, 1000) : 0,
    attrs: { release: base.release, environment: ENVIRONMENTS.includes(s.environment) ? s.environment : "production" },
  };
}

function dsn(text) {                       // https://<key>@<host>/<project>
  try {
    const u = new URL(text);
    const project = u.pathname.replace(/^\/+|\/+$/g, "");
    return u.username && /^\d+$/.test(project) ? { key: u.username, url: `${u.protocol}//${u.host}/api/${project}/envelope/` } : null;
  } catch { return null; }
}

async function crash(request, env, body) {
  const target = dsn(env.SENTRY_DSN || "");
  if (!target || !Array.isArray(body.items)) return new Response(null, { status: target ? 400 : 204 });
  const base = {
    install_id: body.install_id,
    release: `orkcraft@${VERSION.test(body.app_version || "") ? body.app_version : "unknown"}`,
    os: OS.includes(body.os) ? body.os : "unknown",
    python: /^3\.\d{1,2}$/.test(body.python || "") ? body.python : "unknown",
  };
  const lines = [JSON.stringify({ sent_at: new Date().toISOString() })];
  for (const item of body.items.slice(0, 5)) {
    const made = item && item.type === "event" ? crashEvent(item, base) : item && item.type === "session" ? crashSession(item, base) : null;
    if (!made) continue;
    lines.push(JSON.stringify({ type: item.type }), JSON.stringify(made));
  }
  if (lines.length === 1) return new Response(null, { status: 204 });
  const res = await fetch(target.url, {
    method: "POST",
    headers: { "Content-Type": "application/x-sentry-envelope",
      "X-Sentry-Auth": `Sentry sentry_version=7, sentry_key=${target.key}, sentry_client=orkcraft-proxy/1` },
    body: lines.join("\n") + "\n",
  });
  return new Response(null, { status: 204, headers: { "X-Sentry-Status": String(res.status) } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/install.sh") return installer();
    if (request.method === "POST" && url.pathname === "/v1/crash") {
      const body = await batch(request, env);
      return body instanceof Response ? body : crash(request, env, body);
    }
    if (request.method !== "POST" || url.pathname !== "/v1/events") return new Response(null, { status: 404 });
    const body = await batch(request, env);
    if (body instanceof Response) return body;
    if (!Array.isArray(body.events)) return new Response(null, { status: 400 });

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
