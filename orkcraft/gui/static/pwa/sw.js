// The app's worker (gui/pwa.py): the shell opens without the network, the town never does. Every file is
// asked of the town first, so a new version arrives the next time it is reachable; the cache is only for
// when it is not. The socket is never cached: what the town is comes live or not at all.
const CACHE = "orkcraft-app-v12";
const SHELL = ["./", "app.js", "util.js", "dock.js", "town.js", "fields.js", "icons.js", "links.js", "ground.js", "camp.js", "look.js", "slots.js", "board.js", "camp/ork-walk.png",
  "camp/layout.js", "camp/track.js", "camp/services.js", "camp/ground.js",
  "tokens.css", "components.css", "app.css",
  "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png", "fonts/fonts.css",
  "fonts/titillium-web-latin-400-normal.woff2", "fonts/titillium-web-latin-600-normal.woff2",
  "fonts/new-rocker-latin-400-normal.woff2"];
const CACHE_PREFIXES = ["v3/", "sprites/", "icons/", "fence/", "fonts/"];

function isCacheFirst(key) {
  return CACHE_PREFIXES.some((p) => key.startsWith(p)) || key.endsWith(".png") || key.endsWith(".webp");
}

// What the worker hands the page is never fresh to the page's own memory cache: a reloaded page asks the worker
// again (it answers from its cache, no network), so a picture the map dropped is not drawn old from memory.
function toPage(resp) {
  if (!resp.ok) return resp;
  const headers = new Headers(resp.headers);
  headers.set("Cache-Control", "no-cache");
  return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers });
}

async function updateAssets(newAssets) {
  if (!newAssets || typeof newAssets !== "object") return;
  const cache = await caches.open(CACHE);
  const oldResp = (await cache.match("assets.json")) || (await cache.match("/app/assets.json"));
  if (oldResp) {
    try {
      const oldAssets = await oldResp.json();
      for (const [path, hash] of Object.entries(newAssets)) {
        if (oldAssets[path] && oldAssets[path] !== hash) {
          await cache.delete(path);
          await cache.delete("/app/" + path);
        }
      }
      for (const path of Object.keys(oldAssets)) {
        if (!newAssets[path]) {
          await cache.delete(path);
          await cache.delete("/app/" + path);
        }
      }
    } catch {}
  }
  await cache.put("assets.json", new Response(JSON.stringify(newAssets), {
    headers: { "Content-Type": "application/json" },
  }));
}

// A new cache is filled from the town, never from the browser's HTTP cache (the PNGs and fonts are immutable
// there), and starts with the assets' map, so the next sync has one to compare against.
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then(async (c) => {
    await Promise.all(SHELL.map(async (path) => {
      const resp = await fetch(path, { cache: "reload" });
      if (!resp.ok) throw new Error(`${path}: ${resp.status}`);
      await c.put(path, resp);
    }));
    try {
      const map = await fetch("assets.json", { cache: "reload" });
      if (map.ok) await c.put("assets.json", map);
    } catch {}
  }).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin || !url.pathname.startsWith("/app/")) return;
  const key = url.pathname.endsWith("/") ? "./" : url.pathname.slice("/app/".length);
  if (key.startsWith("manifest")) return;             // it may carry a token (?k=): never kept

  if (isCacheFirst(key)) {
    e.respondWith(caches.open(CACHE).then(async (cache) => {
      const hit = (await cache.match(e.request)) || (await cache.match(key));
      if (hit) return toPage(hit);
      const resp = await fetch(e.request, { cache: "reload" });
      if (resp.ok) cache.put(key, resp.clone());
      return toPage(resp);
    }));
    return;
  }

  if (key === "assets.json") {
    e.respondWith(fetch(e.request).then(async (r) => {
      if (r.ok) {
        try {
          const newAssets = await r.clone().json();
          await updateAssets(newAssets);
        } catch {}
      }
      return r;
    }).catch(() => caches.open(CACHE).then((c) => c.match(key)).then((r) => r || Response.error())));
    return;
  }

  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) {
      const copy = r.clone();
      caches.open(CACHE).then((c) => c.put(key, copy));
    }
    return r;
  }).catch(() => caches.open(CACHE).then((c) => c.match(key)).then((r) => r || Response.error())));
});

self.addEventListener("message", (e) => {
  if (e.data?.type === "precache" && Array.isArray(e.data.paths)) {
    const port = e.ports?.[0];
    const paths = e.data.paths;
    const p = caches.open(CACHE).then(async (c) => {
      for (let i = 0; i < paths.length; i += 20) {
        const batch = paths.slice(i, i + 20);
        await Promise.all(batch.map(async (path) => {
          try {
            const resp = await fetch(path, { cache: "reload" });
            if (resp.ok) await c.put(path, resp);
          } catch {}
        }));
        port?.postMessage({ type: "progress", loaded: Math.min(i + 20, paths.length), total: paths.length });
      }
      port?.postMessage({ type: "done", loaded: paths.length, total: paths.length });
    });
    e.waitUntil(p);
  }
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((all) => (all[0] ? all[0].focus() : self.clients.openWindow("./"))));
});
