// A modal (design-system/components.md: Dialog): the only place a primary action lives. Escape and
// a click outside cancel it. Its head and its actions stay put; what is between them scrolls, so a long
// report never pushes its buttons off the screen. `meta` is a quiet line under the title.
import { useLayoutEffect } from "preact/hooks";
import { html, cls } from "./html.js";

export function Dialog({ title, meta, text, children, actions, onCancel, warn = false, wide = false }) {
  // Listening from the moment it is drawn: an effect after the paint missed an Escape pressed at once.
  useLayoutEffect(() => {
    const key = (e) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onCancel]);
  return html`<div class="gui-modal" onClick=${(e) => e.target === e.currentTarget && onCancel()}>
    <div class=${cls("ok-dialog", { "is-warn": warn, "is-wide": wide })} role="dialog" aria-modal="true" aria-label=${title}>
      <div class="ok-dialog__head"><h3 class="ok-dialog__title">${title}</h3></div>
      ${meta && html`<p class="ok-dialog__hint gui-dialog__meta">${meta}</p>`}
      <div class="gui-dialog__body">
        ${text && html`<p class="ok-dialog__text">${text}</p>`}
        ${children}
      </div>
      <div class="ok-dialog__actions">${actions}</div>
    </div>
  </div>`;
}
