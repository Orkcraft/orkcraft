// The onboarding (gui/onboarding.py, docs/design/gui-onboarding.md): a project with no town yet opens on it.
// Your AI tools → who you are (every class at once, only when the landing page did not say) → the MCP servers the orks may use
// (only when some are connected) → your first town, drawn → the town going up on the map, with the Autonomy
// card in a corner. Every answer goes to the host at once; the host decides the next step and the page draws
// what the snapshot's `onboarding` says.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { Dialog } from "./dialog.js";
import { MascotHead, BIOMES, headerSprite } from "./icons.js";
import { terrainUrl } from "./terrain.js";

const asking = signal(false);          // the Request a tool dialog
const autonomyLater = signal(false);   // the Autonomy card was put away

const send = (name, args = {}) => command(name, args).catch(() => {});

const GLYPHS = new Set(["github", "gitlab", "gmail", "discord", "jira", "confluence", "figma"]);
const TOOL_GLYPHS = new Set(["claude", "cursor", "pi"]);   // icons/tools

/** A service's glyph (icons/services); a service without one shows its first letter, Slack its `#`.
 *  An AI tool's (`tool`, icons/tools) stands bare beside its checkbox; a tool without one shows its harness mark. */
function Glyph({ id, big = false, tool = false, mark = "" }) {
  const has = (tool ? TOOL_GLYPHS : GLYPHS).has(id);
  const text = has ? "" : mark || (id === "slack" ? "#" : (id[0] || "?").toUpperCase());
  return html`<span class=${cls(`gui-onb__svc gui-onb__svc--${tool ? "tool-" : ""}${id}`, { "is-big": big, "is-bare": tool, "has-glyph": has })}
    aria-hidden="true">${text}</span>`;
}

function Ground({ biome, children, className = "" }) {
  const b = BIOMES[biome] || BIOMES.dirt;
  const glyphs = terrainUrl(biome);
  return html`<div class=${`gui-onb__ground ${className}`}
      style=${`--ground:${b.ground};--land:${b.land};--glyphs:${glyphs ? `url("${glyphs}")` : "none"}`}>${children}</div>`;
}

function Head({ o, title, lead }) {
  return html`<header class="gui-onb__head">
    <div class="gui-onb__steps" aria-label=${say(`Step ${o.n + 1} of ${o.steps.length}`)}>
      ${o.steps.map((s, i) => html`<span key=${s} class=${cls("gui-onb__pip", { "is-done": i <= o.n })}></span>`)}
      <span class="ok-font-status ok-tone-muted">${say(`Setting up · step ${o.n + 1} of ${o.steps.length}`)}</span>
    </div>
    <h1 class="gui-onb__title">${title}</h1>
    ${lead && html`<p class="gui-onb__lead ok-font-body ok-tone-muted">${lead}</p>`}
  </header>`;
}

function Foot({ back = true, skip = true, next, nextLabel = "Next", children }) {
  return html`<footer class="gui-onb__foot">
    ${back && html`<button class="ok-btn" onClick=${() => send("onboarding.back")}>Back</button>`}
    ${skip && html`<button class="ok-btn gui-onb__quiet" onClick=${() => send("onboarding.skip")}>
      ${town.value?.onboarding?.again ? "Cancel" : "Skip: empty town"}</button>`}
    <span class="gui-onb__spacer">${children}</span>
    ${next && html`<button class="ok-btn primary" onClick=${next}>${nextLabel}</button>`}
  </footer>`;
}

// -- 1 · Your AI tools ---------------------------------------------------------------------------------

