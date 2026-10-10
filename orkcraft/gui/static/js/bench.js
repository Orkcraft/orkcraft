// 🧪 The Test bench (gui/bench.py, docs/design/test-bench.md): one building on its own, in three tabs. Tech runs
// a test case in the building and in the bare AI tool and puts them side by side; UX and Product are agents'
// reviews of the building. Ticked findings become tasks of an Agent pool with Make tasks, never by themselves.
// It is drawn in the Test bench building's window (js/buildings/lab.js), for a building whose road comes into it.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, toast } from "./link.js";

const LOG_LINES = 4;                              // the run's terminal shows its last lines; Copy takes them all

/** Text onto the clipboard for an analysis elsewhere: the clipboard when the page may write it, else a selection. */
export function copyText(text, what = "Copied") {
  const done = () => toast(what);
  const fallback = () => {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand && document.execCommand("copy");
    area.remove();
    ok ? done() : toast("Could not copy: select the text and copy it", "warning");
  };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
  else fallback();
}

const TABS = [["tech", "Tech"], ["ux", "UX"], ["product", "Product"]];
const LEVELS = [["simple", "Every simple case"], ["medium", "Every medium case"], ["parallel", "Every parallel case"]];
const pct = (v) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${Math.round(v * 100)}%`);
const SIDES = [["", "Both"], ["building", "The building only"], ["bare", "The bare AI tool only"]];
const many = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const money = (x) => `$${(x || 0).toFixed(2)}`;
const clock = (s) => `${Math.floor((s || 0) / 60)}:${String(Math.round((s || 0) % 60)).padStart(2, "0")}`;
const busy = (s) => !!s && ((s.job && !s.job.done) || Object.values(s.reviews).some((r) => r.roles.some((x) => x.running)));

/** The bench of building `id`, drawn in the Test bench `lab`'s window: its tabs, what is in them, Make tasks. */
export function BenchView({ id, lab }) {
  const [s, setS] = useState(null);
  const [tab, setTab] = useState("tech");
  const [picks, setPicks] = useState(new Set());
  useEffect(() => {
    setS(null);
    setPicks(new Set());
    if (!id) return undefined;
    command("bench.open", { id, lab }).then(setS, () => {});
    return undefined;
  }, [id]);
  useEffect(() => {                         // while something works, its lines and findings come in
    if (!id || !busy(s)) return undefined;
    const timer = setTimeout(() => command("bench.state", { id, lab }).then(setS, () => {}), 1500);
    return () => clearTimeout(timer);
  }, [id, s]);
  if (!s) return html`<p class="ok-font-body ok-tone-muted">${say("Opening the bench…")}</p>`;
  const call = (name, args = {}) => command(name, { id, lab, ...args }).then(setS, () => {});
  const flip = (fid) => { const next = new Set(picks); next.has(fid) ? next.delete(fid) : next.add(fid); setPicks(next); };
  return html`<div class="gui-bench">
    <p class="ok-font-status ok-tone-muted gui-bench__about">${say(s.word)} · ${say(s.summary)}</p>
    <div class="ok-tabs gui-bench__tabs" role="tablist">
      ${TABS.map(([t, label]) => html`<button key=${t} role="tab" aria-selected=${tab === t}
        class=${cls("ok-tab", { "is-active": tab === t })} onClick=${() => setTab(t)}>${label}
        ${s.reviews[t].roles.some((r) => r.running) && html`<span class="gui-bench__spin" aria-label="Working"></span>`}</button>`)}
    </div>
    <div class="gui-bench__body">
      ${tab === "tech" ? html`<${Tech} s=${s} call=${call} picks=${picks} flip=${flip} />`
        : tab === "product" ? html`<${Product} s=${s} call=${call} picks=${picks} flip=${flip} />`
        : html`<${Reviews} s=${s} tab="ux" call=${call} picks=${picks} flip=${flip} />`}
    </div>
    <div class="gui-bench__make"><${MakeTasks} s=${s} lab=${lab} picks=${picks} done=${() => setPicks(new Set())} /></div>
  </div>`;
}

// -- Tech ----------------------------------------------------------------------------------------------------

function Tech({ s, call, picks, flip }) {
  return html`
    ${s.can_run ? html`<${RunForm} s=${s} call=${call} />`
      : html`<p class="ok-font-status ok-tone-muted">${say(`Runs come to the ${s.word} later: the Test bench runs ${s.runs_for} so far. Its reviews below work now.`)}</p>`}
    ${s.job && html`<${JobLog} s=${s} call=${call} />`}
    ${s.against.length > 0 && html`<${Against} s=${s} />`}
    ${s.runs.length > 0 && html`<${Runs} s=${s} />`}
    ${s.can_run && html`<${Cases} s=${s} call=${call} />`}
    <${Reviews} s=${s} tab="tech" call=${call} picks=${picks} flip=${flip} />`;
}

function RunForm({ s, call }) {
  const ready = s.cases.filter((c) => c.reviewed);
  const [f, setF] = useState({ case: ready[0] ? ready[0].id : "", tool: "main", tier: "", max_spend: s.max_spend,
                               only: "", orders: s.orders });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const on = s.job && !s.job.done;
  const series = f.case === "all" || f.case.startsWith("level:");
  const pooled = s.orders_of && s.orders_of !== s.type;
  const field = (label, control) => html`<label class="gui-field"><span class="ok-font-label">${label}</span>${control}</label>`;
  return html`<section class="gui-bench__section">
    <h4 class="ok-font-label gui-bench__h">Run a case</h4>
    <p class="ok-font-status ok-tone-muted">${say(`The same case goes to the ${s.word} and to the bare AI tool on the same model, each in a copy of the project with no remote: nothing is pushed and your town is not changed.`)}</p>
    <div class="gui-bench__form">
      ${field("Case", html`<select class="ok-input" value=${f.case} onChange=${set("case")}>
        ${ready.length > 1 && html`<optgroup label="One after another">
          <option value="all">Every case (${ready.length})</option>
          ${LEVELS.filter(([l]) => s.levels[l] > 0).map(([l, label]) => html`<option key=${l} value=${`level:${l}`}>${label} (${s.levels[l]})</option>`)}
        </optgroup>`}
        <optgroup label="One case">${ready.map((c) => html`<option key=${c.id} value=${c.id}>${c.title}${c.level ? ` · ${c.level}` : ""}</option>`)}</optgroup></select>`)}
      ${field("AI tool", html`<select class="ok-input" value=${f.tool} onChange=${set("tool")}>
        ${s.tools.map((t) => html`<option key=${t.id} value=${t.id}>${t.title}</option>`)}</select>`)}
      ${field(s.type === "barracks" || pooled ? "Orks' tier" : "Tier", html`<select class="ok-input" value=${f.tier} onChange=${set("tier")}>
        ${s.tiers.map((t) => html`<option key=${t.id} value=${t.id}>${t.title}</option>`)}</select>`)}
      ${field("Sides", html`<select class="ok-input" value=${f.only} onChange=${set("only")}>
        ${SIDES.map(([v, l]) => html`<option key=${v} value=${v}>${say(l)}</option>`)}</select>`)}
      ${field("Spend limit, $", html`<input class="ok-input" type="number" min="0.1" max="50" step="0.5" value=${f.max_spend}
        onInput=${set("max_spend")} />`)}
    </div>
    ${s.orders_of && html`<details class="gui-bench__more"><summary class="ok-font-label">${pooled ? "The Agent pool's instructions for this run" : "Instructions for this run"}${f.orders !== s.orders ? " (changed)" : ""}</summary>
      <p class="ok-font-status ok-tone-muted">${pooled
        ? say(`The ${s.word} hands its work to an Agent pool. Empty: the case's own instructions; what you write here is for this run only.`)
        : say(`What the ${s.word}'s steward keeps as its rules. A change here is for this run only; the building keeps its own.`)}</p>
      <textarea class="ok-input gui-textarea" rows="6" value=${f.orders} onInput=${set("orders")}></textarea>
      ${f.orders !== s.orders && html`<button class="ok-btn" onClick=${() => setF({ ...f, orders: s.orders })}>${pooled ? "Back to the case's own" : "Back to the building's own"}</button>`}
    </details>`}
    <div class="gui-bench__row">
      <button class="ok-btn primary" disabled=${on || !f.case} onClick=${() => call("bench.run", f)}>Run</button>
      <span class="ok-font-status ok-tone-muted">${say(`It runs AI tools: the building's side stops at ${money(+f.max_spend)}${series ? " for each case" : ""}; the bare AI tool's run is one call${series ? " a case" : ""}.`)}</span>
    </div>
  </section>`;
}

