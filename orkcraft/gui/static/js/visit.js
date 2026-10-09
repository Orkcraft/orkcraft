// The ork that comes out of its building (docs/design/yards.md §4), in Camp. Its building's plinth runs on a little
// to the left of the house; there the ork stands. Its building selected, it walks out of the door onto it (facing
// left, two steps), turns to you and speaks in a pixel bubble: 👎 and a gear, its settings (its AI tool, pressed to change it) — a 👎
// is what teaches it; 👍 stays in the building's Info (js/console.js). The
// mouse over a building brings nobody out. A press anywhere else, or Escape, closes the AI tool's picker; the
// building no longer selected, it waits a moment and walks back in (facing right). An ork that asks comes out by itself and waits there,
// a `!` in its bubble: a press answers it (js/orders.js). An ork come to a yard for a wake stands there while it is.
// A yard's 👍 / 👎 rate the building (its steward wakes on a 👎), a hut's its lead ork's work. Office draws none of
// it (office.css): its 👍 / 👎 and models are in the building's Info (js/console.js).
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say } from "./link.js";
import { openOrders } from "./orders.js";
import { ModelDialog } from "./acts.js";
import { DislikeDialog, NoteDialog } from "./console.js";
import { ToolMark } from "./icons.js";

const WALK_MS = 240;               // out of the door to its place on the plinth, or back
const STAY_MS = 400;               // the mouse gone, it waits this long before it walks back in
const RANK = { laborer: 1, warrior: 2, elder: 3 };              // the chevrons it wears (icons/rank-N.png)
const TIER_WORD = { laborer: "Novice", warrior: "Seasoned", elder: "Veteran" };   // realm/tiers.py TIER_LABELS
const TOOL_OF_MARK = new Set(["✻", "✦", "⌬", "☤", "π", "◆"]);

const visitDialog = signal(null);  // {kind: "ork-bad" | "dislike" | "model", b, o?, i?}

const still = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const lead = (b) => b.garrison.find((o) => o.status === "alert") || b.garrison.find((o) => o.lead) || b.garrison[0];
/** Whether its scheme is one AI tool, which the bubble's picker changes in place (a pipeline's go to the dialog). */
const oneTool = (scheme) => !!scheme && [...scheme].length === 1 && TOOL_OF_MARK.has(scheme);

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

/** A press outside `ref`, or Escape, while `on`: `close`. A bubble left open never hangs over the town. */
function useAway(ref, on, close) {
  useEffect(() => {
    if (!on) return undefined;
    const down = (e) => { if (ref.current && !ref.current.contains(e.target)) close(); };
    const key = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("pointerdown", down, true);
    window.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", down, true); window.removeEventListener("keydown", key); };
  }, [on]);
}

