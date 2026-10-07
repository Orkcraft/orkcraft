// 🗑️ Scroll Dump, the wiki its ork keeps (core/workers/scrolls.py does the work). Closed: how many
// pages, what waits to be taken in, the page changed last. Open, made for the half panel: the counters
// on one line, what waits to be taken in as a strip with Take in beside it, the pages changed lately over
// the tree of the wiki and its sources; a page opens over them (← back). A page's mark opens it in Lake.
// + Quick note opens a note over the tree: its section, tags and links suggested from the wiki as it is
// typed (docs/design/wiki-librarian.md §4), each dropped with one click.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
import { openBuilding } from "../windows.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";

const sheet = new URL("./scrolls.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const adding = signal(null);       // the building whose "Add a folder" dialog is open
const noting = signal(null);       // the building whose Quick note is open
const open = signal({});           // building id → {path, html}: the page open over the tree
const toLake = (id, path, title) => openInLake({ path, title: title || path.split("/").pop(), from: id });

function LakeMark({ id, path, title }) {
  return html`<button class="gui-scrolls__lake" title=${say("Open in Lake")} aria-label=${say("Open in Lake")}
    onClick=${(e) => { e.stopPropagation(); toLake(id, path, title); }}>↗</button>`;
}

function read(id, path, page) {
  act(id, "read", { path, page }).then((r) => { open.value = { ...open.value, [id]: r }; }, () => {});
}

const close = (id) => { open.value = { ...open.value, [id]: null }; };

function FolderDialog({ id, onClose }) {
  const [path, setPath] = useState("");
  const add = () => act(id, "add_folder", { path }).then(onClose, () => {});
  return html`<${Dialog} title="Connect a folder of notes" text="A folder in the project: the librarian reads it, never writes it."
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!path.trim()} onClick=${add}>Connect it</button>`}>
    <input class="ok-input" placeholder="docs/handbook" value=${path} autofocus
      onInput=${(e) => setPath(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && path.trim() && add()} />
  </${Dialog}>`;
}

function Adding({ id }) {
  return adding.value === id ? html`<${FolderDialog} id=${id} onClose=${() => { adding.value = null; }} />` : null;
}

const quiet = (label, onClick, title = "") => html`<button class="ok-act" title=${title} onClick=${onClick}>
  <span class="ok-act__label">${label}</span></button>`;

/** The head: the counters on one line, Check the wiki and Add a folder quiet on the right; what waits to be
 *  taken in (or runs, or failed) as a strip under it with its act beside it. */
function Head({ id, data }) {
  const ingest = () => act(id, "ingest").catch(() => {});
  const q = data.quality;
  return html`<div>
    <div class="wiki-head">
      <span><b>${data.pages_count}</b> ${say(data.pages_count === 1 ? "page" : "pages")}</span>
      <span><b>${data.sources.length}</b> ${say(data.sources.length === 1 ? "source" : "sources")}</span>
      <span title=${say("The wiki's topic")}>${data.topic}</span>
      ${!data.running && !data.error && !data.pending && html`<span class="ok-tone-ok">✓ ${say("up to date")}</span>`}
      <span class="wiki-head__spacer"></span>
      <span class="wiki-head__acts">
        ${noting.value !== id && quiet(`+ ${say("Quick note")}`, () => { noting.value = id; }, say("Leave a note for the wiki"))}
        ${!data.running && !data.pending && quiet(say("Take in"), ingest, say("Read the sources again"))}
        ${!data.running && quiet(say("Check the wiki"), () => act(id, "lint").catch(() => {}), say("Look for broken links, gaps and contradictions"))}
        ${quiet(say("Add a folder"), () => { adding.value = id; }, say("Connect a folder of notes"))}
      </span>
    </div>
    ${data.running ? html`<div class="wiki-strip">
        <span class="wiki-strip__what ok-tone-wait">● ${data.state_plain}</span>
        <button class="ok-btn" onClick=${() => act(id, "stop").catch(() => {})}>Stop</button></div>`
      : data.error ? html`<div class="wiki-strip is-error">
        <span class="wiki-strip__what ok-tone-error" title=${data.state_plain}>✗ ${data.state_plain}</span>
        <button class="ok-btn" onClick=${ingest}>${say("Try again")}</button></div>`
      : data.pending > 0 ? html`<div class="wiki-strip">
        <span class="wiki-strip__what"><span class="ok-tone-wait">●</span> ${say(data.pending === 1 ? "1 note waits to be taken in" : `${data.pending} notes wait to be taken in`)}</span>
        <button class="ok-btn primary" onClick=${ingest}>Take in</button></div>`
      : q && q.total > 0 && html`<div class="wiki-strip">
        <span class="wiki-strip__what"><span class="ok-tone-wait">⚠</span> ${say("Quality check found")} <b>${q.total}</b>
          ${say(q.total === 1 ? "problem" : "problems")}${q.last ? ` · ${say("checked")} ${q.last}` : ""}</span>
        ${q.fixable > 0 && html`<button class="ok-btn primary" onClick=${() => act(id, "fix").catch(() => {})}>Fix links and indexes</button>`}
      </div>`}
  </div>`;
}

function ago(mtime) {
  const s = Math.max(0, Date.now() / 1000 - mtime);
  return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago`
    : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
}

const CHECKS = [["ingest", "After each take-in"], ["daily", "Daily"], ["weekly", "Weekly"], ["off", "Off"]];
const KINDS = { structure: "Structure", link: "Broken links", contradiction: "Contradictions", orphan: "Orphans",
  stale: "Stale", missing: "Missing pages", other: "Other" };

/** The quality check: how often it runs, when next, what it cost; a count per kind of problem and the list
 *  (a page opens on a click). Folded while the wiki is clean. */
function Quality({ id, data }) {
  const q = data.quality;
  if (!q || !data.pages_count) return null;
  const kinds = Object.keys(KINDS).filter((k) => q.counts[k]);
  return html`<details class="wiki-recent wiki-quality" open=${q.total > 0}>
    <summary><h3 class="ok-font-heading">${say("Quality")}</h3>
      <span class=${q.total ? "ok-tone-wait" : "ok-tone-ok"}>${q.total ? `⚠ ${q.total}` : `✓ ${say("clean")}`}</span></summary>
    <div class="wiki-quality__when">
      <span class="ok-font-label">${say("Check")}</span>
      <div class="wiki-note__chips" role="radiogroup" aria-label=${say("How often the wiki is checked")}>
        ${CHECKS.map(([v, label]) => html`<button key=${v} role="radio" aria-checked=${q.check === v}
          class=${cls("wiki-note__chip", { "is-on": q.check === v })} onClick=${() => act(id, "check", { check: v }).catch(() => {})}>${say(label)}</button>`)}
      </div>
      ${!data.running && quiet(say("Check now"), () => act(id, "lint").catch(() => {}), say("Look for broken links, gaps and contradictions"))}
    </div>
    <p class="ok-font-status ok-tone-muted">${[q.last && `${say("Last check")} ${q.last}`, q.next && `${say("next")} ${q.next}`,
      q.cost != null && `${say("it cost")} $${q.cost.toFixed(2)}`].filter(Boolean).join(" · ") || say("Not checked yet")}</p>
    ${kinds.length > 0 && html`<div class="wiki-quality__counts">${kinds.map((k) => html`<span key=${k}>
      <b>${q.counts[k]}</b> ${say(KINDS[k])}</span>`)}</div>`}
    <ul>${q.problems.map((p, i) => html`<li key=${i}>
      <span class=${p.kind === "link" || p.kind === "contradiction" ? "ok-tone-error" : "ok-tone-wait"}>${p.kind === "link" || p.kind === "contradiction" ? "✗" : "⚠"} ${say(KINDS[p.kind] || p.kind)}</span>
      ${p.page && html` <span class="gui-tree__item" title=${p.page} onClick=${() => read(id, `${data.root}/${p.page}`, true)}>${p.page}</span>`}
      <span class="ok-tone-muted"> — ${p.text}</span></li>`)}</ul>
  </details>`;
}

/** What the coming meetings should cover, from the notes left for them; the open items (a person, no
 *  meeting yet) under them. A meeting's title opens its page. */
function Meetings({ id, data }) {
  const a = data.agenda || { meetings: [], open: [] };
  if (!a.meetings.length && !a.open.length) return null;
  return html`<section class="wiki-recent wiki-meet">
    <h3 class="ok-font-heading">${say("To discuss")}</h3>
    ${a.meetings.map((m) => html`<div key=${m.id} class="wiki-meet__one">
      <div class="wiki-meet__head"><span class="gui-tree__item" title=${m.page} onClick=${() => m.page && read(id, m.page, true)}><b>${m.title}</b></span>
        <span class="wiki-recent__when">${m.when}</span></div>
      <ul>${m.items.map((i) => html`<li key=${i.path} class=${cls("", { "ok-tone-muted": i.done })}>
        <span class="gui-tree__item" title=${i.path} onClick=${() => read(id, i.path, false)}>${i.done ? "✓ " : "▪ "}${i.line}</span></li>`)}</ul>
    </div>`)}
    ${a.open.length > 0 && html`<div class="wiki-meet__one">
      <div class="wiki-meet__head"><b>${say("Open items")}</b><span class="wiki-recent__when">${say("no meeting yet")}</span></div>
      <ul>${a.open.map((i) => html`<li key=${i.path}><span class="gui-tree__item" title=${i.path}
        onClick=${() => read(id, i.path, false)}>▪ ${i.line}</span> <span class="ok-tone-muted">· ${i.with.join(", ")}</span></li>`)}</ul>
    </div>`}
  </section>`;
}

/** The pages changed lately: the ones read most, over the tree. */
function Recent({ id, data }) {
  if (!data.recent || !data.recent.length) return null;
  return html`<section class="wiki-recent">
    <h3 class="ok-font-heading">${say("Changed lately")}</h3>
    <ul>${data.recent.map((p) => html`<li key=${p.path}>
      <span class="gui-tree__item" title=${p.path} onClick=${() => read(id, p.path, true)}>${p.title}</span>
      <span class="wiki-recent__when">${say(ago(p.mtime))}</span><${LakeMark} id=${id} path=${p.path} title=${p.title} /></li>`)}</ul>
  </section>`;
}

function Tree({ id, data }) {
  const row = (path, page, label, extra) => html`<li key=${path} class="gui-tree__item" title=${path} onClick=${() => read(id, path, page)}>
    <span class="wiki-tree__name">${label}</span>${extra}</li>`;
  return html`<div class="gui-tree wiki-tree">
    <details open>
      <summary><b>${data.root}</b> <span class="ok-tone-muted">${data.pages_count}</span></summary>
      <ul>${data.pages.length ? data.pages.map((p) => row(p.path, true,
          html`<span style=${`padding-left:${p.depth}em`}>${p.title}</span>`,
          html`${p.locked && html` <span class="ok-word ok-tone-muted">people's</span>`}<${LakeMark} id=${id} path=${p.path} title=${p.title} />`))
        : html`<li class="ok-tone-muted">${say("No wiki yet — Take in makes it from the sources.")}</li>`}</ul>
    </details>
    ${data.sources.map((b) => html`<details key=${b.path}>
      <summary><b>${b.path}</b> <span class="ok-tone-muted">${b.count}</span>
        ${b.todo > 0 && html` <span class="ok-tone-wait" title=${say("to take in")}>● ${b.todo}</span>`}
        ${b.error && html` <span class="ok-tone-wait">⚠ ${b.error}</span>`}</summary>
      <ul>${b.items.map((n) => row(n.path, false, n.title,
          n.fresh ? html` <span class="ok-tone-wait" title=${say("to take in")}>●</span>` : ""))}</ul>
    </details>`)}
    ${!data.sources.length && html`<p class="ok-tone-muted">${say("No sources yet — Add a folder of notes for the wiki to read.")}</p>`}
  </div>`;
}

/** A page open over the tree: ← back, its path, Open in Lake for a wiki page, the page rendered. */
function Page({ id, data, page }) {
  const isPage = data.pages.some((p) => p.path === page.path);
  const back = () => close(id);
  return html`<div class="wiki-page" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <div class="wiki-page__bar">
      <button class="ok-btn" onClick=${back}>← ${say("All pages")}</button>
      <span class="wiki-page__path" title=${page.path}>${page.path}</span>
      ${isPage && quiet(say("Open in Lake"), () => toLake(id, page.path))}
    </div>
    ${page.meta && html`<p class="wiki-page__meta" title=${page.meta}>${page.meta}</p>`}
    <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: page.html }}></div>
  </div>`;
}

const DELAY_MS = 400;               // the suggestions wait for the typing to stop

/** A Quick note: the text, then what the wiki suggests for it — the section, tags, the pages to link —
 *  each dropped with one click; Save note keeps it in the wiki's inbox (and takes it in at once). */
function QuickNote({ id, data }) {
  const [text, setText] = useState("");
  const [hint, setHint] = useState({ section: "", tags: [], links: [], meeting: null, people: [] });
  const [section, setSection] = useState(null);     // null: the suggested one
  const [dropped, setDropped] = useState([]);        // tags taken off
  const [added, setAdded] = useState([]);            // tags of the person's own
  const [off, setOff] = useState([]);                // links unticked
  const [tagging, setTagging] = useState(false);
  const [tag, setTag] = useState("");
  const [now, setNow] = useState(true);
  const [noMeeting, setNoMeeting] = useState(false);
  const [busy, setBusy] = useState(false);
  const asked = useRef(0);
  useEffect(() => {
    const n = ++asked.current;
    if (!text.trim()) { setHint({ section: "", tags: [], links: [], meeting: null, people: [] }); return undefined; }
    const t = setTimeout(() => act(id, "suggest", { text })
      .then((r) => { if (n === asked.current && r) setHint(r); }, () => {}), DELAY_MS);
    return () => clearTimeout(t);
  }, [id, text]);
  const close = () => { noting.value = null; };
  const picked = section ?? hint.section;
  const tags = [...hint.tags.filter((x) => !dropped.includes(x)), ...added.filter((x) => !hint.tags.includes(x))];
  const links = hint.links.filter((l) => !off.includes(l.path)).map((l) => l.path);
  const save = () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    const meeting = noMeeting ? null : hint.meeting;
    act(id, "note", { text, section: picked, tags, links, take_in: now, meeting, people: hint.people || [] })
      .then((path) => { toast(`${say("Kept in")} ${path}`, "information", say("Quick note")); close(); },
        () => setBusy(false));
  };
  const keys = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
  };
  const addTag = () => {
    const t = tag.trim().toLowerCase();
    if (t && !tags.includes(t)) { setAdded([...added, t]); setDropped(dropped.filter((x) => x !== t)); }
    setTag(""); setTagging(false);
  };
  const sections = data.sections || [];
  return html`<section class="wiki-note" onKeyDown=${keys}>
    <div class="wiki-note__head"><h3 class="ok-font-heading">${say("Quick note")}</h3>
      <span class="ok-font-status ok-tone-muted">Ctrl+Enter ${say("saves")} · Esc ${say("closes")}</span></div>
    <textarea class="ok-input gui-textarea" rows="4" value=${text} autofocus aria-label=${say("The note")}
      placeholder=${say("Discuss the pricing tiers with Sergey tomorrow…")} onInput=${(e) => setText(e.target.value)}></textarea>
    ${hint.meeting && html`<div class=${cls("wiki-note__meet", { "is-off": noMeeting })}>
      <span class="ok-font-label">${say("For the meeting")}</span>
      <span class="wiki-note__meet-what"><b>${hint.meeting.title}</b> · ${hint.meeting.when}</span>
      <button class="gui-link" onClick=${() => setNoMeeting(!noMeeting)}>${say(noMeeting ? "Back to the meeting" : "Not for a meeting")}</button>
    </div>`}
    ${(noMeeting || !hint.meeting) && (hint.people || []).length > 0 && html`<p class="ok-font-status ok-tone-muted">
      ${say("An open item for")} ${hint.people.join(", ")}: ${say("it goes to the next meeting with them.")}</p>`}
    ${sections.length > 0 && html`<div class="wiki-note__row"><span class="ok-font-label">${say("Section")}</span>
      <div class="wiki-note__chips" role="radiogroup" aria-label=${say("Section")}>
        ${sections.map((s) => html`<button key=${s} role="radio" aria-checked=${s === picked}
          class=${cls("wiki-note__chip", { "is-on": s === picked })} onClick=${() => setSection(s === picked ? "" : s)}>${s}</button>`)}
      </div></div>`}
    <div class="wiki-note__row"><span class="ok-font-label">${say("Tags")}</span>
      <div class="wiki-note__chips">
        ${tags.map((t) => html`<span key=${t} class="wiki-note__tag">${t}<button aria-label=${`${say("Drop tag")} ${t}`}
          onClick=${() => { setDropped([...dropped, t]); setAdded(added.filter((x) => x !== t)); }}>✕</button></span>`)}
        ${tagging ? html`<input class="ok-input wiki-note__tag-in" value=${tag} autofocus aria-label=${say("New tag")}
            onInput=${(e) => setTag(e.target.value)} onBlur=${addTag}
            onKeyDown=${(e) => { if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); addTag(); } }} />`
          : html`<button class="gui-link" onClick=${() => setTagging(true)}>+ ${say("Add tag")}</button>`}
      </div></div>
    ${hint.links.length > 0 && html`<div class="wiki-note__row"><span class="ok-font-label">${say("Link to")}</span>
      <ul class="wiki-note__links">${hint.links.map((l) => html`<li key=${l.path}>
        <label class="ok-check" onClick=${() => setOff(off.includes(l.path) ? off.filter((x) => x !== l.path) : [...off, l.path])}>
          <i>${off.includes(l.path) ? "" : "✓"}</i> ${l.title}</label>
        <span class="wiki-note__path" title=${l.path}>${l.path}</span></li>`)}</ul></div>`}
    <div class="wiki-note__foot">
      <span class="ok-font-status ok-tone-muted">${say("Saves to")} <code>${data.inbox}/</code></span>
      <span class="wiki-head__spacer"></span>
      <label class="ok-check" onClick=${() => setNow(!now)}><i>${now ? "✓" : ""}</i> ${say("Take in now")}</label>
      <button class="ok-btn" onClick=${close}>Cancel</button>
      <button class="ok-btn primary" disabled=${!text.trim() || busy} onClick=${save}>Save note</button>
    </div>
  </section>`;
}

