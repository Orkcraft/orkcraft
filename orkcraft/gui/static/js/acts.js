// The console's dialogs that change a garrison or a window, as the TUI's (screens/orders.py,
// screens/orc_flow.py): an ork's orders and model, a road's handler, a redesign — and the jobs a
// model call makes (gui/console.py): the Recruiter's handler to hire, the Council's notes, the
// steward's findings and proposals.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { Dialog } from "./dialog.js";
import { selectOrk } from "./windows.js";
import { KeeperJob } from "./keeper.js";

function Field({ label, children }) {
  return html`<label class="gui-field"><span class="ok-font-label">${label}</span>${children}</label>`;
}

function Select({ value, options, onChange }) {
  return html`<select class="ok-input" value=${value} onChange=${(e) => onChange(e.target.value)}>
    ${options.map(([v, label]) => html`<option key=${v} value=${v} selected=${v === value}>${label}</option>`)}
  </select>`;
}

/** T: an ork's orders and trigger, and a handler's tier. */
export function OrdersDialog({ b, i, onClose, onDone }) {
  const [orders, setOrders] = useState(i.orders || "");
  const [kind, setKind] = useState(i.trigger.type);
  const [expr, setExpr] = useState(i.trigger.expression || "");
  const handlerTier = i.uses_model && !i.lead && i.steps.length > 0;
  const [tier, setTier] = useState(handlerTier ? i.steps[0].tier : "");
  const save = () => command("ork.orders", { id: b.id, ork: i.ref, orders, trigger: { type: kind, expression: expr },
                                             ...(handlerTier && tier !== i.steps[0].tier ? { tier } : {}) })
    .then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`Standing orders — ${i.name}`)} text=${i.about_plain} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save}>${say("Save")}</button>`}>
    <div class="gui-form">
      <${Field} label=${say("Standing orders (context for this ork's work)")}>
        <textarea class="ok-input gui-textarea" rows="3" value=${orders} onInput=${(e) => setOrders(e.target.value)}
          placeholder=${say("e.g. keep an eye on T1092 and nudge me before 06:00")}></textarea></${Field}>
      <${Field} label=${say("Trigger")}><div class="gui-form__row">
        <${Select} value=${kind} options=${i.triggers} onChange=${setKind} />
        ${kind !== "on_demand" && html`<input class="ok-input" value=${expr} onInput=${(e) => setExpr(e.target.value)}
          placeholder=${kind === "cron" ? "*/15 * * * *" : "/path"} />`}</div></${Field}>
      ${handlerTier && html`<${Field} label=${say("Tier")}><${Select} value=${tier} options=${i.tiers} onChange=${setTier} /></${Field}>`}
    </div>
  </${Dialog}>`;
}

/** The Inventory's model: harness and tier per step (a pipeline's own steps keep theirs). */
export function ModelDialog({ b, i, onClose, onDone }) {
  const [steps, setSteps] = useState(i.steps.map((s) => ({ harness: s.harness, tier: s.tier })));
  const set = (n, key, v) => setSteps(steps.map((s, k) => (k === n ? { ...s, [key]: v } : s)));
  const save = () => command("ork.model", { id: b.id, ork: i.ref, steps }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`${i.name} — model and tier`)} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save}>${say("Save")}</button>`}>
    <div class="gui-form">${i.steps.map((s, n) => html`<${Field} key=${n} label=${s.role}>
      ${s.editable ? html`<div class="gui-form__row">
          <${Select} value=${steps[n].harness} options=${i.harnesses.map((h) => [h, h])} onChange=${(v) => set(n, "harness", v)} />
          <${Select} value=${steps[n].tier} options=${i.tiers} onChange=${(v) => set(n, "tier", v)} /></div>`
        : html`<span class="ok-font-status ok-tone-muted">${s.harness}</span>`}</${Field}>`)}</div>
  </${Dialog}>`;
}

