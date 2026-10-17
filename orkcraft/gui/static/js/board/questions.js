// The Taskmaster's questions as choices (docs/specs/29c-after-the-merge.md §2): each question's options as chips, the
// recommended one marked, its why on hover or focus, and *Other…* for a one-line answer of one's own. One tap answers
// (`ideas.answer`); when every question is answered the host sends them to the talk together and clears them.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { run } from "./store.js";

/** What a question's answer reads as: a text, or the chosen option when the host gives its index. */
function answered(q) {
  const a = q.answer;
  if (a === null || a === undefined || a === "") return "";
  if (typeof a === "string") return a;
  return a.text ?? q.options?.[a.choice] ?? "";
}

function Question({ slug, q }) {
  const [other, setOther] = useState(null);
  const done = answered(q);
  const send = (args) => run("ideas.answer", { slug, id: q.id, ...args });
  const submit = async (e) => {
    e.preventDefault();
    const text = other.trim();
    if (!text) return;
    setOther(null);
    await send({ text });
  };
  const options = q.options || [];
  return html`<div class=${cls("board-q", { "is-answered": !!done })} data-id=${q.id}>
    <p class="board-q__text">${q.text}</p>
    ${options.length ? html`<div class="board-opts" role="group" aria-label=${q.text}>
      ${options.map((o, n) => html`<span key=${n} class="board-optwrap">
        <button class=${cls("ok-btn board-opt", { "is-rec": q.recommended === n })} aria-pressed=${String(done === o)}
          aria-describedby=${q.recommended === n && q.why ? `why-${slug}-${q.id}` : null} onClick=${() => send({ choice: n })}>
          <span>${o}</span>${q.recommended === n && html`<small class="board-opt__rec">recommended</small>`}</button>
        ${q.recommended === n && q.why && html`<span class="board-why" role="tooltip" id=${`why-${slug}-${q.id}`}>${q.why}</span>`}</span>`)}
      <button class=${cls("ok-btn board-opt", { "is-on": other !== null })} aria-expanded=${String(other !== null)}
        onClick=${() => setOther(other === null ? "" : null)}>Other…</button></div>` : ""}
    ${(other !== null || !options.length) && html`<form class="board-row board-other" onSubmit=${submit}>
      <input class="ok-input" autofocus=${options.length > 0} value=${other ?? ""} aria-label=${`Your answer to: ${q.text}`}
        placeholder="Your answer, in a line" onInput=${(e) => setOther(e.target.value)} />
      <button class="ok-btn primary" disabled=${!(other ?? "").trim()}>Answer</button></form>`}
    ${done && html`<p class="board-q__got ok-tone-muted">Answered: ${done}</p>`}
  </div>`;
}

export function Questions({ slug, questions }) {
  if (!questions || !questions.length) return "";
  return html`<div class="board-qs" aria-label="The Taskmaster asks">${questions.map((q) => html`<${Question} key=${q.id} slug=${slug} q=${q} />`)}</div>`;
}
