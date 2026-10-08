// 📍 Places, in the Watchtower's Sources & intent (docs/design/phone-places.md §5–§6): the names a paired phone
// reports, each with how freely its news is acted on, how long a late report stays news and what its cart says;
// how many days this machine keeps what the phones said, and Clear. Where a place is lives on the phone only:
// here it is a name. The roads: a place's arrived and left each take a road of their own (a stub on the map).
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";

const LEVELS = [["chains", "Propose only"], ["clock", "Apply if unanswered"], ["free", "Apply at once"]];
const HELP = {
  chains: "asks in Answers; nothing starts until you say Send",
  clock: "asks in Answers; goes by itself after 10 minutes unless you say Skip",
  free: "goes down its road at once",
};
const OUTCOME = { sent: "sent", asked: "asked in Answers", waiting: "asked, goes by itself", refused: "skipped",
  stale: "too late, not sent", "no road": "no road takes it" };

const blank = () => ({ name: "", autonomy: "chains", shelf_h: 2, say: "" });

export function Places({ id, p }) {
  const [rows, setRows] = useState(p.places);
  const [days, setDays] = useState(p.keep_days);
  const [error, setError] = useState("");
  useEffect(() => { setRows(p.places); setDays(p.keep_days); }, [JSON.stringify(p.places), p.keep_days]);
  const edit = (i, change) => setRows(rows.map((r, j) => (j === i ? { ...r, ...change } : r)));
  const dirty = JSON.stringify(rows) !== JSON.stringify(p.places) || Number(days) !== p.keep_days;
  const save = () => act(id, "places_save", { places: rows.filter((r) => r.name.trim()), keep_days: Number(days) })
    .then(() => setError(""), (e) => setError(String(e.message || e)));
  return html`<div class="gui-tower__places">
    <div class="gui-head"><p class="ok-list__head" style="flex: 1">${say("Places")} · ${p.places.length}</p>
      ${p.waiting > 0 && html`<span class="ok-tone-fire">${p.waiting} ${say("waiting in Answers")}</span>`}</div>
    <p class="ok-tone-muted gui-tower__note">${say("A paired phone says when it comes to a place or leaves it. Where a place is stays on the phone: here it is only a name. A place's news never reaches a model: its cart says only what you write below.")}</p>
    <ul class="gui-tower__sources">
      ${rows.map((r, i) => html`<li key=${i} class="gui-tower__place">
        <input class="ok-input gui-tower__place-name" placeholder="home" value=${r.name} aria-label=${say("Name")}
          onInput=${(e) => edit(i, { name: e.target.value })} />
        <select class="ok-input" value=${r.autonomy} aria-label=${say("Autonomy")} title=${say(HELP[r.autonomy])}
          onChange=${(e) => edit(i, { autonomy: e.target.value })}>
          ${LEVELS.map(([v, label]) => html`<option key=${v} value=${v}>${label}</option>`)}</select>
        <label class="gui-tower__shelf" title=${say("A report older than this is kept, but sends nothing")}>
          ${say("news for")} <input class="ok-input" type="number" min="0.25" max="48" step="0.25" value=${r.shelf_h}
            onInput=${(e) => edit(i, { shelf_h: Number(e.target.value) })} /> h</label>
        <button class="ok-btn" title=${say("Remove this place")} onClick=${() => setRows(rows.filter((_, j) => j !== i))}>✕</button>
        <input class="ok-input gui-tower__place-say" placeholder=${say("What its cart says, e.g. You may start the evening's work.")}
          value=${r.say || ""} aria-label=${say("What its cart says")} onInput=${(e) => edit(i, { say: e.target.value })} />
        ${p.places[i] && p.places[i].name === r.name && html`<span class="ok-tone-muted gui-tower__place-roads">
          ${["arrived", "left"].map((c) => html`<span key=${c} class=${cls("", { "ok-tone-ok": p.places[i].roads.includes(c) })}>
            ${r.name} · ${c}: ${p.places[i].roads.includes(c) ? say("a road takes it") : say("no road yet: pull one from its stub on the map")}</span>`)}
        </span>`}
      </li>`)}
      ${!rows.length && html`<li class="ok-item ok-tone-muted">${say("No place yet.")}</li>`}
    </ul>
    <div class="gui-head">
      <button class="ok-btn" disabled=${rows.length >= 10} onClick=${() => setRows([...rows, blank()])}>+ ${say("Place")}</button>
      <label class="gui-tower__shelf">${say("History kept for")}
        <input class="ok-input" type="number" min="1" max="365" value=${days} onInput=${(e) => setDays(e.target.value)} /> ${say("days, on this machine only")}</label>
      <button class="ok-btn primary" disabled=${!dirty} onClick=${save}>${say("Save")}</button>
    </div>
    ${error && html`<p class="ok-tone-error" role="alert">✗ ${error}</p>`}
    ${p.history.length > 0 && html`<div class="gui-head"><p class="ok-list__head" style="flex: 1">${say("What the phones said")}</p>
      <button class="ok-btn" onClick=${() => act(id, "places_clear").catch(() => {})}>${say("Clear history")}</button></div>
      <ul class="gui-tower__heard">${p.history.map((h, i) => html`<li key=${i}>
        <span class="gui-tower__at">${h.at.slice(5)}</span>
        <span><b>${h.place}</b> · ${h.change} · ${h.device || say("a phone")}</span>
        <span class="ok-tone-muted">${say(OUTCOME[h.outcome] || h.outcome)}</span></li>`)}</ul>`}
  </div>`;
}
