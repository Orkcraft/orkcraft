// A modal (design-system/components.md: Dialog): the only place a primary action lives. Escape and
// a click outside cancel it.
import { useEffect } from "preact/hooks";
import { html } from "./html.js";

export function Dialog({ title, text, children, actions, onCancel, warn = false }) {
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onCancel]);
  return html`<div class="gui-modal" onClick=${(e) => e.target === e.currentTarget && onCancel()}>
    <div class=${warn ? "ok-dialog is-warn" : "ok-dialog"} role="dialog" aria-modal="true" aria-label=${title}>
      <div class="ok-dialog__head"><h3 class="ok-dialog__title">${title}</h3></div>
      ${text && html`<p class="ok-dialog__text">${text}</p>`}
      ${children}
      <div class="ok-dialog__actions">${actions}</div>
    </div>
  </div>`;
}
