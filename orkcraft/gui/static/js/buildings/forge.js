// ⚒️ The Forge: the branches with their PRs, tests and changes (design-system/components.md: Forge).
// Closed: how many branches, the PRs open, a merge that waits for a yes, the last merge and when. Open,
// made for the half panel: the counters on one line with Look again, a merge a road brought as a strip
// with Merge right there, every branch on its own row (its PR, its last commit, tests, +/−); a branch
// opens over the list (← back) with Merge, Run tests, Diff and its PR, commits, files, test output and
// merges; the settings fold to one line. Every merge asks first. The work is the worker's
// (core/workers/forge.py); the diff opens in Lake.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, details, toast, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { showBuilding } from "../windows.js";

const sheet = new URL("./forge.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const opened = signal({});            // building id → the branch open over the list (the worker keeps `picked`)
const confirming = signal({});        // building id → the branch whose merge waits for a yes on this page

function pick(id, name) {
  opened.value = { ...opened.value, [id]: name };
  act(id, "pick", { branch: name }).catch(() => {});
}

function merge(id, name) {
  confirming.value = { ...confirming.value, [id]: name };
}

function openPr(id, name) {
  act(id, "pr", { branch: name }).then((url) => { if (url) window.open(url, "_blank", "noopener"); }, () => {});
}

function diff(id, name) {
  act(id, "diff", { branch: name }).then(
    (d) => d.text ? openInLake({ text: d.text, title: d.title, from: id }) : toast(`${name}: no changes against the base`),
    () => {});
}

/** The type's quick actions in its Info (catalog: Merge, Open PR) act on the chosen branch. */
export function quick(id, action) {
  const d = (details.value[id] || {}).data;
  if (action !== "forge.merge" && action !== "git.open_pr") return false;
  const name = d && d.picked;
  if (!name) { showBuilding(id); toast(say("Pick a branch first")); return true; }     // from its closed card: the list to pick from
  if (action === "forge.merge") merge(id, name);
  else openPr(id, name);
  return true;
}

function MergeDialog({ id, data }) {
  const name = confirming.value[id];
  if (!name) return null;
  const close = () => { confirming.value = { ...confirming.value, [id]: null }; };
  const yes = () => { close(); act(id, "merge", { branch: name }).catch(() => {}); };
  const tests = data.settings.test_cmd;
  return html`<${Dialog} title=${`Squash-merge ${name} into ${data.base}?`} warn onCancel=${close}
      text=${tests ? `The tests run first: ${tests}` : "No test command is set: it merges without tests."}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" onClick=${yes}>Merge</button>`} />`;
}

/** A branch a road brought waits for the person's yes (the `confirm` setting): the strip is the question. */
function Asking({ id, data }) {
  if (!data.asking) return null;
  return html`<div class="forge-ask">
    <span class="forge-ask__who">? ${say("Merge")}</span>
    <span class="forge-ask__what" title=${data.asking}>A road brought <b>${data.asking}</b>: merge it into ${data.base}?</span>
    <button class="ok-btn" onClick=${() => act(id, "decline").catch(() => {})}>Not now</button>
    <button class="ok-btn primary" onClick=${() => act(id, "merge", { branch: data.asking }).catch(() => {})}>Merge</button>
  </div>`;
}

function Pr({ pr }) {
  if (!pr) return null;
  return html`<span class="ok-pr" data-state=${pr.state}>#${pr.number} ${pr.state}</span>`;
}

function Tests({ state }) {
  if (!state) return null;
  const mark = { running: "tests…", passed: "tests ✓", failed: "tests ✗" }[state];
  return html`<span class=${cls("ok-ab", { "ok-tone-ok": state === "passed", "ok-tone-error": state === "failed",
    "ok-tone-wait": state === "running" })}>${mark}</span>`;
}

