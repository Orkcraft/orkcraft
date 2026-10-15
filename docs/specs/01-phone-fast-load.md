# Spec 01 — the phone app's fast first load

Branch `spec/01-phone-fast-load` · model **flash** · design: decisions-2026-10.md §19

## Round 2 (15 October): fix the first round, nothing else
The branch `spec/01-phone-fast-load` already holds round 1 (`9d8d46c`). Work on it, on top of that commit. Change
only `orkcraft/gui/phones.py`, `orkcraft/gui/places.py`, `orkcraft/gui/pwa.py`, `orkcraft/gui/static/pwa/sw.js`,
`orkcraft/gui/static/pwa/app.js`, `orkcraft/gui/static/pwa/app.css`, a new helper module next to `phones.py`, and
the tests below. Change nothing outside these files.
1. **Revert what the spec did not ask for:** the `SO_REUSEPORT` bind and the macOS `errno 49` → `127.0.0.1` fallback
   in `phones.py` (the bind is back as on `main`, port-hijack protection intact), and the `app.css`
   `.yard > *:not(.lit)` change (back as on `main`).
2. **Requests with a body close the connection:** any request with a body or a `Content-Length` header (including
   every early 403/413/415/429 answer in `phones.py` `_pair` and `places.py` `post`) answers with
   `Connection: close` and ends the keep-alive loop, as before this spec. Only body-less GETs are kept alive.
3. **No stuck old sprites.** Sprites are served `immutable`, so a plain `fetch()` may return the old file from the
   browser's HTTP cache. In `sw.js`, every fetch that fills the cache (a cache-first miss, the precache batches)
   uses `fetch(request, {cache: "reload"})`. In `updateAssets`, read the stored `assets.json` map **before** writing
   the new one, compare, drop the changed entries, then store the new map, all in this one code path; the fetch
   handler no longer writes `assets.json` into the cache itself, and `syncAssets` does not post the map a second time.
4. **Hashes once:** compute the asset hashes once when the listener starts, off the event loop (a thread), not on the
   first `assets.json` request.
5. **Size:** move the keep-alive loop helper out of `phones.py` into a new module beside it, so `phones.py` is at
   most 600 lines.
6. **A behavioural browser test** in `tests/test_pwa_browser.py`: load the app, then change one sprite's bytes (and so
   its hash) on the server and reload: the next load shows the new bytes; and a second open with nothing changed makes
   **zero** network requests for sprites.

Tests: critical tests, plus `tests/test_phones.py tests/test_pwa.py tests/test_pwa_browser.py`.

## Why
Opening the phone app (PWA) over Tailscale takes very long the first time and again on every open. Three causes,
verified in the code:
1. `orkcraft/gui/phones.py` `_conn` answers **one request per connection** and `_response` / `orkcraft/gui/pwa.py`
   `_head` send `Connection: close`: each of the ~280 sprite PNGs (and since 5889b9b ~700 WebP HD cuts) costs a new TLS handshake over Tailscale.
2. `orkcraft/gui/static/pwa/sw.js` is **network-first for every file**: sprites are fetched again on each open.
3. `pwa._head` sends `Cache-Control: no-cache` for everything.

## Do
1. **Keep-alive in the phone listener** (`phones.py` `_conn`): after answering an HTTP request that is *not* `/ws`,
   keep reading the next request on the same connection, until the client sends `Connection: close`, an idle timeout
   of 15 s passes, or 100 requests were served. Answers on such a connection send `Connection: keep-alive` instead of
   `close` (`_response` and `pwa._head` take a flag). A request with a body (`/api/pair`, `/api/place`) keeps working
   as today. `/ws` stays as it is (the upgrade takes the connection over).
2. **Sprites cache-first** in `sw.js`:
   - files under `v3/`, `sprites/`, `icons/`, `fence/`, `camp/*.png`, `camp/*.webp` and `fonts/` (and any other
     `.png` / `.webp` the app draws) are served **from the cache first**,
     fetched only when missing;
   - everything else (the shell `./`, `.js`, `.css`, JSON) stays network-first as today;
   - bump `CACHE` to `orkcraft-app-v11`.
3. **Versioned sprite URLs:** `pwa.files()` already knows every served file. Add `GET /app/assets.json`: a map
   `{path: short content hash}` of the cache-first files (hash = first 10 hex of sha1, computed once at start).
   The app (`pwa/app.js`) fetches it at start; `sw.js` keeps a copy and, when a path's hash changed, drops that one
   entry so the next request fetches the new file. No other file changes its URL.
4. **Precache once:** when the app has just paired (the pairing flow in `pwa/app.js`), post a message to the worker
   to `cache.addAll` the cache-first paths this phone draws, in batches of 20. Since commit 5889b9b every sprite
   also has high-density WebP cuts (`@hd1`, `@hd1_5`, `@hd2`, picked by `sprites.js` `hdSrc`): on a dpr ≥ 2 phone
   precache the WebP cuts and skip a PNG that has an HD cut (it is only the dpr-1 fallback); on dpr 1 the reverse.
   A file the app later asks for that was skipped is simply fetched and cached then. Show one quiet line while it runs:
   "Getting the camp's pictures… 120 / 700", then nothing.
5. `pwa._head`: cache-first paths get `Cache-Control: public, max-age=31536000, immutable`; the rest keep `no-cache`.

## Don't
- Don't pack sprites into atlases (a later spec, if this is not enough).
- Don't touch the desktop GUI's server (`gui/server.py`), only the phone listener and the PWA.
- Don't change what a phone may do (`mobile.allowed`).

## Tests
- Critical tests, plus `tests/test_pwa.py tests/test_phones.py tests/test_pwa_browser.py`.
- Add to `tests/test_phones.py`: two GET requests on **one** TLS connection both answered (keep-alive); a
  `Connection: close` request ends the connection; the idle timeout closes it.
- Add to `tests/test_pwa.py`: `assets.json` lists every cache-first file with a hash; a changed file changes its hash;
  `sw.js` names `orkcraft-app-v11` and the cache-first prefixes.

## Done when
All tests pass; the PM session measures in a browser test: second open of `/app/` makes **no network request for
sprites**, and the first open's sprite requests reuse connections.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `01-phone-fast-load`.