function RequestTool() {
  const [f, setF] = useState({ name: "", link: "", note: "" });
  const close = () => { asking.value = false; };
  const open = () => command("onboarding.request", f).then((r) => {
    window.open(r.url, "_blank", "noopener");
    close();
  }, () => {});
  const field = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return html`<${Dialog} title="Request a tool" onCancel=${close}
      meta="Which agent should orks be able to run on? Requests decide what the town learns next."
      actions=${html`<span class="gui-dialog__note">Opens a GitHub issue in your browser, filled in. Nothing is sent until you submit it there.</span>
        <button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!f.name.trim()} onClick=${open}>Open the request</button>`}>
    <label class="gui-field"><span class="ok-font-label">Tool name</span>
      <input class="ok-input" value=${f.name} onInput=${field("name")} placeholder="Aider" /></label>
    <label class="gui-field"><span class="ok-font-label">Link (optional)</span>
      <input class="ok-input" value=${f.link} onInput=${field("link")} placeholder="https://" /></label>
    <label class="gui-field"><span class="ok-font-label">What would orks do with it? (optional)</span>
      <textarea class="ok-input gui-textarea" rows="3" value=${f.note} onInput=${field("note")}></textarea></label>
  </${Dialog}>`;
}

function ToolsStep({ o }) {
  const t = o.tools;
  const set = (id, change) => send("onboarding.tools", { tools: { [id]: { ...t.rows.find((r) => r.id === id), ...change } } });
  return html`<section class="gui-onb__card">
    <${Head} o=${o} title="Your AI tools"
      lead="Orks run on the ones you check. Found on this machine: nothing was run and no key was read." />
    ${!t.ready ? html`<p class="ok-font-body ok-tone-muted">Looking for your AI tools…</p>` : html`
      <div class="gui-onb__table" role="table">
        <div class="gui-onb__row is-head" role="row"><span></span><span class="ok-font-label">Tool</span>
          <span class="ok-font-label">Status</span><span class="ok-font-label">Paid by</span></div>
        ${t.rows.map((r) => html`<div key=${r.id} class=${cls("gui-onb__row", { "is-off": !r.enabled })} role="row">
          <label class="ok-check" title=${say(`Orks run on ${r.title}`)}>
            <input type="checkbox" class="gui-onb__hide" checked=${r.enabled} onChange=${() => set(r.id, { enabled: !r.enabled })} />
            <i>${r.enabled ? "✓" : ""}</i></label>
          <span class="gui-onb__tool"><${Glyph} id=${r.id} tool=${true} mark=${r.mark} />${r.title}
            ${r.version && html`<span class="ok-font-status ok-tone-muted">${r.version}</span>`}</span>
          <span class=${cls("ok-font-status", r.logged_in === false ? "ok-tone-wait" : "ok-tone-ok")}>
            ${r.logged_in === false ? say(`⚠ not logged in: ${r.login}`) : "✓ logged in"}</span>
          <select class="ok-input" value=${r.billing} aria-label=${say(`How ${r.title} is paid`)}
              onChange=${(e) => set(r.id, { billing: e.target.value })}>
            <option value="subscription">Subscription</option><option value="api">API</option></select>
        </div>`)}
        ${t.rows.length === 0 && html`<p class="ok-font-body">No agent the orks can run on is installed. Install Claude Code
          (<code>npm i -g @anthropic-ai/claude-code</code>) and open Orkcraft again, or start with an empty town.</p>`}
      </div>
      <div class="gui-onb__line">
        <span class="ok-font-status ok-tone-muted">${[
          t.others.length ? say(`Also here: ${t.others.map((x) => x.title).join(", ")}. Orks can't run on these yet.`) : "",
          ...t.cli.map((x) => say(`${x.title}: install the CLI (${x.bin}) to run orks on it.`)),
          t.missing.length ? say(`Not found: ${t.missing.join(", ")}.`) : ""].filter(Boolean).join(" ")}</span>
        <button class="ok-btn" onClick=${() => { asking.value = true; }}>Request a tool</button>
      </div>
      ${!o.again && html`<label class="ok-check gui-onb__warder">
        <input type="checkbox" class="gui-onb__hide" checked=${t.warder} onChange=${() => send("onboarding.tools", { warder: !t.warder })} />
        <i>${t.warder ? "✓" : ""}</i>
        <span><b>Guard this project with the Security reviewer</b> (recommended)<br />
          <span class="ok-font-status ok-tone-muted">Adds hooks to .claude/settings.json that stop risky commands and secrets before an ork runs them.</span>
          ${t.warder_agy && html`<br /><span class="ok-font-status ok-tone-wait gui-onb__warder-agy">${say(t.warder_agy)}</span>`}</span>
      </label>`}`}
    <${Foot} back=${false} next=${t.ready ? () => send("onboarding.tools", { next: true }) : null} />
    ${asking.value && html`<${RequestTool} />`}
  </section>`;
}

