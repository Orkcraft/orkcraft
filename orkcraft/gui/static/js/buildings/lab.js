// 🧪 The Test bench (docs/design/test-bench.md §2, §10). Closed: what it tests, its goal and how its cases stand
// against the bare AI tool. Open, in the order a person works: environments and their case sets, single cases,
// Run all (its settings folded), the results of the latest runs with Copy for analysis and the zip of every call,
// and the recommendations (the tech review of what it tests, reading those runs). The goal, what to change, the
// virtual building and the shipped cases stay folded under More (docs/design/improve-buildings.md §11). A road
// into it says what it tests; a road out, where results go.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, town } from "../link.js";
import { BenchView, copyText } from "../bench.js";
import { settingUp } from "../build.js";
import { framing } from "../frame.js";
import { Dialog } from "../dialog.js";

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
      <div class="gui-hut__text ok-tone-muted">${say("Open it and set it up: pick what it tests")}</div>
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
    return html`<div class="lab-window"><${Check} id=${id} c=${data.check || {}} /><div class="lab-empty">
      <p class="ok-font-body">${say("The Test bench tests one building, or several in a row as one chain.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("Its setup lays its roads: pick a building, or frame several on the map.")}</p>
      <span><button class="ok-btn primary" onClick=${() => setUp(id)}>${say("Set it up")}</button></span>
    </div></div>`;
  }
  const pick = data.subject || subjects[0].id;
  return html`<div class="lab-window">
    <${Check} id=${id} c=${data.check || {}} />
    <span><button class="gui-link ok-font-status" onClick=${() => setUp(id)}>${say("Change what it tests")}</button></span>
    ${subjects.length > 1 && html`<label class="gui-field lab-pick"><span class="ok-font-label">${say("Tests")}</span>
      <select class="ok-input" value=${pick} onChange=${(e) => act(id, "pick", { id: e.target.value })}>
        ${subjects.map((s) => html`<option key=${s.id} value=${s.id}>${say(s.title)} · ${say(s.word)}</option>`)}</select></label>`}
    <${LabView} key=${pick} id=${id} d=${data} pick=${pick} />
  </div>`;
}

const field = (label, control) => html`<label class="gui-field"><span class="ok-font-label">${say(label)}</span>${control}</label>`;

/** The Test bench's own work for what it tests: goal, settings, cases, the run, what to change. */
function LabView({ id, d, pick }) {
  const on = !!(d.job && !d.job.done);
  const reviewing = (d.recs || []).some((r) => r.running);
  const [more, setMore] = useState(false);     // its shipped cases open (and are first reviewed) only when unfolded
  useEffect(() => {                         // while a run, an agent or a review works, its lines and results come in
    if (!on && !d.busy && !reviewing) return undefined;
    const timer = setTimeout(() => act(id, "refresh").catch(() => {}), 1500);
    return () => clearTimeout(timer);
  }, [id, d]);
  return html`<div class="lab-own">
    <${Envs} id=${id} d=${d} on=${on} />
    <${Cases} id=${id} d=${d} on=${on} />
    <${RunAll} id=${id} d=${d} on=${on} />
    ${d.job && html`<${RunLog} id=${id} job=${d.job} />`}
    <${Results} id=${id} d=${d} />
    <${Recommendations} id=${id} d=${d} on=${on} />
    <details class="gui-bench__more lab-more" onToggle=${(e) => setMore(e.currentTarget.open)}><summary class="ok-font-label">${say("More: the goal, what to change, the shipped cases")}</summary>
      <${Goal} id=${id} d=${d} on=${on} />
      <${Proposals} id=${id} d=${d} on=${on} />
      <${Virtual} id=${id} d=${d} on=${on} />
      ${more && html`<section class="gui-bench__section"><h4 class="ok-font-label gui-bench__h">${say("Shipped cases")}</h4>
        <${BenchView} key=${pick} id=${pick} lab=${id} /></section>`}
    </details>
  </div>`;
}

