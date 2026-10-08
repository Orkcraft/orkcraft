// The War Tent, the Sessions tab of the Town Hall's window as in the TUI (js/buildings/town_hall.js):
// the sessions of this run, new ones and earlier ones to reopen, and the selected one's terminal.
// The processes are the host's (core/sessions.py); closing the window leaves them running.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { Scheme } from "./icons.js";
import { town, command } from "./link.js";
import { Terminal } from "./terminal.js";
import { showBuilding } from "./windows.js";

export const HALL = "town_hall";
const tentKey = signal(null);       // the session the War Tent shows
export const hallTab = signal("chat");     // the Town Hall's tab open: chat | hall | sessions | limits

const HARNESSES = [["claude", "Claude"], ["codex", "Codex"], ["agy", "agy"], ["hermes", "Hermes"], ["pi", "pi"],
  ["cursor", "Cursor"]];
const MARK = { claude: "✻", agy: "✦", codex: "⌬", hermes: "☤", pi: "π", cursor: "◆" };

/** Show a session in the War Tent (it opens the Town Hall on its Sessions tab). */
export function showSession(key) {
  tentKey.value = key;
  hallTab.value = "sessions";
  showBuilding(HALL);
}

function newSession(harness) {
  return command("sessions.new", { harness }).then(showSession, () => {});
}

export function deploy(ork) {
  return command("sessions.deploy", { ork }).then((key) => key && showSession(key), () => {});
}

function Earlier({ onClose }) {
  const [list, setList] = useState(null);
  useEffect(() => { command("sessions.past").then(setList, () => setList([])); }, []);
  return html`<div class="gui-tent__earlier">
    <div class="gui-head"><b>Earlier sessions</b><span class="gui-head__spacer"></span>
      <button class="ok-act" onClick=${onClose}><span class="ok-act__label">Close</span></button></div>
    ${list === null ? html`<p class="ok-tone-muted">Looking…</p>`
      : !list.length ? html`<p class="ok-tone-muted">No earlier sessions in this project.</p>`
      : html`<ul class="gui-rows">${list.map((s) => html`<li key=${s.key} class="gui-tent__row"
            onClick=${() => command("sessions.resume", { key: s.key }).then((k) => { onClose(); showSession(k); }, () => {})}>
          <${Scheme} scheme=${MARK[s.harness] || ""} /> ${s.title}
          <span class="ok-font-status ok-tone-muted"> · ${s.when.replace("T", " ")}${s.live ? " · open" : ""}</span></li>`)}</ul>`}
  </div>`;
}

export function WarTent() {
  const t = town.value;
  const [earlier, setEarlier] = useState(false);
  const sessions = t.sessions;
  const current = sessions.find((s) => s.key === tentKey.value) || sessions.find((s) => s.running) || sessions[0];
  return html`<div class="gui-tent">
    <aside class="gui-tent__side">
      <div class="gui-head"><b>Sessions</b> <span class="ok-tone-muted">${sessions.filter((s) => s.running).length} running</span></div>
      <ul class="gui-rows">${sessions.map((s) => html`<li key=${s.key}
          class=${cls("gui-tent__row", { "is-selected": current && s.key === current.key })}
          onClick=${() => { tentKey.value = s.key; }}>
        <${Scheme} scheme=${MARK[s.harness] || ""} /> ${s.title}
        <span class="ok-font-status ok-tone-muted"> · ${s.running ? "running" : `exited${s.exit_code ? ` ${s.exit_code}` : ""}`}</span>
      </li>`)}
      ${!sessions.length && html`<li class="ok-tone-muted">No sessions in this run yet.</li>`}</ul>
      <div class="gui-tent__new">
        ${HARNESSES.map(([h, label]) => html`<button key=${h} class="ok-btn" onClick=${() => newSession(h)}>New ${label}</button>`)}
        <button class="ok-btn" onClick=${() => setEarlier(true)}>Reopen…</button>
      </div>
    </aside>
    <section class="gui-tent__main">
      ${earlier ? html`<${Earlier} onClose=${() => setEarlier(false)} />`
        : current ? html`
          <div class="gui-head">
            <span class="gui-head__what"><b>${current.title}</b>${current.ticket ? ` · ${current.ticket}` : ""}</span>
            <span class="gui-head__spacer"></span>
            ${current.running ? html`
              <button class="ok-act" onClick=${() => command("term.interrupt", { key: current.key })}><span class="ok-act__label">Interrupt</span></button>
              <button class="ok-act" onClick=${() => command("term.stop", { key: current.key })}><span class="ok-act__label">Stop</span></button>`
            : html`<button class="ok-act" onClick=${() => command("term.forget", { key: current.key })}><span class="ok-act__label">Remove</span></button>`}
          </div>
          <${Terminal} key=${current.key} sessionKey=${current.key} />`
        : html`<p class="ok-tone-muted">Start a session, or reopen an earlier one.</p>`}
    </section>
  </div>`;
}
