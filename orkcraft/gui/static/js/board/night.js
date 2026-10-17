// The Night report (docs/specs/32-night-gate.md §3): what the night's deep checks found on `dev`'s head. Green → *N changes
// ready for main*, the steps' one-line summaries, the cost against its budget, Pass to main (a confirm naming the count)
// and Details (the commits with their ideas, the steps' failures); red → it stands in Needs you with what failed and
// what the check could not fix. The board's Today shows it; the Review gate's window shows the same card (NightPanel).
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { town, toast } from "../link.js";
import { board, run, refresh } from "./store.js";

// Its rules live in board.css, which the board loads; the Review gate's window loads it here.
const sheet = new URL("./board.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const usd = (n) => `$${Number(n || 0).toFixed(2)}`;
const hhmm = (iso) => (iso ? String(iso).slice(11, 16) : "");
const changes = (n) => `${n} change${n === 1 ? "" : "s"}`;

/** Whether the card waits for the person in Needs you: finished, red, not passed. */
export const isRed = (n) => !!n && !n.running && !n.green && !n.passed_at;
/** Whether Today shows the card at all: one not yet passed (the Review gate shows a passed one too). */
export const shown = (n) => !!n && !n.passed_at;

function lead(n) {
  if (n.running) return `The night run is on · since ${hhmm(n.started)}`;
  if (n.passed_at) return `Passed to main at ${hhmm(n.passed_at)}`;
  if (n.green) return n.count ? `${changes(n.count)} ready for main` : "Nothing new for main";
  const red = (n.steps || []).filter((s) => !s.ok).map((s) => s.name);
  return n.error ? `Red: ${n.error}` : `Red: ${red.join(", ") || "the check found what it could not fix"}`;
}

function Details({ n }) {
  const failing = (n.steps || []).filter((s) => (s.failed || []).length);
  return html`<div class="board-night__details">
    <h4 class="board-night__h">What merged into dev since main</h4>
    ${(n.commits || []).length ? html`<ul class="board-night__commits">${n.commits.map((c) => html`<li key=${c.sha}>
        <code class="board-commit" title=${c.sha}>${c.sha.slice(0, 7)}</code> <span>${c.subject}</span>
        ${c.idea ? html` <span class="board-chip">${c.idea}</span>` : ""}</li>`)}</ul>`
      : html`<p class="ok-tone-muted">Nothing.</p>`}
    ${failing.map((s) => html`<div key=${s.name}><h4 class="board-night__h">${s.name}: failed</h4>
      <ul class="board-night__failed">${s.failed.map((f) => html`<li key=${f}><code>${f}</code></li>`)}</ul></div>`)}
    ${(n.fixed || []).length ? html`<h4 class="board-night__h">Fixed tonight</h4>
      <ul class="board-night__failed">${n.fixed.map((f) => html`<li key=${f}>${f}</li>`)}</ul>` : ""}
  </div>`;
}

export function NightCard({ n }) {
  const [sure, setSure] = useState(false);
  const [open, setOpen] = useState(false);
  const red = isRed(n);
  const canPass = n.green && !n.running && !n.passed_at && !n.stale && n.count > 0;
  const pass = async () => {
    setSure(false);
    const got = await run("gate.pass_night", { date: n.date });
    if (got && !got.error) toast(`${changes(n.count)} passed to main.`);
  };
  const again = async () => {
    const got = await run("gate.run_night", {});
    if (got && !got.error) toast("The night run started.");
  };
  return html`<section class=${cls("board-night", { "is-red": red, "is-green": n.green && !n.running })} aria-label="Night report"
      data-state=${n.running ? "running" : n.passed_at ? "passed" : n.green ? "green" : "red"}>
    <div class="board-night__head"><b class="board-night__title">Night report · ${n.date}</b>
      <span class="board-chip board-night__chip">${n.running ? "running" : n.green ? "green" : "red"}</span></div>
    <p class="board-night__lead">${lead(n)}</p>
    <ul class="board-night__steps">${(n.steps || []).map((s) => html`<li key=${s.name} data-ok=${String(!!s.ok)}>
      <span class="board-night__mark" aria-hidden="true">${s.ok ? "✓" : "✗"}</span><b>${s.name}</b>
      <span class="ok-tone-muted">${s.summary}</span></li>`)}</ul>
    ${red && (n.not_fixed || []).length ? html`<div class="board-night__notfixed"><b>The check could not fix</b>
      <ul>${n.not_fixed.map((f) => html`<li key=${f}>${f}</li>`)}</ul></div>` : ""}
    <p class="board-night__cost ok-tone-muted">Cost ${usd(n.cost)} of its ${usd(n.budget)} budget</p>
    ${n.stale && !n.passed_at && !n.running ? html`<p class="board-night__stale">dev moved since the night; run again</p>` : ""}
    ${sure ? html`<div class="board-row board-night__sure"><span>Pass ${changes(n.count)} to main?</span>
        <button class="ok-btn primary" onClick=${pass}>Pass ${changes(n.count)}</button>
        <button class="ok-btn" onClick=${() => setSure(false)}>Not now</button></div>`
      : html`<div class="board-row">
        ${canPass ? html`<button class="ok-btn primary" onClick=${() => setSure(true)}>Pass to main</button>` : ""}
        <button class="ok-btn" aria-expanded=${String(open)} onClick=${() => setOpen(!open)}>Details</button>
        ${!n.running && (red || n.stale) ? html`<button class="ok-btn" onClick=${again}>Run now</button>` : ""}</div>`}
    ${open ? html`<${Details} n=${n} />` : ""}
  </section>`;
}

/** The Review gate's window: the same card, read from the board's data (its own refresh outside the board). */
export function NightPanel() {
  const rev = town.value.ideas_rev;
  useEffect(() => { refresh(); }, [rev]);
  const n = board.value?.today?.night;
  if (!n) return "";
  return html`<div class="board-night-panel"><${NightCard} n=${n} /></div>`;
}
