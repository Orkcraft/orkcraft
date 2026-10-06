// 🌾 Task Fields: one board, three parts (design-system/components.md: TaskFields) — the orks' tasks as
// lanes of cards (a kanban), the person's own to-dos (a checklist) and the notes (ideas, questions) in
// lanes of their own. The mouse does it all: drag a card to another lane or part, click it to select
// it, double-click it to open it; the selected card's acts sit over the board; a to-do is ticked off
// by its box. The Command Card shows a small board: the status lanes with their top cards (a drag
// works there too), the open to-dos and the lanes of notes folded to counters. The closed card shows
// all three parts at a glance; a checkbox over them hides any one (js/parts.js). The worker writes the
// board file (core/workers/fields.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, details } from "../link.js";
import { Dialog } from "../dialog.js";
import { PartToggles, shown, hidden } from "../parts.js";

const selected = signal({});       // building id → card id
const asking = signal(null);       // {id, lane, kind}: a New task / note / chore asked from the Command Card
const TOP = 3;                     // cards a lane shows in the Command Card
// The closed card's three parts, each one the person may hide (js/parts.js).
const PARTS = [{ key: "work", label: "Ork work" }, { key: "chores", label: "My chores" }, { key: "scribbles", label: "Scribbles" }];

// Every rule is this building's own: the closed card (`.gui-fhut`, and the hut that holds one) stands
// larger than other huts — about a fifth of the window high — so its three parts read at a glance.
const CSS = `
.gui-town__room > .gui-hut.ok-hut[class]:has(.gui-fhut) { width: clamp(340px, 26vw, 460px); max-width: none; }
.gui-hut .ok-hut__card:has(.gui-fhut:not(.is-folded)) { min-height: 20vh; box-sizing: border-box; }
.gui-hut__body:has(> .gui-fhut) { flex: 1 1 auto; display: flex; }
.gui-fhut { flex: 1 1 auto; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-content: start;
  gap: var(--space-2) var(--space-3); min-width: 0; }
.gui-fhut > .gui-parts { grid-column: 1 / -1; }
.gui-fhut__part { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.gui-fhut__part--work { grid-column: 1 / -1; }
.gui-fhut__part--solo { grid-column: 1 / -1; }
.gui-fhut__head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 var(--space-2); }
.gui-fhut__item { min-width: 0; overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
  overflow-wrap: anywhere; }
.gui-fhut__mark { color: var(--ink-muted); margin-right: 4px; }
.gui-fields--mini .ok-lane { min-height: 0; }
.gui-fields--mini .ok-card { padding: var(--space-1) var(--space-2); }
.gui-fields--mini .ok-card__title > span:not(.ok-word) { min-width: 0; overflow-wrap: anywhere; }
.gui-fields--mini .ok-card__title > .ok-word { flex: none; }
.gui-counters__notes { flex-basis: 100%; }
.gui-fields__folded { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.gui-fields__folded .ok-chip.gui-drop { box-shadow: inset 0 0 0 1px var(--frame-focus); }
.gui-fields__part { display: flex; flex-direction: column; gap: var(--space-1); min-width: 0; }
.gui-fields__part > h3 { margin: 0; }
.gui-fields__lower { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(0, 2fr); gap: var(--space-3); align-items: start; }
.gui-fields--mini .gui-fields__lower { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-2); }
.gui-todos { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: 2px;
  background: var(--panel-inset); box-shadow: var(--bevel-sunken); min-height: 40px; }
.gui-todos.gui-drop { box-shadow: inset 0 0 0 1px var(--frame-focus); }
.gui-todo { display: flex; align-items: flex-start; gap: var(--space-2); padding: 2px var(--space-1); cursor: grab; }
.gui-todo:hover, .gui-todo.is-selected { background: var(--selection); }
.gui-todo .ok-check { flex: none; padding-top: 2px; }
.gui-todo__title { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; }
.gui-todo.is-done .gui-todo__title { text-decoration: line-through; color: var(--ink-muted); }
.gui-todo__add { display: flex; gap: var(--space-1); }
.gui-fields--mini .gui-todos { padding: var(--space-1); min-height: 0; }
.gui-fields--mini .gui-todo { font-size: 12px; line-height: 16px; padding: 1px 2px; }
.gui-fields--mini .gui-todo .ok-check { padding-top: 0; }
.gui-todo__add .ok-input { flex: 1 1 auto; min-width: 0; }
`;
if (typeof document !== "undefined" && !document.getElementById("gui-css-fields")) {
  const style = document.createElement("style");
  style.id = "gui-css-fields";
  style.textContent = CSS;
  document.head.append(style);
}

