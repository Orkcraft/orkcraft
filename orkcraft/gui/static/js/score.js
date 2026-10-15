// The score in the HUD (docs/design/the-score.md §2, decisions-2026-10.md §13.5): the wood (tokens) per accepted result
// this week — a cart passed at the Review gate, a task done — with its trend against last week, and the quality guard
// beside it (👎 and send-backs per result), so a cheaper week with worse work never reads as a win. Quiet: a calm
// colour, never louder than 🔥 or ❓. Only what the town recorded is shown; a part never recorded is left out and the
// hint says what is not measured yet. Both looks, the same words.
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { tokensWord } from "./camp/waybill.js";

const pct = (x) => `${Math.abs(Math.round(x * 100))} %`;
const one = (x) => (!x ? "0" : x < 0.1 ? x.toFixed(2) : x.toFixed(1));
const known = (x) => x !== null && x !== undefined;

export function ScoreHud({ s }) {
  if (!s) return null;
  const has = known(s.tokens), trend = known(s.trend), guarded = s.results > 0;
  const missing = [!s.results && "no result accepted this week yet", s.results && !has && "the tokens of this week's results",
    has && !trend && "last week, to compare with", "a cart's share of the window"].filter(Boolean);
  const title = say((has ? `Tokens per accepted result this week: ${tokensWord(Math.round(s.tokens))} over ${s.recorded} results`
      + (trend ? `, ${pct(s.trend)} ${s.trend < 0 ? "less" : "more"} than last week` : "")
      + (known(s.cost) ? ` · $${s.cost.toFixed(2)} per result` : "") + ". " : "Cost per accepted result. ")
    + `Not measured yet: ${missing.join("; ")}.`);
  const guard = guarded ? say(`Quality: 👎 ${one(s.dislikes)} and ${one(s.reworks)} sent back per result`
    + (s.guard === "worse" ? ", more than last week" : s.guard === "steady" ? ", not more than last week" : "")) : "";
  return html`<span class=${cls("ok-res gui-score kit-well", { "is-lean": !!s.lean, "is-worse": s.guard === "worse", "is-empty": !has })}
      title=${title} aria-label=${title}>
    <span class="ok-word">${say("per result")}</span>${has ? tokensWord(Math.round(s.tokens)) : ""}
    ${trend && html`<span class=${cls("gui-score__trend", { "is-down": s.trend < 0, "is-up": s.trend > 0 })}>${s.trend < 0 ? "↓" : s.trend > 0 ? "↑" : "→"}${Math.abs(Math.round(s.trend * 100))}%</span>`}
    ${guarded && html`<span class="gui-score__guard" title=${guard} aria-label=${guard}>👎${one(s.dislikes)} ↺${one(s.reworks)}</span>`}
  </span>`;
}
