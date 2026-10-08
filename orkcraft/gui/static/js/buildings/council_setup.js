// 🪔 Setting up a Review board, in its own panel — never a dialog (docs/design/review-board.md §3): the purpose,
// the clan the keeper proposes for it, the exits. The steps' state is the worker's (core/workers/council_setup.py);
// what the person edits stays in a draft here until Save sends it. Past the purpose, ← Back stands in the
// panel's top right corner (js/setup.js); Save opens the board's Info.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { useSetupBack } from "../setup.js";
import { setupDone } from "../windows.js";
import { openInLake } from "../lake.js";

const STEPS = [["purpose", "Purpose"], ["clan", "Clan"], ["exits", "Exits"]];
const TIERS = ["", "laborer", "warrior", "elder"];
const STARTS = [
  ["PRD review", "PRDs before development: is the scope clear, what can go wrong, can marketing sell it."],
  ["Code review", "Code changes before they merge: correctness, tests, security."],
  ["Inbox triage", "Messages from the support inbox and Slack: who should take each one on, and how soon."],
  ["New event check", "New calendar events: is the meeting needed, is the time right, is there an agenda."],
];

/** An exit's id, as realm/team.py makes it (a road out waits for it). */
const exitId = (name) => String(name).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32);

function Steps({ step }) {
  const at = STEPS.findIndex(([s]) => s === step);
  return html`<div class="council-setup__steps" aria-label=${say("Steps")}>
    ${STEPS.map(([s, label], i) => html`<span key=${s} class=${cls({ "is-on": i === at, "is-done": i < at })}>
      ${i < at ? "✓" : i + 1} ${label}</span>${i < STEPS.length - 1 ? html`<span class="ok-tone-muted">›</span>` : ""}`)}
  </div>`;
}

const fresh = (s) => ({ purpose: s.purpose, members: s.members.map((m) => ({ ...m })), exits: s.exits.map((e) => ({ ...e })) });

/** What the person edits, taken again from the worker whenever its proposal changes (the keeper proposed). */
function Draft({ id, s, data, briefOf }) {
  const from = JSON.stringify([s.purpose, s.members, s.exits]);
  const [draft, setDraft] = useState(() => fresh(s));
  useEffect(() => setDraft(fresh(s)), [from]);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  return s.step === "purpose" ? html`<${Purpose} id=${id} s=${s} draft=${draft} set=${set} />`
    : s.step === "clan" ? html`<${Clan} id=${id} s=${s} draft=${draft} set=${set} briefOf=${briefOf} />`
    : html`<${Exits} id=${id} s=${s} draft=${draft} set=${set} data=${data} onSaved=${() => setupDone(id)} />`;
}

function Purpose({ id, s, draft, set }) {
  return html`<div class="council-setup">
    <p class="ok-tone-muted council-setup__sub">Say what this board reviews and what matters. The steward picks the clan for it, and you check the pick.</p>
    <label class="council-setup__label" for=${`purpose-${id}`}>What does this board review, and what matters?</label>
    <textarea id=${`purpose-${id}`} class="ok-input gui-textarea" rows="4" value=${draft.purpose}
      placeholder=${say("e.g. PRDs before development: scope, risks, whether marketing can sell it")}
      onInput=${(e) => set({ purpose: e.target.value })}></textarea>
    <p class="ok-tone-muted council-setup__sub">One board, one kind of document. Another kind — another board beside it.</p>
    <span class="council-setup__label">Or start from</span>
    <div class="council-setup__row">${STARTS.map(([label, text]) => html`<button key=${label} class="ok-chip"
      onClick=${() => set({ purpose: text })}>${label}</button>`)}</div>
    ${(s.presets || []).length > 0 && html`<span class="council-setup__label">${say("Or set it up in one click")}</span>
      <div class="council-setup__row">${s.presets.map((p) => html`<button key=${p.id} class="ok-chip" title=${say(p.purpose)}
        onClick=${() => act(id, "setup_preset", { preset: p.id }).catch(() => {})}>${say(p.title)}</button>`)}</div>`}
    <div class="council-setup__foot">
      <span class="ok-tone-muted council-setup__sub">The steward proposes in one turn</span>
      <button class="ok-btn primary" disabled=${!draft.purpose.trim() || !!s.busy}
        onClick=${() => act(id, "propose", { purpose: draft.purpose }).catch(() => {})}>Propose the clan</button>
    </div>
  </div>`;
}

