// Changing the town: Build (the Warchief asked, or a building raised from the catalog), laying a road
// between two buildings and taking one up. The acts are the core's (gui/builder.py); the dialogs are the page's.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { HutSprite, activeBiome } from "./icons.js";
import { Dialog } from "./dialog.js";
import { HandlerDialog } from "./acts.js";
import { closeBuilding } from "./windows.js";

export const building = signal(false);            // the Build dialog is open: true, or {hut: [x, y], need}
export const laying = signal(null);                // {from, to}: a road waits for what it carries
export const pickedRoad = signal(null);            // the road key the person clicked
export const demolishing = signal(null);           // the building id a Demolish dialog asks about
export const settingUp = signal(null);             // {id, type, service}: just raised, its setup asked in the Warchief's line
export const placing = signal(null);               // {type, title, bare, service}: picked in Build, its ghost under the mouse
export const constructing = signal({});            // building id → until when its scaffolding stands (Infinity: its setup)
export const built = signal(new Set());            // the buildings that just came up: they rise into place once
const RAISE_MS = 1600;                             // a building with no questions: its construction, then it stands

// Build, as a strategy game does it (docs/design/select-a-building.md §8): pick a building, place its ghost with the
// mouse, it goes up under scaffolding while the Warchief asks its setup (if its type has one), then it stands.

/** Picked in Build: its ghost follows the mouse until a press places it (js/town.js), Escape lets it go. */
export function place(t, service = "") {
  placing.value = { type: t.id, title: t.title, bare: false, service };
  import(`./buildings/${t.id}.js`).then((m) => {
    if (placing.value && placing.value.type === t.id) placing.value = { ...placing.value, bare: !!m.bare };
  }, () => {});
}

function stands(id) {
  const { [id]: _, ...rest } = constructing.value;
  constructing.value = rest;
  built.value = new Set([...built.value, id]);
  setTimeout(() => { const s = new Set(built.value); s.delete(id); built.value = s; }, 1200);
}

/** The setup in the Warchief's line is over (answered, Later, or put away): the building stands. */
export function endSetup() {
  const s = settingUp.value;
  settingUp.value = null;
  if (s && constructing.value[s.id] !== undefined) stands(s.id);
}

/** A building just raised: it goes up under scaffolding; a type with a `Setup` of its own (js/types.js) is set up
 *  in the Warchief's line meanwhile (docs/design/select-a-building.md §7–8), and stands when that is over; any other
 *  stands after a moment. */
export function raised(id, type, service = "") {
  if (!id) return;
  constructing.value = { ...constructing.value, [id]: Infinity };
  const plain = () => {
    constructing.value = { ...constructing.value, [id]: Date.now() + RAISE_MS };
    setTimeout(() => stands(id), RAISE_MS);
  };
  import(`./buildings/${type}.js`).then((m) => { if (m.Setup) settingUp.value = { id, type, service }; else plain(); }, plain);
}

// Build is a row of small icons the Warchief's line grows upward (docs/design/warchief-line-and-cards.md §2): each says
// what you want done — mail, Slack, Jira, tasks, a calendar — not which house does it (tools/intent_sprites.py). The
// line's own field filters it while Build is on (js/warchief.js), Enter takes the first icon left or, with none, asks
// the Warchief what to build. One line over the row says what the icon under the mouse raises. First three for you
// (the onboarding's role's own, not standing yet), then the rest in the catalog's groups, a thin rule between them.
// A press picks one and its ghost follows the mouse (`place`), a double press builds it at a free spot; from the
// map's menu (*Build here*) a press builds it on that spot. A source's icon (mail, Slack, Jira, Confluence) raises
// External listeners already listening to it when Claude has a connector for it (js/buildings/watchtower.js `Setup`).
export const INTENTS = [
  { id: "mail", word: "Mail", type: "watchtower", service: "gmail" },
  { id: "chat", word: "Slack", type: "watchtower", service: "slack" },
  { id: "tickets", word: "Jira", type: "watchtower", service: "jira" },
  { id: "pages", word: "Confluence", type: "watchtower", service: "confluence" },
  { id: "drop", word: "Drop files", type: "pit" },
  { id: "tasks", word: "Tasks", type: "fields" },
  { id: "calendar", word: "Calendar", type: "war_drum" },
  { id: "agents", word: "Agents", type: "barracks" },
  { id: "review", word: "Review", type: "council" },
  { id: "wiki", word: "Wiki", type: "scrolls" },
  { id: "research", word: "Research", type: "mine" },
  { id: "listen", word: "Listen", type: "gramophone" },
  { id: "code", word: "Code", type: "forge" },
  { id: "check", word: "Check", type: "loot" },
  { id: "send", word: "Send", type: "catapult" },
  { id: "route", word: "Route", type: "signpost" },
  { id: "transform", word: "Transform", type: "mill" },
  { id: "chart", word: "Chart", type: "crag" },
  { id: "sound", word: "Sound", type: "horn" },
];
const FOR_YOU = 3;
const DOUBLE_MS = 240;                             // a second press within this builds at a free spot
const SOURCE_OF = { mail: "gmail", gmail: "gmail", slack: "slack", jira: "jira", confluence: "confluence" };

