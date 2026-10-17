// Today (§7): what needs the person, then the to-dos of the plans. A to-do is ticked; a secret asks for its value in a
// password field, a choice offers its choices, instructions show their steps.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { board, asked, run, open } from "./store.js";
import { Questions } from "./questions.js";
import { Merged } from "./merged.js";
import { NightCard, isRed, shown } from "./night.js";

function Todo({ t }) {
  const [value, setValue] = useState("");
  const done = (extra = {}) => run("ideas.todo", { idea: t.idea, id: t.id, done: true, ...extra });
  return html`<li class=${cls("board-todo", { "is-done": t.done })} data-kind=${t.kind}>
    <div class="board-todo__head">
      <input type="checkbox" checked=${!!t.done} aria-label=${`Done: ${t.title}`}
        onChange=${(e) => run("ideas.todo", { idea: t.idea, id: t.id, done: e.target.checked })} />
      <b>${t.title}</b>
      <button class="board-link" onClick=${() => open(t.idea)}>${t.idea}</button>
    </div>
    ${t.why && html`<p class="ok-tone-muted board-todo__why">${t.why}</p>`}
    ${t.kind === "secret" && !t.done && html`<form class="board-row" onSubmit=${(e) => { e.preventDefault(); if (value) done({ value }); }}>
      <input class="ok-input" type="password" autocomplete="off" value=${value} aria-label=${`Value of ${t.title}`}
        placeholder="The value (kept on this machine, never in a prompt)" onInput=${(e) => setValue(e.target.value)} />
      <button class="ok-btn primary" disabled=${!value}>Keep it</button></form>`}
    ${t.kind === "choice" && !t.done && html`<div class="board-row">${(t.choices || []).map((c) =>
      html`<button key=${c} class="ok-btn" onClick=${() => done({ value: c })}>${c}</button>`)}</div>`}
    ${t.kind === "instructions" && html`<ol class="board-steps">${(t.steps || []).map((s, n) => html`<li key=${n}>${s}</li>`)}</ol>`}
  </li>`;
}

export function Today() {
  const today = board.value.today;
  const open_ = today.todos.filter((t) => !t.done), list = [...open_, ...today.todos.filter((t) => t.done)];
  // The Night report (spec 32 §3): red stands in Needs you; green (or running) right under it.
  const night = today.night, red = isRed(night), needs = today.needs_you.length + (red ? 1 : 0);
  return html`<section class="board-today" aria-label="Today">
    <h3 class="board-sub kit-band">Needs you ${needs ? html`<span class="board-count kit-well">${needs}</span>` : ""}</h3>
    ${red ? html`<${NightCard} n=${night} />` : ""}
    ${today.needs_you.length ? html`<ul class="board-list">${today.needs_you.map((n) => html`<li key=${n.idea + n.kind}>
      <button class="board-need" data-kind=${n.kind} onClick=${() => open(n.idea)}>
        <b>${n.title}</b><span class="ok-tone-muted">${n.text}</span></button>
      ${n.kind === "asks" && html`<${Questions} slug=${n.idea} questions=${asked.value[n.idea]} />`}</li>`)}</ul>`
      : red ? "" : html`<p class="ok-tone-muted">Nothing waits for you.</p>`}
    ${!red && shown(night) ? html`<${NightCard} n=${night} />` : ""}
    <${Merged} />
    <h3 class="board-sub kit-band">To-dos ${open_.length ? html`<span class="board-count kit-well">${open_.length}</span>` : ""}</h3>
    ${list.length ? html`<ul class="board-list">${list.map((t) => html`<${Todo} key=${t.idea + t.id} t=${t} />`)}</ul>`
      : html`<p class="ok-tone-muted">No to-dos from a plan yet.</p>`}
    <p class="board-silence ok-tone-muted">The orks ask you when a question, a plan, a red gate twice, a conflict or a spent window needs you.
      Otherwise they work and merge.</p>
  </section>`;
}