/** `orkcraft check`: the main jobs on the cheap AI tool and a quiet town, green or red, and all it saw as a zip. */
function Check({ id, c }) {
  const job = c.job;
  const on = !!(job && !job.done);
  const last = c.last || {};
  useEffect(() => {                         // while it runs, its lines come in
    if (!on) return undefined;
    const timer = setTimeout(() => act(id, "refresh").catch(() => {}), 2000);
    return () => clearTimeout(timer);
  }, [id, c]);
  return html`<section class="gui-bench__section lab-check">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">
      ${on && html`<span class="gui-bench__spin" aria-hidden="true"></span>`}${say("Check the main jobs")}</h4>
      <span class="gui-bench__acts">
        ${on ? html`<button class="ok-btn" onClick=${() => act(id, "check_stop")}>${say("Stop")}</button>`
          : html`<button class="ok-btn primary" onClick=${() => act(id, "check_run")}>${say("Run the check")}</button>`}
        ${last.zip && html`<a class="ok-btn" href=${`/api/check/latest?t=${encodeURIComponent(TOKEN)}`} download
          title=${say("Every run and every model call it made, with a README for the agent that reads it")}>${say("Download (.zip)")}</a>`}</span></div>
    <p class="ok-font-status ok-tone-muted">${say("Mail sorted, tasks from mail, the Review board and pictures redrawn, each case 3 times against the bare AI tool on agy's lightest model; then a quiet town that must call no model. It spends: each run stops at $2.")}</p>
    ${job && html`<pre class="gui-bench__log gui-bench__term">${(job.lines || []).slice(-LOG_LINES).join("\n")}</pre>`}
    ${job && job.error && html`<p class="ok-font-status ok-tone-error">${job.error}</p>`}
    ${last.stamp && html`<details class="lab-check__last" open=${!on}><summary class=${cls("ok-font-body", last.green ? "ok-tone-ok" : "ok-tone-error")}>
        ${say(`${last.green ? "Green" : "Red"} · ${last.stamp.replace(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2}).*/, "$1-$2-$3 $4:$5")}`)}</summary>
      <pre class="gui-bench__log lab-results__table">${last.report}</pre></details>`}
  </section>`;
}

/** Run every case, each the times the settings say, against the bare AI tool. */
function RunAll({ id, d, on }) {
  const n = (d.cases || []).length;
  const times = (d.settings || {}).repeat || 3;
  return html`<section class="gui-bench__section lab-run">
    <div class="gui-bench__row">
      <button class="ok-btn primary lab-run-all" disabled=${on || !n} onClick=${() => act(id, "run_all")}>${say(`Run all cases${n ? ` (${n})` : ""}`)}</button>
      ${on && html`<button class="ok-btn" onClick=${() => act(id, "stop")}>${say("Stop")}</button>`}
      <span class="ok-font-status ok-tone-muted">${say(times > 1 ? `Each case runs ${times} times: the results read their medians.` : "Each case runs once.")}</span>
    </div>
    <${Settings} id=${id} d=${d} />
  </section>`;
}

const TOKEN = new URLSearchParams(location.search).get("t") || "";

/** The latest runs side by side, to copy for an analysis or to download with every call in full. */
function Results({ id, d }) {
  const r = d.report || {};
  const copy = () => act(id, "export").then((text) => copyText(text, "Copied the runs and the recommendations"), () => {});
  return html`<section class="gui-bench__section lab-results">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">${say("Results")}</h4>
      ${r.text && html`<span class="gui-bench__acts">
        <button class="ok-btn" onClick=${copy} title=${say("The table, every run in full with its model calls, and the recommendations, as text")}>${say("Copy for analysis")}</button>
        <a class="ok-btn" href=${`/api/bench/${encodeURIComponent(id)}?t=${encodeURIComponent(TOKEN)}`} download
          title=${say("The same, plus every model call itself (what went in, what came out, how it worked), as a zip")}>${say("Download (.zip)")}</a></span>`}</div>
    ${r.text ? html`<p class="ok-font-status ok-tone-muted">${say(`${many(r.cases, "case")}, ${many(r.runs, "run")} · latest ${(r.at || "").replace("T", " ").slice(0, 16)}`)}</p>
        <pre class="gui-bench__log lab-results__table">${r.text}</pre>`
      : html`<p class="ok-font-status ok-tone-muted">${say("No run yet: add an environment and a case set, then Run all cases.")}</p>`}
  </section>`;
}

