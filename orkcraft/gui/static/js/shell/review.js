// Review, on the right (docs/specs/33-v1-shell.md §3, §6): Merge into `dev` ▾ at the top, then the results oldest first,
// one card each — what changed, its tests, its cost. Three answers, on the card and in the result's preview: Merge
// (only when the tests are green and nothing conflicts), Send back / Fix (one line, required), Drop (quiet, apart).
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { review, preview, act, showResult, closePreview } from "./store.js";

const usd = (n) => (n == null ? "" : `$${n < 10 ? n.toFixed(2) : Math.round(n)}`);

export function isRed(r) { return r.tests.failed > 0 || r.tests.green === false; }
export function noTests(r) { return !isRed(r) && r.tests.passed === 0; }

/** The tests, in the person's words: "20 / 20 passed" ✓, "10 / 20 failed" ✗ with the first failing names, or no tests ran. */
export function testsWords(r) {
  const t = r.tests, all = t.passed + t.failed;
  if (isRed(r)) return { mark: "✗", text: t.failed ? `${t.failed} / ${all} failed` : "the tests failed", names: (t.failing || []).slice(0, 2), tone: "danger" };
  if (noTests(r)) return { mark: "", text: "no tests ran", names: [], tone: "muted" };
  return { mark: "✓", text: `${t.passed} / ${all} passed`, names: [], tone: "success" };
}
export const changesWords = (d) => `${d.files} file${d.files === 1 ? "" : "s"}, +${d.added} −${d.removed}`;

/** Why Merge is off, or "": red tests, a conflict, or both. */
export function mergeReason(r, into) {
  const why = [];
  if (isRed(r)) why.push("Its tests are red");
  if (r.conflict) why.push(r.conflict);
  return why.length ? `${why.join(" · ")}: send it back to fix ${why.length > 1 ? "them" : r.conflict ? "the conflict" : "them"}` : "";
}

export function fixLine(r, into) {
  if (r.conflict) return `Resolve the conflict with ${into}`;
  if (isRed(r)) return `Fix the failing tests${r.tests.failing?.[0] ? `: ${r.tests.failing[0]}` : ""}`;
  return "";
}

/** Merge · Send back / Fix · Drop for one result; `pinned` in a preview's foot. */
export function ResultActions({ r, pinned = false }) {
  const into = review.value?.into || "dev";
  const [line, setLine] = useState(null);       // null: the one-line box is closed
  const [sure, setSure] = useState(false);
  const [working, setWorking] = useState(false);
  const reason = mergeReason(r, into), fix = isRed(r) || !!r.conflict;
  const key = { slug: r.idea, task: r.task };
  const done = () => { if (preview.value?.task === r.task && preview.value?.slug === r.idea) closePreview(); };
  const merge = async () => { setWorking(true); const got = await act("ideas.merge", key); setWorking(false); if (got?.ok) done(); };
  const back = async (e) => {
    e.preventDefault();
    if (!line.trim()) return;
    setWorking(true);
    const got = await act("ideas.back", { ...key, why: line.trim() });
    setWorking(false);
    if (got?.ok) { setLine(null); done(); }
  };
  const drop = async () => { const got = await act("ideas.drop_task", key); if (got?.ok) done(); };
  return html`<div class=${cls("shell-actions", { "is-pinned": pinned })} onClick=${(e) => e.stopPropagation()}>
    <div class="shell-actions__main">
      <button class="ok-btn primary" disabled=${!!reason || working} title=${reason || `Merge into ${into}`}
        onClick=${merge}>Merge into ${into}</button>
      <button class="ok-btn" aria-expanded=${line !== null} onClick=${() => setLine(line === null ? fixLine(r, into) : null)}>${fix ? "Fix" : "Send back"}</button>
      ${sure ? html`<span class="shell-actions__sure">Drop this result?
          <button class="ok-btn danger" onClick=${drop}>Drop it</button><button class="ok-btn" onClick=${() => setSure(false)}>Keep it</button></span>`
        : html`<button class="shell-quiet" onClick=${() => setSure(true)}>Drop…</button>`}
    </div>
    ${reason && html`<p class="shell-actions__why ok-tone-error" role="status">${reason}</p>`}
    ${line !== null && html`<form class="shell-actions__line" onSubmit=${back}>
      <input class="ok-input" autofocus value=${line} aria-label=${fix ? "What to fix, in one line" : "Why you send it back, in one line"}
        placeholder="One line: what should change?" onInput=${(e) => setLine(e.target.value)}
        onKeyDown=${(e) => e.key === "Escape" && (e.stopPropagation(), setLine(null))} />
      <button class="ok-btn primary" disabled=${!line.trim() || working}>${fix ? "Fix" : "Send back"}</button></form>`}
  </div>`;
}