function Branch({ id, b, picked }) {
  return html`<li class=${cls("ok-branch forge-row", { "is-selected": b.name === picked })} title=${b.subject}
      tabIndex="0" onClick=${() => pick(id, b.name)} onKeyDown=${(e) => e.key === "Enter" && pick(id, b.name)}>
    <span class="ok-branch__cur" aria-label=${b.current ? say("checked out") : ""}>${b.current ? "●" : ""}</span>
    <span class="ok-branch__name">${b.name}</span>
    <${Pr} pr=${b.pr} />
    <span class="forge-row__sub">${b.pr ? b.pr.title : b.subject}${b.when ? html`<span class="forge-row__when"> · ${b.when}</span>` : ""}</span>
    <span class="ok-branch__stat">
      <${Tests} state=${b.tests} />
      ${b.files > 0 && html`<span class="ok-add">+${b.added}</span><span class="ok-del">−${b.removed}</span>`}
      ${(b.ahead > 0 || b.behind > 0) && html`<span class="ok-ab">↑${b.ahead} ↓${b.behind}</span>`}
    </span>
  </li>`;
}

function Head({ id, data }) {
  const rows = data.branches.filter((b) => b.name !== data.base);
  const prs = rows.filter((b) => b.pr && (b.pr.state === "open" || b.pr.state === "draft")).length;
  const failing = rows.filter((b) => b.tests === "failed").length;
  const last = data.last;
  return html`<div>
    <${Asking} id=${id} data=${data} />
    <div class="forge-head">
      ${data.looking ? html`<span>${say("looking…")}</span>`
        : data.error ? html`<span class="ok-tone-error forge-head__err" title=${data.error}>✗ ${data.error}</span>`
        : html`<span><b>${rows.length}</b> ${say("branches")}</span>
          <span><b>${prs}</b> ${say("PRs open")}</span>
          ${failing > 0 && html`<span class="ok-tone-error">✗ <b>${failing}</b> ${say("tests failing")}</span>`}
          <span>${say("into")} <b>${data.base}</b></span>`}
      ${data.merging && html`<span class="ok-tone-wait">${say("merging")} ${data.merging}…</span>`}
      ${data.testing.length > 0 && html`<span class="ok-tone-wait">${say("testing")} ${data.testing.join(", ")}…</span>`}
      ${last && !data.merging && html`<span class="forge-head__last" title=${last.ok ? "" : last.why}>
        <span class=${last.ok ? "ok-tone-ok" : "ok-tone-error"}>${last.ok ? "✓" : "✗"}</span> ${last.branch}${last.ok ? "" : `: ${last.why}`}${last.at ? ` · ${last.at}` : ""}</span>`}
      <span class="gui-head__spacer"></span>
      <button class="ok-btn" onClick=${() => act(id, "look").catch(() => {})}>Look again</button>
    </div>
    ${!data.prs_known && !data.looking && !data.error && html`<p class="forge-note">${say("PRs: install and log in to gh to see them")}</p>`}
    <${MergeDialog} id=${id} data=${data} />
  </div>`;
}

function Branches({ id, data }) {
  if (data.looking) return html`<p class="ok-tone-muted">${say("Looking at the branches…")}</p>`;
  if (data.error) return html`<p class="ok-tone-muted">${say("No branches to show until git can read this folder (the line above says why).")}</p>`;
  const open = opened.value[id];
  if (open && data.chosen && data.chosen.name === open) return html`<${Detail} id=${id} data=${data} />`;
  const rows = data.branches;
  if (rows.length < 2) return html`<p class="ok-tone-muted">${say(`No branches but ${data.base} — an ork's task brings one.`)}</p>`;
  return html`<div><ul class="ok-branches forge-list">${rows.map((b) => html`<${Branch} key=${b.name} id=${id} b=${b} picked=${data.picked} />`)}</ul></div>`;
}

function Actions({ id, data, name }) {
  const b = data.branches.find((x) => x.name === name);
  if (!b) return null;
  const base = name === data.base;
  return html`<div class="ok-detail__actions">
    ${!base && html`<button class="ok-btn primary" disabled=${!!data.merging} onClick=${() => merge(id, name)}>Merge</button>`}
    <button class="ok-btn" disabled=${b.tests === "running"} onClick=${() => act(id, "test", { branch: name }).catch(() => {})}>Run tests</button>
    ${!base && html`<button class="ok-btn" onClick=${() => diff(id, name)}>Diff in Inspector</button>`}
    ${b.pr && html`<button class="ok-btn" onClick=${() => openPr(id, name)}>${say("Open PR")} ↗</button>`}
  </div>`;
}

