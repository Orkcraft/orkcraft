// The right click (docs/design/calm-town.md §3): a building's menu on its hut — Open, Info, Listen to…,
// Ask the Warchief, Demolish — and the bare map's — Build here, Settings. What the Command Card had, without
// opening the panel; each entry names the Warchief's command that does the same (js/warchief.js), so the
// menu teaches the line.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { say } from "./link.js";

// {x, y, items: [{label, hint, run, danger}]} while a menu is up
export const menu = signal(null);

export function openMenu(e, items) {
  e.preventDefault();
  e.stopPropagation();
  menu.value = { x: e.clientX, y: e.clientY, items: items.filter(Boolean) };
}

const close = () => { menu.value = null; };

export function Menu() {
  const m = menu.value;
  const ref = useRef(null);
  useEffect(() => {
    if (!m) return undefined;
    const away = (e) => { if (!ref.current || !ref.current.contains(e.target)) close(); };
    const key = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
    window.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", key, true);
    window.addEventListener("blur", close);
    return () => {
      window.removeEventListener("pointerdown", away, true);
      window.removeEventListener("keydown", key, true);
      window.removeEventListener("blur", close);
    };
  }, [m]);
  useEffect(() => {                         // kept inside the window
    const el = ref.current;
    if (!el || !m) return;
    const r = el.getBoundingClientRect();
    if (r.right > window.innerWidth) el.style.left = `${Math.max(window.innerWidth - r.width - 4, 0)}px`;
    if (r.bottom > window.innerHeight) el.style.top = `${Math.max(window.innerHeight - r.height - 4, 0)}px`;
  }, [m]);
  if (!m) return null;
  return html`<ul ref=${ref} class="ok-list__items gui-menu" role="menu" style=${`left:${m.x}px;top:${m.y}px`}>
    ${m.items.map((it, i) => it === "-" ? html`<li key=${i} class="gui-menu__sep" role="separator"></li>`
      : html`<li key=${i} role="menuitem" tabindex="-1" class=${cls("ok-item gui-menu__item", { "is-danger": !!it.danger })}
          onClick=${() => { close(); it.run(); }}>
        <span>${say(it.label)}</span>${it.hint && html`<span class="meta ok-font-mono">${it.hint}</span>`}</li>`)}
  </ul>`;
}
