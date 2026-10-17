// The Board tab (docs/specs/33-v1-shell.md §6, §8; 29a §7): the goal at the top (a switch when there are several), New idea,
// Today (Needs you, then the to-dos), the ideas in order with their state in words. A tap opens the idea's spec, or the
// plan scrolled to the to-do, on its own screen. A secret is entered only over this paired link (29a).
import { h, sheet } from "./util.js";
import { steady } from "./shell-util.js";
import { field, foot } from "./shell-forms.js";
import { makeGoalSheet, GOAL_STATE, PRIORITY_WORDS } from "./shell-goal.js";

const HOLD_MS = 450;                    // a card held this long can be dragged
const NEEDS = { asks: "❓", plan: "📋", failed: "⚠️", held: "⏳", goal: "🎯" };
const STATE_WORDS = { raw: "new", reading: "the Taskmaster is reading", asks: "asks you", ready: "ready", planning: "the Taskmaster is planning",
  plan: "plan ready", working: "working", done: "done", failed: "needs you" };
export const BUSY = new Set(["reading", "planning", "working"]);

export function stateWords(idea) {
  const p = idea.progress;
  if (idea.state === "working" && p && p.total) return `working ${p.done}/${p.total}`;
  return STATE_WORDS[idea.state] || idea.state;
}

