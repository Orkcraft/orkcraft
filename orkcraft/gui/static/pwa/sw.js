// The app's worker (gui/pwa.py): the shell opens without the network, the town never does. Every file is
// asked of the town first, so a new version arrives the next time it is reachable; the cache is only for
// when it is not. The socket is never cached: what the town is comes live or not at all.
const CACHE = "orkcraft-app-v1";
const SHELL = ["./", "app.js", "app.css", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin || !url.pathname.startsWith("/app/")) return;
  const key = url.pathname.endsWith("/") ? "./" : url.pathname.split("/").pop();
  if (key.startsWith("manifest")) return;             // it may carry a token (?k=): never kept
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(key, copy)); }
    return r;
  }).catch(() => caches.open(CACHE).then((c) => c.match(key)).then((r) => r || Response.error())));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((all) => (all[0] ? all[0].focus() : self.clients.openWindow("./"))));
});
