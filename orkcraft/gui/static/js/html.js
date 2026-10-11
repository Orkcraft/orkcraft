// htm over Preact: JSX-like templates with no build step.
import { h } from "preact";
import htm from "htm";
// A template's own text is written in today's words (realm/lexicon.py), never an old Camp spelling:
// tests/test_gui_wording.py reads every template. What the town's data says goes through say().
export const html = htm.bind(h);

/** Class names from an object of flags: cls("ok-hut", {"is-alert": true}) → "ok-hut is-alert". */
export function cls(base, flags = {}) {
  if (typeof flags === "string") return flags ? `${base} ${flags}` : base;     // a class name of its own, not flags
  return [base, ...Object.entries(flags).filter(([, on]) => on).map(([name]) => name)].join(" ");
}

// An address in a text: a full URL, or a bare host of a known kind with its path (tailscale.com/download), never a
// file name (roads.py); a sentence's closing stop or bracket stays outside it, and an e-mail address's domain is no
// link. markdown.py links the same in a page's Markdown.
const ADDRESS = /\bhttps?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]]|(?<![@\w.-])(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|ai)\b(?:\/[^\s<>"']*[^\s<>"'.,;:!?)\]])?(?![\w.-]*@)/gi;

/** A text with its addresses as links that open in the browser (the app's window hands `_blank` to it). */
export function linked(text) {
  if (!text || typeof text !== "string") return text;
  const out = [];
  let at = 0;
  for (const m of text.matchAll(ADDRESS)) {
    if (m.index > at) out.push(text.slice(at, m.index));
    const href = /^https?:/i.test(m[0]) ? m[0] : `https://${m[0]}`;
    out.push(h("a", { class: "gui-link", href, target: "_blank", rel: "noopener noreferrer", key: m.index }, m[0]));
    at = m.index + m[0].length;
  }
  if (!out.length) return text;
  if (at < text.length) out.push(text.slice(at));
  return out;
}