function JobLog({ s, call }) {
  const j = s.job;
  const on = !j.done;
  return html`<section class="gui-bench__section">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">
      ${on && html`<span class="gui-bench__spin" aria-hidden="true"></span>`}
      ${j.what === "case" ? "Writing a case" : `Run: ${j.label}`} · ${clock(j.seconds)}</h4>
      <span class="gui-bench__acts">
        ${j.lines.length > 0 && html`<button class="ok-btn" title=${`Copy all ${j.lines.length} lines`}
          onClick=${() => copyText([`${j.what === "case" ? "Writing a case" : `Run: ${j.label}`} · ${clock(j.seconds)}`, ...(j.error ? [`error: ${j.error}`] : []), ...j.lines].join("\n"),
                                   `Copied ${many(j.lines.length, "line")}`)}>Copy</button>`}
        ${on && html`<button class="ok-btn" onClick=${() => call("bench.stop")}>Stop</button>`}</span></div>
    ${j.error && html`<p class="ok-font-status ok-tone-error">${j.error}</p>`}
    ${j.done && !j.error && j.what === "case" && html`<p class="ok-font-status">The case <b>${j.result}</b> is written. Read it below before it counts.</p>`}
    ${j.lines.length > 0 && html`<pre class="gui-bench__log gui-bench__term" title=${j.lines.length > LOG_LINES ? `${j.lines.length - LOG_LINES} earlier lines: Copy takes them all` : ""}>${j.lines.slice(-LOG_LINES).join("\n")}</pre>`}
  </section>`;
}

