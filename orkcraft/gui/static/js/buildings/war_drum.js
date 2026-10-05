// 🥁 War Drum: the day's rhythm from a calendar (core/workers/war_drum.py). Closed: the day's first
// three meetings; command: the day, now marked, a meeting's document a click away; full: today by the
// hour and the week, the chosen meeting, the settings. A meeting's document opens in Lake.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";

const chosen = signal({});         // building id → the chosen meeting's id
const adding = signal({});         // building id → true while the New event dialog is open
const FIRST_HOUR = 8, LAST_HOUR = 19;   // the day's grid, widened to the meetings it holds

const pick = (id, e) => { chosen.value = { ...chosen.value, [id]: e.id }; };
const today = (d) => d.days[0].events;
const meeting = (id, d) => d.days.flatMap((x) => x.events).find((e) => e.id === chosen.value[id]);

function openDoc(id, e) {
  act(id, "doc", { id: e.id }).then((doc) => openInLake({ path: doc.path, title: doc.title, from: id }), () => {});
}

function prepare(id, e) {
  act(id, "prepare", e ? { id: e.id } : {}).then((line) => toast(line, "information", say("Preparing the document")),
    () => {});
}

function DocMark({ id, e }) {
  if (!e.doc) return null;
  return html`<button class="ok-chip" title=${say(`Open ${e.doc} in Lake`)}
    onClick=${(ev) => { ev.stopPropagation(); openDoc(id, e); }}>doc</button>`;
}