/** D: what should change in the building's window; `default` brings its type's layout back. */
export function RedesignDialog({ b, onClose }) {
  const [request, setRequest] = useState("");
  const send = () => command("building.redesign", { id: b.id, request }).then(onClose, () => {});
  return html`<${Dialog} title=${say(`Redesign — ${b.title}`)} text=${say("What should change in its window? Its steward redraws it.")}
      onCancel=${onClose} actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn" onClick=${() => command("building.redesign", { id: b.id, request: "default" }).then(onClose, () => {})}>
          ${say("Its own layout")}</button>
        <button class="ok-btn primary" disabled=${!request.trim()} onClick=${send}>${say("Ask the steward")}</button>`}>
    <input class="ok-input" autofocus value=${request} placeholder=${say("e.g. the tree narrower, the page larger")}
      onInput=${(e) => setRequest(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && request.trim() && send()} />
  </${Dialog}>`;
}

/** H: who takes a road's carts — one of its building's handlers, or plain. */
export function HandlerDialog({ road, onClose, onDone }) {
  const [h, setH] = useState(null);
  useEffect(() => { command("road.handlers", { key: road.key }).then(setH, () => setH({ current: "", handlers: [] })); }, [road.key]);
  const pick = (handler) => command("road.handler", { key: road.key, handler }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`Handler — ${road.title} · ${road.label}`)} text=${say("Who takes what this road brings?")}
      onCancel=${onClose} actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>`}>
    ${h === null ? html`<p class="ok-tone-muted">${say("Looking…")}</p>` : html`<div class="gui-orders__options">
      <button class="ok-btn" disabled=${!h.current} onClick=${() => pick("")}>${say("Plain (no ork)")}</button>
      ${h.handlers.map(([id, label]) => html`<button key=${id} class="ok-btn" disabled=${id === h.current}
        onClick=${() => pick(id)}>${label}</button>`)}</div>`}
  </${Dialog}>`;
}

// -- the jobs: what a model call brought back -----------------------------------------------------------

function RecruitView({ v }) {
  return html`<div class="gui-form">
    <p class="ok-font-body"><b>${v.name}</b> <span class="ok-tone-muted">· ${v.kind_label || v.kind}${v.tier ? ` · ${v.tier}` : ""}</span></p>
    ${v.why && html`<p class="ok-font-status">Why ${v.kind_label || v.kind}: ${v.why}</p>`}
    ${v.role && html`<p class="ok-font-status ok-tone-muted">${v.role}</p>`}
    ${v.orders && html`<p class="ok-font-status">${v.kind === "steward" ? "Rule" : "Orders"}: ${v.orders}</p>`}
    ${v.kind === "steward" && html`<p class="ok-font-status ok-tone-muted">The steward carries it out on its own tool: no new ork.</p>`}
    ${v.chain > 0 && html`<p class="ok-font-status ok-tone-muted">A chain of ${v.chain} steps, never calls a model.</p>`}
    ${v.roads.length > 0 && html`<p class="ok-font-status">Listens: ${v.roads.map((r) => `${r.from} · ${r.event}`).join(", ")}</p>`}
    ${v.script && html`<pre class="gui-pre gui-orders__context">${v.script}</pre>`}
    <p class="ok-font-status ok-tone-muted">Attempts: ${v.attempts}${v.cost ? ` · cost ${v.cost}` : ""}</p>
    ${v.notes && html`<h3 class="ok-font-heading">${v.blocked ? "The Council rejected it" : "The Council's notes"}</h3>
      <ul class="gui-rows">${v.notes.map((n, k) => html`<li key=${k} class=${n.severity === "block" ? "ok-tone-fire" : ""}>
        <span class="ok-tone-muted">${n.role}:</span> ${n.text}</li>`)}</ul>`}
  </div>`;
}

/** A steward's report: what it found, then each proposal as a block with its own Apply and Skip. A proposal
 *  taken stays in the list, quieter, saying what it did; the report closes on Done or when all are taken. */
function ReportView({ job, v, skipped, onSkip }) {
  const apply = (index) => command("job.accept", { job: job.id, index }).catch(() => {});
  return html`<div class="gui-form">
    <p class="ok-dialog__section">${job.kind === "redesign" ? say("Asked") : say("Findings")}${v.findings.length ? ` · ${v.findings.length}` : ""}</p>
    ${v.findings.length ? html`<ul class="gui-findings">${v.findings.map((f, k) => html`<li key=${k}>${f}</li>`)}</ul>`
      : html`<p class="ok-font-status ok-tone-muted">${say("Nothing found: it runs as it should.")}</p>`}
    ${v.rules && v.rules.length > 0 && html`<p class="ok-dialog__section">${say("What its rules and agents cost")}</p>
      <ul class="gui-findings">${v.rules.map((r, k) => html`<li key=${k}>${r}</li>`)}</ul>`}
    <p class="ok-dialog__section">${say("Proposals")}${v.proposals.length ? ` · ${v.proposals.length}` : ""}</p>
    ${v.proposals.length ? html`<ul class="gui-proposals">${v.proposals.map((p) => {
        const skip = skipped.has(p.index);
        return html`<li key=${p.index} class=${cls("gui-proposal", { "is-done": !!p.applied, "is-skipped": skip })}>
          <div class="gui-proposal__title"><span class="gui-proposal__kind">${say(p.type)}</span>${p.why}</div>
          ${p.replay && html`<p class="gui-proposal__why">${p.replay}</p>`}
          ${p.saves && html`<p class="gui-proposal__why">${say("Spend")}: ${p.saves}</p>`}
          ${p.outline && html`<p class="gui-proposal__more">${p.outline}</p>`}
          ${p.script && html`<pre class="gui-pre gui-orders__context">${p.script}</pre>`}
          ${p.applied && html`<p class="gui-proposal__why ok-tone-ok">✓ ${p.applied}</p>`}
          <div class="gui-proposal__acts">
            ${p.applied ? html`<span class="ok-tone-ok">✓ ${say("Applied")}</span>`
              : skip ? html`<button class="ok-btn" onClick=${() => onSkip(p.index)}>${say("Undo skip")}</button>`
              : p.ready ? html`<button class="ok-btn" onClick=${() => onSkip(p.index)}>${say("Skip")}</button>
                  <button class="ok-btn primary" onClick=${() => apply(p.index)}>${say("Apply")}</button>`
              : html`<span class="ok-tone-muted" title=${say("A note, or a change its replay did not back")}>${say("note only")}</span>`}
          </div></li>`;
      })}</ul>`
      : html`<p class="ok-font-status ok-tone-muted">${say("No proposals.")}</p>`}
  </div>`;
}

/** The report as a dialog: its body scrolls, its foot keeps Apply the rest and Done. */
function ReportDialog({ job, title, drop }) {
  const [skipped, setSkipped] = useState(() => new Set());
  const v = job.view;
  const flip = (i) => setSkipped((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  const rest = v.proposals.filter((p) => p.ready && !p.applied && !skipped.has(p.index));
  const taken = v.proposals.filter((p) => p.applied).length;
  const applyRest = async () => {
    for (const p of rest) {
      try { await command("job.accept", { job: job.id, index: p.index }); } catch { return; }
    }
  };
  const meta = [v.ts && `${say("Watched")} ${v.ts}`, v.cost && `${say("cost")} ${v.cost}`].filter(Boolean).join(" · ");
  return html`<${Dialog} title=${title} meta=${meta} onCancel=${drop} wide
      actions=${html`<span class="gui-dialog__note">${v.proposals.length ? say(`${taken} of ${v.proposals.length} applied`) : ""}</span>
        ${rest.length > 1 && html`<button class="ok-btn" onClick=${applyRest}>${say("Apply the rest")} · ${rest.length}</button>`}
        <button class="ok-btn primary" onClick=${drop}>${say("Done")}</button>`}>
    <${ReportView} job=${job} v=${v} skipped=${skipped} onSkip=${flip} /></${Dialog}>`;
}

const JOB_TITLE = { recruit: "Recruiter", watch: "Steward", redesign: "Redesign", road: "Listen" };

/** The roads the steward offers for what the person said (gui/road_planner.py): lay one, or hand it to the
 *  Recruiter when an ork has to read the carts by a rule. */
function RoadOptions({ job, v }) {
  const take = (index) => command("job.accept", { job: job.id, index }).catch(() => {});
  if (!v.options.length) return html`<p>${say("No road fits:")} ${v.missing}</p>`;
  return html`<ul class="gui-rows">${v.options.map((o) => html`<li key=${o.index}>
      <div>${o.say}</div>
      <div class="ok-font-status ok-tone-muted">${o.from} · ${o.event}${o.match ? ` · only “${o.match}”` : ""}
        ${o.rule ? html` · ${say("a road rule:")} ${o.rule}` : ""}</div>
      <button class="ok-act" onClick=${() => take(o.index)}><span class="ok-act__label">${o.rule ? say("Set up the rule") : say("Lay it")}</span></button>
    </li>`)}</ul>
    ${v.cost && html`<p class="ok-font-status ok-tone-muted">${v.cost}</p>`}`;
}

/** The oldest job of the console, as a dialog: running, ready to take, the Council's notes, failed. */
export function Jobs() {
  const jobs = town.value.jobs || [];
  if (!jobs.length) return null;
  const job = jobs[0];
  if (job.kind === "keeper") return html`<${KeeperJob} job=${job} />`;
  const drop = () => command("job.drop", { job: job.id }).catch(() => {});
  const accept = () => command("job.accept", { job: job.id }).then((ref) => ref && selectOrk(ref), () => {});
  const title = say(`${JOB_TITLE[job.kind] || "Job"} — ${job.title}`);
  if (job.state === "running") {
    return html`<${Dialog} title=${title} text=${job.text} onCancel=${drop}
      actions=${html`<button class="ok-btn" onClick=${drop}>${say("Cancel")}</button>`}>
      <p class="ok-font-status ok-tone-muted">${say("This calls a model; it takes a moment.")}</p></${Dialog}>`;
  }
  if (job.state === "failed") {
    return html`<${Dialog} title=${title} text=${job.error} onCancel=${drop} warn
      actions=${html`<button class="ok-btn primary" onClick=${drop}>${say("Close")}</button>`} />`;
  }
  if (job.kind === "road") {
    return html`<${Dialog} title=${title} text=${job.view.options.length ? say("Pick the road to lay.") : ""} onCancel=${drop}
        actions=${html`<button class="ok-btn" onClick=${drop}>${say("Cancel")}</button>`}>
      <${RoadOptions} job=${job} v=${job.view} /></${Dialog}>`;
  }
  if (job.kind === "recruit") {
    const blocked = job.view.blocked;
    return html`<${Dialog} title=${title} text=${job.text} onCancel=${drop} warn=${job.state === "verdict"}
        actions=${html`<button class="ok-btn" onClick=${drop}>${blocked ? "Close" : "Decline"}</button>
          ${!blocked && html`<button class="ok-btn primary" onClick=${accept}>${job.state === "verdict" ? "Hire anyway" : "Hire"}</button>`}`}>
      <${RecruitView} v=${job.view} /></${Dialog}>`;
  }
  return html`<${ReportDialog} key=${job.id} job=${job} title=${title} drop=${drop} />`;
}
