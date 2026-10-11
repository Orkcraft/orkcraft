// Task Fields kept open on the phone (docs/design/mobile.md §10), as a widget on a home screen: the person's
// to-dos and the latest notes always in view, the orks' lanes a tap away, and a to-do, a note or a task
// written from the phone. A task or a note goes down the board's roads like one written at the desk, so the
// sheet says where it goes before it is added (the snapshot's `widget.sends`), and after it is added the widget
// keeps its trail for a while: where it went and how the buildings down the road changed since.

import { h, sheet, clock, fenced } from "./util.js";
import { mark } from "./icons.js";
import { kind as stateOf } from "./town.js";

const TRAIL_MS = 10 * 60 * 1000;        // a card's trail stays this long after its last step
const STATE_WORDS = { asks: "asks you", trouble: "in trouble", work: "at work", quiet: "quiet" };

const KINDS = {
  todo: { title: "New to-do", placeholder: "What you will do", lane: (w) => w.todo_lane },
  note: { title: "New note", placeholder: "An idea, a question, a link", lane: (w) => w.note_lane },
  task: { title: "New task", placeholder: "What an ork should do", lane: () => "todo" },
};

/** Where a new card of `kind` goes, in words: a to-do is the person's own; a note or a task goes down the roads
 *  that leave the board for it, or waits on the board. */
export function goes(kind, w, camp = true) {
  if (kind === "todo") return "A to-do is yours: it starts nothing.";
  const to = ((w.sends || {})[kind] || []).map((b) => (camp ? b.title : (b.title_plain || b.title)));
  const what = kind === "task" ? "The task" : "The note";
  if (!to.length) return kind === "task" ? "The task waits in To Do for an ork to take it." : "The note is kept on the board.";
  return `${what} goes down the road to ${to.join(", ")}. The work it starts there is paid from Spend.`;
}

