// 🌾 Task Fields: one board, three parts (design-system/components.md: TaskFields) — the orks' tasks as
// lanes of cards (a kanban), the person's own to-dos (a checklist) and the notes (ideas, questions) in
// lanes of their own. The mouse does it all: drag a card to another lane or part, click it to select
// it, double-click it to open it; the selected card's acts sit over the board; a to-do is ticked off
// by its box. The closed card shows
// all three parts at a glance; a checkbox over them hides any one (js/parts.js). The worker writes the
// board file (core/workers/fields.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, details } from "../link.js";
import { Dialog } from "../dialog.js";
import { PartToggles, shown, hidden } from "../parts.js";
import { usePeek } from "../windows.js";

const selected = signal({});       // building id → card id
const asking = signal(null);       // {id, lane, kind}: a New task / note / chore asked from its Info's quick actions
// The closed card's three parts, each one the person may hide (js/parts.js).
const PARTS = [{ key: "work", label: "Ork work" }, { key: "chores", label: "My to-dos" }, { key: "scribbles", label: "Notes" }];

const sheet = new URL("./fields.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
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

/** A card is written as one text: a short line is its title; a longer text is its text, and a light model
 *  names it in a few words (the card shows up once named). An open card keeps its title. */
function CardDialog({ id, card, lane, onClose }) {
  const [body, setBody] = useState(card ? card.body || card.title : "");
  const kind = card ? card.kind : lane.kind;
  const what = kind === "task" ? "task" : kind === "mine" ? "to-do" : "note";
  const head = card ? what[0].toUpperCase() + what.slice(1) : `New ${what}`;
  function keep() {
    const call = card ? act(id, "edit", { card: card.id, text: body }) : act(id, "add", { lane: lane.id, text: body });
    call.then((kept) => {
      if (kept) selected.value = { ...selected.value, [id]: kept };     // a card's id follows its title
      onClose();
    }, () => {});
  }
  const keys = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && body.trim()) { e.preventDefault(); keep(); } };
  return html`<${Dialog} title=${say(card ? `${head} · ${card.title}` : `${head} · ${lane.label}`)} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!body.trim()} onClick=${keep}>${card ? "Keep it" : "Add it"}</button>`}>
    <textarea class="ok-input gui-textarea" rows="6" value=${body} autofocus aria-label=${say("Text")}
      placeholder=${say(card ? "Its text (Ctrl+Enter keeps it)" : "What it is — a short line is its title, a longer text gets one (Ctrl+Enter adds it)")}
      onInput=${(e) => setBody(e.target.value)} onKeyDown=${keys}></textarea>
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
 * dropped here becomes a to-do. `top` cuts it. */
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
        <label class="ok-check" title=${say(c.done ? "Put it back on my to-dos" : "Tick it off")}
          onClick=${(e) => { e.stopPropagation(); act(id, "check", { card: c.id }).catch(() => {}); }}><i>${c.done ? "✓" : ""}</i></label>
        <span class="gui-todo__title">${c.title}${c.new ? html`<span class="ok-word gui-new"> new</span>` : ""}</span>
      </li>`)}
      ${cards.length === 0 && html`<li class="ok-tone-muted ok-font-status">${todos.cards.length ? "All done ✓" : "No to-dos yet — add one below"}</li>`}
      ${top && todos.cards.filter((c) => !c.done).length > top
        && html`<li class="ok-font-status ok-tone-muted">+${todos.cards.filter((c) => !c.done).length - top} more</li>`}
    </ul>
    ${!top && html`<div class="gui-todo__add">
      <input class="ok-input" placeholder=${say("A to-do of my own…")} value=${title}
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

/** The selected card in a strip: its title, Open, where it goes next (the orks, a note, my to-dos) and
 *  Send; Colour and Delete quiet after them; × lets it go. */
function Acts({ id, sel, setDialog, wiki }) {
  const a = (label, onClick) => html`<button class="ok-act" onClick=${onClick}><span class="ok-act__label">${label}</span></button>`;
  return html`<div class="fields-sel" role="toolbar" aria-label=${say("The selected card")}>
    <span class="fields-sel__what" title=${sel.title}>${sel.title}</span>
    <span class="fields-sel__acts">
      <button class="ok-btn primary" onClick=${() => setDialog({ card: sel })}>Open</button>
      ${sel.kind !== "task" && a("Give it to the orks", () => act(id, "flip", { card: sel.id }))}
      ${sel.kind === "task" && a("Make it a note", () => act(id, "flip", { card: sel.id }))}
      ${sel.kind !== "mine" && sel.mine && a("Make it my to-do", () => act(id, "mine", { card: sel.id }))}
      ${a("Send", () => act(id, "send", { card: sel.id }))}
      ${wiki && sel.kind === "note" && a("→ Wiki", () => act(id, "to_wiki", { card: sel.id }).catch(() => {}))}
      ${a("Colour", () => act(id, "color", { card: sel.id }))}
      ${a("Delete", () => setDialog({ remove: sel }))}
      <button class="ok-act" aria-label=${say("Let the card go")} title=${say("Let the card go")} onClick=${() => pick(id, null)}>
        <span class="ok-act__label">×</span></button>
    </span>
  </div>`;
}

/** The counters on one line: the orks' lanes, my to-dos open of all, the notes; New note folder quiet on
 *  the right. How the mouse works is its tooltip: a click selects a card and its strip says the rest. */
