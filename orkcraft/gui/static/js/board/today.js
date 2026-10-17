// Today (29a §7, 33 §6): what needs the person (each opens its idea), then the to-dos of the plans (each opens the plan, scrolled
// to it). A to-do is ticked; a secret asks for its value in a
// password field, a choice offers its choices, instructions show their steps.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { board } from "./store.js";
import { act as run, showIdea, showPlan } from "../shell/store.js";

function Todo({ t }) {
  const [value, setValue] = useState("");
  const done = (extra = {}) => run("ideas.todo", { idea: t.idea, id: t.id, done: true, ...extra });
  return html`<li class=${cls("board-todo", { "is-done": t.done })} data-kind=${t.kind}>
    <div class="board-todo__head">
      <input type="checkbox" checked=${!!t.done} aria-label=${`Done: ${t.title}`}
        onChange=${(e) => run("ideas.todo", { idea: t.idea, id: t.id, done: e.target.checked })} />
      <button class="board-link board-todo__title" onClick=${() => showPlan(t.idea, t.id)}><b>${t.title}</b></button>
      <button class="board-link board-todo__idea" onClick=${() => showIdea(t.idea)}>${t.idea}</button>
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
  const open_ = today.todos.filter((t) => !t.done), shown = [...open_, ...today.todos.filter((t) => t.done)];
  return html`<section class="board-today" aria-label="Today">
    <h3 class="board-sub kit-band">Needs you ${today.needs_you.length ? html`<span class="board-count kit-well">${today.needs_you.length}</span>` : ""}</h3>
    ${today.needs_you.length ? html`<ul class="board-list">${today.needs_you.map((n) => html`<li key=${n.idea + n.kind}>
      <button class="board-need" data-kind=${n.kind} onClick=${() => showIdea(n.idea)}>
        <b>${n.title}</b><span class="ok-tone-muted">${n.text}</span></button></li>`)}</ul>`
      : html`<p class="ok-tone-muted">Nothing waits for you.</p>`}
    <h3 class="board-sub kit-band">To-dos ${open_.length ? html`<span class="board-count kit-well">${open_.length}</span>` : ""}</h3>
    ${shown.length ? html`<ul class="board-list">${shown.map((t) => html`<${Todo} key=${t.idea + t.id} t=${t} />`)}</ul>`
      : html`<p class="ok-tone-muted">No to-dos from a plan yet.</p>`}
  </section>`;
}
