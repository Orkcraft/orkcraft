// New goal / Edit goal (docs/specs/34-v1-round-2.md §1): a title, a description, the metrics (what is measured and the
// target), a priority, the links to documents, a deadline. Saving sends the goal to the Taskmaster at once.
import { useState } from "preact/hooks";
import { html } from "../html.js";
import { board, track } from "../board/store.js";
import { act, showGoal } from "./store.js";
import { Modal, closeDialog } from "./modals.js";

export const PRIORITIES = [["high", "High"], ["normal", "Normal"], ["low", "Low"]];

export function GoalDialog({ slug = "" }) {
  const g = slug ? board.value?.tracks.find((t) => t.slug === slug) : null;
  const [title, setTitle] = useState(g?.title || "");
  const [about, setAbout] = useState(g?.about || "");
  const [priority, setPriority] = useState(g?.priority || "normal");
  const [deadline, setDeadline] = useState(g?.deadline || "");
  const [metrics, setMetrics] = useState(g?.metrics?.length ? g.metrics.map((m) => ({ name: m.name, target: m.target })) : [{ name: "", target: "" }]);
  const [links, setLinks] = useState(g?.links?.length ? [...g.links] : [""]);
  const [saving, setSaving] = useState(false);
  const set = (list, setList, n, patch) => setList(list.map((x, i) => (i === n ? (typeof x === "string" ? patch : { ...x, ...patch }) : x)));
  const save = async (e) => {
    e?.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    const got = await act("ideas.goal_save", { ...(slug ? { slug } : {}), title: title.trim(), about, priority, deadline,
      metrics: metrics.filter((m) => m.name.trim()).map((m) => ({ name: m.name.trim(), target: m.target.trim() })),
      links: links.map((l) => l.trim()).filter(Boolean) });
    setSaving(false);
    if (got?.slug) { closeDialog(); track.value = got.slug; showGoal(got.slug); }
  };
  return html`<${Modal} title=${slug ? "Edit goal" : "New goal"} onClose=${closeDialog} wide=${true}
    foot=${html`<button type="button" class="ok-btn" onClick=${closeDialog}>Cancel</button>
      <button type="submit" form="goal-form" class="ok-btn primary" disabled=${!title.trim() || saving}>${slug ? "Save goal" : "Save goal"}</button>`}>
    <form id="goal-form" class="shell-form" onSubmit=${save}>
      <label class="shell-field"><span class="ok-font-label">Title</span>
        <input class="ok-input" autofocus required value=${title} aria-label="Title" placeholder="What you want to reach" onInput=${(e) => setTitle(e.target.value)} /></label>
      <label class="shell-field"><span class="ok-font-label">Description</span>
        <textarea class="ok-input" rows="3" value=${about} aria-label="Description" placeholder="A few lines: what it is for"
          onInput=${(e) => setAbout(e.target.value)}></textarea></label>
      <div class="shell-field" role="group" aria-label="Metrics"><span class="ok-font-label">Metrics</span>
        ${metrics.map((m, n) => html`<div key=${n} class="shell-rowfields">
          <input class="ok-input" value=${m.name} aria-label=${`Metric ${n + 1}: what is measured`} placeholder="What is measured: weekly installs"
            onInput=${(e) => set(metrics, setMetrics, n, { name: e.target.value })} />
          <input class="ok-input shell-rowfields__target" value=${m.target} aria-label=${`Metric ${n + 1}: the target`} placeholder="Target: 50"
            onInput=${(e) => set(metrics, setMetrics, n, { target: e.target.value })} />
          <button type="button" class="ok-btn" aria-label=${`Remove metric ${n + 1}`} onClick=${() => setMetrics(metrics.length > 1 ? metrics.filter((_, i) => i !== n) : [{ name: "", target: "" }])}>−</button></div>`)}
        <button type="button" class="board-link" onClick=${() => setMetrics([...metrics, { name: "", target: "" }])}>+ Add a metric</button></div>
      <div class="shell-field" role="group" aria-label="Priority"><span class="ok-font-label">Priority</span>
        <div class="shell-seg">${PRIORITIES.map(([id, name]) => html`<label key=${id} class=${`shell-seg__one${priority === id ? " is-on" : ""}`}>
          <input type="radio" name="priority" class="gui-onb__hide" checked=${priority === id} onChange=${() => setPriority(id)} />${name}</label>`)}</div></div>
      <div class="shell-field" role="group" aria-label="Links"><span class="ok-font-label">Links</span>
        <span class="ok-font-status ok-tone-muted">A path in the repository, a Wiki page or a web address. Web addresses are kept as links, never fetched.</span>
        ${links.map((l, n) => html`<div key=${n} class="shell-rowfields">
          <input class="ok-input" value=${l} aria-label=${`Link ${n + 1}`} placeholder="docs/plan.md · pages/notes.md · https://…"
            onInput=${(e) => set(links, setLinks, n, e.target.value)} />
          <button type="button" class="ok-btn" aria-label=${`Remove link ${n + 1}`} onClick=${() => setLinks(links.length > 1 ? links.filter((_, i) => i !== n) : [""])}>−</button></div>`)}
        <button type="button" class="board-link" onClick=${() => setLinks([...links, ""])}>+ Add a link</button></div>
      <label class="shell-field"><span class="ok-font-label">Deadline <span class="ok-tone-muted">(optional)</span></span>
        <input class="ok-input" type="date" value=${deadline} aria-label="Deadline" onInput=${(e) => setDeadline(e.target.value)} /></label>
    </form>
  <//>`;
}