// -- 2 · Who are you ------------------------------------------------------------------------------------

function WhoStep({ o }) {
  // From the landing page's class (`--role gnome`): only its two cards, with a lead of their own.
  const lead = o.only_kin
    ? say(`Two kinds of ${o.kin_word}. Each gets towns for its own work.`)
    : "Your class picks your first town, your mascot and the land it stands on.";
  return html`<section class=${cls("gui-onb__card", { "is-wide": !o.only_kin })}>
    <${Head} o=${o} title="Who are you?" lead=${lead} />
    <div class=${cls("gui-onb__kins", { "is-few": !!o.only_kin })}>
      ${o.classes.map((c) => html`<button key=${c.id} class=${cls("gui-onb__kin", { "is-on": o.role === c.id })}
          aria-pressed=${o.role === c.id} onClick=${() => send("onboarding.role", { role: c.id })}>
        <${Ground} biome=${c.biome}><${MascotHead} sprite=${c.sprite} stage=${1} size=${5} /></${Ground}>
        <span class="gui-onb__kin-name">${c.nick}</span>
        <span class="ok-font-status ok-tone-muted">${c.title}</span>
      </button>`)}
    </div>
    <${Foot} skip=${false} />
  </section>`;
}

// -- 3 · The tools the orks can use (MCP) ---------------------------------------------------------------

function McpStep({ o }) {
  const on = new Set(o.mcp.on);
  const flip = (id) => {
    const next = on.has(id) ? o.mcp.on.filter((x) => x !== id) : [...o.mcp.on, id];
    send("onboarding.mcp", { on: next });
  };
  return html`<section class="gui-onb__card">
    <${Head} o=${o} title="Tools the orks can use"
      lead="MCP servers already connected to your AI tools. The town planner gives the ones you turn on to the orks that need them, and shows them on their buildings." />
    <div class="gui-onb__table">
      ${o.mcp.servers.map((s) => html`<label key=${s.id} class=${cls("gui-onb__row is-mcp", { "is-off": !on.has(s.id) })}>
        <span class="ok-check"><input type="checkbox" class="gui-onb__hide" checked=${on.has(s.id)} onChange=${() => flip(s.id)} />
          <i>${on.has(s.id) ? "✓" : ""}</i></span>
        <${Glyph} id=${s.glyph || s.id} />
        <span class="gui-onb__tool">${s.title}<code class="ok-font-status ok-tone-muted">${s.id}</code></span>
        <span class="ok-font-status">${s.tools.map((x) => o.tool_titles[x] || x).join(" · ")}</span>
      </label>`)}
    </div>
    <p class="ok-font-status ok-tone-muted">Read from ~/.claude.json, .mcp.json, ~/.codex/config.toml and ~/.gemini/settings.json:
      names only. Tokens stay where they are.</p>
    <${Foot} next=${() => send("onboarding.mcp", { on: o.mcp.on, next: true })}>
      <span class="ok-font-status">${say(`${on.size} of ${o.mcp.servers.length} on`)}</span></${Foot}>
  </section>`;
}

// -- 4 · Your first town --------------------------------------------------------------------------------