function Comments({ c, pr }) {
  if (!pr) return null;
  if (!c.comments_known) return html`<p class="ok-detail__meta">Reading the comments…</p>`;
  if (c.comments === null) return html`<p class="ok-detail__meta">The comments need gh, installed and logged in.</p>`;
  if (!c.comments.length) return html`<p class="ok-detail__meta">No comments yet.</p>`;
  return html`<ul class="gui-rows">${c.comments.map((m, i) => html`<li key=${i}>
    <div class="ok-detail__meta"><b>${m.author}</b> · ${m.at}${m.state && ` · ${m.state.replace("_", " ")}`}</div>
    <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: m.html }}></div></li>`)}</ul>`;
}

function Merges({ merges }) {
  if (!merges.length) return null;
  return html`<p class="ok-detail__section">Merges</p>
    <ul class="gui-rows">${merges.map((m, i) => html`<li key=${i} class="ok-detail__result">
      ${m.ok ? html`<span class="ok">✓ merged</span> ${m.commit} · ${m.at}`
        : html`<span class="bad">✗ ${m.conflicts.length ? "conflicts" : m.error}</span> · ${m.at}`}
      ${m.conflicts.length > 0 && html`<ul class="ok-files">${m.conflicts.map((f) => html`<li key=${f} class="ok-file">
        <span>${f}</span></li>`)}</ul>`}
    </li>`)}</ul>
    ${!merges[0].ok && merges.some((m) => m.ok) && html`<p class="ok-detail__meta">Settled later: a merge after it went through.</p>`}`;
}

function Files({ files }) {
  if (!files.length) return null;
  const most = Math.max(1, ...files.map((f) => f.added + f.removed));
  return html`<p class="ok-detail__section">Files · ${files.length}</p>
    <ul class="ok-files">${files.map((f) => html`<li key=${f.path} class="ok-file">
      <span title=${f.path}>${f.path}</span>
      <span class="ok-file__n"><span class="ok-add">+${f.added}</span> <span class="ok-del">−${f.removed}</span></span>
      <span class="ok-file__bar"><i class="a" style=${`width:${(f.added / most) * 100}%`}></i>
        <i class="d" style=${`width:${(f.removed / most) * 100}%`}></i></span></li>`)}</ul>`;
}

function Detail({ id, data }) {
  const c = data.chosen;
  if (!c) return null;
  const b = data.branches.find((x) => x.name === c.name) || {};
  const back = () => { opened.value = { ...opened.value, [id]: null }; };
  return html`<div class="forge-open" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn forge-open__back" onClick=${back}>← ${say("All branches")} · ${data.branches.length}</button>
    <div class="ok-detail">
    <div class="ok-detail__head forge-open__name"><span title=${c.name}>⎇ ${c.name}</span> <${Pr} pr=${b.pr} /></div>
    ${b.pr && html`<p class="ok-detail__pr">${b.pr.title}</p>`}
    ${c.name !== data.base && html`<p class="ok-detail__meta">${`${b.ahead} ahead, ${b.behind} behind ${data.base} · ${b.files} files · +${b.added} −${b.removed}`}</p>`}
    <${Actions} id=${id} data=${data} name=${c.name} />
    ${data.merging === c.name && html`<div class="ok-meter is-busy"><span>merging</span>
      <span class="ok-meter__track"><span class="ok-meter__fill"></span></span><span class="ok-meter__val">…</span></div>`}
    <${Merges} merges=${c.merges} />
    ${c.test && html`<p class="ok-detail__section">Tests · ${c.test.ok ? "passed" : "failed"} · ${c.test.at}</p>
      <pre class="gui-pre">${c.test.output || "(no output)"}</pre>`}
    ${b.pr && html`<p class="ok-detail__section">Pull request · comments</p><${Comments} c=${c} pr=${b.pr} />`}
    <p class="ok-detail__section">Commits</p>
    ${c.commits.length ? html`<ul class="ok-commits">${c.commits.map((x) => html`<li key=${x.hash} class="ok-commit">
        <code>${x.hash}</code><span>${x.subject}</span><span class="when">${x.when}</span></li>`)}</ul>`
      : html`<p class="ok-detail__meta">No commits of its own.</p>`}
    <${Files} files=${c.files} />
  </div></div>`;
}

