// 🌾 Task Fields: the board, a lane per column, a card per task or note (design-system/components.md:
// TaskFields). The mouse does it all: drag a card to another lane, click it to select it, double-click
// it to open it; the selected card's acts sit over the board. The worker writes the board file
// (core/workers/fields.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";

const selected = signal({});       // building id → card id

function CardDialog({ id, card, lane, onClose }) {
  const [title, setTitle] = useState(card ? card.title : "");
  const [body, setBody] = useState(card ? card.body : "");
  const what = card ? (card.kind === "task" ? "Task" : "Note") : (lane.kind === "task" ? "New task" : "New note");
  function keep() {
    const call = card ? act(id, "edit", { card: card.id, title, body }) : act(id, "add", { lane: lane.id, title, body });
    call.then((kept) => {
      if (kept) selected.value = { ...selected.value, [id]: kept };     // a card's id follows its title
      onClose();
    }, () => {});
  }
  return html`<${Dialog} title=${card ? `${what} · ${card.title}` : `${what} · ${lane.label}`} onCancel=${onClose}
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

function Card({ id, card, isSelected, onOpen }) {
  return html`<div class=${cls("ok-card", { "is-selected": isSelected, "is-done": card.column === "done" })}
      data-color=${card.color || undefined} draggable="true"
      onDragStart=${(e) => { e.dataTransfer.setData("text/x-ork-card", card.id); e.dataTransfer.effectAllowed = "move"; }}
      onClick=${() => { selected.value = { ...selected.value, [id]: card.id }; }}
      onDblClick=${() => onOpen(card)}>
    <div class="ok-card__title"><i class="ok-card__sw"></i>
      ${card.column === "done" && html`<span class="ok-card__check">✓</span>`}<span>${card.title}</span>
      ${card.new && html`<span class="ok-word gui-new"> new</span>`}</div>
    ${card.body && html`<p class="ok-card__text">${card.body}</p>`}
  </div>`;
}

function Lane({ id, lane, sel, onOpen, onAdd }) {
  const [over, setOver] = useState(false);
  return html`<section class=${cls("ok-lane", { "is-notes": lane.kind === "note", "gui-drop": over })}
      onDragOver=${(e) => { if (e.dataTransfer.types.includes("text/x-ork-card")) { e.preventDefault(); setOver(true); } }}
      onDragLeave=${() => setOver(false)}
      onDrop=${(e) => {
        e.preventDefault(); setOver(false);
        const card = e.dataTransfer.getData("text/x-ork-card");
        if (card) act(id, "move", { card, lane: lane.id }).catch(() => {});
      }}>
    <header class="ok-lane__head">${lane.label}<span class="ok-lane__count">${lane.cards.length}</span></header>
    ${lane.cards.map((c) => html`<${Card} key=${c.id} id=${id} card=${{ ...c, column: lane.id }} isSelected=${c.id === sel} onOpen=${onOpen} />`)}
    <button class="ok-lane__add" onClick=${() => onAdd(lane)}>+ New ${lane.kind === "task" ? "task" : "note"}</button>
  </section>`;
}

function Board({ id, data }) {
  const [dialog, setDialog] = useState(null);      // {card} | {lane} | {remove: card}
  useEffect(() => { act(id, "seen").catch(() => {}); }, [id]);
  const cards = data.lanes.flatMap((ln) => ln.cards.map((c) => ({ ...c, column: ln.id })));
  const sel = cards.find((c) => c.id === selected.value[id]);
  const close = () => setDialog(null);
  if (data.error) return html`<p class="ok-tone-error">⚠ ${data.error}</p>`;
  return html`<div class="gui-fields">
    <div class="gui-head">
      ${sel ? html`<span class="gui-head__what"><b>${sel.title}</b></span>
        <span class="gui-head__spacer"></span>
        <button class="ok-act" onClick=${() => setDialog({ card: sel })}><span class="ok-act__label">Open</span></button>
        <button class="ok-act" onClick=${() => act(id, "color", { card: sel.id })}><span class="ok-act__label">Colour</span></button>
        <button class="ok-act" onClick=${() => act(id, "flip", { card: sel.id })}>
          <span class="ok-act__label">${sel.kind === "task" ? "Make it a note" : "Make it a task"}</span></button>
        <button class="ok-act" onClick=${() => act(id, "send", { card: sel.id })}><span class="ok-act__label">Send</span></button>
        <button class="ok-act" onClick=${() => setDialog({ remove: sel })}><span class="ok-act__label">Delete</span></button>`
      : html`<span class="ok-tone-muted">Drag a card to another lane · click to select · double-click to open</span>`}
    </div>
    <div class="ok-board" style=${`--lanes:${data.lanes.length}`}>
      ${data.lanes.map((ln) => html`<${Lane} key=${ln.id} id=${id} lane=${ln} sel=${sel && sel.id}
        onOpen=${(card) => setDialog({ card })} onAdd=${(lane) => setDialog({ lane })} />`)}
    </div>
    ${dialog && dialog.remove && html`<${Confirm} title=${`Delete “${dialog.remove.title.slice(0, 60)}”?`}
      text="It goes from the file too (git keeps it)." yes="Delete"
      onYes=${() => act(id, "remove", { card: dialog.remove.id }).catch(() => {})} onClose=${close} />`}
    ${dialog && !dialog.remove && html`<${CardDialog} id=${id} card=${dialog.card} lane=${dialog.lane} onClose=${close} />`}
  </div>`;
}

/** Closed: a counter per lane, `*` on a lane with unseen cards (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<span class="ok-tone-fire">${c.error}</span>`;
  return html`<div class="gui-counters">${c.lanes.map((l) => html`<span key=${l.label} class="gui-counter">
    <span class="ok-tone-muted">${say(l.label)}</span> <b>${l.count}</b>${l.new ? "*" : ""}</span>`)}</div>`;
}

export function panes(id, data) {
  return { board: () => html`<${Board} id=${id} data=${data} />` };
}