/** A card dragged onto a lane (a folded lane, the checklist) moves there. */
function useDrop(id, laneId) {
  const [over, setOver] = useState(false);
  return [over, {
    onDragOver: (e) => { if (e.dataTransfer.types.includes("text/x-ork-card")) { e.preventDefault(); setOver(true); } },
    onDragLeave: () => setOver(false),
    onDrop: (e) => {
      e.preventDefault(); setOver(false);
      const card = e.dataTransfer.getData("text/x-ork-card");
      if (card) act(id, "move", { card, lane: laneId }).catch(() => {});
    },
  }];
}

const dragCard = (cardId) => (e) => { e.dataTransfer.setData("text/x-ork-card", cardId); e.dataTransfer.effectAllowed = "move"; };

function CardDialog({ id, card, lane, onClose }) {
  const [title, setTitle] = useState(card ? card.title : "");
  const [body, setBody] = useState(card ? card.body : "");
  const kind = card ? card.kind : lane.kind;
  const what = kind === "task" ? "task" : kind === "mine" ? "chore" : "note";
  const head = card ? what[0].toUpperCase() + what.slice(1) : `New ${what}`;
  function keep() {
    const call = card ? act(id, "edit", { card: card.id, title, body }) : act(id, "add", { lane: lane.id, title, body });
    call.then((kept) => {
      if (kept) selected.value = { ...selected.value, [id]: kept };     // a card's id follows its title
      onClose();
    }, () => {});
  }
  return html`<${Dialog} title=${say(card ? `${head} · ${card.title}` : `${head} · ${lane.label}`)} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!title.trim()} onClick=${keep}>${card ? "Keep it" : "Add it"}</button>`}>
    <p class="ok-dialog__section">Title</p>
    <input class="ok-input" value=${title} autofocus onInput=${(e) => setTitle(e.target.value)}
      onKeyDown=${(e) => e.key === "Enter" && title.trim() && keep()} />
    <p class="ok-dialog__section">Text</p>
    <textarea class="ok-input gui-textarea" rows="6" value=${body} onInput=${(e) => setBody(e.target.value)}></textarea>
  </${Dialog}>`;
}

function Confirm({ title, text, yes, onYes, onClose }) {
  return html`<${Dialog} title=${title} text=${text} warn onCancel=${onClose}
    actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
      <button class="ok-btn danger" onClick=${() => { onYes(); onClose(); }}>${yes}</button>`} />`;
}

const pick = (id, cardId) => { selected.value = { ...selected.value, [id]: cardId }; };

function Card({ id, card, isSelected, onOpen }) {
  return html`<div class=${cls("ok-card", { "is-selected": isSelected, "is-done": card.column === "done" })}
      data-color=${card.color || undefined} draggable="true" onDragStart=${dragCard(card.id)}
      onClick=${() => pick(id, card.id)} onDblClick=${() => onOpen(card)}>
    <div class="ok-card__title"><i class="ok-card__sw"></i>
      ${card.column === "done" && html`<span class="ok-card__check">✓</span>`}<span>${card.title}</span>
      ${card.new && html`<span class="ok-word gui-new"> new</span>`}</div>
    ${card.body && html`<p class="ok-card__text">${card.body}</p>`}
  </div>`;
}

function Lane({ id, lane, sel, onOpen, onAdd }) {
  const [over, drop] = useDrop(id, lane.id);
  return html`<section class=${cls("ok-lane", { "is-notes": lane.kind === "note", "gui-drop": over })} ...${drop}>
    <header class="ok-lane__head">${lane.label}<span class="ok-lane__count">${lane.cards.length}</span></header>
    ${lane.cards.map((c) => html`<${Card} key=${c.id} id=${id} card=${{ ...c, column: lane.id }} isSelected=${c.id === sel} onOpen=${onOpen} />`)}
    <button class="ok-lane__add" onClick=${() => onAdd(lane)}>+ New ${lane.kind === "task" ? "task" : "note"}</button>
  </section>`;
}

/** The person's checklist: a box ticks a to-do off, a click selects it, a double-click opens it; a card
 * dropped here becomes a to-do. `top` cuts it (the Command Card). */