function Settings({ id, data }) {
  const s = data.settings;
  const [base, setBase] = useState(s.base);
  const [tests, setTests] = useState(s.test_cmd);
  useEffect(() => { setBase(s.base); setTests(s.test_cmd); }, [s.base, s.test_cmd]);
  const changed = base !== s.base || tests !== s.test_cmd;
  return html`<details class="forge-fold">
    <summary><span>${say("Settings")}</span>
      <span class="forge-fold__sum ok-font-status">${say("Base")} ${data.base} · ${say("Tests")}: ${s.test_cmd || say("none")}${s.confirm ? ` · ${say("asks before a road's merge")}` : ""}</span></summary>
    <div class="gui-form">
      <div class="gui-form__row">
        <label class="gui-field"><span class="ok-font-label">Base branch</span>
          <input class="ok-input" placeholder=${data.base} value=${base} onInput=${(e) => setBase(e.target.value)} /></label>
        <label class="gui-field"><span class="ok-font-label">Test command</span>
          <input class="ok-input" placeholder="pytest -q" value=${tests} onInput=${(e) => setTests(e.target.value)} /></label>
      </div>
      <label class="ok-check" onClick=${() => act(id, "settings", { confirm: !s.confirm }).catch(() => {})}>
        <i>${s.confirm ? "✓" : ""}</i> Ask before merging a branch a road brings</label>
      <div><button class="ok-btn" disabled=${!changed}
        onClick=${() => act(id, "settings", { base, test_cmd: tests }).catch(() => {})}>Keep the settings</button></div>
    </div>
  </details>`;
}

const keep = (e) => e.stopPropagation();          // a press on the card's control is not a press on the hut

/** Closed: the headline is how many branches wait besides the base, with the PRs open; a merge a road
 *  brought asks here with Merge; the foot is the last merge and when (`merging …` meanwhile). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.looking) return html`<div class="gui-hut__body-in"><div class="gui-hut__big">…<small>${say("looking at the branches")}</small></div></div>`;
  if (c.error) return html`<div class="gui-hut__body-in"><div class="gui-hut__big ok-tone-error">✗<small>${say("cannot read the repository")}</small></div>
    <div class="gui-hut__text" title=${c.error}>${c.error}</div></div>`;
  const last = c.last;
  return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big">${c.branches}<small>${say(c.branches === 1 ? "branch" : "branches")} · ${c.prs} ${say(c.prs === 1 ? "PR open" : "PRs open")}</small></div>
    ${c.asking && html`<div class="gui-hut__text ok-tone-fire forge-card__ask"><span>? ${say("merge")} <b>${c.asking}</b></span>
      <button class="ok-act gui-hut__act" onPointerDown=${keep}
        onClick=${(e) => { keep(e); act(b.id, "merge", { branch: c.asking }).catch(() => {}); }}><span class="ok-act__label">Merge</span></button></div>`}
    ${c.merging ? html`<div class="gui-hut__foot"><span class="ok-tone-wait">${say("merging")} ${c.merging}…</span></div>`
      : last ? html`<div class="gui-hut__foot"><span><span class=${last.ok ? "ok-tone-ok" : "ok-tone-error"}>${last.ok ? "✓ merged" : `✗ ${last.why}`}</span> ${last.branch}</span>
          ${last.at && html`<span class="gui-hut__when">${last.at}</span>`}</div>`
      : html`<div class="gui-hut__foot"><span>${say("Nothing merged yet")}</span></div>`}
  </div>`;
}

/** Folded (docs/design/folded-cards.md): a repository it cannot read, a merge under way, else the PRs open. */
export function mark(b) {
  const c = b.card;
  if (!c || c.looking) return null;
  if (c.error) return { text: "cannot read", tone: "error" };
  if (c.merging) return { text: "merging", tone: "wait" };
  return c.prs ? { text: `${c.prs} ${c.prs === 1 ? "PR" : "PRs"}` } : null;
}

/** The window by its UI document (design/buildings/forge.json). `detail` shows nothing of its own: a branch
 *  opens over the list (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    branches: () => html`<${Branches} id=${id} data=${data} />`,
    detail: () => null,                   // a branch opens over the list, in `branches`
    settings: () => html`<${Settings} id=${id} data=${data} />`,
  };
}