function Clan({ id, s, draft, set, briefOf }) {
  const [role, setRole] = useState("");
  const edit = (i, patch) => set({ members: draft.members.map((m, j) => (j === i ? { ...m, ...patch } : m)) });
  const add = () => { if (role.trim()) { set({ members: [...draft.members, { role: role.trim(), checks: "", tier: "", veto: false }] }); setRole(""); } };
  return html`<div class="council-setup">
    ${s.busy ? html`<p class="ok-tone-muted" role="status">${s.busy}</p>`
      : html`<p class="ok-tone-muted council-setup__sub">The steward read the purpose and proposes these. Each brief is a file you can open and change.</p>`}
    <ul class="council-setup__list">${draft.members.map((m, i) => html`<li key=${i} class="council-setup__item">
      <div class="council-setup__name"><b>${m.role}</b>
        <button class="council-setup__tag" title=${say("The model tier: a click changes it")}
          onClick=${() => edit(i, { tier: TIERS[(TIERS.indexOf(m.tier) + 1) % TIERS.length] })}>${m.tier || say("default")}</button>
        <button class=${cls("council-setup__tag", { "is-veto": m.veto })} aria-pressed=${!!m.veto}
          onClick=${() => edit(i, { veto: !m.veto })}>${m.veto ? "veto" : say("no veto")}</button></div>
      <div class="council-setup__acts">
        ${briefOf(m.role) && html`<button class="ok-btn" onClick=${() => openInLake({ path: briefOf(m.role), title: `Brief — ${m.role}`, from: id })}>Brief</button>`}
        <button class="ok-btn" onClick=${() => set({ members: draft.members.filter((_x, j) => j !== i) })}>Remove</button></div>
      <input class="ok-input council-setup__checks" aria-label=${say(`What ${m.role} checks`)} value=${m.checks}
        placeholder=${say("What it checks, in a sentence")} onInput=${(e) => edit(i, { checks: e.target.value })} />
    </li>`)}</ul>
    <div class="council-setup__row">
      <input class="ok-input" style="flex: 1; width: auto" value=${role} placeholder=${say("Add a member: its role, e.g. Accessibility checker")}
        onInput=${(e) => setRole(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && add()} />
      <button class="ok-btn" disabled=${!role.trim()} onClick=${add}>Add</button>
    </div>
    ${s.error && html`<p class="ok-tone-wait">⚠ ${s.error}</p>`}
    <div class="council-setup__foot">
      <span class="ok-tone-muted council-setup__sub">${draft.members.length} ${draft.members.length === 1 ? "member" : "members"}</span>
      <button class="ok-btn primary" disabled=${!draft.members.length || !!s.busy}
        onClick=${() => act(id, "setup_go", { step: "exits" }).catch(() => {})}>Next: the exits</button>
    </div>
  </div>`;
}

function Exits({ id, s, draft, set, data, onSaved }) {
  const [name, setName] = useState("");
  const edit = (i, patch) => set({ exits: draft.exits.map((e, j) => (j === i ? { ...e, ...patch } : e)) });
  const connected = (e) => (data.exits || []).find((x) => x.id === exitId(e.name))?.connected;
  const add = () => { if (name.trim()) { set({ exits: [...draft.exits, { name: name.trim(), when: "" }] }); setName(""); } };
  const save = () => act(id, "setup_save", { purpose: draft.purpose, members: draft.members, exits: draft.exits }).then(onSaved, () => {});
  return html`<div class="council-setup">
    <div class="council-setup__row"><span class="council-setup__label" style="margin: 0">Start from</span>
      ${Object.entries(s.templates).map(([k, list]) => html`<button key=${k} class="ok-chip"
        onClick=${() => set({ exits: list.map((e) => ({ ...e })) })}>${k === "who" ? "Who does it" : "Decision"}</button>`)}</div>
    <p class="ok-tone-muted council-setup__sub">The steward sends each document down exactly one exit, by its rule. Every exit carries the clan's verdict on top.</p>
    <ul class="council-setup__list">
      ${draft.exits.map((e, i) => html`<li key=${i} class="council-setup__item">
        <input class="ok-input council-setup__exit" aria-label=${say("The exit's name")} value=${e.name} onInput=${(ev) => edit(i, { name: ev.target.value })} />
        <div class="council-setup__acts">
          ${connected(e) ? html`<span class="ok-tone-ok">→ ${say("connected")} ✓</span>` : html`<span class="ok-tone-wait">⚠ ${say("not connected")}</span>`}
          <button class="ok-btn" onClick=${() => set({ exits: draft.exits.filter((_x, j) => j !== i) })}>Remove</button></div>
        <input class="ok-input council-setup__checks" aria-label=${say(`When to take ${e.name}`)} value=${e.when}
          placeholder=${say("When: the rule the steward follows, in a sentence")} onInput=${(ev) => edit(i, { when: ev.target.value })} />
      </li>`)}
      <li class="council-setup__item is-builtin"><b>↩ Back to the author</b><span class="ok-tone-muted">built in · with what to fix</span></li>
      <li class="council-setup__item is-builtin"><b>? Ask me</b><span class="ok-tone-muted">built in · the building burns</span></li>
    </ul>
    <div class="council-setup__row">
      <input class="ok-input" style="flex: 1; width: auto" value=${name} placeholder=${say("Add an exit: e.g. Backlog")}
        onInput=${(ev) => setName(ev.target.value)} onKeyDown=${(ev) => ev.key === "Enter" && add()} />
      <button class="ok-btn" disabled=${!name.trim()} onClick=${add}>Add</button>
    </div>
    <p class="ok-tone-muted council-setup__sub">An exit with no road is never taken: the board asks you instead. Connect one by pulling a road from this building. At most ${data.max_cycles} cycles and ${data.budget} a review.</p>
    <div class="council-setup__foot">
      <button class="ok-btn primary" disabled=${!draft.exits.length || !draft.members.length} onClick=${save}>Save the board</button>
    </div>
  </div>`;
}

/** The setup, in the review pane: opens itself on a board that was never set up. */
export function Setup({ id, data, briefOf }) {
  const s = data.setup;
  const before = s && { clan: "purpose", exits: "clan" }[s.step];
  useSetupBack(id, before ? () => act(id, "setup_go", { step: before }).catch(() => {}) : null);
  useEffect(() => { if (!s) act(id, "setup_open", { step: "purpose" }).catch(() => {}); }, [!s]);
  if (!s) return html`<p class="ok-tone-muted">${say("Opening…")}</p>`;
  return html`<div class="council-setup__pane">
    <div class="council-setup__head"><h3 class="council-setup__title">${data.set_up ? "Change the board" : "Set up the review"}</h3>
      <${Steps} step=${s.step} />
      ${data.set_up && html`<button class="ok-btn" onClick=${() => act(id, "setup_close").catch(() => {})}>Cancel</button>`}</div>
    <${Draft} id=${id} s=${s} data=${data} briefOf=${briefOf} />
  </div>`;
}
