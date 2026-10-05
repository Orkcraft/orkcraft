// 🌊 Lake: a document as it reads best (Markdown rendered, code, a diff side by side, a picture, a PDF,
// a page) and a file edited in place. The editor's text is the page's; it goes to the host as the
// person types (a moment after), every `autosave_s` seconds, when the editor loses focus and on Done
// (core/workers/lake.py). A part of the document is selected — lines, paragraphs, an area of a
// picture — and a task written for the keeper of the building it came from: the part is marked in
// the keeper's colour, the keeper's mark stands beside it and its answer comes in a dialog
// (askKeeper, js/keeper.js). The town's Lake window (js/lake.js) draws `Document` in each tab; an old
// Lake building still draws through `panes`.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, town, say } from "../link.js";
import { askKeeper } from "../keeper.js";
import { Dialog } from "../dialog.js";

const TYPED_MS = 400;
const MARK = { "-": "−", "+": "+" };

// -- what each kind looks like ---------------------------------------------------------------------

function Diff({ rows, cut }) {
  return html`<table class="gui-diff ok-font-mono">
    <thead><tr><th></th><th>Before</th><th></th><th>After</th></tr></thead>
    <tbody>${rows.map(([l, r, c], i) => html`<tr key=${i} class=${`is-${{ "-": "del", "+": "add", "~": "mod", "@": "hunk" }[c] || "same"}`}>
      <td class="gui-diff__mark">${c === "-" || c === "~" ? MARK["-"] : c === "@" ? "@" : ""}</td><td>${l}</td>
      <td class="gui-diff__mark">${c === "+" || c === "~" ? MARK["+"] : c === "@" ? "@" : ""}</td><td>${r}</td>
    </tr>`)}</tbody>
    ${cut > 0 && html`<tfoot><tr><td colspan="4" class="ok-tone-muted">${cut} more rows not shown</td></tr></tfoot>`}
  </table>`;
}

// A picture's or a PDF's bytes as a URL the page can show (made once per document revision).
const blobs = new Map();          // key → {data, url}

function blobUrl(key, media) {
  const had = blobs.get(key);
  if (had && had.data === media.data) return had.url;
  if (had) URL.revokeObjectURL(had.url);
  const bytes = Uint8Array.from(atob(media.data), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: media.type }));
  blobs.set(key, { data: media.data, url });
  return url;
}

/** The URL of a tab's picture or PDF goes when its tab goes. */
export function forget(key) {
  const had = blobs.get(key);
  if (had) URL.revokeObjectURL(had.url);
  blobs.delete(key);
  editors.delete(key);
  asks.value = Object.fromEntries(Object.entries(asks.value).filter(([k]) => k !== key));
}

// -- the editor (and read-only text): lines are what is selected -----------------------------------

const editors = new Map();        // key → its textarea, the draft it holds and its timers (kept out of renders)

function editorAct(key, send, name, extra = {}) {
  const ed = editors.get(key);
  if (!ed || !ed.el) return Promise.resolve();
  clearTimeout(ed.typing);
  ed.sent = ed.el.value;
  return send(name, { text: ed.el.value, ...extra }).catch(() => {});
}

/** What the editor of `key` holds that the host has not had yet, taken (the tab is closing); null if nothing. */
export function takeText(key) {
  const ed = editors.get(key);
  if (!ed || !ed.el || ed.readOnly) return null;
  clearTimeout(ed.typing);
  ed.sent = ed.el.value;
  return ed.el.value;
}

function lineOf(text, at) {
  let n = 1;
  for (let i = text.indexOf("\n"); i !== -1 && i < at; i = text.indexOf("\n", i + 1)) n++;
  return n;
}

function linesPicked(el) {
  const { selectionStart: a, selectionEnd: b, value } = el;
  if (a === b) return null;
  const start = lineOf(value, a), end = lineOf(value, Math.max(b - 1, a));
  return { kind: "lines", start, end, text: value.slice(a, b) };
}