/** The latest run of each case: how far the building is from the bare AI tool, and whether it stays within the limit. */
function Against({ s }) {
  const limit = Math.round(s.gap_limit * 100);
  const ok = s.against.filter((r) => r.within).length;
  const quality = (r) => (r.quality > 0 ? "worse" : r.quality < 0 ? "better" : "same");
  return html`<section class="gui-bench__section">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">${say(`The ${s.word} against the bare AI tool`)}</h4>
      ${s.against_copy && html`<button class="ok-btn" onClick=${() => copyText(s.against_copy, "Copied the summary")}>Copy for analysis</button>`}</div>
    <p class="ok-font-status ok-tone-muted">${say(`The latest run of each case. Time and spend: how much more the ${s.word} took. Within ${limit}%: no worse on the check, and at most ${limit}% more time and spend. ${ok} of ${s.against.length} are.`)}</p>
    <table class="gui-bench__table gui-bench__against">
      <thead><tr><th>Case</th><th>Level</th><th>Time</th><th>Spend</th><th>Check</th><th>${`Within ${limit}%`}</th></tr></thead>
      <tbody>${s.against.map((r) => html`<tr key=${r.case}><th>${r.case}</th><td>${r.level || "—"}</td>
        <td>${pct(r.time)}</td><td>${pct(r.spend)}</td>
        <td title=${`${say(s.word)}: ${r.building} · bare: ${r.bare}`}>${quality(r)}</td>
        <td><span class=${cls("gui-bench__verdict", { "is-ok": r.within, "is-bad": !r.within })}>${r.within ? "yes" : "no"}</span></td></tr>`)}</tbody>
    </table>
  </section>`;
}