function Head({ id, data, setDialog }) {
  const lanes = data.lanes.filter((ln) => (data.todos ? ln.kind === "task" : true));
  const notes = data.todos ? data.lanes.filter((ln) => ln.kind === "note").reduce((n, ln) => n + ln.cards.length, 0) : 0;
  const open = data.todos ? data.todos.cards.filter((c) => !c.done).length : 0;
  return html`<div class="fields-head" title=${say("Drag a card to another lane · click to select · double-click to open")}>
    ${lanes.map((ln) => html`<span key=${ln.id}><b>${ln.cards.length}</b> ${ln.label}</span>`)}
    ${data.todos && html`<span><b>${open}</b>/${data.todos.cards.length} ${say("to-dos open")}</span>
      <span><b>${notes}</b> ${say("notes")}</span>`}
    <span class="fields-head__spacer"></span>
    <button class="ok-act" title=${say("A lane of its own for notes")} onClick=${() => setDialog({ folder: true })}>
      <span class="ok-act__label">${say("New note folder")}</span></button>
  </div>`;
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
  const todoOpen = parts ? data.todos.cards.filter((c) => !c.done).length : 0;
  return html`<div class="gui-fields">
    <${Head} id=${id} data=${data} setDialog=${setDialog} />
    ${sel && html`<${Acts} id=${id} sel=${sel} setDialog=${setDialog} wiki=${data.wiki} />`}
    ${parts ? html`
      <section class="gui-fields__part"><h3 class="ok-font-heading">Ork work</h3>
        ${lanes(data.lanes.filter((ln) => ln.kind === "task"))}</section>
      <div class="gui-fields__lower">
        <section class="gui-fields__part"><h3 class="ok-font-heading">My to-dos <small>${todoOpen}/${data.todos.cards.length}</small></h3>
          <${Todos} id=${id} todos=${data.todos} sel=${sel && sel.id} onOpen=${open} /></section>
        <section class="gui-fields__part"><h3 class="ok-font-heading">Notes</h3>
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
  if (!c.todos) {             // a kanban or a wall of notes: the one number, the lanes under it, the card in work
    const wall = c.mode === "notes";
    const open = c.lanes.filter((l) => l.id !== "done");
    const doing = c.lanes.filter((l) => l.id === "in_progress").flatMap((l) => l.top).concat(open.flatMap((l) => l.top))[0];
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${open.reduce((n, l) => n + l.count, 0)}<small>${say(wall ? "notes" : "open tasks")}</small></div>
      <div class="gui-hut__text gui-counters">${c.lanes.map(counter)}</div>
      ${notes.length > 0 && html`<div class="gui-hut__text gui-counters">${notes.map(counter)}</div>`}
      ${doing && html`<div class="gui-hut__foot"><span>${wall ? "✎" : "⚒"} ${doing}</span></div>`}
    </div>`;
  }
  const doing = c.lanes.filter((l) => l.id === "in_progress").flatMap((l) => l.top.slice(0, 1));
  const next = c.lanes.filter((l) => l.id === "todo").flatMap((l) => l.top).slice(0, 2 - doing.length);
  const t = c.todos, idea = c.ideas;
  const on = (part) => shown(b.id, part);
  const lower = ["chores", "scribbles"].filter(on).length;
  // An empty part says only its head and count: a line that says "none yet" under a 0 says it twice.
  const quiet = !doing.length && !next.length && !t.top.length;
  return html`<div class=${cls("gui-fhut", { "is-folded": hidden(b.id).length > 0, "is-quiet": quiet })}>
    <${PartToggles} id=${b.id} parts=${PARTS} />
    ${on("work") && html`<section class="gui-fhut__part gui-fhut__part--work">
      <div class="gui-fhut__head"><span class="ok-font-label">Ork work</span>${c.lanes.map(counter)}</div>
      ${doing.map((x, i) => mark("⚒", x, `d${i}`))}${next.map((x, i) => mark("▸", x, `n${i}`))}
    </section>`}
    ${on("chores") && html`<section class=${cls("gui-fhut__part", { "gui-fhut__part--solo": lower === 1 })}>
      <div class="gui-fhut__head"><span class="ok-font-label">My to-dos</span><span><b>${t.open}</b><span class="ok-tone-muted">/${t.count}</span></span></div>
      ${t.top.map((x, i) => mark("☐", x, i))}
      ${!t.top.length && t.count > 0 && html`<span class="ok-tone-ok">all done ✓</span>`}
    </section>`}
    ${on("scribbles") && html`<section class=${cls("gui-fhut__part", { "gui-fhut__part--solo": lower === 1 })}>
      <div class="gui-fhut__head"><span class="ok-font-label">Notes</span><span><b>${idea.count}</b>${idea.new ? "*" : ""}</span></div>
      ${idea.top.map((x, i) => mark("✎", x, i))}
    </section>`}
  </div>`;
}

/** The New task / New note / New chore asked from its Info's quick actions. */
function Asking({ id, data }) {
  const a = asking.value;
  if (!a || a.id !== id) return null;
  const lane = a.kind === "mine" && data.todos ? { id: data.todos.id, label: data.todos.label, kind: "mine" }
    : (data.lanes || []).find((ln) => ln.id === a.lane) || { id: a.lane, label: a.lane, kind: a.kind };
  return html`<${CardDialog} id=${id} lane=${lane} onClose=${() => { asking.value = null; }} />`;
}

/** The type's quick actions in its Info (realm/catalog.py): New task, New note, New chore. */
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

function Peeked({ id }) {
  usePeek(id);
  return html`<${Asking} id=${id} data=${(details.value[id] || {}).data || {}} />`;
}

/** Its New task / note / chore window, over the town, whether the board is open or not (js/types.js). */
export function overlay() {
  return asking.value ? html`<${Peeked} key=${asking.value.id} id=${asking.value.id} />` : null;
}
