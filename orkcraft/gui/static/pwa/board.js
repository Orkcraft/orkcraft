// The v1 shell on a phone (docs/specs/33-v1-shell.md §6, §8; decisions §45.2): the one face when the compact snapshot's `focus` is
// "board". Three tabs at the foot — Board · Agents · Review, each with its count when it is not zero — under a top bar (what is
// left of the AI tools, Spend, Stop all, the gear). An idea's spec, a plan, a task or a result's code opens on its own full
// screen over the tab, with Back (and the system back gesture) to the tab it came from and its actions pinned at the bottom.
// It speaks the host's commands (§5) through the phone's protocol (app.js `send`) and reads again when the snapshot's
// `ideas_rev` changes (and every POLL_MS while the Taskmaster or a task works). Always Office's calm look.
import { h } from "./util.js";
import { makeTop } from "./shell-top.js";
import { makeBoardTab, BUSY } from "./shell-board.js";
import { makeAgents } from "./shell-agents.js";
import { makeReview } from "./shell-review.js";
import { makePreview } from "./shell-preview.js";

const POLL_MS = 10000;
const TABS = [["board", "Board"], ["agents", "Agents"], ["review", "Review"]];
const LIVE = new Set(["running", "testing"]);

export { stateWords } from "./shell-board.js";
export { price } from "./shell-preview.js";

/** `ctx`: {send, deliver, flash, unpair}. Returns {el, sheets, content(), render(snapshot), dispose()}. */
export function makeBoard(ctx) {
  const st = { board: null, review: null, agents: null, snap: null, tab: "board", track: "", preview: null };
  let poll = 0;
  let seenRev;                          // the snapshot's ideas_rev read last
  let loading = false;
  let pushed = false;                   // the preview put a step in the history: the system back gesture closes it

  const core = {
    st,
    /** A command of the contract; null (and the plain-words error said) when it fails. */
    async call(name, args) {
      const r = await ctx.send(name, args);
      if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return null; }
      return r.result ?? {};
    },
    refresh, open, close, back,
    draw() { drawAll(); },
  };

  const top = makeTop(core, ctx);
  const boardTab = makeBoardTab(core, ctx);
  const agents = makeAgents(core);
  const review = makeReview(core);
  const preview = makePreview(core, ctx);
  const panes = { board: boardTab.el, agents: agents.el, review: review.el };

  const tabs = {};
  const tabBar = h("nav", { class: "board-tabs", role: "tablist", "aria-label": "Board, Agents, Review" });
  for (const [id, label] of TABS) {
    tabs[id] = h("button", { class: "board-tab", type: "button", role: "tab", onclick: () => go(id) }, h("span", {}, label), h("span", { class: "count", hidden: true }));
    tabBar.append(tabs[id]);
  }
  const el = h("div", { class: "board v1" }, top.el, ...Object.values(panes), tabBar, preview.el);

  /** What the person opened, for the day's analysis (docs/specs/33-v1-shell.md §9): the host's one loggable event. The listener
   *  allows a device only a few commands a second, so the lines go out one at a time, a moment apart, behind the ones that matter. */
  const opened = [];
  let draining = 0;
  function logOpened(what, ref) {
    opened.push({ event: "opened", what, ref: String(ref || ""), device: "phone" });
    if (!draining) draining = setTimeout(drain, 800);
  }
  async function drain() {
    const next = opened.shift();
    if (next) await ctx.send("ideas.log", next);
    draining = opened.length ? setTimeout(drain, 800) : 0;
  }

  function go(id) {
    logOpened("tab", id);
    st.tab = id;
    drawPanes();
    window.scrollTo(0, 0);
  }

  function drawPanes() {
    for (const [id, p] of Object.entries(panes)) p.hidden = st.tab !== id;
    for (const [id, b] of Object.entries(tabs)) { b.classList.toggle("is-active", id === st.tab); b.setAttribute("aria-selected", String(id === st.tab)); }
    el.classList.toggle("is-open", Boolean(st.preview));
  }

  function counts() {
    const t = st.board?.today;
    const n = { board: t ? t.needs_you.length + t.todos.filter((x) => !x.done).length : st.snap?.needs_you || 0, agents: 0,
      review: st.review ? st.review.results.length : st.snap?.review_count || 0 };
    for (const [id, b] of Object.entries(tabs)) {
      const c = b.querySelector(".count");
      c.hidden = !n[id];
      c.textContent = String(n[id] || "");
      b.setAttribute("aria-label", `${TABS.find((x) => x[0] === id)[1]}${n[id] ? `, ${n[id]}` : ""}`);
    }
  }

  function drawAll() {
    boardTab.draw();
    agents.draw();
    review.draw();
    counts();
    drawPanes();
    preview.redraw();
  }

  // -- the preview on its own screen: opened over the tab, Back (or the system gesture) to it -----------------------
  function open(p) {
    logOpened(p.kind === "plan" && p.todo ? "todo" : p.kind, p.task ? `${p.slug}/${p.task}` : p.todo ? `${p.slug}/${p.todo}` : p.slug);
    if (!st.preview) {
      try { history.pushState({ preview: true }, ""); pushed = true; } catch { pushed = false; }
    }
    st.preview = p;
    el.classList.add("is-open");
    preview.show(p);
  }
  function hideNow() {
    st.preview = null;
    el.classList.remove("is-open");
    preview.hide();
  }
  function close() { if (pushed) history.back(); else hideNow(); }
  function back() { close(); }
  window.addEventListener("popstate", () => { pushed = false; if (st.preview) hideNow(); });

  // -- reading the town ------------------------------------------------------------------------------------------
  async function refresh() {
    const [b, r, a] = await Promise.all([ctx.send("ideas.board"), ctx.send("ideas.review_list"), ctx.send("ideas.agents")]);
    const ok = (x) => x.ok && x.result && !x.result.error;
    if (ok(b)) st.board = b.result;
    if (ok(r)) st.review = r.result;
    if (ok(a)) st.agents = a.result;
    if (!st.board && !ok(b)) boardTab.el.replaceChildren(h("p", { class: "muted" }, b.error || "Loading…"));
    else drawAll();
    if (st.preview) preview.reload();
    schedule();
  }

  function schedule() {
    clearTimeout(poll);
    const busy = (st.board?.ideas || []).some((i) => BUSY.has(i.state))
      || (st.agents?.roles || []).some((r) => (r.chips || []).some((c) => LIVE.has(c.state)));
    if (busy) poll = setTimeout(refresh, POLL_MS);
  }

  drawPanes();
  drawAll();

  return {
    el,
    sheets: [...top.sheets, ...boardTab.sheets, ...review.sheets],
    // What is acted on only while the town answers: not the bar's Stop all, nor New idea (kept with no signal).
    content: () => [panes.board, panes.agents, panes.review, preview.el],
    render(s) {
      st.snap = s;
      top.render(s);
      counts();
      if (loading || (seenRev !== undefined && s.ideas_rev === seenRev)) return;
      loading = true;
      refresh().finally(() => { loading = false; });
      seenRev = s.ideas_rev;
    },
    dispose() { clearTimeout(poll); },
  };
}