function Runs({ s }) {
  const [pick, setPick] = useState(0);
  const r = s.runs[Math.min(pick, s.runs.length - 1)];
  const sides = [r.building, r.bare].filter(Boolean);
  const name = (x) => (x.name === "building" ? say(s.word) : "Bare AI tool");
  const verdict = (x) => (x.error ? "did not finish" : x.passed === true ? "passed" : x.passed === false ? "failed" : "no check");
  const tier = (s.tiers.find((t) => t.id === r.tier) || {}).title;
  const rows = [
    ["Time", (x) => `${clock(x.seconds)}${x.cut ? " (cut)" : ""}`],
    ["Spend", (x) => money(x.cost)],
    ["Tokens", (x) => (x.tokens ? x.tokens.toLocaleString() : "not reported")],
    ["Check", (x) => html`<span class=${cls("gui-bench__verdict", { "is-ok": x.passed === true && !x.error, "is-bad": x.passed === false || !!x.error })}>${verdict(x)}</span>`],
    ...(sides.some((x) => x.checks && x.checks.length)
      ? [["Checks", (x) => (x.checks && x.checks.length ? `${x.checks.filter((c) => c.ok).length} of ${x.checks.length}` : "—")],
         ["Model", (x) => (x.model ? (s.tiers.find((t) => t.id === x.model) || {}).title || x.model : "its default")]]
      : [["Change", (x) => `${many(x.files.length, "file")}, ${many(x.lines, "line")}`]]),
    ...(sides.some((x) => x.orks) ? [["Orks", (x) => (x.name === "building" ? String(x.orks) : "one AI tool")]] : []),
  ];
  return html`<section class="gui-bench__section">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">Runs</h4>
      <span class="gui-bench__acts">
        <button class="ok-btn" title="The whole run as text: both sides, every check, how it went, the reports"
          onClick=${() => copyText(r.copy, "Copied the run")}>Copy for analysis</button>
        <select class="ok-input gui-bench__pick" value=${pick} onChange=${(e) => setPick(+e.target.value)}>
          ${s.runs.map((x, i) => html`<option key=${x.id} value=${i}>${x.at.replace("T", " ")} · ${x.case}</option>`)}</select></span></div>
    <p class="ok-font-status ok-tone-muted">${r.case} · ${r.tool === "main" ? "main tool" : r.tool}${tier && r.tier ? ` · ${tier}` : ""}${r.orders_changed ? " · instructions changed for this run" : ""}</p>
    <table class="gui-bench__table">
      <thead><tr><th></th>${sides.map((x) => html`<th key=${x.name}>${name(x)}</th>`)}</tr></thead>
      <tbody>${rows.map(([label, cell]) => html`<tr key=${label}><th>${label}</th>${sides.map((x) => html`<td key=${x.name}>${cell(x)}</td>`)}</tr>`)}</tbody>
    </table>
    ${sides.filter((x) => x.checks && x.checks.some((c) => !c.ok)).map((x) => html`<details key=${`m-${x.name}`} class="gui-bench__more" open>
      <summary class="ok-font-label">${name(x)} missed ${x.checks.filter((c) => !c.ok).length}</summary>
      <ul class="gui-bench__missed">${x.checks.filter((c) => !c.ok).map((c, i) => html`<li key=${i}><b>${c.name}</b>${c.detail ? html` <span class="ok-tone-muted">— ${c.detail}</span>` : ""}</li>`)}</ul>
    </details>`)}
    ${sides.filter((x) => x.error || (x.passed === false && x.check_tail)).map((x) => html`<details key=${x.name} class="gui-bench__more">
      <summary class="ok-font-label">${name(x)}: ${x.error ? "why it did not finish" : "the check's last lines"}</summary>
      <pre class="gui-bench__log">${x.error || x.check_tail}</pre></details>`)}
    ${r.building && r.building.steps && r.building.steps.length > 0 && html`<${Timeline} side=${r.building} />`}
    ${r.building && !(r.building.steps && r.building.steps.length) && r.building.how && r.building.how.length > 0 && html`<details class="gui-bench__more" open>
      <summary class="ok-font-label">Inside the run</summary><pre class="gui-bench__log">${r.building.how.join("\n")}</pre></details>`}
    ${sides.filter((x) => x.text).map((x) => html`<details key=${x.name} class="gui-bench__more">
      <summary class="ok-font-label">${name(x)}: its report</summary><pre class="gui-bench__log">${x.text}</pre></details>`)}
    ${sides.filter((x) => x.where).map((x) => html`<p key=${x.name} class="ok-font-status ok-tone-muted">${name(x)}'s result: <code>${x.where}</code></p>`)}
  </section>`;
}

/** Inside the building's run: a lane per ork and one for the steward, a mark per decision on the run's clock. */
function Timeline({ side }) {
  const total = Math.max(side.seconds, ...side.steps.map((x) => x.t), 1);
  const who = [...new Set(side.steps.map((x) => x.who))].sort((a, b) => (a === "steward" ? -1 : b === "steward" ? 1 : 0));
  const [hover, setHover] = useState(null);
  return html`<div class="gui-bench__timeline">
    <h4 class="ok-font-label gui-bench__h">Inside the run</h4>
    ${who.map((w) => {
      const mine = side.steps.filter((x) => x.who === w);
      const first = Math.min(...mine.map((x) => x.t)), last = Math.max(...mine.map((x) => x.t));
      return html`<div key=${w} class="gui-bench__lane">
        <span class="gui-bench__who">${w === "steward" ? "Steward" : w}</span>
        <span class="gui-bench__track">
          <i class="gui-bench__span" style=${`left:${(first / total) * 100}%;width:${Math.max(((last - first) / total) * 100, 0.6)}%`}></i>
          ${mine.map((x, i) => html`<button key=${i} class=${cls("gui-bench__mark", { "is-on": hover === x })}
            style=${`left:${(x.t / total) * 100}%`} title=${`+${clock(x.t)} ${x.action}: ${x.why}`}
            onMouseEnter=${() => setHover(x)} onFocus=${() => setHover(x)} aria-label=${`${x.action} at ${clock(x.t)}`}></button>`)}
        </span></div>`;
    })}
    <div class="gui-bench__axis"><span>0:00</span><span>${clock(total)}</span></div>
    <p class="ok-font-status gui-bench__step">${hover ? html`<b>+${clock(hover.t)} ${hover.action}</b>${hover.who !== "steward" ? ` (${hover.who})` : ""}: ${hover.why}`
      : html`<span class="ok-tone-muted">Point at a mark to read the decision.</span>`}</p>
  </div>`;
}

/** What a case gives a building that is not about code, in a line: "8 messages · intent: …". */
function given(inputs) {
  return Object.entries(inputs).map(([k, v]) => (Array.isArray(v) ? (k === "expect_headings" ? `sections: ${v.join(", ")}` : many(v.length, k.replace(/s$/, "")))
    : typeof v === "string" ? `${k}: ${v.length > 120 ? `${v.slice(0, 120)}…` : v}` : k)).join(" · ");
}

function Cases({ s, call }) {
  const [brief, setBrief] = useState("");
  const on = s.job && !s.job.done;
  return html`<section class="gui-bench__section">
    <h4 class="ok-font-label gui-bench__h">Cases</h4>
    <ul class="gui-bench__cases">
      ${s.cases.map((c) => html`<li key=${c.id} class=${cls("gui-bench__case", { "is-unread": !c.reviewed })}>
        <details><summary><b>${c.title}</b> <span class="ok-tone-muted">${c.id}${c.own ? "" : " · shipped"}</span>
          ${!c.reviewed && html` <span class="ok-word gui-bench__badge">not read yet</span>`}</summary>
          ${c.task && html`<p class="ok-font-status">${c.task}</p>`}
          ${Object.keys(c.inputs || {}).length > 0 && html`<p class="ok-font-status">${given(c.inputs)}</p>`}
          ${c.expect && html`<p class="ok-font-status ok-tone-muted">A good result: ${c.expect}</p>`}
          ${c.check ? html`<p class="ok-font-status">Check: <code>${c.check}</code></p>`
            : Object.keys(c.inputs || {}).length > 0 && html`<p class="ok-font-status ok-tone-muted">Checked in code, item by item, the same way on both sides.</p>`}
          ${Object.keys(c.files).length > 0 && html`<p class="ok-font-status ok-tone-muted">Its project: ${Object.keys(c.files).join(", ")}</p>`}
          ${!c.reviewed && html`<button class="ok-btn" onClick=${() => call("bench.case.read", { case: c.id })}>I read it: it counts</button>`}
        </details></li>`)}
    </ul>
    <div class="gui-bench__row">
      <input class="ok-input gui-bench__grow" value=${brief} placeholder="What the new case should test (or leave it to the agent)"
        onInput=${(e) => setBrief(e.target.value)} />
      <button class="ok-btn" disabled=${on} onClick=${() => { call("bench.case.write", { brief }); setBrief(""); }}>Write a case</button>
    </div>
    <p class="ok-font-status ok-tone-muted">An agent writes the case and its check; it counts once you have read it. One AI tool run.</p>
  </section>`;
}

// -- the reviews ---------------------------------------------------------------------------------------------

function Reviews({ s, tab, call, picks, flip }) {
  const r = s.reviews[tab];
  const on = r.roles.some((x) => x.running);
  const titles = r.roles.map((x) => x.title).join(", ");
  return html`<section class="gui-bench__section">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">${tab === "tech" ? "Reviews" : "Reviewers"}: ${titles}</h4>
      ${on ? html`<button class="ok-btn" onClick=${() => call("bench.stop", { tab })}>Stop</button>`
        : html`<button class="ok-btn" onClick=${() => call("bench.review", { tab })}>${r.at ? "Review again" : "Review"}</button>`}</div>
    <p class="ok-font-status ok-tone-muted">${r.at ? `Reviewed ${r.at.replace("T", " ")}, Orkcraft ${r.version}.` : "Not reviewed yet."}
      ${r.stale ? " The building has changed since: review it again." : ""} Each reviewer is one AI tool run; they only read Orkcraft's code.</p>
    ${r.roles.map((role) => html`<div key=${role.id} class="gui-bench__role">
      <div class="gui-bench__row"><b>${role.title}</b>
        ${role.running ? html`<span class="ok-font-status ok-tone-muted"><span class="gui-bench__spin" aria-hidden="true"></span> reading…</span>`
          : role.status === "done" ? html`<span class="ok-font-status ok-tone-muted">${many(role.findings.length, "finding")} · ${money(role.cost)} · ${clock(role.seconds)}</span>` : ""}</div>
      <p class="ok-font-status ok-tone-muted">Looks at ${role.focus}.</p>
      ${role.status === "failed" && html`<p class="ok-font-status ok-tone-error">${role.error}</p>`}
      <ul class="gui-bench__findings">${role.findings.map((f) => html`<${Finding} key=${f.id} f=${f} picked=${picks.has(f.id)} flip=${flip} />`)}</ul>
    </div>`)}
  </section>`;
}

function Finding({ f, picked, flip }) {
  return html`<li class=${cls("gui-bench__finding", { "is-picked": picked })}>
    <label class="ok-check"><input type="checkbox" class="gui-onb__hide" checked=${picked} onChange=${() => flip(f.id)} />
      <i>${picked ? "✓" : ""}</i><span><span class=${`gui-bench__sev is-${f.severity}`}>${f.severity}</span> <b>${f.title}</b></span></label>
    ${f.detail && html`<p class="ok-font-status">${f.detail}</p>`}
    ${f.where && html`<p class="ok-font-status ok-tone-muted">${f.where}</p>`}
  </li>`;
}

function Product({ s, call, picks, flip }) {
  const ahas = s.reviews.product.roles.filter((r) => r.aha);
  return html`
    ${ahas.length > 0 ? ahas.map((r) => html`<section key=${r.id} class="gui-bench__section gui-bench__aha">
      <h4 class="ok-font-label gui-bench__h">The AHA moment, as the ${r.title} sees it</h4>
      <p class="ok-font-body"><b>${r.aha.moment}</b></p>
      ${r.aha.script.length > 0 && html`<ol class="gui-bench__script">${r.aha.script.map((x, i) => html`<li key=${i}>${x}</li>`)}</ol>`}
      ${(r.aha.measure || r.aha.time_to_it) && html`<p class="ok-font-status ok-tone-muted">
        ${r.aha.measure && `Measured by: ${r.aha.measure}`}${r.aha.measure && r.aha.time_to_it ? " · " : ""}${r.aha.time_to_it && `Reached in: ${r.aha.time_to_it}`}</p>`}
    </section>`)
      : html`<p class="ok-font-status ok-tone-muted">The AHA moment shows here once the review has found it.</p>`}
    <${Reviews} s=${s} tab="product" call=${call} picks=${picks} flip=${flip} />`;
}

// -- Make tasks ----------------------------------------------------------------------------------------------

function MakeTasks({ s, lab, picks, done }) {
  const ROADS = "@roads";
  const [pool, setPool] = useState(s.roads.length ? ROADS : s.pools[0] ? s.pools[0].id : "");
  const n = picks.size;
  if (!s.pools.length && !s.roads.length) {
    return html`<span class="gui-dialog__note">${say("Pull a road out of the Test bench, or build an Agent pool, to make tasks of the findings.")}</span>`;
  }
  const make = () => command("bench.tasks", { id: s.id, lab, picks: [...picks], pool }).then(done, () => {});
  return html`<span class="gui-dialog__note">${n ? `${n} finding${n === 1 ? "" : "s"} ticked` : "Tick findings to make tasks of them"}</span>
    <select class="ok-input gui-bench__pick" value=${pool} onChange=${(e) => setPool(e.target.value)} aria-label=${say("Where the tasks go")}>
      ${s.roads.length > 0 && html`<option value=${ROADS}>${say(`Down its roads (${s.roads.map((r) => r.title).join(", ")})`)}</option>`}
      ${s.pools.map((p) => html`<option key=${p.id} value=${p.id}>${say(p.title)}</option>`)}</select>
    <button class="ok-btn primary" disabled=${!n || !pool} onClick=${make}>Make ${n || ""} task${n === 1 ? "" : "s"}</button>`;
}