function Pages({ id, data }) {
  if (noting.value === id) return html`<${QuickNote} key=${`note-${id}`} id=${id} data=${data} />`;
  const page = open.value[id];
  if (page) return html`<${Page} key=${page.path} id=${id} data=${data} page=${page} />`;
  return html`<div><${Quality} id=${id} data=${data} /><${Meetings} id=${id} data=${data} /><${Recent} id=${id} data=${data} /><${Tree} id=${id} data=${data} /></div>`;
}

/** The notes a task was given lately: what it is and the pages named for it. */
function Lent({ lent }) {
  return html`<div class="gui-scrolls__lent gui-hut__text">
    <span class="ok-tone-accent">${say("Read for")}: <b>${lent.task}</b></span>
    <ul>${lent.pages.slice(0, 2).map((t) => html`<li key=${t}>${t}</li>`)}</ul></div>`;
}

/** Closed: how many pages; what waits to be taken in, runs or failed; the notes a task was given lately,
 *  while they are fresh; the foot the page changed last and when. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const state = c.error ? html`<span class="ok-tone-error">✗ ${say("the last take-in failed")}</span>`
    : c.running ? html`<span class="ok-tone-wait">● ${c.running}…</span>`
    : c.pending ? html`<span class="ok-tone-wait">● <b>${c.pending}</b> ${say(c.pending === 1 ? "note to take in" : "notes to take in")}</span>`
    : html`<span class="ok-tone-ok">✓ ${say("up to date")}</span>`;
  return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big">${c.pages}<small>${say(c.pages === 1 ? "page" : "pages")}</small></div>
    <div class="gui-hut__text">${state}</div>
    ${c.quality > 0 && html`<div class="gui-hut__text ok-tone-wait">⚠ <b>${c.quality}</b> ${say(c.quality === 1 ? "quality problem" : "quality problems")}</div>`}
    ${c.discuss && html`<div class="gui-hut__text"><span class="ok-tone-accent">${say("To discuss")}:</span>
      <b>${c.discuss.count}</b> · ${c.discuss.title}</div>`}
    ${c.lent && html`<${Lent} lent=${c.lent} />`}
    ${c.last && html`<div class="gui-hut__foot"><span>✎ ${c.last.title}</span><span class="gui-hut__when">${say(ago(c.last.mtime))}</span></div>`}
  </div>`;
}

/** The type's quick actions in its Info (realm/catalog.py). */
const QUICK = {
  "wiki.note": (id) => { noting.value = id; openBuilding(id, "work"); },
  "wiki.ingest": (id) => act(id, "ingest").catch(() => {}),
  "wiki.lint": (id) => act(id, "lint").catch(() => {}),
  "knowledge.add": (id) => { adding.value = id; },
};

/** Does one of its quick actions (js/types.js); true when it did. */
export function quick(id, action) {
  const f = QUICK[action];
  if (!f) return false;
  f(id);
  return true;
}

/** The window by its UI document (design/buildings/scrolls.json). `page` shows nothing of its own: a page
 *  opens over the tree (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    tree: () => html`<${Pages} id=${id} data=${data} />`,
    page: () => null,
  };
}

/** Its Add a folder window, over the town, whether the building is open or not (js/types.js). */
export function overlay() {
  return adding.value ? html`<${Adding} id=${adding.value} />` : null;
}