/** The ork outside its building, and its bubble. `selected`: its building is the one selected (js/hut.js). */
export function Outside({ b, selected }) {
  const [picking, setPicking] = useState(null);       // the ork's models, while its AI tool is picked
  const ref = useRef(null);
  const o = b.yard ? null : lead(b);
  const asking = !!b.alert;
  const visiting = !!(b.yard && b.visit);
  const rates = !asking && (b.yard || !!o);
  useEffect(() => { if (!selected) setPicking(null); }, [selected]);
  useAway(ref, !!picking, () => setPicking(null));
  const place = usePlace(asking || visiting || (rates && selected) || !!picking);
  if (place === "in" || (!o && !b.yard)) return null;
  const who = o ? o.name : say(b.title);
  const stop = (e) => e.stopPropagation();

  const dislike = (e) => { stop(e); visitDialog.value = b.yard ? { kind: "dislike", b } : { kind: "ork-bad", b, o }; };
  const tool = (e) => {
    stop(e);
    if (picking) { setPicking(null); return; }
    command("info", { id: b.id, ork: o.ref }).then((i) => {
      if (!i || !i.uses_model) return;
      const ready = (i.ready || []).filter((h) => h !== "main");
      if (i.steps.length === 1 && i.steps[0].editable && ready.length > 1 && oneTool(o.scheme)) setPicking({ ...i, ready });
      else visitDialog.value = { kind: "model", b, i };
    }, () => {});
  };
  const pick = (e, harness) => {
    stop(e);
    const step = picking.steps[0];
    if (harness === step.harness) { setPicking(null); return; }
    command("ork.model", { id: b.id, ork: o.ref, steps: [{ harness, tier: step.tier }] }).then(() => setPicking(null), () => {});
  };

  const walking = place === "out-walk" || place === "in-walk";
  // its frames are the stylesheet's (yards.css); it wears its tier's chevrons, how seasoned its mind is (realm/tiers.py)
  const rank = o && RANK[o.rank || o.tier];
  const body = html`<i class="gui-out__ork" aria-hidden="true"></i>${rank && html`<img class="gui-out__rank ok-sprite"
    src=${`/ds/sprites/icons/rank-${rank}.png`} srcset=${`/ds/sprites/icons/rank-${rank}@2x.png 2x`} width="16" height="16"
    alt="" title=${say(TIER_WORD[o.rank || o.tier])} draggable="false" />`}`;
  const tools = o && o.kind !== "chain" && o.kind !== "script" && o.scheme;
  const bubble = place !== "out" ? null
    : asking ? html`<span class="gui-out__bubble is-ask" aria-hidden="true">!</span>`
    : rates && (selected || picking) ? html`<span ref=${ref} class="gui-out__bubble" role="group" aria-label=${`${who}: ${say("rate its work")}`}
        onPointerDown=${stop} onClick=${stop}>
        ${picking ? picking.ready.map((h) => html`<button key=${h} class=${cls("gui-out__act", { "is-on": h === picking.steps[0].harness })}
            title=${`${say("AI tool")}: ${h}`} aria-label=${`${say("AI tool")}: ${h}`} onClick=${(e) => pick(e, h)}><${ToolMark} id=${h} /></button>`)
          : html`
          <button class="gui-out__act" onClick=${dislike}
            title=${say(b.yard ? "Bad: what went wrong?" : "Bad work: what went wrong?")}
            aria-label=${say("Bad")}><img class="ok-sprite" src="/ds/sprites/icons/thumb-down.png"
            srcset="/ds/sprites/icons/thumb-down@2x.png 2x" width="20" height="20" alt="" draggable="false" /></button>
          ${tools && html`<button class="gui-out__act is-tool" onClick=${tool}
            title=${`${say("Settings")} · ${say("AI tool")}: ${o.scheme} · ${say("press to change it (from its next run)")}`}
            aria-label=${say("Its settings: AI tool and model")}><img class="ok-sprite" src="/ds/sprites/icons/settings.png"
            srcset="/ds/sprites/icons/settings@2x.png 2x" width="20" height="20" alt="" draggable="false" /></button>`}`}</span>`
    : null;
  const at = cls("gui-out", { [`is-${place}`]: true, "is-asking": asking, "is-step": walking });
  if (asking) {
    return html`<button class=${at} title=${`${who}: ${b.alert.title}`} aria-label=${`${say("Answer")} ${who}`}
        onPointerDown=${stop} onClick=${(e) => { stop(e); openOrders(b.alert.id); }}>${bubble}${body}</button>`;
  }
  return html`<span class=${at} title=${visiting ? `${who} · ${say("visiting")}` : who}>${bubble}${body}</span>`;
}

/** The dialogs a bubble opens: a 👎's note, the model dialog of a pipeline or of one tool with no other ready. */
export function VisitDialogs() {
  const d = visitDialog.value;
  if (!d) return null;
  const close = () => { visitDialog.value = null; };
  if (d.kind === "dislike") return html`<${DislikeDialog} b=${d.b} onClose=${close} onDone=${() => {}} />`;
  if (d.kind === "ork-bad") {
    return html`<${NoteDialog} title=${say(`Bad work — ${d.o.name}`)} onClose=${close}
      onSend=${(note) => command("ork.dislike", { id: d.b.id, ork: d.o.ref, note }).then(close, () => {})} />`;
  }
  return html`<${ModelDialog} b=${d.b} i=${d.i} onClose=${close} onDone=${() => {}} />`;
}