/** The tech review of each building it tests, reading the latest runs: what to change, as advice. */
function Recommendations({ id, d, on }) {
  const recs = d.recs || [];
  const busy = recs.some((r) => r.running);
  return html`<section class="gui-bench__section lab-recs">
    <div class="gui-bench__row"><h4 class="ok-font-label gui-bench__h">${say("Recommendations")}</h4>
      <button class="ok-btn" disabled=${on || busy || !(d.report || {}).text} onClick=${() => act(id, "recommend")}>
        ${busy ? say("Reading the code and the runs…") : recs.some((r) => r.at) ? say("Review again") : say("Review")}</button></div>
    <p class="ok-font-status ok-tone-muted">${say("Three reviewers read the code and the latest runs with their model calls, and say what to change. Each is one AI tool run; nothing changes by itself.")}</p>
    ${recs.map((r) => html`<div key=${r.type} class="lab-rec">
      ${recs.length > 1 && html`<b class="ok-font-body">${say(r.word)}</b>`}
      ${r.at && html`<p class="ok-font-status ok-tone-muted">${say(`Reviewed ${r.at.replace("T", " ").slice(0, 16)}`)}</p>`}
      ${r.errors.filter(Boolean).map((e, n) => html`<p key=${n} class="ok-font-status ok-tone-error">${e}</p>`)}
      <ul class="gui-bench__findings">${r.findings.map((f, n) => html`<li key=${n} class="gui-bench__finding">
        <span><span class=${`gui-bench__sev is-${f.severity}`}>${f.severity}</span> <b>${f.title}</b> <span class="ok-tone-muted">· ${f.who}</span></span>
        ${f.detail && html`<p class="ok-font-status">${f.detail}</p>`}
        ${f.where && html`<p class="ok-font-status ok-tone-muted">${f.where}</p>`}</li>`)}</ul>
    </div>`)}
  </section>`;
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
      ${field("Runs a case", html`<select class="ok-input" value=${String(s.repeat || 3)} onChange=${(e) => set("repeat", +e.target.value)}>
        ${[[1, "Once"], [3, "3 times: medians"], [5, "5 times: medians"]].map(([v, l]) => html`<option key=${v} value=${v}>${say(l)}</option>`)}</select>`)}
    </div>
    <label class="lab-check"><input type="checkbox" checked=${!!s.judge} onChange=${(e) => set("judge", e.target.checked)} />
      <span class="ok-font-body">${say("A blind judge scores both results 0–10 (one more AI call a case)")}</span></label>
    <p class="ok-font-status ok-tone-muted">${say("Each case runs in a copy of the project with no remote: nothing is pushed and your town is not changed. The scheme's side stops at the spend limit; the bare AI tool's is one call.")}</p>
  </details>`;
}

// -- environments and their case sets (docs/design/improve-buildings.md §5.2) ----------------------------------------

/** Each environment as a frame with its case sets in it; the setup's (this project) first. */
function Envs({ id, d, on }) {
  const envs = d.envs || [];
  const sets = d.sets || [];
  return html`<section class="gui-bench__section lab-envs">
    <h4 class="ok-font-label gui-bench__h">${say("Environments")}</h4>
    <p class="ok-font-status ok-tone-muted">${say("Where the runs stand. A case set is alike cases in one of them; the mean over the set is what counts.")}</p>
    ${envs.map((e) => html`<div key=${e.id} class="lab-env">
      <div class="lab-env__head"><b class="ok-font-body">${say(e.name)}</b>
        <span class="ok-font-status ok-tone-muted">${say(e.about)}${e.files ? ` · ${e.files} ${say("files")}` : ""}</span></div>
      <ul class="lab-set-list">${sets.filter((x) => x.env === e.id).map((x) => html`<${SetRow} key=${x.id} id=${id} x=${x} on=${on} />`)}</ul>
      <${AddSet} id=${id} env=${e.id} busy=${d.busy_what === "set"} />
    </div>`)}
    <${AddEnv} id=${id} busy=${d.busy_what === "env"} />
  </section>`;
}

function SetRow({ id, x, on }) {
  const s = x.summary || {};
  const est = x.estimate || {};
  const mean = s.ran ? `${say("last run")}: ${say("time")} ${pct(s.time)} · ${say("tokens")} ${pct(s.tokens)} · ${say("quality")} ${pts(s.quality)} (${s.ran}/${x.cases.length})`
    : say("not run yet");
  const cost = est.cost !== undefined ? ` · ${say("about")} $${est.cost.toFixed(2)}${est.tokens ? `, ${est.tokens.toLocaleString()} ${say("tokens")}` : ""} ${say("on the building's side")}` : "";
  return html`<li class="lab-set">
    <div class="lab-case__head"><span class="ok-font-body">${x.about}</span>
      <span class="ok-font-status ok-tone-muted">${say(many(x.cases.length, "case"))}</span>
      <span class="gui-bench__acts">
        <button class="ok-btn primary" disabled=${on || !x.cases.length} onClick=${() => act(id, "set_run", { set: x.id })}>${say("Run")}</button>
        <button class="ok-btn" title=${say("Remove the case set and its cases")} onClick=${() => act(id, "set_remove", { set: x.id })}>×</button></span></div>
    <p class="ok-font-status ok-tone-muted">${mean}${cost}</p>
    ${x.cassette && x.cassette.answers > 0 && html`<p class="ok-font-status ok-tone-muted">${say(`MCP: ${x.cassette.answers} answers recorded, played back on each run`)}${x.cassette.missed ? ` · ${say(`${x.cassette.missed} calls not in it`)}` : ""}
      <button class="gui-link" disabled=${on} onClick=${() => act(id, "cassette_reset", { set: x.id })}>${say("Record again")}</button></p>`}
  </li>`;
}

function AddSet({ id, env, busy }) {
  const [open, setOpen] = useState(false);
  const [about, setAbout] = useState("");
  const [count, setCount] = useState(6);
  if (busy) return html`<p class="ok-font-status ok-tone-muted" role="status">${say("Writing a case set…")}</p>`;
  if (!open) return html`<button class="ok-btn lab-add-open" onClick=${() => setOpen(true)}>${say("Add a case set")}</button>`;
  return html`<div class="lab-add">
    ${field("What its cases do here", html`<textarea class="ok-input gui-textarea" rows="2" maxlength="2000" value=${about}
      placeholder=${say("e.g. Fix one failing test; each a different bug")} onInput=${(e) => setAbout(e.target.value)}></textarea>`)}
    ${field("How many cases (alike, written in one go)", html`<input class="ok-input lab-count" type="number" min="1" max="20" value=${count}
      onInput=${(e) => setCount(Number(e.target.value) || 1)} />`)}
    <div class="gui-bench__row">
      <button class="ok-btn primary" disabled=${about.trim().length < 5}
        onClick=${() => act(id, "set_add", { env, about, count: Math.max(1, Math.min(20, count)) }).then(() => { setAbout(""); setOpen(false); }, () => {})}>${say("Write the cases")}</button>
      <button class="ok-btn" onClick=${() => setOpen(false)}>${say("Cancel")}</button></div>
  </div>`;
}

function AddEnv({ id, busy }) {
  const [open, setOpen] = useState(false);
  const [about, setAbout] = useState("");
  if (busy) return html`<p class="ok-font-status ok-tone-muted" role="status">${say("Writing an environment…")}</p>`;
  if (!open) return html`<button class="ok-btn lab-add-open" onClick=${() => setOpen(true)}>${say("Add an environment")}</button>`;
  return html`<div class="lab-add">
    ${field("What it is, in plain words", html`<textarea class="ok-input gui-textarea" rows="3" maxlength="2000" value=${about}
      placeholder=${say("e.g. A small Python inventory service, standard library only, with its tests; two of them fail")}
      onInput=${(e) => setAbout(e.target.value)}></textarea>`)}
    <p class="ok-font-status ok-tone-muted">${say("Written once by the AI tool, with no network; every run starts from a copy of it.")}</p>
    <div class="gui-bench__row">
      <button class="ok-btn primary" disabled=${about.trim().length < 10}
        onClick=${() => act(id, "env_add", { about }).then(() => { setAbout(""); setOpen(false); }, () => {})}>${say("Write it")}</button>
      <button class="ok-btn" onClick=${() => setOpen(false)}>${say("Cancel")}</button></div>
  </div>`;
}

function Cases({ id, d, on }) {
  const cases = (d.cases || []).filter((c) => !c.set);     // a set's cases stand in its environment
  const results = d.results || {};
  return html`<section class="gui-bench__section lab-cases">
    <h4 class="ok-font-label gui-bench__h">${say(`Single cases (${cases.length})`)}</h4>
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
    <p class="ok-font-status ok-tone-muted">${say(tested ? "An agent reads the buildings' code, the roads and the last tests, and proposes changes to the code, the roads, the prompts or the settings." : "Test the cases first: the proposals lean on what the tests said.")}${d.proposals && d.proposals.at ? ` ${say("Written")} ${d.proposals.at.replace("T", " ").slice(0, 16)}.` : ""}</p>
    ${items.length > 0 && html`<ul class="lab-proposal-list">${items.map((p) => html`<li key=${p.id} class="lab-proposal">
      <label class="lab-check"><input type="checkbox" checked=${picks.has(p.id)} onChange=${() => flip(p.id)} />
        <span class="lab-area">${say(AREA[p.area] || p.area)}</span> <b class="ok-font-body">${p.title}</b></label>
      <p class="ok-font-status">${p.detail}</p>
      ${(p.where || p.effect) && html`<p class="ok-font-status ok-tone-muted">${p.where ? `${say("Where")}: ${p.where}` : ""}${p.where && p.effect ? " · " : ""}${p.effect ? `${say("Should")}: ${p.effect}` : ""}</p>`}
      ${p.area !== "roads" && html`<span><button class="ok-btn" disabled=${on || !!d.busy_what}
        title=${say("Tried on the Test bench's copy of the building only: the town's keeps what it has until Save changes")}
        onClick=${() => act(id, "try", { proposal: p.id })}>${d.busy_what === "try" ? say("Trying…") : say("Try it")}</button></span>`}
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

// -- the virtual building (docs/design/improve-buildings.md §5.3) ---------------------------------------------------

/** The changes tried on the Test bench's copy of the buildings: its runs stand them, the town's do not. Save changes
 *  makes the settings and prompts the buildings' own; code goes to Orkcraft as a pull request. */
function Virtual({ id, d, on }) {
  const [pr, setPr] = useState(false);
  const changes = d.virtual || [];
  if (!changes.length) return null;
  const data = changes.filter((c) => c.kind !== "code");
  const code = changes.find((c) => c.kind === "code");
  return html`<section class="gui-bench__section lab-virtual">
    <h4 class="ok-font-label gui-bench__h">${say(`The virtual building (${changes.length})`)}</h4>
    <p class="ok-font-status ok-tone-muted">${say("Its runs stand the buildings with these changes; the town's keep what they have.")}</p>
    <ul class="lab-proposal-list">${changes.map((c) => html`<li key=${c.id} class="lab-proposal">
      <div class="lab-case__head"><span class="lab-area">${say(c.kind === "code" ? "Code" : c.kind)}</span>
        <b class="ok-font-body">${c.kind === "code" ? say(`${(c.files || []).length} files`) : `${say(c.building)}: ${c.title}`}</b>
        <span class="gui-bench__acts"><button class="ok-btn" disabled=${on} onClick=${() => act(id, "take_back", { change: c.id })}>${say("Take back")}</button></span></div>
      ${c.why && html`<p class="ok-font-status ok-tone-muted">${c.why}</p>`}
      <details><summary class="ok-font-status ok-tone-muted">${say("What changes")}</summary>
        <pre class="lab-case__body">${typeof c.diff === "string" ? c.diff : (c.diff || []).map((x) => `${x[0]} ${x[1]}`).join("\n")}</pre></details>
    </li>`)}</ul>
    <div class="gui-bench__row">
      ${data.length > 0 && html`<button class="ok-btn primary" disabled=${on}
        onClick=${() => act(id, "save_changes").catch(() => {})}>${say("Save changes")}</button>`}
      <span class="ok-font-status ok-tone-muted">${say(data.length ? "Settings and prompts become the buildings' own, a checkpoint each (undo takes them back)." : "")}</span>
    </div>
    ${code && html`<div class="gui-bench__row">
      ${d.pr ? html`<a class="gui-link ok-font-status" href=${d.pr} target="_blank" rel="noopener">${say("Its pull request")}</a>`
        : html`<button class="ok-btn" disabled=${on || d.busy_what === "pr"} onClick=${() => setPr(true)}>${say(d.busy_what === "pr" ? "Sending…" : "Send to Orkcraft as a pull request…")}</button>`}
      <span class="ok-font-status ok-tone-muted">${say("Code changes reach you only through a pull request and the update that carries it.")}</span></div>`}
    ${pr && html`<${PullRequest} id=${id} onClose=${() => setPr(false)} />`}
  </section>`;
}

/** What would leave the machine, before it does: the pull request's title, body and diff; Send when it may go. */
function PullRequest({ id, onClose }) {
  const [x, setX] = useState(null);
  useEffect(() => { act(id, "pr_preview").then(setX, onClose); }, [id]);
  const send = () => act(id, "pr_send").then(onClose, () => {});
  return html`<${Dialog} title=${say("A pull request to Orkcraft")} wide=${true} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" disabled=${!x || !x.ready || !x.login} onClick=${send}>${say("Send")}</button>`}>
    ${!x ? html`<p class="ok-tone-muted">${say("Looking…")}</p>` : html`
      <p class="ok-font-status">${say("This is all that leaves this machine: the title, the description and the diff below. The cases' inputs and your project stay here.")}</p>
      ${!x.login && html`<p class="ok-font-status ok-tone-wait">${say("Connect GitHub first: the mascot's menu → GitHub.")}</p>`}
      ${!x.ready && html`<p class="ok-font-status ok-tone-wait">${say(x.why)}</p>`}
      <p class="ok-font-label">${x.title}</p>
      <pre class="lab-case__body">${x.body}</pre>
      <details><summary class="ok-font-status ok-tone-muted">${say("The diff")}</summary><pre class="lab-case__body">${x.diff}</pre></details>`}
  </${Dialog}>`;
}

// -- set up in the Warchief's line (js/warchief.js; docs/design/improve-buildings.md §5.1) -------------------------

/** Its setup asked again: from its window, when what it tests changes (its roads are laid only here). */
function setUp(id) {
  framing.value = null;
  settingUp.value = { id, type: "lab" };
}

/** What the Warchief asks of a Test bench just raised. */
export function setupAsk(b) {
  return `${b.title} is going up. What should it test?`;
}

const titleOf = (bid) => (town.value.buildings.find((x) => x.id === bid) || {}).title || bid;

/** One press on a building tests it; a frame on the map tests several as one chain, in the order their roads go. */
export function Setup({ id, done }) {
  const [list, setList] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { act(id, "candidates").then(setList, () => setList([])); }, [id]);
  const f = framing.value && framing.value.by === id ? framing.value : null;
  const go = (ids) => act(id, "setup", { ids }).then(() => { framing.value = null; done(); },
    (e) => setError(String((e && e.message) || e)));
  const frameOn = () => { setError(""); framing.value = { by: id, rect: null, ids: [] }; };
  const err = error && html`<p class="ok-font-status ok-tone-error" role="alert">✗ ${say(error)}</p>`;
  if (f && f.ids.length) {
    return html`${err}<p class="ok-font-status">${say(`Framed: ${f.ids.map(titleOf).join(", ")}`)}</p>
      <div class="gui-setup__ways"><button class="ok-btn primary" onClick=${() => go(f.ids)}>${say(f.ids.length > 1 ? "Test them as one chain" : "Test it")}</button>
        <button class="ok-btn" onClick=${frameOn}>${say("Frame again")}</button></div>`;
  }
  if (f) return html`${err}<p class="ok-font-status ok-tone-muted" role="status">${say("Drag a frame round the buildings on the map. Esc lets it go.")}</p>`;
  if (!list) return html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>`;
  return html`${err}${list.length ? html`<div class="gui-setup__ways">
      ${list.map((x) => html`<button key=${x.id} class="ok-btn" onClick=${() => go([x.id])}>${say(x.title)}</button>`)}</div>`
    : html`<p class="ok-font-status ok-tone-muted">${say("No building to test yet: build one first.")}</p>`}
    ${list.length > 1 && html`<span><button class="ok-btn" onClick=${frameOn}>${say("Frame several on the map")}</button></span>`}`;
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
