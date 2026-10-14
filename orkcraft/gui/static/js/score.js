// The score in the HUD (docs/design/the-score.md §2, decisions-2026-10.md §13.5): the wood (tokens) per accepted result
// this week — a cart passed at the Review gate, a task done — with its trend against last week, and the quality guard
// beside it (👎 and send-backs per result), so a cheaper week with worse work never reads as a win. Quiet: a calm
// colour, never louder than 🔥 or ❓. A number the town has not recorded says so. Both looks, the same words.
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { tokensWord } from "./camp/waybill.js";

const pct = (x) => `${Math.abs(Math.round(x * 100))} %`;
const one = (x) => (x === null || x === undefined ? "—" : x < 0.1 && x > 0 ? x.toFixed(2) : x.toFixed(1));

export function ScoreHud({ s }) {
  if (!s) return null;
  const has = s.tokens !== null && s.tokens !== undefined;
  const arrow = s.trend === null || s.trend === undefined ? "" : s.trend < 0 ? "↓" : s.trend > 0 ? "↑" : "→";
  const title = !s.results ? say("Cost per accepted result: no result accepted this week yet")
    : !has ? say(`${s.results} results this week; their tokens were not recorded`)
    : say(`Tokens per accepted result this week: ${tokensWord(Math.round(s.tokens))} over ${s.recorded} results`
      + (s.trend !== null ? `, ${pct(s.trend)} ${s.trend < 0 ? "less" : "more"} than last week` : ", no last week to compare")
      + (s.cost !== null ? ` · $${s.cost.toFixed(2)} per result` : ""));
  const guard = say(`Quality: 👎 ${one(s.dislikes)} and ${one(s.reworks)} sent back per result`
    + (s.guard === "worse" ? ", more than last week" : s.guard === "steady" ? ", not more than last week" : ""));
  return html`<span class=${cls("ok-res gui-score", { "is-lean": !!s.lean, "is-worse": s.guard === "worse" })} title=${title}
      aria-label=${title}>
    <span class="ok-word">${say("per result")}</span>${has ? tokensWord(Math.round(s.tokens)) : "—"}
    ${arrow && html`<span class=${cls("gui-score__trend", { "is-down": s.trend < 0, "is-up": s.trend > 0 })}>${arrow}${pct(s.trend)}</span>`}
    <span class="gui-score__guard" title=${guard} aria-label=${guard}>👎 ${one(s.dislikes)} · ↺ ${one(s.reworks)}</span>
  </span>`;
}
