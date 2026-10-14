// 🥩 The ork slots and the console, folded (docs/design/ork-console.md §7–§9): the town's one list of orks at work
// or waiting on you, from the host's `slots` (core/slots.py), in the one status of realm/status.py.
//
//   SlotsHud     in the HUD: 🥩 working/limit, 🔥 · ❓ when something waits for you, and Stop all beside them as one
//                block "what runs". A press opens the list, waiting first, then the longest running; Stop all is
//                its first row too.
//   OrkConsole   at the town's foot, beside the Warchief's line: the ork a row picked, folded — its status, its
//                question with its answers (or Reply), ⏹ Stop, its spend and AI tool. Open shows its building.
//
// The list leads to the console, it does not repeat it. ⏹ stops one ork softly; Stop all stops everything at once.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, act, say } from "./link.js";
import { openBuilding } from "./windows.js";

export const consoleOrk = signal(null);        // the key of the row whose console is shown (folded)

function since(s) {
  if (s === null || s === undefined) return "";
  if (s < 60) return "0m";
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.floor(s / 3600)}h${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`;
}

function money(v) {
  return v ? `$${Number(v).toFixed(2)}` : "";
}

function stop(row) {
  if (row.stop) command(row.stop.command, row.stop.args).catch(() => {});
}

function haltAll() {
  command("halt").catch(() => {});
}

/** What a row says after its name: the question it asks, else what it does. */
function doing(r) {
  if (r.answer) return html`${say("asks")}: “${r.answer.question}”`;
  return [r.doing, r.cart ? `on «${r.cart}»` : ""].filter(Boolean).join(" · ");
}

function Row({ r, onPick }) {
  return html`<li class=${cls("gui-slots__row", { "is-asks": !!r.answer })}>
    <button class="gui-slots__pick" title=${r.line} onClick=${() => onPick(r)}>
      <span class="gui-slots__mark" title=${r.word} aria-label=${r.word}>${r.mark}</span>
      <b>${r.name}</b>${r.building ? ` · ${r.building}` : ""}
      <span class="gui-slots__doing ok-tone-muted">${doing(r)}</span>
      <span class="gui-slots__num">${since(r.since_s)}</span>
      <span class="gui-slots__num">${money(r.spend)}</span></button>
    ${r.stop ? html`<button class="ok-btn gui-slots__stop" title=${say(`Stop ${r.name}: its run ends where it is`)}
      aria-label=${say(`Stop ${r.name}`)} onClick=${() => stop(r)}>⏹</button>` : html`<span class="gui-slots__stop"></span>`}
  </li>`;
}

/** 🥩 in the HUD with 🔥 · ❓, Stop all beside it; a press opens the list. */
export function SlotsHud({ word, online }) {
  const s = town.value.slots || { working: 0, limit: 0, asks: 0, fire: 0, rows: [] };
  const [open, setOpen] = useState(false);
  const [by, setBy] = useState("attention");
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const key = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", away, true); window.removeEventListener("keydown", key); };
  }, [open]);
  const over = s.limit && s.working > s.limit;
  const rows = by === "work" ? [...s.rows].sort((a, b) => (b.since_s || 0) - (a.since_s || 0)) : s.rows;
  const pick = (r) => { setOpen(false); consoleOrk.value = r.key; if (r.building_id) openBuilding(r.building_id); };
  const waits = s.fire || s.asks;
  return html`<span ref=${ref} class="gui-slots">
    <button class=${cls("ok-res gui-slots__open", { "is-over": over })} aria-expanded=${open}
        title=${say("Orks at work and waiting for you")} onClick=${() => setOpen(!open)}>
      <img src="/ds/sprites/icons/res-meat.png" srcset="/ds/sprites/icons/res-meat@2x.png 2x" alt="" />
      <span class="ok-word">${word}</span>${s.working}/${s.limit}
      ${waits ? html`<span class="gui-slots__waits">${s.fire ? ` 🔥 ${s.fire}` : ""}${s.fire && s.asks ? " ·" : ""}${s.asks ? ` ❓ ${s.asks}` : ""}</span>` : ""}
    </button>
    ${online
      ? html`<button class="gui-hud__stop" title=${say("Stop every ork, script and browser at once")} onClick=${haltAll}>Stop all</button>`
      : html`<span class="ok-hud__halt">Disconnected — reconnecting</span>`}
    ${open && html`<div class="gui-slots__list" role="dialog" aria-label=${say("Orks at work")}>
      <div class="gui-slots__head">
        <span class="ok-font-status">${s.working}/${s.limit} ${say("at work")}${s.asks ? ` · ${s.asks} ${say("wait for you")}` : ""}</span>
        <span class="ok-hud__spacer"></span>
        <button class=${cls("ok-btn", { primary: by === "attention" })} onClick=${() => setBy("attention")}>${say("Waiting first")}</button>
        <button class=${cls("ok-btn", { primary: by === "work" })} onClick=${() => setBy("work")}>${say("Longest running")}</button>
      </div>
      <ul class="gui-rows gui-slots__rows">
        <li class="gui-slots__row"><button class="gui-hud__stop" onClick=${haltAll}>Stop all</button>
          <span class="ok-tone-muted"> ${say("stops every ork, script and browser at once")}</span></li>
        ${rows.map((r) => html`<${Row} key=${r.key} r=${r} onPick=${pick} />`)}
        ${!rows.length && html`<li class="ok-tone-muted">${say("No ork is at work.")}</li>`}
      </ul>
    </div>`}
  </span>`;
}

/** The answer in the folded console: its answers as buttons, else a field (Reply). */
function Reply({ r }) {
  const [text, setText] = useState("");
  const a = r.answer;
  const done = () => setText("");
  if (a.kind === "alert") {
    return html`<div class="ok-row">${a.options.map(([key, label]) => html`<button key=${key} class="ok-btn"
      onClick=${() => command("orders.answer", { id: a.id, key }).then(done, () => {})}>${label}</button>`)}</div>`;
  }
  const send = (said) => act(a.building, "answer", { task: a.task, text: said }).then(done, () => {});
  const qs = a.questions || [];
  return html`<div>
    ${qs.length === 1 && qs[0].options.length > 0 && html`<div class="ok-row">${qs[0].options.map((o) =>
      html`<button key=${o} class="ok-btn" onClick=${() => send(o)}>${o}</button>`)}</div>`}
    <div class="ok-row"><input class="ok-input" value=${text} aria-label=${say("Your answer")} placeholder=${say("Reply…")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === "Enter" && text.trim()) send(text); }} />
      <button class="ok-btn primary" disabled=${!text.trim()} onClick=${() => send(text)}>${say("Reply")}</button></div>
  </div>`;
}

/** The console of the ork a row picked, folded (§7): its state and line, its question, ⏹ Stop, its spend and tool. */
export function OrkConsole() {
  const key = consoleOrk.value;
  const s = town.value.slots;
  const r = key && s ? s.rows.find((x) => x.key === key) : null;
  if (!key) return null;
  if (!r) {
    return html`<div class="gui-orkconsole ok-font-status"><span class="ok-tone-muted">${say("That ork is not at work any more.")}</span>
      <button class="gui-toolerr__close" title=${say("Close")} aria-label=${say("Close")} onClick=${() => { consoleOrk.value = null; }}>×</button></div>`;
  }
  return html`<div class="gui-orkconsole ok-font-status" role="region" aria-label=${say(`${r.name}'s console`)}>
    <div class="gui-orkconsole__head">
      <span class="gui-slots__mark" title=${r.word}>${r.mark}</span>
      <span class="gui-orkconsole__line">${r.line}</span>
      <button class="gui-toolerr__close" title=${say("Close")} aria-label=${say("Close")} onClick=${() => { consoleOrk.value = null; }}>×</button>
    </div>
    ${r.answer && html`<p><b>${r.answer.question}</b></p><${Reply} r=${r} />`}
    ${r.wait && !r.answer && html`<p class="ok-tone-muted">⏳ ${r.wait.line}</p>`}
    <div class="ok-row">
      ${r.stop && html`<button class="ok-btn" onClick=${() => stop(r)}>⏹ ${say("Stop")}</button>`}
      ${r.building_id && html`<button class="ok-btn" title=${say("Its building's window: the whole session, its history")}
        onClick=${() => openBuilding(r.building_id)}>${say("Open")} ▸</button>`}
      <span class="ok-tone-muted">${[money(r.spend), r.tool, since(r.since_s)].filter(Boolean).join(" · ")}</span>
    </div>
  </div>`;
}