function TownPreview({ it, biome }) {
  return html`<${Ground} biome=${biome} className="gui-onb__town">
    ${it.buildings.map((b, i) => html`<div key=${b.key} class="gui-onb__lot">
      <div class="gui-onb__house">
        <img class="ok-sprite" src=${headerSprite(b.type, biome)} alt="" draggable="false" />
        ${b.badges.length > 0 && html`<span class="gui-onb__badges">${b.badges.map((g) => html`<${Glyph} key=${g} id=${g} />`)}</span>`}
      </div>
      <div class="gui-onb__plate">
        <span class="gui-onb__plate-name">${say(b.title)}</span>
        <span class="ok-font-status ok-tone-muted">${b.why}</span>
      </div>
      ${i < it.buildings.length - 1 && html`<span class="gui-onb__road" aria-hidden="true"></span>`}
    </div>`)}
  </${Ground}>`;
}

function TownStep({ o }) {
  const [pick, setPick] = useState(0);
  const it = o.towns[Math.min(pick, o.towns.length - 1)];
  return html`<section class="gui-onb__card is-wide">
    <${Head} o=${o} title="Your first town" lead=${o.nick ? say(`For a ${o.nick}`) : ""} />
    ${it ? html`
      <div class="ok-tabs" role="tablist">
        ${o.towns.map((x, i) => html`<button key=${x.id} role="tab" aria-selected=${i === pick}
            class=${cls("ok-tab", { "is-active": i === pick })} onClick=${() => setPick(i)}>${i === 0 ? "★ " : ""}${x.rhythm ? `${say(x.rhythm)} · ` : ""}${say(x.title)}</button>`)}
      </div>
      <${TownPreview} it=${it} biome=${o.biome} />
      <div class="gui-onb__how">
        <div><span class="ok-font-label">How it works</span><p class="ok-font-body">${it.summary || it.blurb}</p></div>
        <div class="gui-onb__choose">
          <button class="ok-btn primary" onClick=${() => send("onboarding.town", { preset: it.id })}>Use this town</button>
          <button class="ok-btn" disabled=${!o.planner} title=${o.planner ? "" : say("No AI tool that can plan a town is on")}
            onClick=${() => send("onboarding.town", { custom: true })}>Doesn't fit: tell the planner</button>
          <button class="ok-btn gui-onb__quiet" onClick=${() => send("onboarding.town", { empty: true })}>Empty town, I'll build it myself</button>
        </div>
      </div>` : html`<p class="ok-font-body">No ready town for this class yet.</p>
      <div class="gui-onb__choose">
        <button class="ok-btn primary" disabled=${!o.planner} onClick=${() => send("onboarding.town", { custom: true })}>Tell the planner</button>
        <button class="ok-btn" onClick=${() => send("onboarding.town", { empty: true })}>Empty town</button></div>`}
    <${Foot} skip=${false} />
  </section>`;
}

// -- 4b · Doesn't fit: one question, the rest prefilled ------------------------------------------------
// The words are all that is asked; three of the class's examples start them, and what the planner will use is
// already chosen (the MCP servers on, the class's usual sources and places): a click leaves one out.