export function makeBoardTab(core, ctx) {
  const st = core.st;
  const pane = h("section", { class: "pane board-tab-pane", "aria-label": "Board" });
  const fresh = steady(pane);
  const tracks = () => st.board?.tracks || [];
  const mine = () => (st.board?.ideas || []).filter((i) => !st.track || i.track === st.track).sort((a, b) => a.order - b.order);

  // -- New idea: one short text and its goal in a sheet (spec 34 §2): Process now (the Taskmaster reads it at once) or Later (the
  // batch does). Closing the sheet with text in it saves it as Later; closing it empty saves nothing. -------------------------
  const field_ = h("textarea", { class: "ok-input", rows: "5", maxlength: "20000", enterkeyhint: "done", "aria-label": "The idea", placeholder: "An idea…" });
  const goalPick = h("select", { class: "ok-input", "aria-label": "Goal" });
  const hint = h("p", { class: "muted hint" }, "Process now: the Taskmaster reads it at once. Later: it waits for the next round. Closing this with text in it saves it as Later. Speak it with the keyboard’s microphone.");
  const nowBtn = h("button", { class: "ok-btn primary big", type: "button" }, "Process now");
  const laterBtn = h("button", { class: "ok-btn big", type: "button" }, "Later");
  const addSheet = sheet("New idea", field("The idea", field_), field("Belongs to goal", goalPick), hint, foot(laterBtn, nowBtn));
  let saved = false;                                 // a button saved it: closing the sheet after it saves nothing more
  async function drop(now) {
    const text = field_.value.trim();
    if (!text) return null;
    saved = true;
    nowBtn.disabled = laterBtn.disabled = true;
    const short = text.length > 40 ? `${text.slice(0, 40)}…` : text;
    const args = { text, now };
    if (goalPick.value) args.track = goalPick.value;
    const r = await ctx.deliver("ideas.add", args, `the idea “${short}”`);
    nowBtn.disabled = laterBtn.disabled = false;
    if (!r.ok || r.result?.error) { saved = false; ctx.flash(r.error || r.result?.error); return null; }
    field_.value = "";
    return r;
  }
  nowBtn.addEventListener("click", async () => {
    const r = await drop(true);
    if (!r) return;
    addSheet.close();
    ctx.flash(r.kept ? "No signal: the idea is kept and goes when the town answers." : "Dropped: the Taskmaster reads it now.");
    if (!r.kept) core.refresh();
  });
  laterBtn.addEventListener("click", async () => {
    const r = await drop(false);
    if (!r) return;
    addSheet.close();
    ctx.flash(r.kept ? "No signal: the idea is kept and goes when the town answers." : "Kept: the Taskmaster reads it in the next round.");
    if (!r.kept) core.refresh();
  });
  addSheet.el.addEventListener("close", async () => {      // × · Esc · the backdrop: text in it is saved as Later, never lost
    if (saved) { saved = false; return; }
    const r = field_.value.trim() ? await drop(false) : null;
    saved = false;
    if (r) { ctx.flash("Kept as Later."); if (!r.kept) core.refresh(); }
  });
  const newIdea = h("button", { class: "ok-btn primary", type: "button", onclick: () => {
    saved = false;
    goalPick.replaceChildren(...tracks().map((t) => h("option", { value: t.slug }, t.title)),
      ...(tracks().some((t) => t.slug === "general") ? [] : [h("option", { value: "general" }, "General")]));
    goalPick.value = tracks().some((t) => t.slug === st.track) ? st.track : "general";
    addSheet.open();
    field_.focus();
  } }, "New idea");

  // -- goals (spec 34 §7): each with its priority and state in words; a tap opens the goal and shows its ideas, Edit changes it ------
  const goalSheet = makeGoalSheet(core);
  const newGoal = h("button", { class: "ok-btn", type: "button", onclick: () => goalSheet.open() }, "New goal");
  function goals() {
    const list = tracks();
    return h("div", { class: "goals" }, h("h3", {}, "Goals"), ...list.map((g) => h("div", { class: `card goal-card${g.slug === st.track ? " is-on" : ""}`, "data-goal": g.slug },
      h("button", { class: "goal-open", type: "button", "aria-pressed": String(g.slug === st.track),
        onclick: () => { st.track = st.track === g.slug ? "" : g.slug; core.draw(); core.open({ kind: "goal", slug: g.slug }); } },
      h("b", {}, g.title),
      h("span", { class: "goal-meta" }, h("span", { class: `prio prio-${g.priority}` }, PRIORITY_WORDS[g.priority] || "Normal"),
        GOAL_STATE[g.state] ? h("span", { class: `state-word ${g.state === "reading" ? "work" : g.state}` }, GOAL_STATE[g.state]) : null,
        h("span", { class: "muted" }, `${g.count} idea${g.count === 1 ? "" : "s"}`))),
    h("button", { class: "linkish", type: "button", "aria-label": `Edit goal ${g.title}`, onclick: () => goalSheet.open(g.slug) }, "Edit"))));
  }

  // -- Today ---------------------------------------------------------------------------------------------------
  function todoCard(todo) {
    const mark = (done) => h("span", { class: `check${done ? " is-on" : ""}`, "aria-hidden": "true" }, done ? "✓" : "");
    const tick = async (done, value) => {
      const args = { idea: todo.idea, id: todo.id, done };
      if (value !== undefined) args.value = value;
      const r = await ctx.send("ideas.todo", args);
      if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return false; }
      await core.refresh();
      return true;
    };
    // the title opens the plan, scrolled to this to-do; the mark and the controls under it answer it
    const head = (onMark) => h("div", { class: "todo-head" },
      h("button", { class: "todo-mark", type: "button", "aria-pressed": String(Boolean(todo.done)), "aria-label": `Done: ${todo.title}`, onclick: onMark }, mark(todo.done)),
      h("button", { class: "todo-open need-text", type: "button", onclick: () => core.open({ kind: "plan", slug: todo.idea, todo: todo.id }) },
        h("b", {}, todo.title), todo.why ? h("small", {}, todo.why) : null, h("span", { class: "chev", "aria-hidden": "true" }, "›")));
    if (todo.done) return h("div", { class: "card todo is-done", "data-todo": todo.id }, head(() => tick(false)));
    const body = [];
    if (todo.kind === "secret") {
      const f = h("input", { class: "ok-input", type: "password", autocomplete: "off", "aria-label": `${todo.title}: the value`, placeholder: "The value" });
      const save = h("button", { class: "ok-btn primary", type: "button", onclick: async () => {
        const v = f.value;
        if (!v) return;
        save.disabled = true;
        const ok = await tick(true, v);
        f.value = "";
        if (!ok) save.disabled = false;
      } }, "Store it");
      body.push(h("div", { class: "row" }, f, save), h("p", { class: "muted hint" },
        "It goes to this computer’s secret store over the paired link, never into a file or to a model."));
      return h("div", { class: "card todo", "data-todo": todo.id }, head(() => f.focus()), ...body);
    }
    if (todo.kind === "choice") {
      body.push(h("div", { class: "answers" }, ...(todo.choices || []).map((c) => h("button", { class: "ok-btn", type: "button", onclick: () => tick(true, c) }, c))));
      return h("div", { class: "card todo", "data-todo": todo.id }, head(() => {}), ...body);
    }
    if (todo.kind === "instructions") {
      body.push(h("ol", { class: "steps" }, ...(todo.steps || []).map((s) => h("li", {}, s))),
        h("button", { class: "ok-btn primary", type: "button", onclick: () => tick(true) }, "Done"));
      return h("div", { class: "card todo", "data-todo": todo.id }, head(() => {}), ...body);
    }
    return h("div", { class: "card todo", "data-todo": todo.id }, head(() => tick(true)));     // confirm: a tap ticks it
  }

  function today() {
    const t = st.board?.today || { todos: [], needs_you: [] };
    const kids = [h("h3", {}, "Needs you")];
    if (!t.needs_you.length) kids.push(h("p", { class: "muted" }, "Nothing waits on you."));
    for (const n of t.needs_you) {
      kids.push(h("button", { class: `card need need-${n.kind}`, type: "button", onclick: () => core.open(n.goal ? { kind: "goal", slug: n.goal } : { kind: "idea", slug: n.idea }) },
        h("span", { class: "need-mark", "aria-hidden": "true" }, NEEDS[n.kind] || "•"),
        h("span", { class: "need-text" }, h("b", {}, n.title), n.text ? h("small", {}, n.text) : null),
        h("span", { class: "chev", "aria-hidden": "true" }, "›")));
    }
    kids.push(h("h3", {}, "To-dos"));
    if (!t.todos.length) kids.push(h("p", { class: "muted" }, "No to-dos: a task asks for one only when it cannot start without."));
    for (const todo of t.todos) kids.push(todoCard(todo));
    return kids;
  }

  // -- the ideas ------------------------------------------------------------------------------------------------
  function card(idea) {
    return h("li", { class: `idea-card state-${idea.state}`, "data-slug": idea.slug },
      h("button", { class: "idea-open", type: "button", onclick: () => core.open({ kind: "idea", slug: idea.slug }) },
        h("span", { class: "idea-title" }, idea.title),
        idea.thesis ? h("span", { class: "idea-thesis" }, idea.thesis) : null,
        h("span", { class: "idea-meta" },
          idea.size ? h("span", { class: "size", title: "Size" }, idea.size) : null,
          h("span", { class: `prio prio-${idea.priority || "normal"}` }, PRIORITY_WORDS[idea.priority] || "Normal"),
          h("span", { class: `state-word ${BUSY.has(idea.state) ? "work" : idea.state}` }, stateWords(idea)))),
      idea.state === "raw" ? h("button", { class: "ok-btn now", type: "button", "aria-label": `Process now: ${idea.title}`,
        onclick: async () => { if (await core.call("ideas.read_now", { slug: idea.slug })) core.refresh(); } }, "Process now") : null);
  }

  // Long-press, then drag: the held card lifts and follows the finger, the others make room; letting go says where
  // it goes (`ideas.move` with the card it goes before). A finger that moves before the hold scrolls instead.
  function wireDrag(list) {
    let timer = 0, from = null, y0 = 0, dragging = null, cards = [], mids = [], sticky = false;
    const stopTimer = () => { clearTimeout(timer); timer = 0; };
    list.addEventListener("contextmenu", (e) => e.preventDefault());
    list.addEventListener("pointerdown", (e) => {
      const li = e.target.closest?.(".idea-card");
      if (!li || (e.button !== undefined && e.button > 0)) return;
      from = { li, x: e.clientX, y: e.clientY, id: e.pointerId };
      timer = setTimeout(() => {
        dragging = li;
        cards = [...list.children];
        mids = cards.map((c) => { const b = c.getBoundingClientRect(); return b.top + b.height / 2; });
        y0 = from.y;
        li.classList.add("is-dragging");
        try { list.setPointerCapture(from.id); } catch { /* the finger stays on the card */ }
        navigator.vibrate?.(30);
      }, HOLD_MS);
    });
    list.addEventListener("pointermove", (e) => {
      if (!dragging) {
        if (from && Math.hypot(e.clientX - from.x, e.clientY - from.y) > 8) stopTimer();
        return;
      }
      dragging.style.transform = `translateY(${e.clientY - y0}px)`;
    });
    list.addEventListener("touchmove", (e) => { if (dragging) e.preventDefault(); }, { passive: false });
    const drop = async (e) => {
      stopTimer();
      if (!dragging) return;
      const li = dragging;
      dragging = null;
      sticky = true;                                                               // the click that follows is not a tap
      setTimeout(() => { sticky = false; }, 400);
      li.classList.remove("is-dragging");
      li.style.transform = "";
      if (e.type === "pointercancel") return;
      const others = cards.filter((c) => c !== li);
      const at = Math.max(0, mids.filter((m, i) => cards[i] !== li && m < e.clientY).length);
      if (others[at] === cards[cards.indexOf(li) + 1]) return;                      // where it was
      const args = { slug: li.dataset.slug };
      if (others[at]?.dataset.slug) args.before = others[at].dataset.slug;
      await core.call("ideas.move", args);
      core.refresh();
    };
    list.addEventListener("click", (e) => { if (sticky) { e.stopPropagation(); e.preventDefault(); } }, true);
    list.addEventListener("pointerup", drop);
    list.addEventListener("pointercancel", drop);
  }

  function ideas() {
    const list = h("ol", { class: "ideas" }, ...mine().map(card));
    wireDrag(list);
    return [h("h3", {}, "Ideas"), list.children.length ? list
      : h("p", { class: "muted" }, "No ideas here yet. Drop one with New idea: it costs nothing, the Taskmaster reads it later.")];
  }

  return {
    el: pane,
    editGoal: (slug) => goalSheet.open(slug),
    sheets: [addSheet.el, goalSheet.el],
    draw() {
      if (!fresh(JSON.stringify([st.board, st.track]))) return;
      if (!st.board) { pane.replaceChildren(h("h2", {}, "Board"), h("p", { class: "muted" }, "Loading…")); return; }
      if (st.track && !tracks().some((t) => t.slug === st.track)) st.track = "";
      pane.replaceChildren(h("div", { class: "pane-head" }, h("h2", {}, "Board"), h("div", { class: "row" }, newGoal, newIdea)), goals(), ...today(), ...ideas(),
        h("p", { class: "muted foot-line" }, h("button", { class: "linkish", type: "button", onclick: () => ctx.unpair() }, "Unpair this phone")));
    },
  };
}
