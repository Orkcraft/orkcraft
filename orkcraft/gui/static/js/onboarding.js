// The onboarding (gui/onboarding.py, docs/design/gui-onboarding.md): a project with no town yet opens on it.
// Your AI tools → who you are (every class at once, only when the landing page did not say) → the MCP servers the orks may use
// (only when some are connected) → your first town, drawn → the town going up on the map, with the Autonomy
// card in a corner. Every answer goes to the host at once; the host decides the next step and the page draws
// what the snapshot's `onboarding` says. The card over the map offers Connect Google (js/accounts.js) only with ORKCRAFT_GOOGLE=1.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { Dialog } from "./dialog.js";
import { MascotHead, BIOMES, headerSprite, TypeIcon, ToolMark } from "./icons.js";
import { terrainUrl } from "./terrain.js";
import { USAGE_WHAT } from "./settings.js";
import { googleOpen, googleShown } from "./accounts.js";

const asking = signal(false);          // the Request a tool dialog

const send = (name, args = {}) => command(name, args).catch(() => {});

const GLYPHS = new Set(["github", "gitlab", "gmail", "discord", "jira", "confluence", "figma"]);

/** A service's glyph (icons/services); a service without one shows its first letter, Slack its `#`. */
function Glyph({ id, big = false }) {
  const has = GLYPHS.has(id);
  const text = has ? "" : id === "slack" ? "#" : (id[0] || "?").toUpperCase();
  return html`<span class=${cls(`gui-onb__svc gui-onb__svc--${id}`, { "is-big": big, "has-glyph": has })}
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

/** Check: a short request to the tool on its lightest model; ✓ and how long it took, in seconds written out
 *  (a button's capitals made "12.3 s" read as a price), or what went wrong and what to do. */
function CheckCell({ r }) {
  const c = r.check;
  const run = () => send("onboarding.check", { tool: r.id });
  if (c && c.state === "running") return html`<span class="ok-font-status ok-tone-muted" aria-live="polite">Checking…</span>`;
  if (c && c.state === "ok") {
    const secs = Math.max(1, Math.round(c.ms / 1000));
    return html`<button class="ok-btn gui-onb__check is-ok" onClick=${run} aria-live="polite"
        title=${say(`Answered in ${secs} sec on its lightest model. Check again`)}>${`✓ ${secs} sec`}</button>`;
  }
  return html`<button class="ok-btn gui-onb__check" onClick=${run}
    title=${say(`Send ${r.title} a short request to see that it answers`)}>${c ? "Check again" : "Check"}</button>`;
}

function CheckFailed({ c }) {
  return html`<div class="gui-onb__checked ok-font-status" role="alert">
    <span class="ok-tone-error">✗ ${say(c.line)}</span>
    ${c.action && html` <span>${say(c.action)}</span>`}
    <details><summary class="ok-tone-muted">Details</summary><pre>${c.detail}</pre></details>
  </div>`;
}

/** No AI tool here: what one is, three to install with the commands to type, Check again, and what the
 *  town does without one. */
function NoTools({ t }) {
  return html`<div class="gui-onb__none">
    <p class="ok-font-body">AI tools are the coding agents you run in a terminal: Claude Code, Codex, Cursor's agent.
      Orks run on one of yours, with your own sign-in and your own plan. Orkcraft has no AI of its own, so it needs one of them.</p>
    <div class="gui-onb__table">
      ${t.recommended.map((h) => html`<div key=${h.id} class="gui-onb__row is-get">
        <span class="gui-onb__tool"><${ToolMark} id=${h.id} mark=${h.mark} />${h.title}</span>
        <span class="gui-onb__cmds ok-font-status">
          <span><span class="ok-tone-muted">Install</span> <code>${h.install}</code></span>
          <span><span class="ok-tone-muted">Then sign in</span> <code>${h.login}</code></span></span>
      </div>`)}
    </div>
    <div class="gui-onb__line">
      <span class="ok-font-status ok-tone-muted">Installed one? Check again finds it, no restart needed.</span>
      <button class="ok-btn primary" onClick=${() => send("onboarding.detect")}>Check again</button>
    </div>
    <div class="gui-onb__without">
      <div><span class="ok-font-label">Works without AI</span>
        <p class="ok-font-status">External listeners, Calendar, Task board, Output, the Drop: things come in, are sorted and wait for you.</p></div>
      <div><span class="ok-font-label">Needs an AI tool</span>
        <p class="ok-font-status">Agent pool, Research, the Town planner: nothing an ork would do on its own runs until one is here.</p></div>
    </div>
  </div>`;
}

function ToolsStep({ o }) {
  const t = o.tools;
  const set = (id, change) => send("onboarding.tools", { tools: { [id]: { ...t.rows.find((r) => r.id === id), ...change } } });
  const none = t.ready && t.rows.length === 0;
  return html`<section class="gui-onb__card">
    <${Head} o=${o} title=${none ? "No AI tool here yet" : "Your AI tools"}
      lead=${none ? "Nothing was found on this computer that orks can run on. Install one, or open the town without AI."
        : "Orks run on the ones you check. Found on this machine: nothing was run and no key was read. Check sends one short request to its lightest model."} />
    ${!t.ready ? html`<p class="ok-font-body ok-tone-muted">Looking for your AI tools…</p>` : none ? html`<${NoTools} t=${t} />` : html`
      <div class="gui-onb__table" role="table">
        <div class="gui-onb__row is-head" role="row"><span></span><span class="ok-font-label">Tool</span>
          <span class="ok-font-label">Status</span><span class="ok-font-label">Paid by</span><span></span></div>
        ${t.rows.map((r) => html`<div key=${r.id} class=${cls("gui-onb__row", { "is-off": !r.enabled })} role="row">
          <label class="ok-check" title=${say(`Orks run on ${r.title}`)}>
            <input type="checkbox" class="gui-onb__hide" checked=${r.enabled} onChange=${() => set(r.id, { enabled: !r.enabled })} />
            <i>${r.enabled ? "✓" : ""}</i></label>
          <span class="gui-onb__tool"><${ToolMark} id=${r.id} mark=${r.mark} />${r.title}
            ${r.version && html`<span class="ok-font-status ok-tone-muted">${r.version}</span>`}</span>
          <span class=${cls("ok-font-status", r.logged_in === false ? "ok-tone-wait" : "ok-tone-ok")}>
            ${r.logged_in === false ? say(`⚠ not logged in: ${r.login}`) : "✓ logged in"}</span>
          <select class="ok-input" value=${r.billing} aria-label=${say(`How ${r.title} is paid`)}
              onChange=${(e) => set(r.id, { billing: e.target.value })}>
            <option value="subscription">Subscription</option><option value="api">API</option></select>
          <${CheckCell} r=${r} />
          ${r.check && r.check.state === "failed" && html`<${CheckFailed} c=${r.check} />`}
        </div>`)}
      </div>
      <div class="gui-onb__line">
        <span class="ok-font-status ok-tone-muted">${[
          t.others.length ? say(`Also here: ${t.others.map((x) => x.title).join(", ")}. Orks can't run on these yet.`) : "",
          ...t.cli.map((x) => say(`${x.title}: install the CLI (${x.bin}) to run orks on it.`)),
          none ? "" : t.missing.length ? say(`Not found: ${t.missing.join(", ")}.`) : ""].filter(Boolean).join(" ")}</span>
        <button class="ok-btn" onClick=${() => { asking.value = true; }}>Request a tool</button>
      </div>
      ${!o.again && !none && html`<label class="ok-check gui-onb__warder">
        <input type="checkbox" class="gui-onb__hide" checked=${t.warder} onChange=${() => send("onboarding.tools", { warder: !t.warder })} />
        <i>${t.warder ? "✓" : ""}</i>
        <span><b>Guard this project with the Security reviewer</b> (recommended)<br />
          <span class="ok-font-status ok-tone-muted">Adds hooks to .claude/settings.json that stop risky commands and secrets before an ork runs them.</span>
          ${t.warder_agy && html`<br /><span class="ok-font-status ok-tone-wait gui-onb__warder-agy">${say(t.warder_agy)}</span>`}</span>
      </label>`}`}
    <${Foot} back=${false} next=${t.ready ? () => send("onboarding.tools", { next: true }) : null}
      nextLabel=${none ? "Go on without AI" : "Next"} />
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

// One list: a service with one server is a checkbox; a service two servers reach (GitHub through `github` and
// `github-enterprise`) is a checkbox and, under it, the servers to choose from, one at a time. ↑/↓ move
// through every row, Home/End to the ends, Enter or Space turns a service on or off or picks a server; the
// mouse does the same.

function mcpRows(o) {
  const rows = [];
  for (const svc of o.mcp.services) {
    rows.push({ key: `svc:${svc.ids.join(",")}`, svc });
    if (svc.ids.length > 1) for (const id of svc.ids) rows.push({ key: `srv:${id}`, svc, id });
  }
  return rows;
}

function McpStep({ o }) {
  const on = new Set(o.mcp.on);
  const byId = Object.fromEntries(o.mcp.servers.map((s) => [s.id, s]));
  const rows = mcpRows(o);
  const [at, setAt] = useState(0);
  const cur = Math.min(at, rows.length - 1);
  const chosen = (svc) => svc.ids.find((id) => on.has(id));
  const put = (ids) => send("onboarding.mcp", { on: o.mcp.servers.map((s) => s.id).filter((id) => ids.has(id)) });
  const act = (row) => {
    const next = new Set(on);
    if (row.id) {                                             // a server: the one this service goes through
      row.svc.ids.forEach((id) => next.delete(id));
      next.add(row.id);
    } else if (chosen(row.svc)) {
      row.svc.ids.forEach((id) => next.delete(id));
    } else {
      next.add(row.svc.ids[0]);
    }
    put(next);
  };
  const focus = (i, list) => {
    setAt(i);
    const el = list && list.querySelectorAll("[data-row]")[i];
    if (el) el.focus();
  };
  const keys = (e) => {
    const list = e.currentTarget;
    const move = { ArrowDown: cur + 1, ArrowUp: cur - 1, Home: 0, End: rows.length - 1 }[e.key];
    if (move !== undefined) {
      e.preventDefault();
      focus(Math.max(0, Math.min(rows.length - 1, move)), list);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      act(rows[cur]);
    }
  };
  const tools = (ids) => [...new Set(ids.flatMap((id) => byId[id].tools))].map((x) => o.tool_titles[x] || x).join(" · ");
  const services = o.mcp.services.filter((svc) => chosen(svc)).length;
  return html`<section class="gui-onb__card">
    <${Head} o=${o} title="Tools the orks can use"
      lead="MCP servers already connected to your AI tools. The town planner gives the ones you turn on to the orks that need them, and shows them on their buildings." />
    <div class="gui-onb__table gui-onb__mcp" role="listbox" aria-multiselectable="true"
        aria-label=${say("MCP servers the orks may use")} onKeyDown=${keys}>
      ${rows.map((row, i) => {
        const tab = i === cur ? 0 : -1;
        const pick = () => { setAt(i); act(row); };
        if (row.id) {
          const s = byId[row.id];
          const sel = on.has(row.id);
          return html`<div key=${row.key} data-row role="option" aria-selected=${sel} tabindex=${tab}
              class=${cls("gui-onb__row is-mcp is-server", { "is-off": !sel })} onClick=${pick} onFocus=${() => setAt(i)}>
            <span></span>
            <span class=${cls("gui-onb__radio", { "is-on": sel })} aria-hidden="true"></span>
            <span class="gui-onb__tool"><code>${s.id}</code></span>
            <span class="ok-font-status">${tools([s.id])}</span>
          </div>`;
        }
        const svc = row.svc;
        const sel = !!chosen(svc);
        const many = svc.ids.length > 1;
        return html`<div key=${row.key} data-row role="option" aria-selected=${sel} tabindex=${tab}
            class=${cls("gui-onb__row is-mcp", { "is-off": !sel })} onClick=${pick} onFocus=${() => setAt(i)}>
          <span class="ok-check"><i>${sel ? "✓" : ""}</i></span>
          <${Glyph} id=${svc.glyph || svc.ids[0]} />
          <span class="gui-onb__tool">${svc.title}${many
            ? html`<span class="ok-font-status ok-tone-muted">${say(`${svc.ids.length} servers: the orks use the one picked below`)}</span>`
            : html`<code class="ok-font-status ok-tone-muted">${svc.ids[0]}</code>`}</span>
          <span class="ok-font-status">${tools(many ? [chosen(svc) || svc.ids[0]] : svc.ids)}</span>
        </div>`;
      })}
    </div>
    <p class="ok-font-status ok-tone-muted">↑ ↓ to move, Enter to turn on or off or to pick a server.
      Read from ~/.claude.json, .mcp.json, ~/.codex/config.toml and ~/.gemini/settings.json: names only. Tokens stay where they are.</p>
    <${Foot} next=${() => send("onboarding.mcp", { on: o.mcp.on, next: true })}>
      <span class="ok-font-status">${say(`${services} of ${o.mcp.services.length} on`)}</span></${Foot}>
  </section>`;
}

// -- 4 · Your first town --------------------------------------------------------------------------------

function TownPreview({ it, biome }) {
  return html`<${Ground} biome=${biome} className="gui-onb__town">
    ${it.buildings.map((b, i) => html`<div key=${b.key} class="gui-onb__lot">
      <div class="gui-onb__house">
        <img class="ok-sprite" src=${headerSprite(b.type, biome)} alt="" draggable="false" />
        <span class="gui-onb__icon"><${TypeIcon} type=${b.type} /></span>
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

// -- 5 · Setting up the town: one card over the map ------------------------------------------------------
// How the building goes, how free the orks are, quiet hours and the usage question: one card, so the town
// stays in view beside it. Each choice applies at once; Open the town closes it when the town stands.

const MARK = { done: "✓", now: "⚒", next: "·", failed: "✗" };

function Raising({ o }) {
  const r = o.raising;
  const t = town.value;
  const [steps, setSteps] = useState(false);
  const [share, setShare] = useState(false);
  const done = r.phase === "done" || r.phase === "failed";
  const total = r.steps.length;
  const ok = r.steps.filter((s) => s.state === "done").length;
  const now = r.steps.find((s) => s.state === "now");
  const ask = !!(t && t.usage_ask);
  const status = r.phase === "failed" ? `✗ ${say("Stopped")}` : done ? `✓ ${say(`${ok} of ${total} done`)}`
    : now ? `⚒ ${say(now.label)}` : "…";
  const open = () => {
    if (ask) command("usage.share", { share }).catch(() => {});
    send("onboarding.close");
  };
  return html`<div class="gui-onb__over">
    <section class="gui-onb__setup ok-win" aria-live="polite">
      <span class="ok-font-label">${r.phase === "planning" ? say("The town planner is drawing your town…") : say(`${r.title} · setting up`)}</span>
      <div class="gui-onb__bar" role="progressbar" aria-valuemin="0" aria-valuemax=${total} aria-valuenow=${ok}>
        <i style=${`width:${total ? (100 * ok) / total : 0}%`}></i></div>
      <button class=${cls("gui-onb__now ok-font-status", { "is-done": done })} aria-expanded=${steps}
        onClick=${() => setSteps(!steps)}>${status}<span class="ok-tone-muted">${steps ? "Hide steps" : "All steps"}</span></button>
      ${steps && html`<ul class="gui-onb__steplist">
        ${r.steps.map((s, i) => html`<li key=${i} class=${`is-${s.state}`}><span aria-hidden="true">${MARK[s.state]}</span> ${say(s.label)}</li>`)}
      </ul>`}
      ${r.error && html`<p class="ok-font-status ok-tone-error">${r.error}</p>`}
      <${Freedom} o=${o} />
      ${googleShown() && html`<div class="gui-onb__google">
        <h2 class="gui-onb__corner-title">Your Google account</h2>
        <p class="ok-font-status ok-tone-muted">Gmail for External listeners, your calendar for the Calendar, Drive for the Wiki: one sign-in of your own, about 6 minutes.</p>
        <span><button class="ok-btn" onClick=${() => { googleOpen.value = true; }}>Connect Google</button></span>
      </div>`}
      ${ask && html`<label class="ok-check">
        <input type="checkbox" class="gui-onb__hide" checked=${share} onChange=${() => setShare(!share)} />
        <i>${share ? "✓" : ""}</i><span>${say("Share anonymous usage stats")}</span></label>
        <p class="ok-font-status ok-tone-muted">${say(USAGE_WHAT)}</p>`}
      <div class="gui-onb__foot"><span class="ok-font-status ok-tone-muted">All of this changes any time in Settings.</span>
        <span class="gui-onb__spacer"><button class="ok-btn primary" disabled=${!done} onClick=${open}>Open the town</button></span></div>
    </section>
  </div>`;
}

function Freedom({ o }) {
  const [s, setS] = useState(null);
  if (s === null) { command("town.settings").then(setS, () => {}); return null; }
  const pick = (id) => command("town.settings.set", { autonomy: id }).then(setS, () => {});
  return html`<div class="gui-onb__freedom">
    <h2 class="gui-onb__corner-title">How free are your orks?</h2>
    <p class="ok-font-status ok-tone-muted">When an ork asks a question or wants to change its building.</p>
    <div class="gui-onb__levels" role="radiogroup" aria-label=${say("How free are your orks?")}>
      ${s.levels.map((lv) => html`<button key=${lv.id} role="radio" aria-checked=${s.autonomy === lv.id}
          class=${cls("gui-onb__level", { "is-on": s.autonomy === lv.id })} onClick=${() => pick(lv.id)}>
        <span class="ok-font-body"><b>${say(lv.title)}</b></span>${s.autonomy === lv.id
          && html`<span class="ok-font-status ok-tone-muted">${say(lv.questions)}</span>`}</button>`)}
    </div>
    <label class="ok-check">
      <input type="checkbox" class="gui-onb__hide" checked=${o.quiet} onChange=${() => send("onboarding.quiet", { on: !o.quiet })} />
      <i>${o.quiet ? "✓" : ""}</i><span>🌙 Quiet hours 23:00–08:00: no alerts, questions wait</span></label>
  </div>`;
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
      <span class="gui-onb__icon"><${TypeIcon} type=${g.type} /></span>
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