const norm = (s) => say(s || "").toLowerCase();

/** The tray's icons: one per intent whose building the catalog has (a type with none keeps one under its name). */
function tilesOf(types) {
  const byType = Object.fromEntries(types.map((t) => [t.id, t]));
  const tiles = INTENTS.filter((i) => byType[i.type]).map((i) => ({ ...i, t: byType[i.type] }));
  const covered = new Set(tiles.map((x) => x.type));
  for (const t of types) if (!covered.has(t.id)) tiles.push({ id: t.id, word: t.title, type: t.id, t, house: true });
  const order = Object.fromEntries(types.map((t, n) => [t.id, n]));      // the catalog's groups, in their order
  return tiles.map((x, n) => ({ ...x, n })).sort((a, b) => order[a.type] - order[b.type] || a.n - b.n);
}

/** The icons the words find: by their own word first ("mail" is Mail, not every source of External listeners),
 *  else by their building's name, summary, group and what it sends. */
function found(tiles, q) {
  if (!q) return tiles;
  const own = tiles.filter((x) => [x.word, x.id, x.service].some((w) => norm(w).includes(q)));
  if (own.length) return own;
  return tiles.filter(({ t }) => [t.title, t.summary, t.intent, t.id, ...(t.sends || [])].some((w) => norm(w).includes(q)));
}

/** Its first three for the role: its buildings not standing yet, a source the role reads for External listeners. */
function forYou(tiles, standing) {
  const sources = ((tiles.find((x) => x.type === "watchtower") || {}).t || {}).role_sources || [];
  const want = sources.map((w) => SOURCE_OF[w]).find(Boolean) || "gmail";
  return tiles.filter((x) => x.t.yours >= 0 && !standing.has(x.type) && (x.type !== "watchtower" || x.service === want))
    .sort((a, b) => a.t.yours - b.t.yours).slice(0, FOR_YOU);
}

let enter = null;                                  // what Enter in the line does while the row stands

/** Enter in the Warchief's line while Build is on: the first icon left is picked; false when none is left. */
export function buildEnter() {
  return enter ? enter() : false;
}