function Code({ k, send, e, text, readOnly, marks }) {
  const ref = useRef(null);
  const [geo, setGeo] = useState({ top: 0, line: 20, pad: 8 });
  useEffect(() => {
    const ed = editors.get(k) || {};
    editors.set(k, ed);
    ed.el = ref.current;
    ed.readOnly = readOnly;
    const style = getComputedStyle(ref.current);
    setGeo((g) => ({ ...g, line: parseFloat(style.lineHeight) || 20, pad: parseFloat(style.paddingTop) || 0 }));
    if (readOnly) {
      if (ed.el.value !== text) ed.el.value = text;
      return undefined;
    }
    if (ed.draft !== e.draft) {                 // a new draft: its text, once (typing is never overwritten)
      ed.draft = e.draft;
      ed.el.value = ed.sent = e.text;
      ed.el.focus();
    }
    clearInterval(ed.timer);
    ed.timer = setInterval(() => {
      if (ed.el && ed.el.value !== ed.sent) editorAct(k, send, "autosave");
    }, Math.max(e.autosave_s, 1) * 1000);
    return () => clearInterval(ed.timer);
  }, [k, readOnly, readOnly ? text : e.draft, readOnly ? 0 : e.autosave_s]);
  useEffect(() => () => {                       // the editor goes: what it holds is saved
    const ed = editors.get(k);
    if (ed && ed.el && !ed.readOnly && ed.el.value !== ed.sent) send("save", { text: ed.el.value }).catch(() => {});
    if (ed) ed.el = null;
  }, [k]);

  function input() {
    const ed = editors.get(k);
    clearTimeout(ed.typing);
    ed.typing = setTimeout(() => send("typed", { text: ed.el.value }).catch(() => {}), TYPED_MS);
  }
  function keys(ev) {
    if (readOnly) return;
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "s") {
      ev.preventDefault();
      editorAct(k, send, "save", { force: e.conflict });
    } else if (ev.key === "Escape" && e.markdown) {
      ev.preventDefault();
      editorAct(k, send, "done");
    }
  }
  const pickLines = () => marks.pick(linesPicked(ref.current));
  const band = (s) => ({ top: `${geo.pad + (s.start - 1) * geo.line - geo.top}px`, height: `${(s.end - s.start + 1) * geo.line}px` });
  return html`<div class="gui-lake__code">
    ${marks.list.map((m) => html`<div key=${m.id} class=${cls("gui-lake__band", { "is-asked": m.ask })} style=${band(m.sel)}></div>`)}
    <textarea ref=${ref} class="gui-editor gui-lake__text" wrap="off" spellcheck=${!readOnly && !!e?.markdown} readOnly=${readOnly}
      onInput=${readOnly ? undefined : input} onKeyDown=${keys} onSelect=${pickLines} onMouseUp=${pickLines} onKeyUp=${pickLines}
      onScroll=${(ev) => setGeo((g) => ({ ...g, top: ev.target.scrollTop }))}
      onBlur=${() => !readOnly && !e.conflict && editorAct(k, send, "save")}></textarea>
    ${marks.list.filter((m) => m.ask).map((m) => html`<${KeeperMark} key=${m.id} ask=${m.ask} k=${k}
      style=${{ top: `${geo.pad + (m.sel.start - 1) * geo.line - geo.top}px` }} />`)}
  </div>`;
}

// -- rendered Markdown: paragraphs are what is selected --------------------------------------------

function Prose({ k, htmlText, marks }) {
  const ref = useRef(null);
  const [tops, setTops] = useState({});
  function pick() {
    const box = ref.current, s = window.getSelection();
    if (!box || !s || s.isCollapsed || !s.rangeCount) return;
    const range = s.getRangeAt(0);
    if (!box.contains(range.commonAncestorContainer)) return;
    const blocks = Array.from(box.children);
    const hit = blocks.map((b, i) => (range.intersectsNode(b) ? i : -1)).filter((i) => i >= 0);
    if (!hit.length) return;
    const start = hit[0] + 1, end = hit[hit.length - 1] + 1;
    marks.pick({ kind: "paragraphs", start, end, text: blocks.slice(start - 1, end).map((b) => b.textContent).join("\n\n") });
  }
  useLayoutEffect(() => {                       // the marked paragraphs, and where their marks stand
    const blocks = ref.current ? Array.from(ref.current.children) : [];
    blocks.forEach((b) => b.classList.remove("gui-lake__picked", "gui-lake__asked"));
    const next = {};
    for (const m of marks.list) {
      for (let i = m.sel.start - 1; i < m.sel.end && i < blocks.length; i++) {
        blocks[i].classList.add(m.ask ? "gui-lake__asked" : "gui-lake__picked");
      }
      if (blocks[m.sel.start - 1]) next[m.id] = blocks[m.sel.start - 1].offsetTop;
    }
    if (JSON.stringify(next) !== JSON.stringify(tops)) setTops(next);
  });
  return html`<div class="gui-lake__prose">
    <div ref=${ref} class="gui-prose" onMouseUp=${pick} onKeyUp=${pick} dangerouslySetInnerHTML=${{ __html: htmlText }}></div>
    ${marks.list.filter((m) => m.ask && tops[m.id] !== undefined).map((m) => html`<${KeeperMark} key=${m.id} ask=${m.ask} k=${k}
      style=${{ top: `${tops[m.id]}px` }} />`)}
  </div>`;
}

