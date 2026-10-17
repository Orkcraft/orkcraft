// The one modal of the shell (docs/specs/34-v1-round-2.md §5): every dialog and menu that opens over the shell — New goal,
// Edit goal, New idea, Add / Edit agent, the gear's menu, Pair a phone, Merge into, Drop's confirm — opens on a dimmed
// backdrop, in an opaque panel with a title, Close (×) and Esc; the focus stays inside while it is open and goes back to
// what opened it. `dialog` says which one is open; `shell/dialogs.js` draws it.
import { useEffect, useRef } from "preact/hooks";
import { signal } from "@preact/signals";
import { html } from "../html.js";

export const dialog = signal(null);          // null | {kind, props}
let opener = null;

export function openDialog(kind, props = {}) {
  if (!dialog.value) opener = document.activeElement;       // a dialog replacing a dialog keeps the first opener
  dialog.value = { kind, props };
}

export function closeDialog() {
  dialog.value = null;
  const back = opener;
  opener = null;
  if (back && back.isConnected && back.focus) back.focus();
}

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

/** The panel: `title`, `children`, `foot` (the buttons, pinned at the foot), `onClose` (× · Esc · a click on the backdrop). */
export function Modal({ title, onClose, children, foot, wide = false }) {
  const panel = useRef();
  const close = useRef(onClose);
  close.current = onClose;                       // Esc runs the latest close: a dialog saves what is typed in it
  useEffect(() => {
    const el = panel.current;
    (el.querySelector("[autofocus]") || el.querySelector(FOCUSABLE) || el).focus();
    const key = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close.current(); } };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, []);
  const trap = (e) => {
    if (e.key !== "Tab") return;
    const items = [...panel.current.querySelectorAll(FOCUSABLE)].filter((x) => x.offsetParent !== null);
    if (!items.length) { e.preventDefault(); return; }
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  return html`<div class="shell-backdrop" data-modal-backdrop onMouseDown=${(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section class=${`ok-dialog shell-modal${wide ? " is-wide" : ""}`} role="dialog" aria-modal="true" aria-label=${title} tabindex="-1" ref=${panel} onKeyDown=${trap}>
      <header class="ok-dialog__head shell-modal__head"><h2 class="ok-dialog__title">${title}</h2>
        <button type="button" class="ok-btn shell-modal__x" aria-label="Close" onClick=${onClose}>×</button></header>
      <div class="shell-modal__body">${children}</div>
      ${foot && html`<footer class="ok-dialog__actions shell-modal__foot">${foot}</footer>`}
    </section>
  </div>`;
}