/** The row over the Warchief's line: `query` is the line's text. */
export function BuildRow({ query }) {
  const [types, setTypes] = useState(null);
  const [over, setOver] = useState(null);         // the icon under the mouse: the line over the row says it
  const timer = useRef(null);
  useEffect(() => { if (types === null) command("town.catalog").then(setTypes, () => setTypes([])); }, []);
  useEffect(() => {                              // Escape from anywhere puts it away (the field's own does too)
    const key = (e) => { if (e.key === "Escape" && !document.querySelector(".gui-modal")) building.value = false; };
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("keydown", key); enter = null; };
  }, []);
  const hut = building.value && building.value.hut;
  const close = () => { building.value = false; };
  const raise = (x, spot) => command("town.build", spot ? { type: x.type, hut: spot } : { type: x.type })
    .then((id) => { close(); raised(id, x.type, x.service); }, () => {});
  const pick = (x) => { if (hut) raise(x, hut); else { close(); place(x.t, x.service); } };   // a spot given: built there
  const press = (x) => {
    if (hut) { raise(x, hut); return; }
    if (timer.current) { clearTimeout(timer.current); timer.current = null; raise(x); return; }   // twice: a free spot
    timer.current = setTimeout(() => { timer.current = null; pick(x); }, DOUBLE_MS);
  };
  const tiles = tilesOf(types || []);
  const shown = found(tiles, norm((query || "").trim()));
  const yours = query && query.trim() ? [] : forYou(shown, new Set(town.value.buildings.map((b) => b.type)));
  const row = [...yours, ...shown.filter((x) => !yours.includes(x))];
  enter = () => { if (!row.length) return false; pick(row[0]); return true; };
  const biome = activeBiome();
  const said = over ? `${say(over.word)} — ${say(over.t.title)}: ${over.t.summary}`
    : types === null ? say("Looking…")
    : !row.length ? say("Nothing by that name — Enter asks the Warchief what to build.")
    : yours.length ? say(`For you: ${yours.map((x) => x.word).join(", ")}. ${hut ? "A press builds it here." : "A press places it; twice builds it at a free spot."}`)
    : say(hut ? "A press builds it here." : "A press places it; a double press builds it at a free spot.");
  return html`<div class="gui-build" role="group" aria-label=${say("Build")} onMouseDown=${(e) => e.preventDefault()}>
    <p class="ok-font-status ok-tone-muted gui-build__said" title=${said}>${said}</p>
    <div class="gui-build__row" onMouseLeave=${() => setOver(null)}>
      ${row.map((x, n) => html`<button key=${x.id} class=${cls("gui-catalog__item gui-build__tile", {
          "is-yours": yours.includes(x), "is-first": n > 0 && !yours.includes(x) && (yours.includes(row[n - 1]) || row[n - 1].t.intent !== x.t.intent) })}
          data-type=${x.type} data-intent=${x.id} aria-label=${`${say(x.word)}: ${say(x.t.title)}`} title=${say(x.word)}
          onMouseEnter=${() => setOver(x)} onFocus=${() => setOver(x)} onClick=${() => press(x)}>
        ${x.house ? html`<${HutSprite} type=${x.type} biome=${biome} />`
          : html`<img class="ok-sprite" src=${`/ds/sprites/intents/${x.id}.png`} srcset=${`/ds/sprites/intents/${x.id}@2x.png 2x`}
              width="32" height="32" alt="" draggable="false" />`}
        <span class="gui-build__word">${say(x.word)}</span></button>`)}
    </div>
  </div>`;
}

/** A road in words, both ways in: + Listen on the receiver ({to, among}: the steward picks the source) and an
 *  arrow drawn from one building to another ({from, to}). Say what it should listen to and what to do with
 *  it — the steward offers roads (gui/road_planner.py, a job); picking by hand waits folded below. */
