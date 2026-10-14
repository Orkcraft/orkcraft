// "Since your last look" on the phone (docs/design/audience.md §2a; core/last_look.py, the face "phone"): the line
// the camp opens under — what was built first, then how many questions came, the problems with what each waits
// for, what it cost — measured from the person's last look on any face. Honest when nothing changed. A look is a
// break, not a second job: at most three of anything, no counters to clear, and "Back to the camp" puts it away.
// The page beats while it is shown, as the desktop's does (js/lastlook.js): the town decides when a look began.

import { h } from "./util.js";

const LOOK_MIN_S = 5;           // realm/last_look.py keeps the same
const BEAT_S = 30;

/** `ctx`: {send, open(buildingId)}. Returns {el, render(town)}. */
export function makeLook(ctx) {
  const headline = h("p", { class: "look-line" });
  const body = h("div", { class: "look-body" });
  const back = h("button", { class: "ok-btn", type: "button" }, "Back to the camp");
  const el = h("section", { class: "card look", "aria-label": "Since your last look", hidden: true },
    headline, body, h("div", { class: "row" }, back));
  back.addEventListener("click", () => { el.hidden = true; ctx.send("mobile.look_done"); });

  // Seconds the page has been shown; a beat once it is a look, then every BEAT_S while it stays.
  let shown = 0;
  setInterval(() => {
    if (document.visibilityState !== "visible") { shown = 0; return; }
    shown += 1;
    if (shown === LOOK_MIN_S || (shown > LOOK_MIN_S && (shown - LOOK_MIN_S) % BEAT_S === 0)) ctx.send("mobile.beat");
  }, 1000);

  function render(s) {
    const d = s.last_look;
    el.hidden = !d;
    if (!d) return;
    headline.textContent = d.headline;
    const camp = s.look !== "office";
    const parts = [];
    const built = d.built || { items: [] };
    if (built.items.length) {
      parts.push(h("ul", { class: "look-list built" }, ...built.items.map((i) => h("li", {},
        i.building ? h("button", { class: "look-open", type: "button", onclick: () => ctx.open(i.building) }, i.line) : i.line)),
        built.more ? h("li", { class: "muted" }, `and ${built.more} more`) : null));
    }
    if (d.questions?.count) {
      parts.push(h("p", { class: "muted" }, d.questions.count === 1 ? "A question waits in Answers, below the camp."
        : `${d.questions.count} questions wait in Answers, below the camp.`));
    }
    const probs = d.problems || { items: [] };
    if (probs.items.length) {
      parts.push(h("ul", { class: "look-list problems" }, ...probs.items.map((p) => h("li", {},
        h("button", { class: "look-open", type: "button", onclick: () => p.building && ctx.open(p.building) },
          `${camp ? "🔥 " : ""}${p.title}: ${p.line}`), h("small", { class: "muted" }, ` waits for ${p.waits}`))),
        probs.more ? h("li", { class: "muted" }, `and ${probs.more} more`) : null));
    }
    for (const line of d.cost || []) parts.push(h("p", { class: "muted look-cost" }, line));
    if (!d.empty && d.working) parts.push(h("p", { class: "muted" }, `Now ${d.working}.`));
    body.replaceChildren(...parts);
  }

  return { el, render };
}
