// The steward's console, for a building with no ork of its own at work (decisions-2026-10.md §13.1: a click on an ork
// opens its terminal): what the building does, what it is doing now, its runs this week and their spend, its quick
// actions — from what the host already keeps (`info`, gui/info.py) and the snapshot. What is not known says so: a
// building whose work is code or road rules has no session of its own to show.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html } from "../html.js";
import { command, say, town } from "../link.js";
import { runQuick } from "../types.js";
import { openBuilding } from "../windows.js";
import { closeConsole } from "../orkconsole.js";
import { statusLines } from "./steward.js";

export const stewardOf = signal(null);     // the building whose steward's console is open

export function openStewardConsole(id) {
  closeConsole();
  stewardOf.value = id;
}

export function StewardConsole() {
  const id = stewardOf.value;
  const b = id && town.value && town.value.buildings.find((x) => x.id === id);
  const [d, setD] = useState(undefined);
  useEffect(() => {
    if (!id) return undefined;
    let live = true;
    setD(undefined);
    command("info", { id }).then((x) => { if (live) setD(x || null); }, () => { if (live) setD(null); });
    const key = (e) => { if (e.key === "Escape") { e.stopImmediatePropagation(); stewardOf.value = null; } };
    window.addEventListener("keydown", key, true);
    return () => { live = false; window.removeEventListener("keydown", key, true); };
  }, [id]);
  if (!b) return null;
  const close = () => { stewardOf.value = null; };
  const week = d && d.week;
  const code = d && d.script_first && d.script_first.on;
  return html`<section class="gui-camp__waybill gui-camp__steward" role="dialog" aria-label=${say(`${b.ork_name}: its console`)}
      onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => e.stopPropagation()}>
    <header class="gui-camp__waybill-head">
      <b>${say(`${b.ork_name || "Steward"} · ${b.title}`)}</b>
      <button type="button" class="gui-toolerr__close" title=${say("Close")} aria-label=${say("Close")} onClick=${close}>×</button>
    </header>
    ${d === undefined ? html`<p class="ok-tone-muted">${say("Opening…")}</p>` : html`
      ${d && d.about_plain && html`<p>${say(d.about_plain)}</p>`}
      <p><b>${say("Now")}:</b> ${statusLines(b).join(" · ")}</p>
      <p><b>${say("This week")}:</b> ${week ? say(`${week.runs} runs · ✓${week.ok} ✖${week.failed} · ${week.results} results`) : html`<span class="ok-tone-muted">${say("not known")}</span>`}
        ${d && d.spend_plain ? html` · ${say(d.spend_plain)}` : ""}</p>
      <p class="ok-tone-muted">${say(code ? "Its work is code: no ork session runs here unless it wakes on an error or a 👎, so there is no terminal to show."
        : "No ork of its own is at work here now: there is no session or terminal to show.")}</p>
      <div class="gui-camp__scroll-acts">
        ${(b.quick || []).map((a) => html`<button key=${a.id} type="button" class="ok-btn" onClick=${() => runQuick(b, a.id)}>${say(a.label)}</button>`)}
        <button type="button" class="ok-btn primary" onClick=${() => { close(); openBuilding(b.id); }}>${say("Enter")}</button>
      </div>`}
  </section>`;
}
