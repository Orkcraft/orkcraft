// Add agent / Edit agent (docs/specs/34-v1-round-2.md §3): a name, a model, an instruction (added to every task prompt of
// that agent) and how many may work at once. An agent of your own can be deleted (its task types go back to Grunt, said
// before); Taskmaster and Grunt can be edited, not deleted. `assign`: a task type to give the new agent to.
import { useState } from "preact/hooks";
import { html } from "../html.js";
import { say } from "../link.js";
import { roles, act } from "./store.js";
import { Modal, closeDialog } from "./modals.js";

export function AgentDialog({ slug = "", assign = "" }) {
  const data = roles.value, r = slug ? data?.roles.find((x) => x.slug === slug) : null;
  const [name, setName] = useState(r?.name || "");
  const [model, setModel] = useState(r ? r.model : "warrior");
  const [instruction, setInstruction] = useState(r?.instruction || "");
  const [many, setMany] = useState(r?.max_parallel || 2);
  const [sure, setSure] = useState(false);
  const [busy, setBusy] = useState(false);
  const models = (data?.models || []).filter((m) => m.id || r?.slug === "grunt");
  const mine = data ? data.kinds.filter((k) => k.role === slug).map((k) => k.label.toLowerCase()) : [];
  const save = async (e) => {
    e?.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    const got = await act("ideas.role_save", { ...(slug ? { slug } : {}), name: name.trim(), model, max_parallel: Number(many), instruction });
    if (got?.slug && assign) await act("ideas.kind_set", { kind: assign, role: got.slug });
    setBusy(false);
    if (got?.slug) closeDialog();
  };
  const drop = async () => { setBusy(true); const got = await act("ideas.role_drop", { slug }); setBusy(false); if (got?.ok) closeDialog(); };
  return html`<${Modal} title=${slug ? `Edit agent` : "Add agent"} onClose=${closeDialog}
    foot=${sure ? html`<span class="shell-modal__sure">${mine.length ? `Its task types (${mine.join(", ")}) go back to Grunt.` : "No task type uses it."} Delete ${r?.name}?</span>
        <button type="button" class="ok-btn" onClick=${() => setSure(false)}>Keep it</button>
        <button type="button" class="ok-btn danger" disabled=${busy} onClick=${drop}>Delete agent</button>`
      : html`${slug && !r?.builtin && html`<button type="button" class="ok-btn danger shell-modal__left" onClick=${() => setSure(true)}>Delete…</button>`}
        <button type="button" class="ok-btn" onClick=${closeDialog}>Cancel</button>
        <button type="submit" form="agent-form" class="ok-btn primary" disabled=${!name.trim() || busy}>Save agent</button>`}>
    <form id="agent-form" class="shell-form" onSubmit=${save}>
      <label class="shell-field"><span class="ok-font-label">Name</span>
        <input class="ok-input" autofocus required value=${name} aria-label="Name" placeholder="Docs scribe" onInput=${(e) => setName(e.target.value)} /></label>
      <label class="shell-field"><span class="ok-font-label">Model</span>
        <select class="ok-input" aria-label="Model" value=${model} onChange=${(e) => setModel(e.target.value)}>
          ${models.map((m) => html`<option key=${m.id} value=${m.id}>${m.label}</option>`)}</select></label>
      <label class="shell-field"><span class="ok-font-label">At most at once</span>
        <select class="ok-input" aria-label="At most at once" value=${String(many)} onChange=${(e) => setMany(e.target.value)}>
          ${[1, 2, 3, 4, 5, 6, 7, 8].map((n) => html`<option key=${n} value=${String(n)}>${n}</option>`)}</select></label>
      <label class="shell-field"><span class="ok-font-label">Instruction</span>
        <textarea class="ok-input" rows="5" value=${instruction} aria-label="Instruction" placeholder="Added to every task this agent does"
          onInput=${(e) => setInstruction(e.target.value)}></textarea></label>
      ${assign && html`<p class="ok-font-status ok-tone-muted">${say("It will do every task of the type")} “${assign}”.</p>`}
    </form>
  <//>`;
}