function SurveyStep({ o }) {
  const s = o.survey;
  const [words, setWords] = useState("");
  const [out, setOut] = useState([]);           // the prefilled ids left out
  const [extra, setExtra] = useState([]);       // what the person added
  const [adding, setAdding] = useState(null);   // the text of the one being added, or null
  if (!s) return null;
  const flip = (id) => setOut(out.includes(id) ? out.filter((x) => x !== id) : [...out, id]);
  const add = () => {
    const t = (adding || "").trim();
    if (t && !extra.includes(t)) setExtra([...extra, t]);
    setAdding(null);
  };
  const build = () => send("onboarding.survey", { words, keep: s.uses.map((u) => u.id).filter((id) => !out.includes(id)), extra });
  return html`<section class="gui-onb__card">
    <${Head} o=${o} title="What should your town do?"
      lead="One or two sentences are enough. The town planner draws it, and you watch it go up." />
    <label class="gui-onb__hide" for="gui-onb-words">What should your town do</label>
    <textarea id="gui-onb-words" class="ok-input gui-textarea gui-onb__words" rows="3" value=${words}
      onInput=${(e) => setWords(e.target.value)}></textarea>
    ${s.starters.length > 0 && html`<div class="gui-field"><span class="ok-font-label">Or start from one of these</span>
      <div class="gui-onb__starters">${s.starters.map((t) => html`<button key=${t} class="gui-onb__starter ok-font-body"
          onClick=${() => setWords(t)}>${t}</button>`)}</div></div>`}
    <div class="gui-field"><span class="ok-font-label">The planner will use</span>
      <div class="gui-onb__chips">
        ${s.uses.map((u) => html`<button key=${u.id} class=${cls("ok-chip", { "is-on": !out.includes(u.id) })}
            aria-pressed=${!out.includes(u.id)} onClick=${() => flip(u.id)}>
          ${out.includes(u.id) ? "" : "✓ "}${u.title}${u.mcp ? " · MCP" : ""}</button>`)}
        ${extra.map((t) => html`<button key=${t} class="ok-chip is-on" aria-pressed="true"
            onClick=${() => setExtra(extra.filter((x) => x !== t))}>✓ ${t}</button>`)}
        ${adding === null
          ? html`<button class="ok-chip" onClick=${() => setAdding("")}>+ add</button>`
          : html`<input class="ok-input gui-onb__add" value=${adding} placeholder="e.g. Notion" ref=${(el) => el && document.activeElement !== el && el.focus()}
              onInput=${(e) => setAdding(e.target.value)} onBlur=${add}
              onKeyDown=${(e) => { if (e.key === "Enter") add(); if (e.key === "Escape") setAdding(null); }} />`}
      </div>
      <span class="ok-font-status ok-tone-muted">${say(`From your MCP servers and what ${o.nick ? `${o.nick}s` : "people like you"} usually use. A click leaves one out.`)}</span>
    </div>
    <${Foot} skip=${false} next=${words.trim() ? build : null} nextLabel="Build my town">
      ${!words.trim() && html`<span class="ok-font-status ok-tone-muted">Say what the town should do first.</span>`}</${Foot}>
  </section>`;
}

// -- 5 · Setting up the town: over the map --------------------------------------------------------------

const MARK = { done: "✓", now: "⚒", next: "·", failed: "✗" };

function Raising({ o }) {
  const r = o.raising;
  const done = r.phase === "done" || r.phase === "failed";
  return html`<div class="gui-onb__over">
    <section class="gui-onb__log ok-win" aria-live="polite">
      <span class="ok-font-label">${r.phase === "planning" ? say("The town planner is drawing your town…") : say(`${r.title} · setting up`)}</span>
      <ul class="gui-onb__steplist">
        ${r.steps.map((s, i) => html`<li key=${i} class=${`is-${s.state}`}><span aria-hidden="true">${MARK[s.state]}</span> ${s.label}</li>`)}
      </ul>
      ${r.error && html`<p class="ok-font-status ok-tone-error">${r.error}</p>`}
      ${done && html`<button class="ok-btn primary" onClick=${() => send("onboarding.close")}>Open the town</button>`}
    </section>
    ${!autonomyLater.value && html`<${AutonomyCard} o=${o} />`}
  </div>`;
}