function Todos({ id, todos, sel, onOpen, top }) {
  const [over, drop] = useDrop(id, todos.id);
  const [title, setTitle] = useState("");
  const cards = top ? todos.cards.filter((c) => !c.done).slice(0, top) : todos.cards;
  const add = () => {
    const t = title.trim();
    if (t) act(id, "add", { lane: todos.id, title: t }).then(() => setTitle(""), () => {});
  };
  return html`<div class="gui-fields__part">
    <ul class=${cls("gui-todos", { "gui-drop": over })} ...${drop}>
      ${cards.map((c) => html`<li key=${c.id} class=${cls("gui-todo", { "is-done": c.done, "is-selected": c.id === sel })}
          draggable="true" onDragStart=${dragCard(c.id)} onClick=${() => pick(id, c.id)} onDblClick=${() => onOpen && onOpen(c)}>
        <label class="ok-check" title=${say(c.done ? "Put it back on my chores" : "Tick it off")}
          onClick=${(e) => { e.stopPropagation(); act(id, "check", { card: c.id }).catch(() => {}); }}><i>${c.done ? "✓" : ""}</i></label>
        <span class="gui-todo__title">${c.title}${c.new ? html`<span class="ok-word gui-new"> new</span>` : ""}</span>
      </li>`)}
      ${cards.length === 0 && html`<li class="ok-tone-muted ok-font-status">${todos.cards.length ? "All done ✓" : "No chores yet"}</li>`}
      ${top && todos.cards.filter((c) => !c.done).length > top
        && html`<li class="ok-font-status ok-tone-muted">+${todos.cards.filter((c) => !c.done).length - top} more</li>`}
    </ul>
    ${!top && html`<div class="gui-todo__add">
      <input class="ok-input" placeholder=${say("A chore of my own…")} value=${title}
        onInput=${(e) => setTitle(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && add()} />
      <button class="ok-btn" disabled=${!title.trim()} onClick=${add}>Add</button></div>`}
  </div>`;
}

function FolderDialog({ id, onClose }) {
  const [name, setName] = useState("");
  const add = () => act(id, "add_lane", { name }).then((lane) => lane && onClose(), () => {});
  return html`<${Dialog} title=${say("New note folder")} text=${say("A lane of its own for notes: Ideas, Questions, For the sync…")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!name.trim()} onClick=${add}>Add it</button>`}>
    <input class="ok-input" placeholder="Ideas" value=${name} autofocus
      onInput=${(e) => setName(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && name.trim() && add()} />
  </${Dialog}>`;
}

/** The lanes of notes; a board with none yet shows an empty Ideas lane (its first note makes it). */
function noteLanes(data) {
  const notes = data.lanes.filter((ln) => ln.kind === "note");
  return notes.length ? notes : [{ id: "ideas", label: "Ideas", kind: "note", cards: [] }];
}

/** The acts of the selected card: open, colour, where it goes next (the orks, a note, my chores), send, delete. */
function Acts({ id, sel, setDialog }) {
  const a = (label, onClick) => html`<button class="ok-act" onClick=${onClick}><span class="ok-act__label">${label}</span></button>`;
  return html`<span class="gui-head__what"><b>${sel.title}</b></span>
    <span class="gui-head__spacer"></span>
    ${a("Open", () => setDialog({ card: sel }))}
    ${a("Colour", () => act(id, "color", { card: sel.id }))}
    ${sel.kind !== "task" && a("Give it to the orks", () => act(id, "flip", { card: sel.id }))}
    ${sel.kind === "task" && a("Make it a note", () => act(id, "flip", { card: sel.id }))}
    ${sel.kind !== "mine" && sel.mine && a("Make it my chore", () => act(id, "mine", { card: sel.id }))}
    ${a("Send", () => act(id, "send", { card: sel.id }))}
    ${a("Delete", () => setDialog({ remove: sel }))}`;
}

function Board({ id, data }) {
  const [dialog, setDialog] = useState(null);      // {card} | {lane} | {remove: card} | {folder: true}
  useEffect(() => { act(id, "seen").catch(() => {}); }, [id]);
  const parts = !!data.todos;                       // board mode: the three parts
  const cards = data.lanes.flatMap((ln) => ln.cards.map((c) => ({ ...c, column: ln.id })))
    .concat(parts ? data.todos.cards.map((c) => ({ ...c, column: data.todos.id })) : []);
  const found = cards.find((c) => c.id === selected.value[id]);
  const sel = found && { ...found, mine: parts };
  const close = () => setDialog(null);
  const open = (card) => setDialog({ card });
  const lanes = (list) => html`<div class="ok-board" style=${`--lanes:${list.length}`}>
      ${list.map((ln) => html`<${Lane} key=${ln.id} id=${id} lane=${ln} sel=${sel && sel.id}
        onOpen=${open} onAdd=${(lane) => setDialog({ lane })} />`)}
    </div>`;
  if (data.error) return html`<p class="ok-tone-error">⚠ ${data.error}</p>`;
  return html`<div class="gui-fields">
    <div class="gui-head">
      ${sel ? html`<${Acts} id=${id} sel=${sel} setDialog=${setDialog} />`
      : html`<span class="ok-tone-muted">Drag a card to another lane · click to select · double-click to open</span>
        <span class="gui-head__spacer"></span>`}
      <button class="ok-act" onClick=${() => setDialog({ folder: true })}><span class="ok-act__label">New note folder</span></button>
    </div>
    ${parts ? html`
      <section class="gui-fields__part"><h3 class="ok-font-heading">Ork work</h3>
        ${lanes(data.lanes.filter((ln) => ln.kind === "task"))}</section>
      <div class="gui-fields__lower">
        <section class="gui-fields__part"><h3 class="ok-font-heading">My chores</h3>
          <${Todos} id=${id} todos=${data.todos} sel=${sel && sel.id} onOpen=${open} /></section>
        <section class="gui-fields__part"><h3 class="ok-font-heading">Scribbles</h3>
          ${lanes(noteLanes(data))}</section>
      </div>` : lanes(data.lanes)}
    ${dialog && dialog.remove && html`<${Confirm} title=${`Delete “${dialog.remove.title.slice(0, 60)}”?`}
      text="It goes from the file too (git keeps it)." yes="Delete"
      onYes=${() => act(id, "remove", { card: dialog.remove.id }).catch(() => {})} onClose=${close} />`}
    ${dialog && dialog.folder && html`<${FolderDialog} id=${id} onClose=${close} />`}
    ${dialog && !dialog.remove && !dialog.folder && html`<${CardDialog} id=${id} card=${dialog.card} lane=${dialog.lane} onClose=${close} />`}
  </div>`;
}

const mark = (m, t, i) => html`<span key=${i} class="gui-fhut__item"><span class="gui-fhut__mark">${m}</span>${t}</span>`;

/** Closed: a counter per status lane, then the note folders with theirs; `*` on one with unseen cards
 * (docs/design/building-views.md). In board mode the three parts: the orks' lanes with what is in work
 * and next, the person's open to-dos, the latest notes, a checkbox over them hiding any one. In notes
 * mode only the folders. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<span class="ok-tone-fire">${c.error}</span>`;
  const counter = (l) => html`<span key=${l.label} class="gui-counter">
    <span class="ok-tone-muted">${say(l.label)}</span> <b>${l.count}</b>${l.new ? "*" : ""}</span>`;
  const notes = c.notes || [];
  if (!c.todos) {
    return html`<div class="gui-counters">${c.lanes.map(counter)}
      ${notes.length > 0 && html`<div class="gui-counters gui-counters__notes">${notes.map(counter)}</div>`}</div>`;
  }
  const doing = c.lanes.filter((l) => l.id === "in_progress").flatMap((l) => l.top.slice(0, 1));
  const next = c.lanes.filter((l) => l.id === "todo").flatMap((l) => l.top).slice(0, 2 - doing.length);
  const t = c.todos, idea = c.ideas;
  const on = (part) => shown(b.id, part);
  const lower = ["chores", "scribbles"].filter(on).length;
  return html`<div class=${cls("gui-fhut", { "is-folded": hidden(b.id).length > 0 })}>
    <${PartToggles} id=${b.id} parts=${PARTS} />
    ${on("work") && html`<section class="gui-fhut__part gui-fhut__part--work">
      <div class="gui-fhut__head"><span class="ok-font-label">Ork work</span>${c.lanes.map(counter)}</div>
      ${doing.map((x, i) => mark("⚒", x, `d${i}`))}${next.map((x, i) => mark("▸", x, `n${i}`))}
      ${!doing.length && !next.length && html`<span class="ok-tone-muted">nothing to do</span>`}
    </section>`}
    ${on("chores") && html`<section class=${cls("gui-fhut__part", { "gui-fhut__part--solo": lower === 1 })}>
      <div class="gui-fhut__head"><span class="ok-font-label">My chores</span><span><b>${t.open}</b><span class="ok-tone-muted">/${t.count}</span></span></div>
      ${t.top.map((x, i) => mark("☐", x, i))}
      ${!t.top.length && html`<span class="ok-tone-muted">${t.count ? "all done ✓" : "none yet"}</span>`}
    </section>`}
    ${on("scribbles") && html`<section class=${cls("gui-fhut__part", { "gui-fhut__part--solo": lower === 1 })}>
      <div class="gui-fhut__head"><span class="ok-font-label">Scribbles</span><span><b>${idea.count}</b>${idea.new ? "*" : ""}</span></div>
      ${idea.top.map((x, i) => mark("✎", x, i))}
      ${!idea.top.length && html`<span class="ok-tone-muted">none yet</span>`}
    </section>`}
  </div>`;
}

function MiniLane({ id, lane, top }) {
  const [over, drop] = useDrop(id, lane.id);
  const more = lane.cards.length - top;
  return html`<section class=${cls("ok-lane", { "is-notes": lane.kind === "note", "gui-drop": over })} ...${drop}>
    <header class="ok-lane__head">${lane.label}<span class="ok-lane__count">${lane.cards.length}</span></header>
    ${lane.cards.slice(0, top).map((c) => html`<div key=${c.id} class=${cls("ok-card", { "is-done": lane.id === "done" })}
        data-color=${c.color || undefined} draggable="true" title=${c.title} onDragStart=${dragCard(c.id)}>
      <div class="ok-card__title"><i class="ok-card__sw"></i><span>${c.title}</span>
        ${c.new && html`<span class="ok-word gui-new"> new</span>`}</div>
    </div>`)}
    ${more > 0 && html`<span class="ok-font-status ok-tone-muted">+${more} more</span>`}
  </section>`;
}

function Folded({ id, lane }) {
  const [over, drop] = useDrop(id, lane.id);
  return html`<span class=${cls("ok-chip", { "gui-drop": over })} title=${say(`${lane.label}: drop a card here`)} ...${drop}>
    ${lane.label} <b>${lane.cards.length}</b>${lane.cards.some((c) => c.new) ? "*" : ""}</span>`;
}

/** The New task / New note / New chore asked from the Command Card's quick actions. */
function Asking({ id, data }) {
  const a = asking.value;
  if (!a || a.id !== id) return null;
  const lane = a.kind === "mine" && data.todos ? { id: data.todos.id, label: data.todos.label, kind: "mine" }
    : data.lanes.find((ln) => ln.id === a.lane) || { id: a.lane, label: a.lane, kind: a.kind };
  return html`<${CardDialog} id=${id} lane=${lane} onClose=${() => { asking.value = null; }} />`;
}

/** Command: a small board — the status lanes with their top cards (drag between them works); below, the
 * open to-dos (ticked off here) and the lanes of notes folded to counters (a card dropped on one goes
 * there). In notes mode, the notes. */
export function preview(id, data) {
  if (data.error) return html`<p class="ok-tone-fire">⚠ ${data.error}</p>`;
  const tasks = data.lanes.filter((ln) => ln.kind === "task");
  const shown = tasks.length ? tasks : data.lanes;
  const folded = tasks.length ? data.lanes.filter((ln) => ln.kind !== "task") : [];
  const top = data.todos ? 2 : TOP;
  const chips = folded.length > 0 && html`<div class="gui-fields__folded">
      ${folded.map((ln) => html`<${Folded} key=${ln.id} id=${id} lane=${ln} />`)}</div>`;
  return html`<div class="gui-fields gui-fields--mini">
    <div class="ok-board" style=${`--lanes:${shown.length}`}>
      ${shown.map((ln) => html`<${MiniLane} key=${ln.id} id=${id} lane=${ln} top=${top} />`)}
    </div>
    ${data.todos ? html`<div class="gui-fields__lower">
        <section class="gui-fields__part"><span class="ok-font-label">My chores</span>
          <${Todos} id=${id} todos=${data.todos} top=${3} /></section>
        <section class="gui-fields__part"><span class="ok-font-label">Scribbles</span>${chips}</section>
      </div>` : chips}
    <${Asking} id=${id} data=${data} />
  </div>`;
}

/** The type's quick actions on the Command Card (realm/catalog.py): New task, New note, New chore. */
const QUICK = {
  "tasks.new": (id) => { asking.value = { id, lane: "todo", kind: "task" }; },
  "notes.new": (id) => { asking.value = { id, lane: noteLane(id), kind: "note" }; },
  "todos.new": (id) => { asking.value = { id, lane: "mine", kind: "mine" }; },
};

/** Does one of its quick actions (js/types.js); true when it did. */
export function quick(id, action) {
  const f = QUICK[action];
  if (!f) return false;
  f(id);
  return true;
}

function noteLane(id) {
  const d = details.value[id];
  const lane = d && d.data && d.data.lanes.find((ln) => ln.kind === "note");
  return lane ? lane.id : "notes";
}

export function panes(id, data) {
  return { board: () => html`<${Board} id=${id} data=${data} />` };
}
