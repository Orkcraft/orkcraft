// 🧪 The Test bench (docs/design/test-bench.md §2, §10). Closed: what it tests, its goal and how its cases stand
// against the bare AI tool. Open: the goal of the testing (its first cases are written from it, Run all cases runs
// them), the settings of a run, every case with its last test (time, tokens, quality against the bare AI tool), and
// below them what to change in the buildings, the roads or the prompts for the goal. The shipped cases and the
// reviews (js/bench.js) stay folded under them. A road into it says what it tests; a road out, where results go.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { BenchView, copyText } from "../bench.js";

const sheet = new URL("./lab.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const LOG_LINES = 4;
const METRIC = { tokens: "tokens", time: "time", quality: "quality" };
const AREA = { code: "Code", roads: "Roads", prompt: "Prompt", settings: "Settings" };
const pct = (v) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${Math.round(v * 100)}%`);
const pts = (v) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v}`);
const clock = (s) => `${Math.floor((s || 0) / 60)}:${String(Math.round((s || 0) % 60)).padStart(2, "0")}`;
const many = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
/** How a change reads for the metric: less time and fewer tokens are better, a higher quality is. */
const good = (key, v) => (v === null || v === undefined || v === 0 ? "" : (key === "quality" ? v > 0 : v < 0) ? "is-ok" : "is-bad");