function AutonomyCard({ o }) {
  const [s, setS] = useState(null);
  if (s === null) { command("town.settings").then(setS, () => {}); return null; }
  const pick = (id) => command("town.settings.set", { autonomy: id }).then(setS, () => {});
  return html`<section class="gui-onb__corner ok-win" role="dialog" aria-label=${say("How free are your orks?")}>
    <h2 class="gui-onb__corner-title">While they build: how free are your orks?</h2>
    <p class="ok-font-status ok-tone-muted">When an ork asks a question or wants to change its building.</p>
    <div class="gui-onb__levels" role="radiogroup">
      ${s.levels.map((lv) => html`<button key=${lv.id} role="radio" aria-checked=${s.autonomy === lv.id}
          class=${cls("gui-onb__level", { "is-on": s.autonomy === lv.id })} onClick=${() => pick(lv.id)}>
        <span class="ok-font-body"><b>${say(lv.title)}</b></span><span class="ok-font-status ok-tone-muted">${say(lv.questions)}</span></button>`)}
    </div>
    <label class="ok-check">
      <input type="checkbox" class="gui-onb__hide" checked=${o.quiet} onChange=${() => send("onboarding.quiet", { on: !o.quiet })} />
      <i>${o.quiet ? "✓" : ""}</i><span>🌙 Quiet hours 23:00–08:00: no alerts, questions wait</span></label>
    <p class="ok-font-status ok-tone-muted">Both change any time in Settings.</p>
    <div class="gui-onb__foot"><span class="gui-onb__spacer"></span>
      <button class="ok-btn" onClick=${() => { autonomyLater.value = true; }}>Later</button>
      <button class="ok-btn primary" onClick=${() => { autonomyLater.value = true; }}>Done</button></div>
  </section>`;
}

// -- the town's plan on the map (js/town.js draws these where each building will stand) --------------------

/** The buildings the onboarding is raising that do not stand yet: a dashed plan, or scaffolding over the one
 *  going up now. */
export function planned() {
  const r = town.value?.onboarding?.raising;
  return r ? r.buildings.filter((b) => b.state === "planned" || b.state === "raising") : [];
}

/** The ids of the buildings that came up in this raising: their huts rise into place once, when they appear. */
export function risen() {
  const r = town.value?.onboarding?.raising;
  return new Set(r ? r.buildings.filter((b) => b.state === "standing").map((b) => b.id) : []);
}

export function Ghost({ g, spot, biome }) {
  const now = g.state === "raising";
  return html`<div class=${cls("gui-onb__ghost", { "is-raising": now })} style=${`left:${spot.x}px;top:${spot.y}px`}
      aria-label=${say(now ? `${g.title}: being built` : `${g.title}: planned`)}>
    <div class="gui-onb__ghost-roof">
      <img class="ok-sprite gui-onb__ghost-plan" src=${headerSprite(g.type, biome)} alt="" draggable="false" />
      ${now && html`<img class="ok-sprite gui-onb__ghost-rise" src=${headerSprite(g.type, biome)} alt="" draggable="false" />
        <span class="gui-onb__scaffold" aria-hidden="true"></span><span class="gui-onb__hammer" aria-hidden="true">⚒</span>`}
    </div>
    <div class="gui-onb__ghost-card"><span class="gui-onb__ghost-name">${say(g.title)}</span>
      <span class="ok-font-status ok-tone-muted">${now ? "building…" : "planned"}</span></div>
  </div>`;
}

// -- the whole -------------------------------------------------------------------------------------------

const STEPS = { tools: ToolsStep, who: WhoStep, mcp: McpStep, town: TownStep, survey: SurveyStep };

export function Onboarding() {
  const t = town.value;
  const o = t && t.onboarding;
  if (!o) return null;
  if (o.step === "raising") return o.raising ? html`<${Raising} o=${o} />` : null;
  const Step = STEPS[o.step];
  return html`<div class="gui-onb" role="dialog" aria-modal="true" aria-label=${say("Setting up")}>
    <div class="gui-onb__brand"><img src="/ds/logo/orkcraft-dark.svg" alt="Orkcraft" onError=${(e) => { e.target.replaceWith(document.createTextNode("Orkcraft")); }} /></div>
    ${Step && html`<${Step} o=${o} />`}
  </div>`;
}