export function RoadDialog() {
  const pair = laying.value;
  const [choices, setChoices] = useState(null);
  const [words, setWords] = useState("");
  useEffect(() => {
    setChoices(null);
    if (pair && pair.from) command("roads.choices", { from: pair.from, to: pair.to }).then(setChoices, () => setChoices([]));
  }, [pair && pair.from, pair && pair.to]);
  const shownFor = useRef(null);       // cleared when the dialog closes or turns to another building, never as it
  useEffect(() => {                    // opens: an effect run late would wipe the first words typed
    const to = (pair && pair.to) || null;
    if (shownFor.current && shownFor.current !== to) setWords("");
    shownFor.current = to;
  }, [pair && pair.to]);
  if (!pair) return null;
  const close = () => { laying.value = null; };
  const titles = Object.fromEntries(town.value.buildings.map((b) => [b.id, say(b.title)]));
  const lay = (c) => command("roads.lay", { from: pair.from, to: pair.to, event: c.event, handler: c.handler })
    .then(close, () => {});
  const find = () => words.trim() && command("roads.plan", { to: pair.to, from: pair.from || "", prompt: words.trim(),
    among: pair.among || null }).then(close, () => {});
  const sources = (pair.among || []).filter((id) => id !== pair.to && titles[id]);
  const title = pair.from ? `${say("Road")}: ${titles[pair.from]} → ${titles[pair.to]}` : say(`Listen — ${titles[pair.to]}`);
  return html`<${Dialog} title=${title} text=${pair.from ? say("What should the road carry, and what should happen to it?")
      : say("What should it listen to, and what should happen to it?")} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!words.trim()} onClick=${find}>Find the road</button>`}>
    <textarea class="ok-input gui-textarea" rows="3" autofocus value=${words} onInput=${(e) => setWords(e.target.value)}
      onKeyDown=${(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && find()}
      placeholder=${say("e.g. listen to unread messages and make to-dos of them")}></textarea>
    <details class="gui-road__manual">
      <summary class="ok-font-label ok-tone-muted">${pair.from ? "Pick the event by hand" : "Pick the building by hand"}</summary>
      ${!pair.from ? html`<ul class="gui-catalog">${sources.map((id) => html`<li key=${id} class="gui-catalog__item"
          onClick=${() => { laying.value = { ...pair, from: id }; }}><b>${titles[id]}</b></li>`)}</ul>`
      : choices === null ? html`<p class="ok-tone-muted">Looking…</p>`
      : !choices.length ? html`<p class="ok-tone-muted">${say("No plain road fits")} from ${titles[pair.from]} to ${titles[pair.to]}.
          Describe it above: an ork will handle it by a rule.</p>`
      : html`<div class="gui-orders__options">${choices.map((c) => html`<button key=${c.event + (c.handler || "")}
          class="ok-btn" onClick=${() => lay(c)}>${c.label}</button>`)}</div>`}
    </details>
  </${Dialog}>`;
}

/** The road the person clicked: every road from one building into the same other one is one road
 *  (js/town.js together), so its card lists each of them — what it carries, its handler, taking it up —
 *  and lays another between them (the TUI's road console: H, U; docs/design/road-sound.md §2). */
export function RoadBar() {
  const key = pickedRoad.value;
  const t = town.value;
  const [handling, setHandling] = useState(null);
  const road = key && t.roads.find((r) => r.id === key);
  if (!road) return null;
  const titles = Object.fromEntries(t.buildings.map((b) => [b.id, say(b.title)]));
  const name = (id) => titles[id] || id;
  const group = t.roads.filter((r) => r.from === road.from && r.to === road.to);
  const remove = (r) => command("roads.remove", { key: r.id })
    .then(() => { if (group.length === 1 || r.id === key) pickedRoad.value = group.find((x) => x.id !== r.id)?.id || null; }, () => {});
  return html`<div class="gui-roadbar ok-toast">
    <div class="gui-roadbar__head">
      <span><b>${name(road.from)}</b> → <b>${name(road.to)}</b>${group.length > 1 ? html` <span class="ok-tone-muted">· ${group.length} ${say("events")}</span>` : ""}</span>
      <button class="ok-act" title=${say("Lay another road between these two buildings")}
        onClick=${() => { laying.value = { from: road.from, to: road.to }; }}><span class="ok-act__label">${say("Add an event")}</span></button>
      <button class="ok-act" onClick=${() => { pickedRoad.value = null; }}><span class="ok-act__label">Close</span></button>
    </div>
    <ul class="gui-roadbar__list">${group.map((r) => html`<li key=${r.id} class="gui-roadbar__row">
      <span class="gui-roadbar__what">${r.label}${r.handler ? html`<span class="ok-tone-muted"> · ${r.handler}</span>` : ""}</span>
      <button class="ok-act" onClick=${() => setHandling(r)}><span class="ok-act__label">${say("Handler")}</span></button>
      <button class="ok-act" onClick=${() => remove(r)}><span class="ok-act__label">Remove</span></button>
    </li>`)}</ul>
  </div>
  ${handling && html`<${HandlerDialog} road=${{ key: handling.id, title: name(handling.from), label: handling.label }}
    onClose=${() => setHandling(null)} onDone=${() => {}} />`}`;
}

/** Demolish asked from the hut's menu or the Warchief's line. */
export function DemolishAsked() {
  const id = demolishing.value;
  const b = id && town.value.buildings.find((x) => x.id === id);
  if (!b) return null;
  return html`<${Demolish} b=${b} onClose=${() => { demolishing.value = null; }} />`;
}

export function Demolish({ b, onClose }) {
  return html`<${Dialog} title=${`Demolish ${say(b.title)}?`} warn onCancel=${onClose}
      text=${say("It leaves the town and stops its work; its settings and chronicle stay, and git keeps the rest.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn danger" onClick=${() => command("town.demolish", { id: b.id }).then(() => { onClose(); closeBuilding(b.id); }, () => {})}>Demolish</button>`} />`;
}
