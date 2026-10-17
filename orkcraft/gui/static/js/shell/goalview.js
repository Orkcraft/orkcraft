// A goal in the preview (docs/specs/34-v1-round-2.md §7): Description, Summary (the Taskmaster's), Metrics (what is
// measured, the target, how it is counted), Links (a repository path or Wiki page opens in the preview; a web address in
// the browser), the Open questions with a box to answer — the same talk as an idea's, on the goal.
import { useState } from "preact/hooks";
import { html } from "../html.js";
import { say, openLink } from "../link.js";
import { goal, act, showDoc } from "./store.js";
import { openDialog } from "./modals.js";

export const GOAL_STATE = { reading: "the Taskmaster is reading", asks: "asks you", ready: "ready", raw: "" };
const isUrl = (l) => /^[a-z][a-z0-9+.-]*:\/\//i.test(l);

function Answer({ g }) {
  const [text, setText] = useState("");
  const send = async () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    await act("ideas.say", { slug: g.slug, text: t, goal: true });
  };
  return html`<div class="board-say">
    <textarea class="ok-input" rows="2" value=${text} aria-label=${say("Answer the Taskmaster")} placeholder=${say("Answer the Taskmaster…")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } }}></textarea>
    <div class="board-row"><button class="ok-btn" disabled=${!text.trim() || g.busy} onClick=${send}>Answer</button>
      ${g.busy && html`<span class="ok-tone-wait">${say("The Taskmaster is reading…")}</span>`}</div></div>`;
}

export function GoalView() {
  const g = goal.value;
  if (!g) return html`<p class="ok-tone-muted">Opening…</p>`;
  const words = GOAL_STATE[g.state];
  return html`<div class="board-ideaview shell-goal" data-state=${g.state}>
    <div class="board-bar"><span class="board-state" data-state=${g.state}>${say(words || "not read yet")}</span>
      <span class="board-size kit-well">${({ high: "High", normal: "Normal", low: "Low" })[g.priority]}</span>
      ${g.deadline && html`<span class="ok-tone-muted">by ${g.deadline}</span>`}
      <button class="ok-btn" onClick=${() => openDialog("goal", { slug: g.slug })}>Edit</button></div>
    ${g.error && g.state === "raw" && html`<p class="ok-tone-wait" role="status">${g.error}</p>`}
    <section class="shell-goal__sec" aria-label="Description"><h3 class="board-sub">Description</h3>
      <p class="shell-brief">${g.description || html`<span class="ok-tone-muted">No description yet.</span>`}</p></section>
    <section class="shell-goal__sec" aria-label="Summary"><h3 class="board-sub">Summary</h3>
      <p class="shell-brief">${g.summary || html`<span class="ok-tone-muted">${g.state === "reading" ? say("The Taskmaster is reading the goal…") : "Not written yet."}</span>`}</p></section>
    <section class="shell-goal__sec" aria-label="Metrics"><h3 class="board-sub">Metrics</h3>
      ${g.metrics.length ? html`<table class="shell-metrics"><thead><tr><th>What is measured</th><th>Target</th><th>How it is counted</th></tr></thead>
        <tbody>${g.metrics.map((m) => html`<tr key=${m.name}><td>${m.name}</td><td>${m.target || "—"}</td><td>${m.how || html`<span class="ok-tone-muted">—</span>`}</td></tr>`)}</tbody></table>`
        : html`<p class="ok-tone-muted">No metric yet.</p>`}</section>
    <section class="shell-goal__sec" aria-label="Links"><h3 class="board-sub">Links</h3>
      ${g.links.length ? html`<ul class="shell-links">${g.links.map((l) => html`<li key=${l}>${isUrl(l)
        ? html`<a class="gui-link" href=${l} target="_blank" rel="noopener noreferrer" onClick=${(e) => { e.preventDefault(); openLink(l); }}>${l}</a>`
        : html`<button class="board-link" onClick=${() => showDoc(g.slug, l)}>${l}</button>`}</li>`)}</ul>`
        : html`<p class="ok-tone-muted">No link.</p>`}</section>
    <section class="shell-goal__sec" aria-label="Open questions"><h3 class="board-sub">Open questions</h3>
      ${g.questions.length ? html`<ul class="shell-links">${g.questions.map((q) => html`<li key=${q}>${q}</li>`)}</ul>`
        : html`<p class="ok-tone-muted">${g.state === "ready" ? "The Taskmaster has no question." : "No question yet."}</p>`}
      <${Answer} g=${g} /></section>
    ${g.talk?.length > 0 && html`<ol class="board-talk" aria-label="The talk">${g.talk.slice(-8).map((t, n) => html`<li key=${n} data-who=${t.who}>
      <span class="board-talk__who">${t.who === "you" ? "You" : say("The Taskmaster")}</span><span>${t.text}</span></li>`)}</ol>`}
  </div>`;
}