function Card({ r, selected }) {
  const t = testsWords(r);
  return html`<article class=${cls("shell-card", { "is-on": selected })} tabindex="0" role="listitem" aria-label=${r.title}
      data-task=${r.task} data-idea=${r.idea} aria-current=${selected} onClick=${() => showResult(r.idea, r.task)}
      onKeyDown=${(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showResult(r.idea, r.task); } }}>
    <div class="shell-card__head"><b>${r.title}</b>
      <span class="ok-tone-muted">${r.idea_title}${r.round > 1 ? html` · <span class="shell-round">round ${r.round}</span>` : ""}</span></div>
    <dl class="shell-facts">
      <dt>Tests</dt><dd class=${`is-${t.tone}`}>${t.mark} ${t.text}${t.names.length ? html` <span class="ok-tone-muted">${t.names.join(", ")}</span>` : ""}</dd>
      <dt>Changes</dt><dd>${changesWords(r.diff)}</dd>
      ${r.cost != null && html`<dt>Cost</dt><dd>${usd(r.cost)}</dd>`}
    </dl>
    ${r.conflict && html`<p class="ok-tone-error shell-conflict">⚠ ${r.conflict}</p>`}
    <${ResultActions} r=${r} />
  </article>`;
}

function Into() {
  const rv = review.value;
  const [open, setOpen] = useState(false);
  const [making, setMaking] = useState(null);
  if (!rv) return null;
  const pick = async (branch) => { setOpen(false); setMaking(null); if (branch !== rv.into) await act("ideas.into", { branch }); };
  return html`<div class="shell-into" onKeyDown=${(e) => e.key === "Escape" && (e.stopPropagation(), setOpen(false))}>
    <button class="ok-btn" aria-haspopup="menu" aria-expanded=${open} onClick=${() => setOpen(!open)}>Merge into <b>${rv.into}</b> ▾</button>
    ${open && html`<div class="shell-menu ok-win" role="menu" aria-label="Merge into">
      ${(rv.branches || [rv.into]).map((b) => html`<button key=${b} class="shell-menu__item" role="menuitemradio"
        aria-checked=${b === rv.into} onClick=${() => pick(b)}>${b === rv.into ? "✓" : ""} ${b}</button>`)}
      ${making === null ? html`<button class="shell-menu__item" role="menuitem" onClick=${() => setMaking("")}>New branch…</button>`
        : html`<form class="shell-menu__new" onSubmit=${(e) => { e.preventDefault(); if (making.trim()) pick(making.trim()); }}>
          <input class="ok-input" autofocus value=${making} aria-label="Name of the new branch" placeholder="Name of the new branch"
            onInput=${(e) => setMaking(e.target.value)} /><button class="ok-btn primary" disabled=${!making.trim()}>Make it</button></form>`}
    </div>`}
  </div>`;
}

export function ReviewPane() {
  const rv = review.value, p = preview.value;
  const results = rv?.results || [];
  // ↑ ↓ move through the cards and open each one's code; no shortcut merges
  const move = (e) => {
    if ((e.key !== "ArrowDown" && e.key !== "ArrowUp") || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || !results.length) return;
    e.preventDefault();
    const at = results.findIndex((r) => r.task === (e.target.closest?.(".shell-card")?.dataset.task ?? p?.task) && r.idea === (e.target.closest?.(".shell-card")?.dataset.idea ?? p?.slug));
    const next = results[Math.max(0, Math.min(results.length - 1, at + (e.key === "ArrowDown" ? 1 : -1)))];
    showResult(next.idea, next.task);
    requestAnimationFrame(() => document.querySelector(`.shell-card[data-task="${next.task}"][data-idea="${next.idea}"]`)?.focus());
  };
  return html`<aside class="shell-pane shell-review" aria-label="Review" onKeyDown=${move}>
    <header class="shell-pane__head"><h2>Review ${results.length > 0 && html`<span class="shell-count">${results.length}</span>`}</h2></header>
    <${Into} />
    <div class="shell-pane__body">
      ${!rv ? html`<p class="ok-tone-muted">Opening…</p>`
        : results.length ? html`<div role="list" class="shell-cards">${results.map((r) => html`<${Card} key=${r.idea + r.task} r=${r}
            selected=${p?.kind === "result" && p.task === r.task && p.slug === r.idea} />`)}</div>`
        : html`<p class="ok-tone-muted">Nothing waits at Review. A result lands here when a Grunt's work has been tested.</p>`}
    </div>
  </aside>`;
}