// -- a picture: an area is what is selected ---------------------------------------------------------

function Picture({ k, src, title, marks }) {
  const ref = useRef(null);
  const [drag, setDrag] = useState(null);
  const at = (ev) => {
    const r = ref.current.getBoundingClientRect();
    return [Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((ev.clientY - r.top) / r.height, 0), 1)];
  };
  const area = (d) => ({ kind: "area", x: Math.min(d.x0, d.x1), y: Math.min(d.y0, d.y1), w: Math.abs(d.x1 - d.x0), h: Math.abs(d.y1 - d.y0) });
  function down(ev) {
    if (ev.button !== 0) return;
    ev.preventDefault();
    const [x, y] = at(ev);
    setDrag({ x0: x, y0: y, x1: x, y1: y });
    ev.currentTarget.setPointerCapture(ev.pointerId);
  }
  function move(ev) {
    if (!drag) return;
    const [x, y] = at(ev);
    setDrag({ ...drag, x1: x, y1: y });
  }
  function up() {
    if (!drag) return;
    const a = area(drag);
    setDrag(null);
    marks.pick(a.w > 0.01 && a.h > 0.01 ? a : null);
  }
  const box = (a) => ({ left: `${a.x * 100}%`, top: `${a.y * 100}%`, width: `${a.w * 100}%`, height: `${a.h * 100}%` });
  return html`<div class="gui-lake__picture">
    <div ref=${ref} class="gui-lake__frame" onPointerDown=${down} onPointerMove=${move} onPointerUp=${up}>
      <img src=${src} alt=${title} draggable="false" />
      ${marks.list.map((m) => html`<div key=${m.id} class=${cls("gui-lake__area", { "is-asked": m.ask })} style=${box(m.sel)}>
        ${m.ask && html`<${KeeperMark} ask=${m.ask} k=${k} />`}</div>`)}
      ${drag && html`<div class="gui-lake__area" style=${box(area(drag))}></div>`}
    </div>
  </div>`;
}

// -- asking the keeper -------------------------------------------------------------------------------

// key → {sel: what is selected now, list: [{id, sel, request, state, answer}], open: the ask shown}
export const asks = signal({});
let askIds = 1;

function asksOf(key) {
  return asks.value[key] || { sel: null, list: [], open: null };
}

function setAsks(key, change) {
  asks.value = { ...asks.value, [key]: { ...asksOf(key), ...change(asksOf(key)) } };
}

function describe(sel) {
  if (!sel) return "The whole document";
  if (sel.kind === "lines") return sel.start === sel.end ? `Line ${sel.start}` : `Lines ${sel.start}–${sel.end}`;
  if (sel.kind === "paragraphs") return sel.start === sel.end ? `Paragraph ${sel.start}` : `Paragraphs ${sel.start}–${sel.end}`;
  if (sel.kind === "area") return "An area of the picture";
  return "The selection";
}

function answerText(r) {
  if (r === null || r === undefined) return "";
  if (typeof r === "string") return r;
  for (const key of ["answer", "text", "message", "summary"]) if (typeof r[key] === "string") return r[key];
  return JSON.stringify(r, null, 2);
}

/** The keeper of the building a document came from: its lead ork's name, else the building's. */
function keeperOf(from) {
  const b = from && town.value?.buildings.find((x) => x.id === from);
  if (!b) return null;
  const lead = b.garrison.find((o) => o.lead) || b.garrison[0];
  return { building: say(b.title), name: lead ? lead.name : say(b.title) };
}

