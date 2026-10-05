// 🪨 Tally Crag: a dashboard of charts (core/workers/crag.py carves them). Each chart says where it
// shows: all states (the hut too), command only (the Command Card and the dashboard), full only. The
// keeper writes the charts and their thresholds from what the person asks in plain words.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";

const sheet = new URL("./crag.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const SHOW = { all: "all states", command: "command only", full: "full only" };
const NEXT_SHOW = { all: "command", command: "full", full: "all" };
const LEVEL = ["", "is-warn", "is-crit"];

function fmt(v) {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1000) return `${(v / 1000).toFixed(1)}k`;
  if (Number.isInteger(v)) return String(v);
  return a < 10 ? v.toFixed(2) : v.toFixed(1);
}

function levelOf(v, warn, crit) {
  if (crit !== null && crit !== undefined && v >= crit) return 2;
  return warn !== null && warn !== undefined && v >= warn ? 1 : 0;
}

/** Vertical bars in an SVG that fills its box: one bar per value, warn and crit lines dashed. */
function Bars({ values, scale, warn, crit, label }) {
  const n = Math.max(values.length, 1);
  const top = scale || Math.max(...values, 0) || 1;
  const y = (v) => 100 - Math.min(Math.max(v / top, 0), 1) * 100;
  const gap = n > 24 ? 0.1 : 0.2;
  const line = (v, c) => v !== null && v !== undefined && v <= top
    ? html`<line class=${`crag-line ${c}`} x1="0" x2=${n} y1=${y(v)} y2=${y(v)} />` : null;
  return html`<svg viewBox=${`0 0 ${n} 100`} preserveAspectRatio="none" role="img" aria-label=${label}>
    ${values.map((v, i) => html`<rect key=${i} class=${cls("crag-bar", { "is-warn": levelOf(v, warn, crit) === 1,
        "is-crit": levelOf(v, warn, crit) === 2 })}
      x=${i + gap / 2} width=${1 - gap} y=${y(v)} height=${100 - y(v)}><title>${fmt(v)}</title></rect>`)}
    ${line(warn, "is-warn")}${line(crit, "is-crit")}
  </svg>`;
}

/** Horizontal bars: the design system's meters, one per part. */
function Meters({ parts, scale, warn, crit }) {
  const top = scale || Math.max(...parts.map((p) => p[1]), 0) || 1;
  if (!parts.length) return html`<p class="ok-tone-muted">—</p>`;
  return html`<div class="crag-meters">${parts.map(([label, v]) => html`<div key=${label}
      class=${cls("ok-meter", { "is-warn": levelOf(v, warn, crit) === 1, "is-over": levelOf(v, warn, crit) === 2 })}>
    <span class="crag-thumb__title" title=${label}>${label}</span>
    <span class="ok-meter__track"><span class="ok-meter__fill" style=${`width:${Math.min(v / top, 1) * 100}%`}></span></span>
    <span class="ok-meter__val">${fmt(v)}</span></div>`)}</div>`;
}

function Chart({ c }) {
  if (c.orientation === "horizontal" || !c.buckets.length) {
    return html`<div class="crag-chart"><${Meters} parts=${c.parts} scale=${c.scale} warn=${c.warn} crit=${c.crit} />
      ${c.note && html`<span class="ok-font-status ok-tone-muted">${c.note}</span>`}</div>`;
  }
  const values = c.buckets.map((b) => b[1]);
  const step = Math.max(1, Math.floor(c.buckets.length / 4));
  return html`<div class="crag-chart">
    <div class="crag-chart__plot"><${Bars} values=${values} scale=${c.scale} warn=${c.warn} crit=${c.crit} label=${c.title} /></div>
    <div class="crag-chart__labels ok-font-status">${c.buckets.filter((_, i) => i % step === 0).map((b, i) => html`<span key=${i}>${b[0]}</span>`)}</div>
    ${c.note && html`<span class="ok-font-status ok-tone-muted">${c.note}</span>`}
  </div>`;
}

function Head({ c }) {
  return html`<div class="crag-head">
    <b class="crag-head__name" title=${c.line}>${c.title}</b>
    <span class="ok-font-status ok-tone-muted">${c.window}</span>
    <span class=${cls("crag-head__now ok-font-number", { "ok-tone-wait": c.level === 1, "ok-tone-error": c.level === 2 })}>${c.now_text}</span>
  </div>`;
}

