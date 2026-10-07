// 🌾 Task Fields: one board, three parts (design-system/components.md: TaskFields) — the orks' tasks as
// lanes of cards (a kanban), the person's own to-dos (a checklist) and the notes (ideas, questions) in
// lanes of their own. The mouse does it all: drag a card to another lane or part, click it to select
// it, double-click it to open it; the selected card's acts sit over the board; a to-do is ticked off
// by its box. A card's marks: 📜 its context (wiki pages, no model), 🧭 a to-do's plan, 🔒 personal
// (never sent to a model) — docs/design/fields-board.md §5b. The closed card shows
// all three parts at a glance; a checkbox over them hides any one (js/parts.js). The worker writes the
// board file (core/workers/fields.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, details } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
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
  const [personal, setPersonal] = useState(false);
  const kind = card ? card.kind : lane.kind;
  const what = kind === "task" ? "task" : kind === "mine" ? "to-do" : "note";
  const head = card ? what[0].toUpperCase() + what.slice(1) : `New ${what}`;
  function keep() {
    const call = card ? act(id, "edit", { card: card.id, text: body })
      : act(id, "add", { lane: lane.id, text: body, ...(personal ? { private: true } : {}) });
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
    ${!card && html`<label class="fields-personal"><input type="checkbox" checked=${personal}
      onChange=${(e) => setPersonal(e.target.checked)} /> 🔒 Personal — never sent to a model</label>`}
  </${Dialog}>`;
}

function Confirm({ title, text, yes, onYes, onClose }) {
  return html`<${Dialog} title=${title} text=${text} warn onCancel=${onClose}
    actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
      <button class="ok-btn danger" onClick=${() => { onYes(); onClose(); }}>${yes}</button>`} />`;
}

const pick = (id, cardId) => { selected.value = { ...selected.value, [id]: cardId }; };

/** A card's small marks: 🔒 personal, 📜 its context (pale when a page changed since), 🧭 its plan (… while
 *  it is written). A click on 📜 or 🧭 opens it; the card stays as it is. */
function Marks({ card, onMark }) {
  const n = (card.pages || []).length;
  const plan = (card.plan || []).length > 0;
  if (!card.private && !n && !plan && !card.planning) return null;
  const mark = (what, label, title, extra) => html`<button class=${cls("fields-mark", extra)} title=${say(title)}
      aria-label=${say(title)} onClick=${(e) => { e.stopPropagation(); onMark && onMark(what, card); }}
      onDblClick=${(e) => e.stopPropagation()}>${label}</button>`;
  return html`<span class="fields-marks">
    ${card.private && html`<span class="fields-mark is-still" title=${say("Personal: never sent to a model")}>🔒</span>`}
    ${n > 0 && mark("context", `📜 ${n}`, card.stale ? "Context: the wiki changed since — look again" : "Context: pages from the wiki",
      { "is-stale": card.stale })}
    ${card.planning ? html`<span class="fields-mark is-still" title=${say("Writing the plan…")}>🧭 …</span>`
      : plan && mark("plan", "🧭", "Plan")}
  </span>`;
}

function Card({ id, card, isSelected, onOpen, onMark }) {
  return html`<div class=${cls("ok-card", { "is-selected": isSelected, "is-done": card.column === "done" })}
      data-color=${card.color || undefined} draggable="true" onDragStart=${dragCard(card.id)}
      onClick=${() => pick(id, card.id)} onDblClick=${() => onOpen(card)}>
    <div class="ok-card__title"><i class="ok-card__sw"></i>
      ${card.column === "done" && html`<span class="ok-card__check">✓</span>`}<span>${card.title}</span>
      ${card.new && html`<span class="ok-word gui-new"> new</span>`}<${Marks} card=${card} onMark=${onMark} /></div>
    ${card.body && html`<p class="ok-card__text">${card.body}</p>`}
  </div>`;
}

function Lane({ id, lane, sel, onOpen, onAdd, onMark }) {
  const [over, drop] = useDrop(id, lane.id);
  return html`<section class=${cls("ok-lane", { "is-notes": lane.kind === "note", "gui-drop": over })} ...${drop}>
    <header class="ok-lane__head">${lane.label}<span class="ok-lane__count">${lane.cards.length}</span></header>
    ${lane.cards.map((c) => html`<${Card} key=${c.id} id=${id} card=${{ ...c, column: lane.id }} isSelected=${c.id === sel} onOpen=${onOpen} onMark=${onMark} />`)}
    <button class="ok-lane__add" onClick=${() => onAdd(lane)}>+ New ${lane.kind === "task" ? "task" : "note"}</button>
  </section>`;
}

/** The person's checklist: a box ticks a to-do off, a click selects it, a double-click opens it; a card
 * dropped here becomes a to-do. `top` cuts it. */
