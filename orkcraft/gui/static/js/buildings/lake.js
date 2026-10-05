// 🌊 Lake: what a road brought (Markdown rendered, a diff side by side, text) and a file edited in
// place. The editor's text is the page's; it goes to the worker as the person types (a moment
// after), every `autosave_s` seconds, when the editor loses focus and on Done (core/workers/lake.py).
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "../html.js";
import { act } from "../link.js";

const TYPED_MS = 400;
const MARK = { "-": "−", "+": "+", "~": "~", "@": "@", " ": "" };

function Head({ id, data }) {
  const v = data.view, e = data.editing;
  if (e) {
    return html`<div class="gui-head">
      <span class="gui-head__what"><b>Editing</b> · ${e.path}</span>
      ${e.note && html`<span class=${cls("gui-head__note", { "ok-tone-wait": e.conflict || e.note.startsWith("●") })}>
        ${e.note.replace(/^[●⚠]\s*/, "")}</span>`}
      <span class="gui-head__spacer"></span>
      ${e.conflict && html`<button class="ok-btn danger" onClick=${() => editorAct(id, "save", { force: true })}>Save over it</button>`}
      <button class="ok-btn" onClick=${() => editorAct(id, "save")}>Save</button>
      <button class="ok-btn primary" onClick=${() => editorAct(id, "done")}>Done</button>
    </div>`;
  }
  if (!v) return html`<div class="gui-head ok-tone-muted">Nothing to look at yet — a road brings a file, a diff, a URL or a branch.</div>`;
  return html`<div class="gui-head">
    <span class="gui-head__what"><b>${v.kind}</b> · ${v.title}</span>
    <span class="gui-head__spacer"></span>
    ${v.editable && html`<button class="ok-act" onClick=${() => act(id, "edit")}><span class="ok-act__label">Edit</span></button>`}
    ${v.target && html`<button class="ok-act" onClick=${() => act(id, "browse")}><span class="ok-act__label">Open in browser</span></button>`}
  </div>`;
}

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

function View({ data }) {
  const v = data.view;
  if (!v || data.editing) return null;
  if (v.html !== undefined) return html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: v.html }}></div>`;
  if (v.rows) return html`<${Diff} rows=${v.rows} cut=${v.cut} />`;
  return html`<pre class="gui-pre">${v.text}</pre>`;
}

// The editor of each Lake: its textarea, the draft it holds and its timers (kept out of renders).
const editors = new Map();

function editorAct(id, name, extra = {}) {
  const ed = editors.get(id);
  if (!ed || !ed.el) return Promise.resolve();
  clearTimeout(ed.typing);
  ed.sent = ed.el.value;
  return act(id, name, { text: ed.el.value, ...extra }).catch(() => {});
}

function Editor({ id, e }) {
  const ref = useRef(null);
  useEffect(() => {
    const ed = editors.get(id) || {};
    editors.set(id, ed);
    ed.el = ref.current;
    if (ed.draft !== e.draft) {                 // a new draft: its text, once (typing is never overwritten)
      ed.draft = e.draft;
      ed.el.value = ed.sent = e.text;
      ed.el.focus();
    }
    clearInterval(ed.timer);
    ed.timer = setInterval(() => {
      if (ed.el && ed.el.value !== ed.sent) editorAct(id, "autosave");
    }, Math.max(e.autosave_s, 1) * 1000);
    return () => clearInterval(ed.timer);
  }, [id, e.draft, e.autosave_s]);
  useEffect(() => () => {                       // the window goes: what it holds is saved
    const ed = editors.get(id);
    if (ed && ed.el && ed.el.value !== ed.sent) act(id, "save", { text: ed.el.value }).catch(() => {});
    editors.delete(id);
  }, [id]);

  function input() {
    const ed = editors.get(id);
    clearTimeout(ed.typing);
    ed.typing = setTimeout(() => act(id, "typed", { text: ed.el.value }).catch(() => {}), TYPED_MS);
  }
  function keys(ev) {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "s") {
      ev.preventDefault();
      editorAct(id, "save", { force: e.conflict });
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      editorAct(id, "done");
    }
  }
  return html`<textarea ref=${ref} class="gui-editor" spellcheck=${e.markdown}
    onInput=${input} onKeyDown=${keys} onBlur=${() => !e.conflict && editorAct(id, "save")}></textarea>`;
}

export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    view: () => (data.editing ? null : html`<${View} data=${data} />`),
    editor: () => (data.editing ? html`<${Editor} id=${id} e=${data.editing} />` : null),
  };
}
