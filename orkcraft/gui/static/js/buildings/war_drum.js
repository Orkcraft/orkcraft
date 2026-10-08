// 🥁 War Drum: the day's rhythm from a calendar (core/workers/war_drum.py), with the town's scheduled
// runs and ≈ when its limits are reached laid over the meetings (realm/drumbeat.py). Each kind wears
// its role (`b.tone`) and its mark: ▪ meeting, ↻ scheduled run, ≈ limit (an estimate). Closed: the
// next meeting as its headline, the next beats of all three kinds over a strip of the next hours, a
// checkbox per kind hiding it there. Open, made for the half panel: the head with the limits, the agenda
// taking the room (a meeting opens over it, ← back), today by the hour beside it when the window is
// wide, the settings folded to a line. A meeting's document opens in Lake.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { PartToggles, shown, hidden } from "../parts.js";


const sheet = new URL("./war_drum.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const chosen = signal({});         // building id → the chosen meeting's id
const adding = signal({});         // building id → true while the New event dialog is open
const FIRST_HOUR = 8, LAST_HOUR = 19;   // the day's grid, widened to the meetings and beats it holds
const MARK = { meeting: "▪", schedule: "↻", limit: "≈" };
const LIMIT = { gold: "gold limit", lumber: "lumber limit" };
const ESTIMATE = "an estimate at the present burn rate";

const pick = (id, e) => { chosen.value = { ...chosen.value, [id]: e.id }; };
const today = (d) => d.days[0].events;
const meeting = (id, d) => d.days.flatMap((x) => x.events).find((e) => e.id === chosen.value[id]);
const beatKey = (b) => `${b.kind}|${b.ref}|${b.date}|${b.at}`;

function openDoc(id, e) {
  act(id, "doc", { id: e.id }).then((doc) => openInLake({ path: doc.path, title: doc.title, from: id }), () => {});
}

function prepare(id, e) {
  act(id, "prepare", e ? { id: e.id } : {}).then((line) => toast(line, "information", say("Preparing the document")),
    () => {});
}

function DocMark({ id, e }) {
  if (!e.doc) return null;
  return html`<button class="ok-chip is-on gui-drum__doc" title=${say(`Open ${e.doc} in Lake`)}
    onClick=${(ev) => { ev.stopPropagation(); openDoc(id, e); }}>📄 doc</button>`;
}

/** What the Wiki keeps for a meeting (docs/design/wiki-librarian.md §6): the items to discuss, and the pages
 *  its notes link once the brief is back. */
function wikiWords(k) {
  const items = k.discuss === 1 ? "1 to discuss" : `${k.discuss} to discuss`;
  const pages = k.pages ? ` · ${k.pages === 1 ? "1 page" : `${k.pages} pages`}` : "";
  return say(`from the Wiki: ${items}${pages}`);
}

/** The same as a pill beside the meeting; `short` (the closed card, narrow) the count alone, the words on hover. */
function WikiMark({ k, short = false }) {
  if (!k) return null;
  const about = say("Notes left in the Wiki for this meeting; its brief reads them first");
  return html`<span class="ok-chip gui-drum__wiki" title=${short ? `${wikiWords(k)} — ${about}` : about}
    aria-label=${short ? wikiWords(k) : null}>${short ? `✎ ${k.discuss}` : wikiWords(k)}</span>`;
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

// -- one beat: a meeting, a scheduled run or a limit ------------------------------------------------

/** A beat's words: a meeting as written; a run by its building (in the look's words); a limit by name. */
function beatTitle(b) {
  if (b.kind === "meeting") return b.title;
  if (b.kind === "schedule") return say(b.title);
  return say(b.reached ? `${LIMIT[b.title]} reached` : LIMIT[b.title]);
}

/** Its time: `14:00`, `Tue 05:00`, `≈17:40` for an estimate, `now` for a limit already reached. */
function beatWhen(b) {
  if (b.reached) return say("now");
  return `${b.approx ? "≈" : ""}${b.day ? `${b.day} ` : ""}${b.at}`;
}

function beatMeta(b) {
  if (b.kind === "schedule") return `${b.detail}${b.more ? ` +${b.more}` : ""}`;
  if (b.kind === "limit") return b.detail;
  return b.now ? say("now") : "";
}

function Beat({ b }) {
  return html`<li class=${cls(`gui-drum__beat is-${b.kind} ok-tone-${b.tone}`, { "is-now": b.now })}
      title=${b.approx ? say(ESTIMATE) : b.detail}>
    <span class="gui-drum__glyph" aria-hidden="true">${MARK[b.kind]}</span>
    <b class="gui-drum__when">${beatWhen(b)}</b>
    <span class="gui-drum__title">${beatTitle(b)}</span>
    ${b.doc && html`<span class="ok-chip is-on gui-drum__doc" title=${say("Its document is ready")}>📄 doc</span>`}
    <${WikiMark} k=${b.wiki} short=${true} />
    <span class="gui-drum__meta">${beatMeta(b)}</span></li>`;
}

/** The next hours as a line: a mark per beat where it falls, the hours ticked. */
function Strip({ c }) {
  const ticks = [];
  for (let h = 1; h < c.hours; h++) ticks.push(h);
  return html`<div class="gui-drum__strip" aria-hidden="true">
    ${ticks.map((h) => html`<span key=${h} class="gui-drum__tick" style=${`left:${(h / c.hours) * 100}%`}></span>`)}
    ${c.strip.map((m, i) => html`<span key=${i} class=${cls(`gui-drum__mark is-${m.kind} ok-tone-${m.tone}`, { "is-approx": m.approx })}
      style=${`left:${Math.min(m.pos, 1) * 100}%`}>${MARK[m.kind]}</span>`)}
  </div>
  <div class="gui-drum__scale ok-tone-muted"><span>${say("now")} ${c.now}</span><span>+${c.hours}h</span></div>`;
}

/** The closed card's kinds, each one the person may hide (js/parts.js); the checkboxes are its legend. */
const KINDS = [
  { key: "meeting", label: "meetings", mark: MARK.meeting, tone: "text" },
  { key: "schedule", label: "schedules", mark: MARK.schedule, tone: "accent" },
  { key: "limit", label: "limits", mark: MARK.limit, tone: "wait", title: "limits, estimated" },
];

/** Closed: the headline is the next meeting (its time, its title; `now` while it runs); under it the next
 * beats of the kinds shown (meetings, scheduled runs, ≈ limits) over a strip of the next hours, a checkbox
 * over them hiding a kind; the foot how many meetings are left today. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const kinds = KINDS.filter((k) => !c.kinds || c.kinds.includes(k.key));   // its `beats`: a calendar may hold meetings alone
  const on = (x) => shown(b.id, x.kind);
  const beats = c.beats.filter(on);
  const next = c.beats.find((x) => x.kind === "meeting");
  return html`<div class=${cls("gui-drum", { "is-folded": hidden(b.id).length > 0 })}>
    ${kinds.length > 1 && html`<${PartToggles} id=${b.id} parts=${kinds} />`}
    ${c.error ? html`<div class="gui-hut__big ok-tone-wait">⚠ ${say("Unread")}<small>${say("the calendar cannot be read")}</small></div>`
      : next ? html`<div class="gui-hut__big"><span class=${next.now ? "ok-tone-fire" : ""}>${next.now ? say("now") : beatWhen(next)}</span>
          <small title=${next.title}>${next.title}</small></div>`
      : html`<div class="gui-hut__big">${say("Free")}<small>${say("no meeting ahead")}</small></div>`}
    <${Strip} c=${{ ...c, strip: c.strip.filter(on) }} />
    ${beats.length ? html`<ul class="gui-drum__beats">${beats.map((x) => html`<${Beat} key=${beatKey(x)} b=${x} />`)}</ul>`
      : html`<p class="ok-tone-muted">${say("Nothing ahead — New event in its window adds one.")}</p>`}
    <div class="gui-hut__foot"><span>${c.left ? say(`${c.left} meetings left today`) : say("no more meetings today")}</span></div>
  </div>`;
}

/** Its Info's quick actions, done here: New event opens its dialog, Prepare doc the chosen meeting's. */
export function quick(id, action) {
  if (action === "calendar.new") { adding.value = { ...adding.value, [id]: true }; return true; }
  if (action === "calendar.prepare") {
    const e = chosen.value[id];
    act(id, "prepare", e ? { id: e } : {}).then((line) => toast(line, "information", say("Preparing the document")), () => {});
    return true;
  }
  return false;
}

/** A day's beats in time order: the meetings (a click picks one, its document a click away), the
 * scheduled runs and the limits reached that day. `once`: a job's first run only. */
function DayRows({ id, day, once = false, runs = true }) {
  const seen = new Set();
  const hid = runs ? 0 : day.beats.filter((b) => b.kind === "schedule").length;
  const beats = day.beats.filter((b) => runs || b.kind !== "schedule").filter((b) => {
    if (!once || b.kind !== "schedule") return true;
    const key = `${b.ref}|${b.title}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const rows = [...day.events.map((e) => ({ e, min: e.all_day ? -1 : e.from_min, order: 0 })),
                ...beats.map((b) => ({ b, min: b.min, order: b.kind === "schedule" ? 1 : 2 }))]
    .sort((x, y) => x.min - y.min || x.order - y.order);
  const more = hid > 0 && html`<p class="drum-more ok-tone-muted">↻ ${say(`${hid} scheduled runs`)}</p>`;
  if (!rows.length) return more || html`<p class="ok-tone-muted">${say("Nothing this day.")}</p>`;
  return html`<ul class="gui-drum__beats">${rows.map((r) => r.e ? html`<li key=${r.e.id}
      class=${cls("gui-drum__beat is-meeting is-pick", { "is-selected": chosen.value[id] === r.e.id, "is-now": r.e.now,
                                                         "is-past": r.e.past && !r.e.now })}
      onClick=${() => pick(id, r.e)}>
    <span class=${cls("gui-drum__glyph", { "ok-tone-fire": r.e.now })} aria-hidden="true">▪</span>
    <b class="gui-drum__when">${r.e.all_day ? say("all day") : r.e.start}</b><span class="gui-drum__title">${r.e.title}</span>
    <span class="gui-drum__meta">${r.e.now ? say("now") : ""}</span><${WikiMark} k=${r.e.wiki} /><${DocMark} id=${id} e=${r.e} /></li>`
    : html`<${Beat} key=${beatKey(r.b)} b=${{ ...r.b, day: "" }} />`)}</ul>${more}`;
}

/** The limits: where each stands, its burn rate and ≈ when it is reached. */
function Limits({ d }) {
  const known = d.limits.filter((l) => l.known);
  if (!known.length) return null;
  return html`<ul class="gui-drum__limits">${known.map((l) => html`<li key=${l.what}
      class=${`ok-tone-${l.reached ? "error" : "wait"}`} title=${say(ESTIMATE)}>
    <span class="gui-drum__glyph" aria-hidden="true">≈</span>
    <b class="gui-drum__name">${say(LIMIT[l.what])}</b>
    <span class="gui-drum__bar"><span style=${`width:${Math.min(l.share, 1) * 100}%`}></span></span>
    <span class="gui-drum__amount">${l.value} / ${l.limit}</span>
    <span class="gui-drum__meta">${l.rate ? `${l.rate} · ` : ""}${l.reached ? say("reached")
      : l.at ? `≈ ${l.day} ${l.at}`.replace("  ", " ") : say("not at this rate")}</span></li>`)}</ul>`;
}

/** The head: the date, what is on now and next, how many are left; New event, Prepare doc quiet; the
 *  limits with where they stand and ≈ when they are reached on the line under it. */
function Head({ id, d }) {
  const all = today(d);
  const cur = all.find((e) => e.id === d.current), nxt = all.find((e) => e.id === d.next);
  return html`<div class="drum-head">
    <div class="drum-head__row">
      <span class="drum-head__what"><b>${d.date}</b>
        ${cur && html` · <span class="ok-tone-fire">${say("now")}</span> ${cur.title}`}${nxt && html` · ${say("next")} <b>${nxt.start}</b> ${nxt.title}`}</span>
      <span class="drum-head__left"><b>${d.left}</b> ${say("left today")}</span>
      <span class="drum-head__spacer"></span>
      <button class="ok-act" title=${say("Ask for the document of the chosen meeting, else the one on now or next")}
        onClick=${() => prepare(id, meeting(id, d))}><span class="ok-act__label">Prepare doc</span></button>
      <button class="ok-btn primary" onClick=${() => { adding.value = { ...adding.value, [id]: true }; }}>New event</button>
    </div>
    ${d.errors.map((err) => html`<p key=${err} class="drum-head__err ok-tone-wait">⚠ ${err}</p>`)}
    <${Limits} d=${d} />
  </div>`;
}

/** Today by the hour: a row per hour, the meetings, runs and limits that fall in it, the hour that is now marked. */
function Hours({ id, d }) {
  const events = today(d);
  const timed = events.filter((e) => !e.all_day);
  const beats = d.days[0].beats;
  const first = Math.min(FIRST_HOUR, ...timed.map((e) => Math.floor(e.from_min / 60)), ...beats.map((b) => Math.floor(b.min / 60)));
  const last = Math.max(LAST_HOUR, ...timed.map((e) => Math.floor((e.to_min - 1) / 60)), ...beats.map((b) => Math.floor(b.min / 60)));
  const nowHour = Math.floor(d.now_min / 60);
  const hours = [];
  for (let h = first; h <= last; h++) hours.push(h);
  return html`<div>
    ${events.filter((e) => e.all_day).map((e) => html`<div key=${e.id} class="ok-item" onClick=${() => pick(id, e)}>
      <b>${say("all day")}</b> ${e.title}</div>`)}
    <ul class="ok-list__items">${hours.map((h) => {
      const here = timed.filter((e) => Math.floor(e.from_min / 60) === h);
      const marks = beats.filter((b) => Math.floor(b.min / 60) === h);
      return html`<li key=${h} class=${cls("ok-item gui-drum__hour", { "is-alert": h === nowHour })}>
        <span class="ok-tone-muted">${String(h).padStart(2, "0")}:00</span>
        ${here.map((e) => html`<span key=${e.id} class=${cls("ok-chip", { "is-on": chosen.value[id] === e.id })}
          title=${e.when} onClick=${() => pick(id, e)}>${e.start} ${e.title}${e.doc ? " · doc" : ""}</span>`)}
        ${marks.map((b) => html`<span key=${beatKey(b)} class=${`ok-chip gui-drum__chip ok-tone-${b.tone}`}
          title=${b.approx ? say(ESTIMATE) : b.detail}>${MARK[b.kind]} ${b.reached ? say("now") : b.at} ${beatTitle(b)}</span>`)}
      </li>`;
    })}</ul>
  </div>`;
}

/** The agenda: day by day, the meetings with the runs and limits between them — each job once a day, its
 *  cadence beside it (today by the hour shows every run); after tomorrow the runs only counted. A meeting
 *  picked opens over it. */
function Week({ id, d }) {
  const e = meeting(id, d);
  if (e) return html`<${Meeting} id=${id} d=${d} e=${e} />`;
  // Days in a row with nothing in them stand as one line: five "Nothing this day." pushed the next meeting off the window.
  const groups = [];
  d.days.forEach((day, i) => {
    const empty = !day.events.length && !day.beats.length;
    const last = groups[groups.length - 1];
    if (empty && last && last.empty) last.days.push(day);
    else groups.push({ empty, i, days: [day] });
  });
  return html`<div class="drum-week">${groups.map((g) => g.empty && g.days.length > 1
    ? html`<section key=${g.days[0].date}>
        <p class="ok-list__head">${say(g.days[0].label)} – ${say(g.days[g.days.length - 1].label)}</p>
        <p class="ok-tone-muted">${say("Nothing these days.")}</p>
      </section>`
    : html`<section key=${g.days[0].date}>
        <p class="ok-list__head">${say(g.days[0].label)}</p>
        <${DayRows} id=${id} day=${g.days[0]} once=${true} runs=${g.i < 2} />
      </section>`)}</div>`;
}

/** A meeting open over the agenda: ← back, when and where, its document (open it or ask for it). */
function Meeting({ id, d, e }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="drum-meet" onKeyDown=${(ev) => { if (ev.key === "Escape") { ev.stopPropagation(); back(); } }}>
    <button class="ok-btn drum-meet__back" onClick=${back}>← ${say("The agenda")}</button>
    <h3 class="ok-detail__head drum-meet__title">${e.title}</h3>
    <p class="ok-detail__meta">${say((d.days.find((x) => x.date === e.day) || {}).label || e.day)} · ${e.all_day ? say("all day") : e.when}${e.location ? ` · ${e.location}` : ""}
      ${e.now ? html` · <span class="ok-tone-fire">${say("now")}</span>` : ""}</p>
    <p class="ok-detail__meta ok-tone-muted">${e.calendar}</p>
    ${e.wiki && html`<p class="ok-detail__meta drum-meet__wiki">${wikiWords(e.wiki)}</p>`}
    <div class="ok-detail__actions">
      ${e.doc && html`<button class="ok-btn primary" onClick=${() => openDoc(id, e)}>Open the document</button>`}
      ${!e.all_day && html`<button class=${e.doc ? "ok-btn" : "ok-btn primary"} onClick=${() => prepare(id, e)}>${e.doc ? "Prepare it again" : "Prepare doc"}</button>`}
    </div>
    <p class="ok-tone-muted drum-meet__doc">${e.doc ? html`${say("Its document")}: <span class="drum-meet__path" title=${e.doc}>${e.doc}</span>`
      : say("No document yet — Prepare doc asks the orks for one.")}</p>
  </div>`;
}

/** The calendar's settings: one line until opened — they are set once. */
function Settings({ id, d }) {
  const s = d.settings;
  const [form, setForm] = useState(s);
  useEffect(() => setForm(s), [s.ics, s.day_starts, s.lead]);
  const field = (key, label, hint) => html`<label class="gui-field">${label}
    <input class="ok-input" placeholder=${hint} value=${form[key]} onInput=${(e) => setForm({ ...form, [key]: e.target.value })} /></label>`;
  const changed = ["ics", "day_starts", "lead"].some((k) => form[k] !== s[k]);
  return html`<details class="drum-settings">
    <summary><span>${say("Settings")}</span>
      <span class="drum-settings__sum ok-font-status">${s.ics || say("no calendar")} · ${say("digest")} ${s.day_starts || "—"} · ${s.lead ? say(`document ${s.lead} before`) : say("no document asked")}</span></summary>
    <div class="drum-settings__form">
      ${field("ics", "Calendar (.ics file or URL)", "calendar.ics")}
      ${field("day_starts", "Day's digest at", "08:00")}
      ${field("lead", "Document asked for before a meeting", "2h")}
      <button class="ok-btn" disabled=${!changed}
        onClick=${() => act(id, "settings", { ics: form.ics, day_starts: form.day_starts, lead: form.lead }).catch(() => {})}>Save</button>
    </div>
    <p class="ok-tone-muted">New events go to ${s.writes_to}</p>
  </details>`;
}

/** The window by its UI document (design/buildings/war_drum.json), made for the half panel: the head with
 *  the limits, the agenda taking the room (a meeting opens over it), today by the hour beside it when the
 *  window is wide, the settings folded to a line. `meeting` shows nothing of its own: an older document
 *  that still has the pane loses nothing. */
export function panes(id, d) {
  return {
    head: () => html`<${Head} id=${id} d=${d} />`,
    day: () => html`<${Hours} id=${id} d=${d} />`,
    week: () => html`<${Week} id=${id} d=${d} />`,
    meeting: () => null,
    settings: () => html`<${Settings} id=${id} d=${d} />`,
  };
}

/** Its New event window, over the town, whether the building is open or not (js/types.js). */
export function overlay() {
  return html`${Object.keys(adding.value).filter((id) => adding.value[id]).map((id) => html`<${NewEvent} key=${id} id=${id} />`)}`;
}