function KeeperMark({ ask, k, style }) {
  const keeper = keeperOf(ask.from);
  const name = keeper ? keeper.name : say("keeper");
  const label = ask.state === "asking" ? say(`${name} is working on it`) : ask.state === "failed" ? say(`${name} did not answer`)
    : say(`${name} answered — open it`);
  return html`<button class=${cls("gui-lake__keeper", { "is-asking": ask.state === "asking", "is-failed": ask.state === "failed" })}
    style=${style} title=${label} aria-label=${label}
    onPointerDown=${(ev) => ev.stopPropagation()}
    onClick=${(ev) => { ev.stopPropagation(); setAsks(k, () => ({ open: ask.id })); }}>${(name || "?").slice(0, 1)}</button>`;
}

function AnswerDialog({ k, ask, title }) {
  const close = () => setAsks(k, () => ({ open: null }));
  const drop = () => setAsks(k, (a) => ({ open: null, list: a.list.filter((x) => x.id !== ask.id) }));
  const keeper = keeperOf(ask.from);
  return html`<${Dialog} title=${say(`${keeper ? keeper.name : "The keeper"} — ${title}`)} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${drop}>${say("Forget it")}</button>
        <button class="ok-btn primary" onClick=${close}>${say("Close")}</button>`}>
    <p class="ok-font-status ok-tone-muted">${describe(ask.sel)} · ${ask.request}</p>
    ${ask.state === "asking" ? html`<p class="ok-tone-muted">Working on it…</p>`
      : ask.state === "failed" ? html`<p class="ok-tone-muted">The keeper did not answer.</p>`
      : html`<pre class="gui-pre gui-orders__context">${ask.answer}</pre>`}
  </${Dialog}>`;
}

function AskBar({ k, doc, title }) {
  const [request, setRequest] = useState("");
  const a = asksOf(k);
  const keeper = keeperOf(doc.from);
  function send(ev) {
    ev.preventDefault();
    const words = request.trim();
    if (!words || !keeper) return;
    const sel = a.sel, id = askIds++;
    const ask = { id, sel, request: words, state: "asking", answer: "", from: doc.from };
    setAsks(k, (x) => ({ sel: null, list: [...x.list, ask] }));
    setRequest("");
    const selection = { ...(sel || { kind: "document" }), document: { path: doc.path, url: doc.url, title } };
    askKeeper(doc.from, words, selection).then((r) => {
      const failed = r === null || r === undefined;
      setAsks(k, (x) => ({ list: x.list.map((m) => (m.id === id ? { ...m, state: failed ? "failed" : "answered", answer: answerText(r) } : m)),
                           open: failed ? x.open : id }));
    });
  }
  const whole = a.list.filter((m) => !m.sel || m.sel.kind === "document");    // asked of the whole document: their marks stand here
  return html`<form class="gui-lake__ask" onSubmit=${send}>
    ${whole.map((m) => html`<${KeeperMark} key=${m.id} ask=${m} k=${k} />`)}
    <span class=${cls("gui-lake__what ok-font-status", { "is-picked": !!a.sel })}>${describe(a.sel)}</span>
    ${a.sel && html`<button type="button" class="gui-tab__close" title=${say("Clear the selection")} aria-label=${say("Clear the selection")}
      onClick=${() => setAsks(k, () => ({ sel: null }))}>×</button>`}
    <input class="ok-input" value=${request} disabled=${!keeper} onInput=${(ev) => setRequest(ev.target.value)}
      placeholder=${keeper ? say(`A task for ${keeper.name}, the keeper of ${keeper.building}`)
                           : say("No keeper: this document came from no building")} />
    <button class="ok-btn" type="submit" disabled=${!keeper || !request.trim()}>${say("Ask the keeper")}</button>
  </form>`;
}

// -- a document ----------------------------------------------------------------------------------------

function Head({ k, doc, send, onDone }) {
  const v = doc.view, e = doc.editing;
  if (e) {
    return html`<div class="gui-head">
      <span class="gui-head__what"><b>${e.markdown ? "Editing" : "Code"}</b> · ${e.path}</span>
      ${e.note && html`<span class=${cls("gui-head__note", { "ok-tone-wait": e.conflict || e.note.startsWith("●") })}>
        ${e.note.replace(/^[●⚠]\s*/, "")}</span>`}
      <span class="gui-head__spacer"></span>
      ${e.conflict && html`<button class="ok-btn danger" onClick=${() => editorAct(k, send, "save", { force: true })}>Save over it</button>`}
      <button class="ok-btn" onClick=${() => editorAct(k, send, "save")}>Save</button>
      ${(e.markdown || onDone) && html`<button class="ok-btn primary" onClick=${() => editorAct(k, send, "done")}>Done</button>`}
    </div>`;
  }
  if (!v) return html`<div class="gui-head ok-tone-muted">Nothing to look at yet — a road brings a file, a diff, a URL or a branch.</div>`;
  return html`<div class="gui-head">
    <span class="gui-head__what"><b>${v.kind}</b> · ${doc.path || v.title}</span>
    <span class="gui-head__spacer"></span>
    ${v.editable && html`<button class="ok-btn" onClick=${() => send("edit").catch(() => {})}>Edit</button>`}
    ${v.target && html`<button class="ok-btn" onClick=${() => send("browse").catch(() => {})}>Open in browser</button>`}
  </div>`;
}

function Body({ k, doc, send, marks }) {
  const v = doc.view, e = doc.editing;
  if (e) return html`<${Code} k=${k} send=${send} e=${e} marks=${marks} />`;
  if (!v) return null;
  if (v.html !== undefined) return html`<${Prose} k=${k} htmlText=${v.html} marks=${marks} />`;
  if (v.rows) return html`<${Diff} rows=${v.rows} cut=${v.cut} />`;
  if (v.kind === "image" || v.kind === "pdf") {
    if (!v.media) return html`<p class="ok-tone-muted">${v.missing ? "It cannot be shown here (missing, or too big) — Open in browser" : ""}</p>`;
    const src = blobUrl(k, v.media);
    return v.kind === "image" ? html`<${Picture} k=${k} src=${src} title=${v.title} marks=${marks} />`
      : html`<iframe class="gui-lake__page" src=${src} title=${v.title}></iframe>`;
  }
  if (v.kind === "web") {
    return html`<iframe class="gui-lake__page" src=${v.target} title=${v.title} sandbox="allow-scripts allow-forms allow-popups"
      referrerpolicy="no-referrer"></iframe>`;
  }
  return html`<${Code} k=${k} send=${send} text=${v.text || ""} readOnly marks=${marks} />`;
}

/** A document in the town's Lake: `k` its key, `doc` what the host says of it (gui/views/lake.py `doc`),
 *  `send(act, args)` the act on it, `title` its tab's title. */
export function Document({ k, doc, send, title }) {
  const a = asksOf(k);
  const list = [...a.list.map((m) => ({ id: `a${m.id}`, sel: m.sel, ask: m })).filter((m) => m.sel && m.sel.kind !== "document"),
                ...(a.sel ? [{ id: "picked", sel: a.sel, ask: null }] : [])];
  const marks = { list: list.filter((m) => fits(m.sel, doc)), pick: (sel) => setAsks(k, () => ({ sel })) };
  const open = a.open && a.list.find((m) => m.id === a.open);
  return html`<div class="gui-lake__doc">
    <${Head} k=${k} doc=${doc} send=${send} />
    <div class="gui-lake__body">
      <${Body} k=${k} doc=${doc} send=${send} marks=${marks} />
    </div>
    <${AskBar} k=${k} doc=${doc} title=${title} />
    ${open && html`<${AnswerDialog} k=${k} ask=${open} title=${title} />`}
  </div>`;
}

/** A selection belongs to the view it was made in: lines to an editor or text, paragraphs to prose, an area to a picture. */
function fits(sel, doc) {
  const v = doc.view, e = doc.editing;
  if (sel.kind === "lines") return !!e || (!!v && v.html === undefined && !v.rows && !["image", "pdf", "web"].includes(v.kind));
  if (sel.kind === "paragraphs") return !e && !!v && v.html !== undefined;
  if (sel.kind === "area") return !e && !!v && v.kind === "image";
  return false;
}

// -- an old Lake building (a scroll from before) ---------------------------------------------------------

export function panes(id, data) {
  const send = (name, args = {}) => act(id, name, args);
  const doc = { ...data, from: "", path: data.editing ? data.editing.path : "", url: "" };
  return {
    head: () => html`<${Head} k=${id} doc=${doc} send=${send} onDone />`,
    view: () => (data.editing ? null : html`<${Body} k=${id} doc=${doc} send=${send} marks=${{ list: [], pick: () => {} }} />`),
    editor: () => (data.editing ? html`<${Code} k=${id} send=${send} e=${data.editing} marks=${{ list: [], pick: () => {} }} />` : null),
  };
}
