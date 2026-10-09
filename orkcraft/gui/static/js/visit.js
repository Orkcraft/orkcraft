// The ork that comes out of its building (docs/design/yards.md §4), in Camp. Its building's plinth runs on a little
// to the left of the house; there the ork stands. Its building selected, it walks out of the door onto it (facing
// left, two steps), turns to you and speaks in a pixel bubble: 👎 and a gear, its settings (the building's Info,
// at its steward: its tier and AI tool) — a 👎 is what teaches it; 👍 stays in the building's Info (js/console.js).
// The mouse over a building brings nobody out. The building no longer selected, it waits a moment and walks back in (facing right). An ork that asks comes out by itself and waits there,
// a `!` in its bubble: a press answers it (js/orders.js). An ork come to a yard for a wake stands there while it is.
// A yard's 👍 / 👎 rate the building (its steward wakes on a 👎), a hut's its lead ork's work. Office draws none of
// it (office.css): its 👍 / 👎 and models are in the building's Info (js/console.js).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say } from "./link.js";
import { openOrders } from "./orders.js";
import { DislikeDialog, NoteDialog } from "./console.js";
import { openBuilding } from "./windows.js";

const WALK_MS = 240;               // out of the door to its place on the plinth, or back
const STAY_MS = 400;               // the mouse gone, it waits this long before it walks back in
const RANK = { laborer: 1, warrior: 2, elder: 3 };              // the chevrons it wears (icons/rank-N.png)
const TIER_WORD = { laborer: "Novice", warrior: "Seasoned", elder: "Veteran" };   // realm/tiers.py TIER_LABELS

const visitDialog = signal(null);  // {kind: "ork-bad" | "dislike", b, o?}

const still = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const lead = (b) => b.garrison.find((o) => o.status === "alert") || b.garrison.find((o) => o.lead) || b.garrison[0];

/** The building's Info, scrolled to its steward's part (its tier, its AI tool): the bubble's gear. */
export function openSteward(id) {
  openBuilding(id, "info");
  let tries = 0;
  const look = () => {
    const part = document.querySelector(".gui-info-tab .gui-steward-part");
    if (part) { part.scrollIntoView({ block: "start", behavior: still() ? "auto" : "smooth" }); return; }
    if (++tries < 40) setTimeout(look, 50);           // Info asks the host first: a moment
  };
  setTimeout(look, 0);
}

/** Out (true) or in, with the walk between: "in", "out-walk", "out", "in-walk". */
function usePlace(want) {
  const [place, setPlace] = useState(want ? "out" : "in");
  useEffect(() => {
    if (want && (place === "in" || place === "in-walk")) setPlace(still() ? "out" : "out-walk");
    if (!want && (place === "out" || place === "out-walk")) {
      const t = setTimeout(() => setPlace(still() ? "in" : "in-walk"), STAY_MS);
      return () => clearTimeout(t);
    }
    if (place === "out-walk" || place === "in-walk") {
      const t = setTimeout(() => setPlace(place === "out-walk" ? "out" : "in"), WALK_MS);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [want, place]);
  return place;
}

/** The ork outside its building, and its bubble. `selected`: its building is the one selected (js/hut.js). */
export function Outside({ b, selected }) {
  const o = b.yard ? null : lead(b);
  const asking = !!b.alert;
  const visiting = !!(b.yard && b.visit);
  const rates = !asking && (b.yard || !!o);
  const place = usePlace(asking || visiting || (rates && selected));
  if (place === "in" || (!o && !b.yard)) return null;
  const who = o ? o.name : say(b.title);
  const stop = (e) => e.stopPropagation();

  const dislike = (e) => { stop(e); visitDialog.value = b.yard ? { kind: "dislike", b } : { kind: "ork-bad", b, o }; };
  const settings = (e) => { stop(e); openSteward(b.id); };

  const walking = place === "out-walk" || place === "in-walk";
  // its frames are the stylesheet's (yards.css); it wears its tier's chevrons, how seasoned its mind is (realm/tiers.py)
  const rank = o && RANK[o.rank || o.tier];
  const body = html`<i class="gui-out__ork" aria-hidden="true"></i>${rank && html`<img class="gui-out__rank ok-sprite"
    src=${`/ds/sprites/icons/rank-${rank}.png`} srcset=${`/ds/sprites/icons/rank-${rank}@2x.png 2x`} width="16" height="16"
    alt="" title=${say(TIER_WORD[o.rank || o.tier])} draggable="false" />`}`;
  const tools = o && o.kind !== "chain" && o.kind !== "script" && o.scheme;
  const bubble = place !== "out" ? null
    : asking ? html`<span class="gui-out__bubble is-ask" aria-hidden="true">!</span>`
    : rates && selected ? html`<span class="gui-out__bubble" role="group" aria-label=${`${who}: ${say("rate its work")}`}
        onPointerDown=${stop} onClick=${stop}>
          <button class="gui-out__act" onClick=${dislike}
            title=${say(b.yard ? "Bad: what went wrong?" : "Bad work: what went wrong?")}
            aria-label=${say("Bad")}><img class="ok-sprite" src="/ds/sprites/icons/thumb-down.png"
            srcset="/ds/sprites/icons/thumb-down@2x.png 2x" width="20" height="20" alt="" draggable="false" /></button>
          ${tools && html`<button class="gui-out__act is-tool" onClick=${settings}
            title=${`${say("Settings")} · ${say("its steward's tier and AI tool")} (${o.scheme})`}
            aria-label=${say("Its settings: tier and AI tool")}><img class="ok-sprite" src="/ds/sprites/icons/settings.png"
            srcset="/ds/sprites/icons/settings@2x.png 2x" width="20" height="20" alt="" draggable="false" /></button>`}</span>`
    : null;
  const at = cls("gui-out", { [`is-${place}`]: true, "is-asking": asking, "is-step": walking });
  if (asking) {
    return html`<button class=${at} title=${`${who}: ${b.alert.title}`} aria-label=${`${say("Answer")} ${who}`}
        onPointerDown=${stop} onClick=${(e) => { stop(e); openOrders(b.alert.id); }}>${bubble}${body}</button>`;
  }
  return html`<span class=${at} title=${visiting ? `${who} · ${say("visiting")}` : who}>${bubble}${body}</span>`;
}

/** The dialogs a bubble opens: a 👎's note. */
export function VisitDialogs() {
  const d = visitDialog.value;
  if (!d) return null;
  const close = () => { visitDialog.value = null; };
  if (d.kind === "dislike") return html`<${DislikeDialog} b=${d.b} onClose=${close} onDone=${() => {}} />`;
  if (d.kind === "ork-bad") {
    return html`<${NoteDialog} title=${say(`Bad work — ${d.o.name}`)} onClose=${close}
      onSend=${(note) => command("ork.dislike", { id: d.b.id, ork: d.o.ref, note }).then(close, () => {})} />`;
  }
  return null;
}