function Todos({ id, todos, sel, onOpen, onMark, top }) {
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
        <${Marks} card=${c} onMark=${onMark} />
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
function Acts({ id, sel, setDialog, onPlan, wiki }) {
  const a = (label, onClick) => html`<button class="ok-act" onClick=${onClick}><span class="ok-act__label">${label}</span></button>`;
  return html`<div class="fields-sel" role="toolbar" aria-label=${say("The selected card")}>
    <span class="fields-sel__what" title=${sel.title}>${sel.title}</span>
    <span class="fields-sel__acts">
      <button class="ok-btn primary" onClick=${() => setDialog({ card: sel })}>Open</button>
      ${sel.kind !== "task" && a("Give it to the orks", () => act(id, "flip", { card: sel.id }))}
      ${sel.kind === "task" && a("Make it a note", () => act(id, "flip", { card: sel.id }))}
      ${sel.kind !== "mine" && sel.mine && a("Make it my to-do", () => act(id, "mine", { card: sel.id }))}
      ${sel.kind === "mine" && a(sel.plan && sel.plan.length ? "🧭 Plan" : "🧭 Make a plan",
        () => (sel.plan && sel.plan.length ? setDialog({ plan: sel.id }) : onPlan(sel)))}
      ${a(`📜 Context${sel.pages && sel.pages.length ? ` ${sel.pages.length}` : ""}`, () => setDialog({ context: sel.id }))}
      ${a("Send", () => act(id, "send", { card: sel.id }))}
      ${a(sel.private ? "🔒 Not personal" : "🔒 Personal", () => act(id, "private", { card: sel.id }))}
      ${wiki && sel.kind === "note" && !sel.private && a("→ Wiki", () => act(id, "to_wiki", { card: sel.id }).catch(() => {}))}
      ${a("Colour", () => act(id, "color", { card: sel.id }))}
      ${a("Delete", () => setDialog({ remove: sel }))}
      <button class="ok-act" aria-label=${say("Let the card go")} title=${say("Let the card go")} onClick=${() => pick(id, null)}>
        <span class="ok-act__label">×</span></button>
    </span>
  </div>`;
}

/** A card's context: the wiki pages that share its words (found here, no model). A page opens in Lake;
 *  Look again asks the wikis once more. */
function ContextDialog({ id, card, onClose }) {
  const [looking, setLooking] = useState(false);
  const again = () => { setLooking(true); act(id, "context", { card: card.id }).finally(() => setLooking(false)); };
  const pages = card.pages || [];
  return html`<${Dialog} title=${say(`Context · ${card.title}`)} onCancel=${onClose}
      meta=${say("Pages from the wiki that share its words — found on this machine, nothing is sent to a model")}
      actions=${html`<button class="ok-btn" disabled=${looking} onClick=${again}>${looking ? "Looking…" : "Look again"}</button>
        <button class="ok-btn primary" onClick=${onClose}>Close</button>`}>
    ${card.stale && html`<p class="ok-tone-wait">${say("A page changed since it was found — look again")}</p>`}
    ${pages.length ? html`<ul class="fields-pages">${pages.map((p) => html`<li key=${p.path}>
        <button class="gui-link fields-page" onClick=${() => openInLake({ path: p.path, title: p.title, from: id })}>📜 ${p.title}</button>
        <small class="ok-tone-muted">${p.path}</small></li>`)}</ul>`
      : html`<p class="ok-tone-muted">${say("No page of the wiki shares its words yet.")}</p>`}
  </${Dialog}>`;
}

/** What goes to the model, before a plan is asked: the to-do as it leaves (cleaned), what was taken out,
 *  the pages it takes along — each one may stay home — and the model. */
function PreviewDialog({ id, card, preview, onClose, onSent }) {
  const [pages, setPages] = useState((preview.pages || []).map((p) => p.path));
  const [trust, setTrust] = useState(false);
  const toggle = (path) => setPages(pages.includes(path) ? pages.filter((p) => p !== path) : pages.concat(path));
  const send = () => act(id, "plan", { card: card.id, pages, trust }).then(onSent, () => {});
  if (!preview.allowed) {
    return html`<${Dialog} title=${say(`No plan · ${card.title}`)} text=${say(preview.why || "It cannot be sent")} onCancel=${onClose}
      actions=${html`<button class="ok-btn primary" onClick=${onClose}>Close</button>`} />`;
  }
  return html`<${Dialog} title=${say("What goes to the model")} warn wide onCancel=${onClose}
      meta=${say(`For a plan of “${card.title}” · model: ${preview.model}`)}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" onClick=${send}>Send</button>`}>
    <pre class="fields-outgoing ok-font-mono">${preview.text}</pre>
    <p class=${preview.taken_out ? "ok-tone-ok" : "ok-tone-muted"}>${preview.taken_out
      ? say(`Taken out before it goes: ${preview.taken_out}. They come back into the plan here.`)
      : say("Nothing with a shape to take out (e-mails, phones, cards, IBANs, secrets). Names and sums written in words go as they are.")}</p>
    ${(preview.pages || []).length > 0 && html`<div class="fields-pages">
      <p class="ok-font-label">${say("Pages from the wiki it takes along")}</p>
      ${preview.pages.map((p) => html`<label key=${p.path} class="fields-personal">
        <input type="checkbox" checked=${pages.includes(p.path)} onChange=${() => toggle(p.path)} /> 📜 ${p.title}</label>`)}
    </div>`}
    <label class="fields-personal"><input type="checkbox" checked=${trust} onChange=${(e) => setTrust(e.target.checked)} />
      ${say("Don't ask again on this board")}</label>
  </${Dialog}>`;
}

/** A to-do's plan: its steps; they may become to-dos of their own, or the plan be asked again. */
function PlanDialog({ id, card, onPlan, onClose }) {
  const steps = card.plan || [];
  const make = () => act(id, "plan_steps", { card: card.id }).then(onClose, () => {});
  return html`<${Dialog} title=${say(`Plan · ${card.title}`)} onCancel=${onClose}
      actions=${html`<button class="ok-btn" disabled=${card.planning} onClick=${() => onPlan(card)}>Plan again</button>
        <button class="ok-btn" disabled=${!steps.length} onClick=${make}>Make them to-dos</button>
        <button class="ok-btn primary" onClick=${onClose}>Close</button>`}>
    ${card.planning ? html`<p class="ok-tone-muted">${say("Writing the plan…")}</p>`
      : html`<ol class="fields-plan">${steps.map((s, i) => html`<li key=${i}>${s}</li>`)}</ol>`}
  </${Dialog}>`;
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
  const [dialog, setDialog] = useState(null);      // {card} | {lane} | {remove: card} | {folder: true} | {context|plan: id} | {preview, of}
  useEffect(() => { act(id, "seen").catch(() => {}); }, [id]);
  const parts = !!data.todos;                       // board mode: the three parts
  const cards = data.lanes.flatMap((ln) => ln.cards.map((c) => ({ ...c, column: ln.id })))
    .concat(parts ? data.todos.cards.map((c) => ({ ...c, column: data.todos.id })) : []);
  const found = cards.find((c) => c.id === selected.value[id]);
  const sel = found && { ...found, mine: parts };
  const close = () => setDialog(null);
  const open = (card) => setDialog({ card });
  const mark = (what, card) => setDialog({ [what]: card.id });
  // Plan: what leaves is shown first, unless the person said once not to ask on this board.
  const plan = (card) => act(id, "plan_preview", { card: card.id }).then((preview) => {
    if (!preview) return;
    if (preview.allowed && !preview.asked) act(id, "plan", { card: card.id }).then(() => setDialog({ plan: card.id }), () => {});
    else setDialog({ preview, of: card.id });
  }, () => {});
  const byId = (cid) => cards.find((c) => c.id === cid);
  const lanes = (list) => html`<div class="ok-board" style=${`--lanes:${list.length}`}>
      ${list.map((ln) => html`<${Lane} key=${ln.id} id=${id} lane=${ln} sel=${sel && sel.id}
        onOpen=${open} onMark=${mark} onAdd=${(lane) => setDialog({ lane })} />`)}
    </div>`;
  if (data.error) return html`<p class="ok-tone-error">⚠ ${data.error}</p>`;
  const todoOpen = parts ? data.todos.cards.filter((c) => !c.done).length : 0;
  return html`<div class="gui-fields">
    <${Head} id=${id} data=${data} setDialog=${setDialog} />
    ${sel && html`<${Acts} id=${id} sel=${sel} setDialog=${setDialog} onPlan=${plan} wiki=${data.wiki} />`}
    ${parts ? html`
      <section class="gui-fields__part"><h3 class="ok-font-heading">Ork work</h3>
        ${lanes(data.lanes.filter((ln) => ln.kind === "task"))}</section>
      <div class="gui-fields__lower">
        <section class="gui-fields__part"><h3 class="ok-font-heading">My to-dos <small>${todoOpen}/${data.todos.cards.length}</small></h3>
          <${Todos} id=${id} todos=${data.todos} sel=${sel && sel.id} onOpen=${open} onMark=${mark} /></section>
        <section class="gui-fields__part"><h3 class="ok-font-heading">Notes</h3>
          ${lanes(noteLanes(data))}</section>
      </div>` : lanes(data.lanes)}
    ${dialog && dialog.remove && html`<${Confirm} title=${`Delete “${dialog.remove.title.slice(0, 60)}”?`}
      text="It goes from the file too (git keeps it)." yes="Delete"
      onYes=${() => act(id, "remove", { card: dialog.remove.id }).catch(() => {})} onClose=${close} />`}
    ${dialog && dialog.folder && html`<${FolderDialog} id=${id} onClose=${close} />`}
    ${dialog && dialog.context && byId(dialog.context) && html`<${ContextDialog} id=${id} card=${byId(dialog.context)} onClose=${close} />`}
    ${dialog && dialog.plan && byId(dialog.plan) && html`<${PlanDialog} id=${id} card=${byId(dialog.plan)} onPlan=${plan} onClose=${close} />`}
    ${dialog && dialog.preview && byId(dialog.of) && html`<${PreviewDialog} id=${id} card=${byId(dialog.of)} preview=${dialog.preview}
      onClose=${close} onSent=${() => setDialog({ plan: dialog.of })} />`}
    ${dialog && (dialog.card || dialog.lane) && html`<${CardDialog} id=${id} card=${dialog.card} lane=${dialog.lane} onClose=${close} />`}
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