function NewEvent({ id }) {
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState("");
  const [minutes, setMinutes] = useState("30");
  const close = () => { adding.value = { ...adding.value, [id]: false }; };
  const add = () => act(id, "add", { title, when, minutes: Number(minutes) || 30 })
    .then((at) => { toast(`${at} ${title}`, "information", say("Event added")); close(); }, () => {});
  const ready = title.trim() && when.trim();
  return html`<${Dialog} title="New event" onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!ready} onClick=${add}>Add it</button>`}>
    <p class="ok-dialog__section">Title</p>
    <input class="ok-input" value=${title} autofocus onInput=${(e) => setTitle(e.target.value)} />
    <p class="ok-dialog__section">When</p>
    <input class="ok-input" placeholder="14:30 · tomorrow 9:00 · 2026-10-05 14:00" value=${when}
      onInput=${(e) => setWhen(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && ready && add()} />
    <p class="ok-dialog__section">Minutes</p>
    <input class="ok-input" type="number" min="5" max="1440" value=${minutes} onInput=${(e) => setMinutes(e.target.value)} />
  </${Dialog}>`;
}

/** Closed: the day's first three meetings (still to come or under way). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.meetings.length) return html`<span class="ok-tone-muted">${c.error ? "the calendar cannot be read" : "nothing more today"}</span>`;
  return html`<ul class="ok-hut__lines">${c.meetings.map((m, i) => html`<li key=${i} class=${cls("", { "ok-tone-fire": m.now })}>
    <b>${m.at}</b> ${m.title}${m.doc ? html` <span class="ok-word ok-tone-muted">doc</span>` : ""}</li>`)}
    ${c.more > 0 && html`<li class="ok-tone-muted">+${c.more} more</li>`}</ul>`;
}

/** The Command Card's quick actions, done here: New event opens its dialog, Prepare doc the chosen meeting's. */
export function quick(id, action) {
  if (action === "calendar.new") { adding.value = { ...adding.value, [id]: true }; return true; }
  if (action === "calendar.prepare") {
    const e = chosen.value[id];
    act(id, "prepare", e ? { id: e } : {}).then((line) => toast(line, "information", say("Preparing the document")), () => {});
    return true;
  }
  return false;
}

function DayList({ id, d }) {
  const events = today(d);
  if (!events.length) return html`<p class="ok-tone-muted">Nothing today.</p>`;
  return html`<ul class="ok-list__items">${events.map((e) => html`<li key=${e.id}
      class=${cls("ok-item", { "is-selected": chosen.value[id] === e.id, "is-alert": e.now, "is-disabled": e.past && !e.now })}
      onClick=${() => pick(id, e)}>
    <b>${e.all_day ? say("all day") : e.start}</b><span>${e.title}</span>
    <span class="meta">${e.now ? say("now") : ""}</span><${DocMark} id=${id} e=${e} /></li>`)}</ul>`;
}

/** Command: the day (time, title, a document mark), now highlighted. */
export function preview(id, d) {
  return html`<div class="gui-rows">
    <p class="ok-tone-muted">${d.date} · ${d.left} left today${d.errors.length ? html` · <span class="ok-tone-wait">⚠ ${d.errors[0]}</span>` : ""}</p>
    <${DayList} id=${id} d=${d} />
    ${adding.value[id] && html`<${NewEvent} id=${id} />`}
  </div>`;
}

function Head({ id, d }) {
  const all = today(d);
  const cur = all.find((e) => e.id === d.current), nxt = all.find((e) => e.id === d.next);
  return html`<div class="gui-head">
    <span class="gui-head__what"><b>${d.date}</b>
      ${cur && html` · ${say("now")}: ${cur.title}`}${nxt && html` · ${say("next")} ${nxt.start}: ${nxt.title}`}${" · "}${d.left} left today</span>
    ${d.errors.map((err) => html`<span key=${err} class="ok-tone-wait">⚠ ${err}</span>`)}
    <span class="gui-head__spacer"></span>
    <button class="ok-act" onClick=${() => { adding.value = { ...adding.value, [id]: true }; }}><span class="ok-act__label">New event</span></button>
    <button class="ok-act" onClick=${() => prepare(id, meeting(id, d))}><span class="ok-act__label">Prepare doc</span></button>
    ${adding.value[id] && html`<${NewEvent} id=${id} />`}
  </div>`;
}

/** Today by the hour: a row per hour, the meetings that start in it, the hour that is now marked. */
function Hours({ id, d }) {
  const events = today(d);
  const timed = events.filter((e) => !e.all_day);
  const first = Math.min(FIRST_HOUR, ...timed.map((e) => Math.floor(e.from_min / 60)));
  const last = Math.max(LAST_HOUR, ...timed.map((e) => Math.floor((e.to_min - 1) / 60)));
  const nowHour = Math.floor(d.now_min / 60);
  const hours = [];
  for (let h = first; h <= last; h++) hours.push(h);
  return html`<div>
    ${events.filter((e) => e.all_day).map((e) => html`<div key=${e.id} class="ok-item" onClick=${() => pick(id, e)}>
      <b>${say("all day")}</b> ${e.title}</div>`)}
    <ul class="ok-list__items">${hours.map((h) => {
      const here = timed.filter((e) => Math.floor(e.from_min / 60) === h);
      return html`<li key=${h} class=${cls("ok-item", { "is-alert": h === nowHour })}>
        <span class="ok-tone-muted">${String(h).padStart(2, "0")}:00</span>
        ${here.map((e) => html`<span key=${e.id} class=${cls("ok-chip", { "is-on": chosen.value[id] === e.id })}
          title=${e.when} onClick=${() => pick(id, e)}>${e.start} ${e.title}${e.doc ? " · doc" : ""}</span>`)}
      </li>`;
    })}</ul>
  </div>`;
}

function Week({ id, d }) {
  return html`<div>${d.days.map((day) => html`<section key=${day.date}>
    <p class="ok-list__head">${say(day.label)}</p>
    ${day.events.length ? html`<ul class="ok-list__items">${day.events.map((e) => html`<li key=${e.id}
        class=${cls("ok-item", { "is-selected": chosen.value[id] === e.id, "is-alert": e.now })} onClick=${() => pick(id, e)}>
      <b>${e.all_day ? say("all day") : e.start}</b><span>${e.title}</span><${DocMark} id=${id} e=${e} /></li>`)}</ul>`
      : html`<p class="ok-tone-muted">—</p>`}
  </section>`)}</div>`;
}

function Meeting({ id, d }) {
  const e = meeting(id, d);
  if (!e) return html`<p class="ok-tone-muted">Pick a meeting in the day or the week.</p>`;
  return html`<div class="gui-rows">
    <h3 class="ok-font-heading">${e.title}</h3>
    <p>${e.day} · ${e.all_day ? say("all day") : e.when}${e.location ? ` · ${e.location}` : ""}</p>
    <p class="ok-tone-muted">${e.calendar}</p>
    <div class="ok-row">
      ${e.doc ? html`<button class="ok-act" onClick=${() => openDoc(id, e)}><span class="ok-act__label">Open the document</span></button>
                     <span class="ok-tone-muted">${e.doc}</span>`
              : html`<span class="ok-tone-muted">No document yet.</span>`}
      ${!e.all_day && html`<button class="ok-act" onClick=${() => prepare(id, e)}><span class="ok-act__label">Prepare doc</span></button>`}
    </div>
  </div>`;
}

function Settings({ id, d }) {
  const s = d.settings;
  const [form, setForm] = useState(s);
  useEffect(() => setForm(s), [s.ics, s.day_starts, s.lead]);
  const field = (key, label, hint) => html`<label class="gui-field">${label}
    <input class="ok-input" placeholder=${hint} value=${form[key]} onInput=${(e) => setForm({ ...form, [key]: e.target.value })} /></label>`;
  const changed = ["ics", "day_starts", "lead"].some((k) => form[k] !== s[k]);
  return html`<div class="gui-head">
    ${field("ics", "Calendar (.ics file or URL)", "calendar.ics")}
    ${field("day_starts", "Day's digest at", "08:00")}
    ${field("lead", "Document asked for before a meeting", "2h")}
    <button class="ok-act" disabled=${!changed}
      onClick=${() => act(id, "settings", { ics: form.ics, day_starts: form.day_starts, lead: form.lead }).catch(() => {})}>
      <span class="ok-act__label">Save</span></button>
    <span class="ok-tone-muted">New events go to ${s.writes_to}</span>
  </div>`;
}

/** Full: today by the hour and the week, the chosen meeting, the settings. */
export function panes(id, d) {
  return {
    head: () => html`<${Head} id=${id} d=${d} />`,
    day: () => html`<${Hours} id=${id} d=${d} />`,
    week: () => html`<${Week} id=${id} d=${d} />`,
    meeting: () => html`<${Meeting} id=${id} d=${d} />`,
    settings: () => html`<${Settings} id=${id} d=${d} />`,
  };
}