/** "3 of 5 cases ahead on tokens, −18 % on average" — over the last test of every case. */
function summaryLine(sum) {
  if (!sum || !sum.cases) return "";
  const mean = sum.mean === null || sum.mean === undefined ? "" : `, ${sum.metric === "quality" ? pts(sum.mean) : pct(sum.mean)} on average`;
  return `${sum.ahead} of ${many(sum.cases, "case")} ahead on ${METRIC[sum.metric]}${mean}`;
}

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.subject) {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Nothing to test")}</div>
      <div class="gui-hut__text ok-tone-muted">${say("Pull a road from a building into it")}</div>
    </div>`;
  }
  const line = summaryLine(c.summary);
  const last = c.last;
  const tone = !last ? "" : last.passed === true ? "ok-tone-ok" : last.passed === false ? "ok-tone-error" : "";
  return html`<div class="gui-hut__body-in">
    ${line ? html`<div class="gui-hut__big">${say(line)}</div>`
      : html`<div class=${cls("gui-hut__big", tone)}>${last ? say(last.verdict.split(",")[0]) : c.cases ? say(many(c.cases, "case")) : say("No run yet")}<small>${last ? last.case : ""}</small></div>`}
    ${c.goal && html`<div class="gui-hut__text ok-tone-muted lab-card-goal">${c.goal}</div>`}
    <div class="gui-hut__foot"><span>${say(`Tests ${c.subject.title}`)}${c.count > 1 ? ` +${c.count - 1}` : ""}</span>
      ${c.targets > 0 && html`<span class="gui-hut__when">${say(`→ ${c.targets} road${c.targets === 1 ? "" : "s"}`)}</span>`}</div>
  </div>`;
}

function Window({ id, data }) {
  const subjects = data.subjects || [];
  if (!subjects.length) {
    return html`<div class="lab-empty">
      <p class="ok-font-body">${say("The Test bench tests the building whose road comes into it, or a whole chain.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("One building: pull a road from it (the Agent pool, External listeners, the Task board…) into the Test bench.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("A chain: pull a road with “test case” from the Test bench into the chain's first building, and a road from its last building back into the Test bench.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("Any other road out of it takes its reports and findings where they should go.")}</p>
    </div>`;
  }
  const pick = data.subject || subjects[0].id;
  return html`<div class="lab-window">
    ${subjects.length > 1 && html`<label class="gui-field lab-pick"><span class="ok-font-label">${say("Tests")}</span>
      <select class="ok-input" value=${pick} onChange=${(e) => act(id, "pick", { id: e.target.value })}>
        ${subjects.map((s) => html`<option key=${s.id} value=${s.id}>${say(s.title)} · ${say(s.word)}</option>`)}</select></label>`}
    <${LabView} key=${pick} id=${id} d=${data} />
    <details class="gui-bench__more lab-shipped" open=${!(data.cases || []).length}><summary class="ok-font-label">${say("Shipped cases and reviews")}</summary>
      <${BenchView} key=${pick} id=${pick} lab=${id} /></details>
  </div>`;
}

const field = (label, control) => html`<label class="gui-field"><span class="ok-font-label">${say(label)}</span>${control}</label>`;

/** The Test bench's own work for what it tests: goal, settings, cases, the run, what to change. */
function LabView({ id, d }) {
  const on = !!(d.job && !d.job.done);
  useEffect(() => {                         // while a run or an agent works, its lines and results come in
    if (!on && !d.busy) return undefined;
    const timer = setTimeout(() => act(id, "refresh").catch(() => {}), 1500);
    return () => clearTimeout(timer);
  }, [id, d]);
  return html`<div class="lab-own">
    <${Goal} id=${id} d=${d} on=${on} />
    <${Settings} id=${id} d=${d} />
    <${Cases} id=${id} d=${d} on=${on} />
    ${d.job && html`<${RunLog} id=${id} job=${d.job} />`}
    <${Proposals} id=${id} d=${d} on=${on} />
  </div>`;
}

function Goal({ id, d, on }) {
  const [goal, setGoal] = useState(d.goal || "");
  useEffect(() => setGoal(d.goal || ""), [d.goal]);
  const changed = goal.trim() !== (d.goal || "");
  const save = () => (changed ? act(id, "goal", { goal }) : Promise.resolve());
  const line = summaryLine(d.summary);
  return html`<section class="gui-bench__section lab-goal">
    <h4 class="ok-font-label gui-bench__h">${say("Goal of the testing")}</h4>
    <textarea class="ok-input gui-textarea" rows="2" maxlength="1000" value=${goal}
      placeholder=${say("e.g. Spend fewer tokens than the bare AI tool on the same work, with no loss of quality")}
      onInput=${(e) => setGoal(e.target.value)} onBlur=${save}></textarea>
    <p class="ok-font-status ok-tone-muted">${say(`The Test bench leads with ${METRIC[d.metric] || "quality"}: the goal's words say which (tokens or spend, time or speed, else quality).`)}${line ? html` <b>${say(line)}.</b>` : ""}</p>
    <div class="gui-bench__row">
      <button class="ok-btn" disabled=${!goal.trim() || d.busy === "generate"}
        onClick=${() => save().then(() => act(id, "generate"))}>${d.busy === "generate" ? say("Writing cases…") : (d.cases || []).length ? say("Write more cases") : say("Write cases for the goal")}</button>
      <button class="ok-btn primary lab-run-all" disabled=${on || !(d.cases || []).length}
        onClick=${() => save().then(() => act(id, "run_all"))}>${say(`Run all cases${(d.cases || []).length ? ` (${d.cases.length})` : ""}`)}</button>
      ${on && html`<button class="ok-btn" onClick=${() => act(id, "stop")}>${say("Stop")}</button>`}
    </div>
  </section>`;
}

function Settings({ id, d }) {
  const s = d.settings || {};
  const set = (key, value) => act(id, "settings", { [key]: value });
  const pick = (key, list) => html`<select class="ok-input" value=${s[key] || ""} onChange=${(e) => set(key, e.target.value)}>
    ${list.map((t) => html`<option key=${t.id} value=${t.id}>${say(t.title)}</option>`)}</select>`;
  return html`<details class="gui-bench__more lab-settings"><summary class="ok-font-label">${say("Run settings")}
      <span class="ok-tone-muted"> · ${say(`${s.tool === "main" ? "main tool" : s.tool}${s.tier ? `, ${s.tier}` : ""} against ${s.bare_tool === "main" ? "main tool" : s.bare_tool}${s.bare_tier ? `, ${s.bare_tier}` : ""}`)}</span></summary>
    <div class="gui-bench__form">
      ${field("Scheme: AI tool", pick("tool", d.tools || []))}
      ${field("Scheme: tier", pick("tier", d.tiers || []))}
      ${field("Bare: AI tool", pick("bare_tool", d.tools || []))}
      ${field("Bare: tier", pick("bare_tier", d.tiers || []))}
      ${field("Spend limit a case, $", html`<input class="ok-input" type="number" min="0.1" max="50" step="0.5" value=${s.max_spend}
        onChange=${(e) => set("max_spend", e.target.value)} />`)}
    </div>
    <label class="lab-check"><input type="checkbox" checked=${!!s.judge} onChange=${(e) => set("judge", e.target.checked)} />
      <span class="ok-font-body">${say("A blind judge scores both results 0–10 (one more AI call a case)")}</span></label>
    <p class="ok-font-status ok-tone-muted">${say("Each case runs in a copy of the project with no remote: nothing is pushed and your town is not changed. The scheme's side stops at the spend limit; the bare AI tool's is one call.")}</p>
  </details>`;
}

function Cases({ id, d, on }) {
  const cases = d.cases || [];
  const results = d.results || {};
  return html`<section class="gui-bench__section lab-cases">
    <h4 class="ok-font-label gui-bench__h">${say(`Cases (${cases.length})`)}</h4>
    ${!cases.length && html`<p class="ok-font-status ok-tone-muted">${say("No case yet: write the goal and press Write cases for the goal, or add one below.")}</p>`}
    ${cases.length > 0 && html`<ul class="lab-case-list">${cases.map((c) => html`<${CaseRow} key=${c.id} id=${id} c=${c}
      r=${results[c.id]} d=${d} on=${on} />`)}</ul>`}
    <${AddCase} id=${id} entries=${d.entries || []} />
  </section>`;
}

function CaseRow({ id, c, r, d, on }) {
  const entry = (d.entries || []).find((e) => e.id === c.entry);
  const key = METRIC[d.metric] || "quality";
  const cell = (label, k, fmt) => html`<span class=${cls(`lab-delta ${good(k, r[k])}`, { "is-lead": k === key })}
    title=${say(k === "quality" ? "The scheme's score minus the bare AI tool's" : "The scheme against the bare AI tool")}>${say(label)} ${fmt(r[k])}</span>`;
  return html`<li class="lab-case">
    <div class="lab-case__head">
      <b class="ok-font-body">${c.title}</b>
      ${(d.entries || []).length > 1 && entry && html`<span class="ok-font-status ok-tone-muted">→ ${entry.title}</span>`}
      ${c.source === "generated" && html`<span class="ok-font-status ok-tone-muted">${say("from the goal")}</span>`}
      <span class="gui-bench__acts">
        <button class="ok-btn" disabled=${on} onClick=${() => act(id, "run", { case: c.id })}>${say("Test this case")}</button>
        <button class="ok-btn" title=${say("Remove the case")} onClick=${() => act(id, "remove", { case: c.id })}>×</button></span>
    </div>
    <details class="lab-case__text"><summary class="ok-font-status ok-tone-muted">${c.text.slice(0, 140)}${c.text.length > 140 ? "…" : ""}</summary>
      <pre class="lab-case__body">${c.text}</pre>
      ${c.expect && c.expect.length > 0 && html`<p class="ok-font-status">${say("A good result says")}: ${c.expect.map((x) => (Array.isArray(x) ? x.join(" / ") : x)).join(", ")}</p>`}
      ${c.why && html`<p class="ok-font-status ok-tone-muted">${c.why}</p>`}</details>
    ${r && r.scheme && r.bare ? html`<div class="lab-case__result">
        ${cell("Time", "time", pct)} ${cell("Tokens", "tokens", pct)} ${cell("Quality", "quality", pts)}
        <span class="ok-font-status ok-tone-muted">${say("scheme")} ${clock(r.scheme.seconds)} · ${(r.scheme.tokens || 0).toLocaleString()} ${say("tokens")}${r.scheme.score !== null && r.scheme.score !== undefined ? ` · ${r.scheme.score}/10` : r.scheme.checks ? ` · ${r.scheme.checks}` : ""}${r.scheme.error ? ` · ${say("did not finish")}` : ""}
           — ${say("bare")} ${clock(r.bare.seconds)} · ${(r.bare.tokens || 0).toLocaleString()} ${say("tokens")}${r.bare.score !== null && r.bare.score !== undefined ? ` · ${r.bare.score}/10` : r.bare.checks ? ` · ${r.bare.checks}` : ""}${r.bare.error ? ` · ${say("did not finish")}` : ""}
          · ${(r.at || "").replace("T", " ").slice(0, 16)}</span></div>`
      : html`<div class="ok-font-status ok-tone-muted">${say("Not tested yet")}</div>`}
  </li>`;
}

function AddCase({ id, entries }) {
  const blank = { title: "", text: "", entry: entries[0] ? entries[0].id : "", expect: "" };
  const [f, setF] = useState(blank);
  const [open, setOpen] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  if (!open) return html`<button class="ok-btn lab-add-open" onClick=${() => setOpen(true)}>${say("Add a case")}</button>`;
  return html`<div class="lab-add">
    <div class="gui-bench__form">
      ${field("Title", html`<input class="ok-input" maxlength="120" value=${f.title} placeholder=${say("e.g. Write a CSV parser with tests")} onInput=${set("title")} />`)}
      ${entries.length > 1 && field("Goes into", html`<select class="ok-input" value=${f.entry} onChange=${set("entry")}>
        ${entries.map((e) => html`<option key=${e.id} value=${e.id}>${e.title} · ${say(e.word)}</option>`)}</select>`)}
    </div>
    ${field("Input", html`<textarea class="ok-input gui-textarea" rows="4" maxlength="6000" value=${f.text}
      placeholder=${say("What a person would really send in: a task, a message, a question on a hard topic…")} onInput=${set("text")}></textarea>`)}
    ${entries.length && (entries.find((e) => e.id === f.entry) || {}).takes ? html`<p class="ok-font-status ok-tone-muted">${say("It takes")}: ${(entries.find((e) => e.id === f.entry) || {}).takes}</p>` : ""}
    ${field("A good result says (words, comma-separated; optional)", html`<input class="ok-input" maxlength="400" value=${f.expect} onInput=${set("expect")} />`)}
    <div class="gui-bench__row">
      <button class="ok-btn primary" disabled=${!f.text.trim()} onClick=${() => act(id, "add", f).then(() => { setF(blank); setOpen(false); }, () => {})}>${say("Add")}</button>
      <button class="ok-btn" onClick=${() => setOpen(false)}>${say("Cancel")}</button></div>
  </div>`;
}

function RunLog({ id, job }) {
  const title = `${say("Run")}: ${job.label} · ${clock(job.seconds)}`;
  return html`<section class="gui-bench__section">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">
      ${!job.done && html`<span class="gui-bench__spin" aria-hidden="true"></span>`}${title}</h4>
      <span class="gui-bench__acts">
        ${job.lines.length > 0 && html`<button class="ok-btn" onClick=${() => copyText([title, ...(job.error ? [`error: ${job.error}`] : []), ...job.lines].join("\n"), `Copied ${many(job.lines.length, "line")}`)}>${say("Copy")}</button>`}
        ${!job.done && html`<button class="ok-btn" onClick=${() => act(id, "stop")}>${say("Stop")}</button>`}</span></div>
    ${job.error && html`<p class="ok-font-status ok-tone-error">${job.error}</p>`}
    ${job.lines.length > 0 && html`<pre class="gui-bench__log gui-bench__term">${job.lines.slice(-LOG_LINES).join("\n")}</pre>`}
  </section>`;
}

function Proposals({ id, d, on }) {
  const items = (d.proposals && d.proposals.items) || [];
  const [picks, setPicks] = useState(new Set());
  const [pool, setPool] = useState("");
  const pools = [...(d.pools || []), ...((d.targets || []).length ? [{ id: "@roads", title: "Down the Test bench's roads" }] : [])];
  const to = pool || (pools[0] ? pools[0].id : "");
  const flip = (pid) => { const next = new Set(picks); next.has(pid) ? next.delete(pid) : next.add(pid); setPicks(next); };
  const tested = Object.keys(d.results || {}).length;
  return html`<section class="gui-bench__section lab-proposals">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">${say("What to change for the goal")}</h4>
      <button class="ok-btn" disabled=${d.busy === "propose" || on}
        onClick=${() => act(id, "propose")}>${d.busy === "propose" ? say("Reading the code…") : items.length ? say("Propose again") : say("Propose changes")}</button></div>
    <p class="ok-font-status ok-tone-muted">${say(tested ? "An agent reads the buildings' code, the roads and the last tests, and proposes changes to the code, the roads, the prompts or the settings. Run all cases proposes again by itself." : "Test the cases first: the proposals lean on what the tests said.")}${d.proposals && d.proposals.at ? ` ${say("Written")} ${d.proposals.at.replace("T", " ").slice(0, 16)}.` : ""}</p>
    ${items.length > 0 && html`<ul class="lab-proposal-list">${items.map((p) => html`<li key=${p.id} class="lab-proposal">
      <label class="lab-check"><input type="checkbox" checked=${picks.has(p.id)} onChange=${() => flip(p.id)} />
        <span class="lab-area">${say(AREA[p.area] || p.area)}</span> <b class="ok-font-body">${p.title}</b></label>
      <p class="ok-font-status">${p.detail}</p>
      ${(p.where || p.effect) && html`<p class="ok-font-status ok-tone-muted">${p.where ? `${say("Where")}: ${p.where}` : ""}${p.where && p.effect ? " · " : ""}${p.effect ? `${say("Should")}: ${p.effect}` : ""}</p>`}
    </li>`)}</ul>
    <div class="gui-bench__row">
      ${pools.length ? html`<select class="ok-input" value=${to} onChange=${(e) => setPool(e.target.value)}>
        ${pools.map((x) => html`<option key=${x.id} value=${x.id}>${x.id === "@roads" ? say(x.title) : x.title}</option>`)}</select>
        <button class="ok-btn primary" disabled=${!picks.size}
          onClick=${() => act(id, "tasks", { picks: [...picks], pool: to }).then(() => setPicks(new Set()), () => {})}>${say(`Make tasks${picks.size ? ` (${picks.size})` : ""}`)}</button>`
        : html`<span class="ok-font-status ok-tone-muted">${say("Raise an Agent pool, or pull a road out of the Test bench, to make tasks of them.")}</span>`}
      <button class="ok-btn" onClick=${() => copyText(items.map((p) => `- [${p.area}] ${p.title}\n  ${p.detail}${p.where ? `\n  where: ${p.where}` : ""}${p.effect ? `\n  should: ${p.effect}` : ""}`).join("\n"), "Copied the proposals")}>${say("Copy")}</button>
    </div>`}
  </section>`;
}

/** The window: one pane, the bench of the building it tests. */
export function panes(id, data) {
  return { main: () => html`<${Window} id=${id} data=${data} />` };
}

/** Run every case of its own (else the first shipped case) from its Info or closed card. */
export function quick(id, action) {
  if (action === "lab.run") { act(id, "lab.run"); return true; }
  return false;
}
