// Small things the app's modules share (gui/pwa.py): building elements, this browser's storage, a sheet.

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}

export const KEY = "orkcraft.device";   // {id, token, name}: this browser's pairing with the town

// The last town the phone saw, kept on this phone only, to show greyed "as of" while the town cannot be reached
// (docs/design/mobile.md §6); wiped with the pairing.
const KEPT = "orkcraft.town";
export const kept = {
  get() { try { return JSON.parse(localStorage.getItem(KEPT)); } catch { return null; } },
  set(state) { try { localStorage.setItem(KEPT, JSON.stringify({ at: Date.now(), state })); } catch { /* not kept */ } },
  clear() { try { localStorage.removeItem(KEPT); } catch { /* nothing kept */ } },
};

export const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export const store = {
  get() { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } },
  set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* private mode: this run only */ } },
  clear() { try { localStorage.removeItem(KEY); } catch { /* nothing kept */ } kept.clear(); },
};

export const minutes = (s) => (s < 60 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);
export const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");

export function guessName() {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android phone";
  return "Browser";
}

/** A sheet that rises from the screen's foot: a modal <dialog> (Esc and the backdrop close it), its title and
 *  Close at the top, `body` under them. `{el, open, close, title(text)}`. */
export function sheet(title, ...body) {
  const shut = h("button", { class: "btn quiet", type: "button" }, "Close");
  const head = h("h2", {}, title);
  const el = h("dialog", { class: "sheet", "aria-label": title }, h("div", { class: "sheet-in" },
    h("div", { class: "sheet-head" }, head, shut), ...body));
  const open = () => { if (el.open) return; if (el.showModal) el.showModal(); else el.setAttribute("open", ""); };
  const close = () => { if (el.close) el.close(); else el.removeAttribute("open"); };
  shut.addEventListener("click", close);
  el.addEventListener("click", (e) => { if (e.target === el) close(); });   // the backdrop
  return { el, open, close, title(text) { head.textContent = text; el.setAttribute("aria-label", text); } };
}