/** `ctx`: {send, flash}. Returns {el, sheet, render(town)}. */
export function makeFields(ctx) {
  const name = h("h2", { id: "widget-h" });
  const { el, yard } = fenced({ class: "widget", "aria-labelledby": "widget-h" },
    h("div", { class: "w-head" }, h("span", { class: "tile-mark" }), name));
  let w = null;
  let camp = true;
  let lanesOpen = false;
  let kind = "todo";

  const text = h("textarea", { id: "widget-text", class: "ok-input", rows: "3", maxlength: "20000", "aria-label": "Text" });
  const hint = h("p", { class: "muted hint" });
  const add = h("button", { class: "ok-btn primary", type: "button" }, "Add");
  const write = sheet("New to-do", text, hint, add);
  add.addEventListener("click", async () => {
    const value = text.value.trim();
    if (!value || !w) return;
    add.disabled = true;
    const r = await ctx.send("act", { id: w.id, act: "add", args: { text: value, lane: KINDS[kind].lane(w) } });
    add.disabled = false;
    if (!r.ok) { ctx.flash(r.error); return; }
    text.value = "";
    write.close();
    const what = kind === "todo" ? "To-do" : kind === "note" ? "Note" : "Task";
    ctx.flash(`${what} added.`);
    if (kind !== "todo") start(what, value);
  });

  // The trail of the last card written here: added, where it went, then each change of the buildings it went
  // to (they may be busy with other work too: the trail says what they do, not that it is this card).
  let trail = null;
  let buildings = [];
  function start(what, value) {
    const to = (w.sends || {})[kind] || [];
    const now = Date.now();
    const short = value.length > 40 ? `${value.slice(0, 40)}…` : value;
    trail = { until: now + TRAIL_MS, to: to.map((b) => b.id), last: new Map(), steps: [[now, `${what} added: ${short}`],
      [now, to.length ? `It went down the road to ${to.map((b) => (camp ? b.title : (b.title_plain || b.title))).join(", ")}.`
        : kind === "task" ? "It waits in To Do for an ork." : "It is kept on the board."]] };
    for (const id of trail.to) {
      const b = buildings.find((x) => x.id === id);
      if (b) trail.last.set(id, stateOf(b, new Set()));
    }
  }
  function follow() {
    if (!trail) return;
    const now = Date.now();
    for (const id of trail.to) {
      const b = buildings.find((x) => x.id === id);
      if (!b) continue;
      const k = stateOf(b, new Set());
      if (trail.last.get(id) !== k) {
        trail.last.set(id, k);
        trail.steps.push([now, `${camp ? b.title : (b.title_plain || b.title)}: ${STATE_WORDS[k]}.`]);
        trail.until = now + TRAIL_MS;
      }
    }
    if (now > trail.until) trail = null;
  }

  function open(k) {
    kind = k;
    write.title(KINDS[k].title);
    text.placeholder = KINDS[k].placeholder;
    hint.textContent = goes(k, w, camp);
    write.open();
  }

  const list = (items, sign) => h("ul", { class: "w-list" }, ...items.map((t) => h("li", {}, h("span", { class: "w-sign", "aria-hidden": "true" }, sign), t)));

  function render(s) {
    w = s.widget || null;
    camp = s.look !== "office";
    buildings = s.buildings || [];
    follow();
    el.hidden = !w;
    if (!w) return;
    const b = (s.buildings || []).find((x) => x.id === w.id) || { title: "Task Fields", type: "fields" };
    name.previousElementSibling.replaceChildren(mark("fields", camp));
    name.textContent = camp ? b.title : (b.title_plain || b.title);
    if (w.error) {
      yard.replaceChildren(h("p", { class: "warn" }, `The board cannot be read: ${w.error}`));
      return;
    }
    const todos = w.todos || { open: 0, count: 0, top: [] };
    const notes = w.notes || { count: 0, top: [] };
    const more = (n, shown) => (n > shown ? h("p", { class: "muted w-more" }, `+${n - shown} more at the computer`) : null);
    const work = w.lanes.map((ln) => `${ln.label} ${ln.count}`).join(" · ");
    const toggle = h("button", { class: "w-work", type: "button", "aria-expanded": String(lanesOpen),
      onclick: () => { lanesOpen = !lanesOpen; render(s); } },
      h("span", {}, "Ork work"), h("span", { class: "muted" }, work), h("span", { class: "chev", "aria-hidden": "true" }, lanesOpen ? "▾" : "▸"));
    yard.replaceChildren(...[
      h("h3", {}, `My to-dos ${todos.open}/${todos.count}`),
      todos.top.length ? list(todos.top, "☐") : h("p", { class: "muted" }, "Nothing open."), more(todos.open, todos.top.length),
      h("h3", {}, `Notes ${notes.count}`, notes.new ? h("span", { class: "new", title: "New" }, " *") : null),
      notes.top.length ? list(notes.top, "✎") : h("p", { class: "muted" }, "No notes yet."), more(notes.count, notes.top.length),
      toggle,
      lanesOpen && h("div", { class: "w-lanes" }, ...w.lanes.filter((ln) => ln.top.length).map((ln) =>
        h("div", {}, h("h3", {}, `${ln.label} ${ln.count}`), list(ln.top, "▪"), more(ln.count, ln.top.length)))),
      h("div", { class: "w-add" },
        h("button", { class: "ok-btn", type: "button", onclick: () => open("todo") }, "+ To-do"),
        h("button", { class: "ok-btn", type: "button", onclick: () => open("note") }, "+ Note"),
        h("button", { class: "ok-btn", type: "button", onclick: () => open("task") }, "+ Task")),
      trail && h("ol", { class: "trail", "aria-label": "What the card started" },
        ...trail.steps.map(([at, line]) => h("li", {}, h("time", {}, clock(at)), line)))].filter(Boolean));
  }

  return { el, sheet: write.el, render };
}