/** Closed: thumbnails of the charts set to all states, without numbers (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.charts.length) return html`<span class="ok-tone-muted">${say("no chart shows here")}</span>`;
  return html`<div class="crag-thumbs">${c.charts.map((t, i) => html`<div key=${i} class="crag-thumb">
    <span class="crag-thumb__title ok-font-status">${t.title}</span>
    <${Bars} values=${t.values.length ? t.values : [0]} scale=${t.scale} warn=${t.warn} crit=${t.crit} label=${t.title} />
  </div>`)}</div>`;
}

/** Command: the chart in front, of those set to all states or command only; Flip and Next turn it. */
export function preview(id, data) {
  const shown = data.charts.filter((c) => c.show !== "full");
  if (!shown.length) return html`<p class="ok-tone-muted">${say("Every chart here shows in the full window only.")}</p>`;
  const front = shown.find((c) => c.index === data.front) || shown[0];
  return html`<div class="crag-front">
    <${Head} c=${front} />
    <${Chart} c=${front} />
    ${shown.length > 1 && html`<div class="crag-dots" aria-label=${say("charts")}>${shown.map((c) => html`<span key=${c.index}
      class=${cls("", { "is-front": c.index === front.index })} title=${c.title}>●</span>`)}</div>`}
  </div>`;
}

function Ask({ id }) {
  const [text, setText] = useState("");
  const send = () => { const t = text.trim(); if (t) askKeeper(id, t).then((r) => r !== null && setText("")); };
  return html`<div class="crag-ask">
    <input class="ok-input" value=${text} placeholder=${say("A chart or a threshold, in plain words: “spend this week, warn at $5”")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && send()} />
    <button class="ok-act" disabled=${!text.trim()} onClick=${send}><span class="ok-act__label">Ask the keeper</span></button>
  </div>`;
}

function Toolbar({ id, data }) {
  const pick = (w) => act(id, "window", { window: w }).catch(() => {});
  const choice = (w, label) => (data.window === w
    ? html`<b key=${w} class="crag-window is-chosen">${label}</b>`
    : html`<button key=${w} class="ok-act" onClick=${() => pick(w)}><span class="ok-act__label">${label}</span></button>`);
  return html`<div class="gui-head">
    <span class="ok-tone-muted">Window</span>
    ${choice("", say("as set"))}
    ${data.windows.map((w) => choice(w, w))}
    <span class="gui-head__spacer"></span>
    <${Ask} id=${id} />
    ${data.errors.map((e, i) => html`<p key=${i} class="ok-tone-error ok-font-status">⚠ ${e}</p>`)}
  </div>`;
}

function Tile({ id, c }) {
  return html`<section class=${cls("crag-tile", { [LEVEL[c.level]]: c.level > 0 })}>
    <${Head} c=${c} />
    <${Chart} c=${c} />
    <div class="crag-tile__foot ok-font-status">
      <span class="ok-badge crag-show" title=${say("Where it shows — a click moves it on")}
        onClick=${() => act(id, "show", { chart: c.index, show: NEXT_SHOW[c.show] }).catch(() => {})}>${say(SHOW[c.show])}</span>
      ${c.warn !== null && html`<span class="ok-tone-wait">warn ${fmt(c.warn)}</span>`}
      ${c.crit !== null && html`<span class="ok-tone-error">crit ${fmt(c.crit)}</span>`}
      <span class="gui-head__spacer"></span>
      <button class="ok-act" onClick=${() => act(id, "flip", { chart: c.index }).catch(() => {})}><span class="ok-act__label">Flip</span></button>
    </div>
  </section>`;
}

function Crossings({ data }) {
  if (!data.crossings.length) return html`<p class="ok-tone-muted">${say("No value has crossed a line yet.")}</p>`;
  return html`<ul class="gui-rows">${data.crossings.map((x, i) => html`<li key=${i}>
    <span class="ok-tone-muted">${String(x.at || "").slice(5, 16).replace("T", " ")}</span>${" "}
    <b>${x.chart}</b> ${fmt(x.value)} ≥ ${fmt(x.line)}
    <span class=${x.level === "critical" ? "ok-tone-error" : "ok-tone-wait"}> ${x.level}</span></li>`)}</ul>`;
}

/** Full: the dashboard — every chart, the window, the history of crossings; new charts through the keeper. */
export function panes(id, data) {
  return {
    head: () => html`<${Toolbar} id=${id} data=${data} />`,
    charts: () => html`<div class="crag-grid">${data.charts.map((c) => html`<${Tile} key=${c.index} id=${id} c=${c} />`)}</div>`,
    crossings: () => html`<${Crossings} data=${data} />`,
  };
}
