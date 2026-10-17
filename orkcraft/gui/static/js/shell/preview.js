// The preview, the centre (docs/specs/33-v1-shell.md §6): one thing at a time — an idea's spec (29a's sections view), an
// idea's plan (scrolled to a to-do, said what it unblocks), a task (its brief, state and log) or a result's code
// (commits, then the files changed, each patch folded). A result's actions stay pinned at its foot.
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { board, page } from "../board/store.js";
import { IdeaView, PlanView } from "../board/idea.js";
import { preview, detail, review, act, closePreview, showIdea, showResult, refreshShell } from "./store.js";
import { ResultActions, testsWords, changesWords, isRed } from "./review.js";

const TASK_STATE = { waiting: "waiting", ready: "queued", running: "working", testing: "testing", review: "at Review", merged: "merged",
  failed: "needs you", held: "held" };

function Empty() {
  const need = board.value?.today.needs_you[0];
  return html`<div class="shell-empty"><p>Open an idea, a task or a result.</p>
    ${need && html`<p class="ok-tone-muted">First on your list: <button class="board-link" onClick=${() => showIdea(need.idea)}>${need.title}</button> — ${need.text}</p>`}</div>`;
}

function Task({ d }) {
  const t = d?.task;
  const ref = useRef();
  const live = t && (t.state === "running" || t.state === "testing");
  useEffect(() => {                        // the log's tail is read again every 5 s while the task runs
    if (!live) return undefined;
    const id = setInterval(refreshShell, 5000);
    return () => clearInterval(id);
  }, [live]);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [t?.log]);
  if (!t) return html`<p class="ok-tone-muted">Opening…</p>`;
  return html`<div class="shell-task">
    <dl class="shell-facts">
      <dt>State</dt><dd data-state=${t.state}>${TASK_STATE[t.state] || t.state}${t.note ? html` <span class="ok-tone-muted">${t.note}</span>` : ""}</dd>
      <dt>Idea</dt><dd><button class="board-link" onClick=${() => showIdea(t.idea)}>${t.idea_title}</button></dd>
      <dt>Tier</dt><dd>${t.tier}</dd>
      <dt>Branch</dt><dd><code>${t.branch || "—"}</code></dd>
      <dt>Round</dt><dd>${t.round || 1}</dd>
      <dt>Spend</dt><dd>${t.cost != null ? `$${t.cost.toFixed(2)}` : "—"}</dd>
    </dl>
    ${t.error && html`<p class="ok-tone-error" role="alert">${t.error}</p>`}
    <h3 class="board-sub">Brief</h3><p class="shell-brief">${t.brief}</p>
    ${t.state === "review" && html`<p><button class="ok-btn primary" onClick=${() => showResult(t.idea, t.id)}>Open the result</button></p>`}
    ${live && html`<p><button class="ok-btn danger" onClick=${() => act("ideas.stop_task", { slug: t.idea, task: t.id })}>Stop</button></p>`}
    <h3 class="board-sub">Log</h3>
    <pre class="shell-log" ref=${ref} aria-label="Log">${t.log || "Nothing logged yet."}</pre>
  </div>`;
}

function Patch({ patch }) {
  return html`<pre class="shell-patch">${patch.split("\n").map((ln, n) => html`<span key=${n}
    class=${cls("shell-patch__line", { "is-add": ln.startsWith("+") && !ln.startsWith("+++"), "is-del": ln.startsWith("-") && !ln.startsWith("---"),
      "is-hunk": ln.startsWith("@@") })}>${ln}\n</span>`)}</pre>`;
}

function File({ f }) {
  const [open, setOpen] = useState(false);       // the lines are drawn when it opens: a big diff stays light
  return html`<details class="shell-file" onToggle=${(e) => setOpen(e.currentTarget.open)}>
    <summary><code>${f.path}</code><span class="shell-file__n"><span class="is-add">+${f.added}</span> <span class="is-del">−${f.removed}</span></span></summary>
    ${open && (f.patch == null ? html`<p class="ok-tone-muted">Too large to show.</p>` : html`<${Patch} patch=${f.patch} />`)}
  </details>`;
}

function Result({ d, p }) {
  const r = (review.value?.results || []).find((x) => x.idea === p.slug && x.task === p.task);
  const diff = d?.diff;
  const t = r && testsWords(r);
  return html`<div class="shell-result">
    <div class="shell-result__body">
      ${r ? html`<dl class="shell-facts">
        <dt>Tests</dt><dd class=${`is-${t.tone}`}>${t.mark} ${t.text}${t.names.length ? html` <span class="ok-tone-muted">${t.names.join(", ")}</span>` : ""}</dd>
        <dt>Changes</dt><dd>${changesWords(r.diff)}</dd>${r.round > 1 ? html`<dt>Round</dt><dd>${r.round}</dd>` : ""}</dl>
        ${r.conflict && html`<p class="ok-tone-error">⚠ ${r.conflict}</p>`}
        ${isRed(r) && r.tests.tail && html`<details class="shell-file"><summary>What the tests said</summary><pre class="shell-log">${r.tests.tail}</pre></details>`}`
        : html`<p class="ok-tone-muted">This result is no longer waiting at Review.</p>`}
      ${!diff ? html`<p class="ok-tone-muted">Reading the code…</p>` : html`
        <h3 class="board-sub">Commits</h3>
        <ol class="shell-commits">${diff.commits.map((c) => html`<li key=${c.sha}><code>${c.sha}</code> ${c.subject}</li>`)}</ol>
        <h3 class="board-sub">Files changed (${diff.files.length})</h3>
        ${diff.files.map((f) => html`<${File} key=${f.path} f=${f} />`)}
        ${diff.truncated && html`<p class="ok-tone-muted">Some files are too large to show.</p>`}`}
    </div>
    ${r && html`<footer class="shell-result__foot"><${ResultActions} r=${r} pinned=${true} /></footer>`}
  </div>`;
}

export function Preview() {
  const p = preview.value, pg = page.value, d = detail.value;
  const title = !p ? "" : p.kind === "task" || p.kind === "result" ? (d?.task?.title || "…") : (pg?.title || "…");
  const kind = { idea: "Spec", plan: "Plan", task: "Task", result: "Code" }[p?.kind] || "";
  const sub = (p?.kind === "task" || p?.kind === "result") ? d?.task?.idea_title : "";
  return html`<section class=${cls("shell-preview", { "is-open": !!p })} aria-label="Preview">
    ${p && html`<header class="shell-pane__head"><button class="ok-btn shell-back" aria-label="Back" onClick=${closePreview}>← Back</button>
      <h2 title=${title}><span class="ok-tone-muted">${kind}</span> ${title}${sub ? html` <span class="ok-tone-muted">· ${sub}</span>` : ""}</h2>
      <button class="ok-btn shell-close" aria-label="Close the preview (Esc)" onClick=${closePreview}>Close</button></header>`}
    <div class="shell-preview__body">
      ${!p ? html`<${Empty} />`
        : p.kind === "idea" ? (pg ? html`<${IdeaView} p=${pg} />` : html`<p class="ok-tone-muted">Opening…</p>`)
        : p.kind === "plan" ? (pg ? html`<${PlanView} p=${pg} todo=${p.todo} />` : html`<p class="ok-tone-muted">Opening…</p>`)
        : p.kind === "task" ? html`<${Task} d=${d} />` : html`<${Result} d=${d} p=${p} />`}
    </div>
  </section>`;
}
