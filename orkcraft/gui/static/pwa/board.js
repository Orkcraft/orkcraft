// The Task board on a phone, in focus (docs/specs/29a-board-focus.md §7; decisions §43.10): the one face when the compact
// snapshot's `focus` is "board". Three tabs: Today (what needs you, the to-dos), Ideas (a track's ideas in order) and
// + (drop an idea, kept with no signal as the bar's Idea is); an opened idea is a page over them: its sections, the
// talk and what the state allows. It speaks the commands of the spec's §6 through the phone's protocol (app.js
// `send`), and reads again when the snapshot's `ideas_rev` changes (and every POLL_MS while the keeper or a task works).

import { h, sheet } from "./util.js";

const POLL_MS = 10000;
const HOLD_MS = 450;                    // a card held this long can be dragged
const TALK_SHOWN = 6;                   // turns of the talk under a spec
const BUSY = new Set(["reading", "planning", "working"]);

const STATE_WORDS = { raw: "new", reading: "the keeper is reading", asks: "asks you", ready: "ready", planning: "the keeper is planning",
  plan: "plan ready", working: "working", done: "done", failed: "needs you" };
const TASK_WORDS = { waiting: "waiting", ready: "ready", running: "running", testing: "testing", merged: "merged", failed: "failed", held: "held" };
const NEEDS = { asks: "❓", plan: "📋", failed: "⚠️", held: "⏳" };
// A section's colour role (app.css `.sec-*`) and mark.
const SECTIONS = { Gist: ["action", "✦"], Why: ["gold", "❖"], In: ["success", "＋"], Out: ["muted", "－"], Risks: ["danger", "⚠"],
  "Open questions": ["warning", "❓"], Estimate: ["gold", "≈"], Stages: ["action", "☰"], Decisions: ["muted", "✎"] };

export function stateWords(idea) {
  const p = idea.progress;
  if (idea.state === "working" && p && p.total) return `working ${p.done}/${p.total}`;
  return STATE_WORDS[idea.state] || idea.state;
}

const usd = (x) => `$${Number(x) < 10 ? Number(x).toFixed(1) : Math.round(Number(x))}`;
export const price = (e) => (e ? `~${usd(e.usd_low)}–${Number(e.usd_high) < 10 ? Number(e.usd_high).toFixed(1) : Math.round(Number(e.usd_high))}` : "");

/** `ctx`: {send, deliver, flash, unpair}. Returns {el, sheets, content(), render(snapshot)}. */
export function makeBoard(ctx) {
  let boardData = null;                 // ideas.board's answer
  let tab = "today";
  let track = "";                       // the track the Ideas tab shows (and + drops into)
  let open = null;                      // the opened idea's page ({slug, ...}) or null
  let openSlug = "";
  let section = "";                     // the section the ask box is about
  let unfolded = new Set();             // sections open in the page
  let poll = 0;
  let seenRev;                          // the snapshot's ideas_rev read last
  let loading = false;

  // -- the frame: the bar at the top (name, spend, Stop all), the panes, the tabs at the foot -----------------------
  const title = h("h1", {}, "Orkline");
  const spend = h("span", { class: "board-spend muted" });
  const stop = h("button", { class: "ok-btn danger board-stop", type: "button" }, "Stop all");
  const bar = h("header", { class: "board-bar" }, h("div", { class: "board-name" }, title, spend), stop);
  const paneToday = h("section", { class: "pane", "aria-label": "Today" });
  const paneIdeas = h("section", { class: "pane", "aria-label": "Ideas" });
  const paneAdd = h("section", { class: "pane", "aria-label": "Drop an idea" });
  const paneIdea = h("section", { class: "pane idea-page", "aria-label": "Idea" });
  const tabs = {};
  const tabBar = h("nav", { class: "board-tabs", "aria-label": "Board" });
  for (const [id, label] of [["today", "Today"], ["ideas", "Ideas"], ["add", "+"]]) {
    tabs[id] = h("button", { class: "board-tab", type: "button", "aria-label": id === "add" ? "Drop an idea" : label, onclick: () => go(id) },
      h("span", {}, label), id === "today" ? h("span", { class: "q-dot", hidden: true }) : null);
    tabBar.append(tabs[id]);
  }
  const el = h("div", { class: "board" }, bar, paneToday, paneIdeas, paneAdd, paneIdea, tabBar);

  // Stop all: a tap asks first (the confirm is a sheet whose button sits away from this one), as the town's does.
  const really = h("button", { class: "ok-btn danger", type: "button" }, "Stop every ork");
  const stopSheet = sheet("Stop all",
    h("p", {}, "Every ork at work stops now, and every idea's tasks with them: their sessions are interrupted and their processes ended."),
    really);
  stop.addEventListener("click", () => stopSheet.open());
  really.addEventListener("click", async () => {
    stopSheet.close();
    const r = await ctx.send("halt");
    ctx.flash(r.ok ? `Stopped: ${r.result} session(s)` : r.error);
  });

  function go(id) {
    tab = id;
    open = null;
    openSlug = "";
    drawPanes();
    window.scrollTo(0, 0);
  }

  function drawPanes() {
    paneToday.hidden = tab !== "today" || Boolean(openSlug);
    paneIdeas.hidden = tab !== "ideas" || Boolean(openSlug);
    paneAdd.hidden = tab !== "add" || Boolean(openSlug);
    paneIdea.hidden = !openSlug;
    el.classList.toggle("is-open", Boolean(openSlug));
    for (const [id, b] of Object.entries(tabs)) b.classList.toggle("is-active", id === tab);
  }

  // -- reading the town -------------------------------------------------------------------------------------------
  async function load() {
    const r = await ctx.send("ideas.board");
    if (!r.ok || !r.result) { if (!boardData) paneToday.replaceChildren(h("p", { class: "muted" }, r.error || "Loading…")); return; }
    boardData = r.result;
    if (!tracks().some((t) => t.slug === track)) track = tracks()[0]?.slug || "";
    drawToday();
    drawIdeas();
    drawTabs();
    schedule();
  }

  async function loadPage() {
    if (!openSlug) return;
    const slug = openSlug;
    const r = await ctx.send("ideas.page", { slug });
    if (slug !== openSlug) return;
    if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return; }
    open = r.result;
    drawIdea();
    schedule();
  }

  const tracks = () => boardData?.tracks || [];
  const mine = () => (boardData?.ideas || []).filter((i) => !track || i.track === track).sort((a, b) => a.order - b.order);

  function schedule() {
    clearTimeout(poll);
    const busy = (boardData?.ideas || []).some((i) => BUSY.has(i.state)) || open?.busy;
    if (busy) poll = setTimeout(() => { load(); loadPage(); }, POLL_MS);
  }

  function drawTabs() {
    const n = (boardData?.today?.needs_you || []).length + (boardData?.today?.todos || []).filter((t) => !t.done).length;
    const dot = tabs.today.querySelector(".q-dot");
    dot.hidden = !n;
    dot.textContent = String(n);
  }

  // -- Today ------------------------------------------------------------------------------------------------------
  function drawToday() {
    const t = boardData?.today || { todos: [], needs_you: [] };
    const kids = [];
    kids.push(h("h2", {}, "Needs you"));
    if (!t.needs_you.length) kids.push(h("p", { class: "muted" }, "Nothing waits on you."));
    for (const n of t.needs_you) {
      kids.push(h("button", { class: `card need need-${n.kind}`, type: "button", onclick: () => openIdea(n.idea) },
        h("span", { class: "need-mark", "aria-hidden": "true" }, NEEDS[n.kind] || "•"),
        h("span", { class: "need-text" }, h("b", {}, n.title), n.text ? h("small", {}, n.text) : null),
        h("span", { class: "chev", "aria-hidden": "true" }, "›")));
    }
    kids.push(h("h2", {}, "To-dos"));
    if (!t.todos.length) kids.push(h("p", { class: "muted" }, "No to-dos: a task asks for one only when it cannot start without."));
    for (const todo of t.todos) kids.push(todoCard(todo));
    kids.push(h("p", { class: "muted foot-line" }, h("button", { class: "linkish", type: "button", onclick: () => ctx.unpair() }, "Unpair this phone")));
    paneToday.replaceChildren(...kids);
  }

  function todoCard(todo) {
    const mark = (done) => h("span", { class: `check${done ? " is-on" : ""}`, "aria-hidden": "true" }, done ? "✓" : "");
    const tick = async (done, value) => {
      const args = { idea: todo.idea, id: todo.id, done };
      if (value !== undefined) args.value = value;
      const r = await ctx.send("ideas.todo", args);
      if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return false; }
      await load();
      return true;
    };
    const body = [];
    const head = (onclick) => h("button", { class: "todo-head", type: "button", "aria-pressed": String(Boolean(todo.done)), onclick },
      mark(todo.done), h("span", { class: "need-text" }, h("b", {}, todo.title), todo.why ? h("small", {}, todo.why) : null));
    if (todo.done) return h("div", { class: "card todo is-done" }, head(() => tick(false)));
    if (todo.kind === "secret") {
      const field = h("input", { class: "ok-input", type: "password", autocomplete: "off", "aria-label": `${todo.title}: the value`,
        placeholder: "The value" });
      const save = h("button", { class: "ok-btn primary", type: "button", onclick: async () => {
        const v = field.value;
        if (!v) return;
        save.disabled = true;
        const ok = await tick(true, v);
        field.value = "";
        if (!ok) save.disabled = false;
      } }, "Store it");
      body.push(h("div", { class: "row" }, field, save), h("p", { class: "muted hint" },
        "It goes to this computer’s secret store over the paired link, never into a file or to a model."));
      return h("div", { class: "card todo" }, head(() => field.focus()), ...body);
    }
    if (todo.kind === "choice") {
      body.push(h("div", { class: "answers" }, ...(todo.choices || []).map((c) =>
        h("button", { class: "ok-btn", type: "button", onclick: () => tick(true, c) }, c))));
      return h("div", { class: "card todo" }, head(() => {}), ...body);
    }
    if (todo.kind === "instructions") {
      body.push(h("ol", { class: "steps" }, ...(todo.steps || []).map((s) => h("li", {}, s))),
        h("button", { class: "ok-btn primary", type: "button", onclick: () => tick(true) }, "Done"));
      return h("div", { class: "card todo" }, head(() => {}), ...body);
    }
    return h("div", { class: "card todo" }, head(() => tick(true)));         // confirm: a tap ticks it
  }

  // -- Ideas ------------------------------------------------------------------------------------------------------
  function drawIdeas() {
    const switcher = h("div", { class: "track-switch", role: "tablist", "aria-label": "Track" }, ...tracks().map((t) =>
      h("button", { class: `track${t.slug === track ? " is-active" : ""}`, type: "button", role: "tab",
        "aria-selected": String(t.slug === track), onclick: () => { track = t.slug; drawIdeas(); drawAdd(); } },
      t.title, h("small", {}, ` ${(boardData.ideas || []).filter((i) => i.track === t.slug).length}`))));
    const list = h("ol", { class: "ideas" }, ...mine().map(card));
    wireDrag(list);
    paneIdeas.replaceChildren(switcher, list.children.length ? list
      : h("p", { class: "muted" }, "No ideas here yet. Drop one with +: it costs nothing, the keeper reads it later."));
    drawAdd();
  }

  function card(idea) {
    return h("li", { class: `idea-card state-${idea.state}`, "data-slug": idea.slug },
      h("button", { class: "idea-open", type: "button", onclick: () => openIdea(idea.slug) },
        h("span", { class: "idea-title" }, idea.title),
        idea.thesis ? h("span", { class: "idea-thesis" }, idea.thesis) : null,
        h("span", { class: "idea-meta" },
          idea.size ? h("span", { class: "size", title: "Size" }, idea.size) : null,
          h("span", { class: `state-word ${BUSY.has(idea.state) ? "work" : idea.state}` }, stateWords(idea)))));
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
      const y = e.type === "pointercancel" ? null : e.clientY;
      if (y === null) return;
      const others = cards.filter((c) => c !== li);
      const at = Math.max(0, mids.filter((m, i) => cards[i] !== li && m < y).length);
      const before = others[at]?.dataset.slug;
      if (others[at] === cards[cards.indexOf(li) + 1]) return;                      // where it was
      await moveTo(li.dataset.slug, before);
    };
    list.addEventListener("click", (e) => { if (sticky) { e.stopPropagation(); e.preventDefault(); } }, true);
    list.addEventListener("pointerup", drop);
    list.addEventListener("pointercancel", drop);
  }

  async function moveTo(slug, before) {
    const args = { slug };
    if (before) args.before = before;
    const r = await ctx.send("ideas.move", args);
    if (!r.ok || r.result?.error) ctx.flash(r.error || r.result?.error);
    await load();
    if (openSlug === slug) await loadPage();
  }

  // ↑ ↓ on the opened card: one place up or down among its track's ideas.
  function nudge(slug, dir) {
    const list = (boardData?.ideas || []).filter((i) => i.track === (boardData.ideas.find((x) => x.slug === slug)?.track))
      .sort((a, b) => a.order - b.order).map((i) => i.slug);
    const i = list.indexOf(slug);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= list.length) return;
    return moveTo(slug, dir < 0 ? list[j] : list[j + 1]);
  }

  // -- + : one field -----------------------------------------------------------------------------------------------
  const field = h("textarea", { class: "ok-input", rows: "5", maxlength: "20000", enterkeyhint: "done", "aria-label": "The idea",
    placeholder: "An idea…" });
  const where = h("p", { class: "muted hint" });
  const dropBtn = h("button", { class: "ok-btn primary", type: "button" }, "Drop it");
  paneAdd.append(h("h2", {}, "Drop an idea"), field, where, h("div", { class: "row" }, dropBtn));
  dropBtn.addEventListener("click", async () => {
    const text = field.value.trim();
    if (!text) return;
    dropBtn.disabled = true;
    const short = text.length > 40 ? `${text.slice(0, 40)}…` : text;
    const args = { text };
    if (track) args.track = track;
    const r = await ctx.deliver("ideas.add", args, `the idea “${short}”`);
    dropBtn.disabled = false;
    if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return; }
    field.value = "";
    ctx.flash(r.kept ? "No signal: the idea is kept and goes when the town answers." : "Dropped.");
    if (!r.kept) { tab = "ideas"; await load(); drawPanes(); }
  });
  function drawAdd() {
    const t = tracks().find((x) => x.slug === track);
    where.textContent = `Into ${t ? t.title : "General"}. It costs nothing: the keeper reads it later. Speak it with the keyboard’s microphone.`;
  }

  // -- an idea ------------------------------------------------------------------------------------------------------
  async function openIdea(slug) {
    openSlug = slug;
    open = null;
    section = "";
    unfolded = new Set();
    paneIdea.replaceChildren(h("p", { class: "muted" }, "Loading…"));
    drawPanes();
    window.scrollTo(0, 0);
    await loadPage();
  }

  const askField = h("textarea", { class: "ok-input", rows: "1", maxlength: "20000", "aria-label": "Ask or answer the keeper" });
  const askAbout = h("button", { class: "about", type: "button", hidden: true, "aria-label": "Ask about the whole idea instead",
    onclick: () => { section = ""; drawAsk(); } });
  const askSend = h("button", { class: "ok-btn primary", type: "button" }, "Send");
  const ask = h("div", { class: "ask" }, askAbout, h("div", { class: "row" }, askField, askSend));
  function drawAsk() {
    askField.placeholder = section ? `About ${section}…` : "Ask or answer the keeper…";
    askAbout.hidden = !section;
    askAbout.textContent = section ? `${section} ✕` : "";
  }
  askSend.addEventListener("click", async () => {
    const text = askField.value.trim();
    if (!text || !openSlug) return;
    askSend.disabled = true;
    const args = { slug: openSlug, text };
    if (section) args.section = section;
    const r = await ctx.send("ideas.say", args);
    askSend.disabled = false;
    if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return; }
    askField.value = "";
    ctx.flash("Sent: the keeper answers in a moment.");
    await loadPage();
  });

  async function act(name, args, done) {
    const r = await ctx.send(name, args);
    if (!r.ok || r.result?.error) { ctx.flash(r.error || r.result?.error); return; }
    if (done) ctx.flash(done);
    await load();
    await loadPage();
  }

  function drawIdea() {
    const p = open;
    if (!p) return;
    const idx = (boardData?.ideas || []).filter((i) => i.track === p.track).sort((a, b) => a.order - b.order).findIndex((i) => i.slug === p.slug);
    const total = (boardData?.ideas || []).filter((i) => i.track === p.track).length;
    const head = h("div", { class: "idea-head" },
      h("button", { class: "ok-btn", type: "button", "aria-label": "Back to the board", onclick: () => go(tab) }, "‹ Back"),
      h("span", { class: "idea-nudge" },
        h("button", { class: "ok-btn", type: "button", "aria-label": "Move up", disabled: idx <= 0, onclick: () => nudge(p.slug, -1) }, "↑"),
        h("button", { class: "ok-btn", type: "button", "aria-label": "Move down", disabled: idx < 0 || idx >= total - 1, onclick: () => nudge(p.slug, 1) }, "↓")));
    const word = p.busy && BUSY.has(p.state) ? STATE_WORDS[p.state] : (STATE_WORDS[p.state] || p.state);
    const kids = [head, h("h2", { class: "idea-name" }, p.title),
      h("p", { class: "muted" }, [p.size ? `Size ${p.size} · ` : "", word.charAt(0).toUpperCase() + word.slice(1)].join(""))];
    for (const s of p.sections || []) kids.push(sectionBlock(s));
    if (p.plan && ["plan", "working", "failed", "done"].includes(p.state)) kids.push(planBlock(p));
    const talk = (p.talk || []).slice(-TALK_SHOWN);
    if (talk.length) {
      kids.push(h("h3", {}, "The talk"), h("div", { class: "talk" }, ...talk.map((t) =>
        h("div", { class: `turn ${t.who}` }, h("span", { class: "who" }, t.who === "you" ? "You" : "The keeper", t.section ? ` · ${t.section}` : ""),
          h("p", {}, t.text)))));
    }
    const actions = actionsFor(p);
    paneIdea.replaceChildren(...kids, h("div", { class: "idea-foot" }, actions, ask));
    drawAsk();
  }

  function sectionBlock(s) {
    const [role, icon] = SECTIONS[s.name] || ["muted", "•"];
    const on = unfolded.has(s.name);
    const more = s.text && s.text.trim() !== (s.thesis || "").trim();
    const block = h("div", { class: `sec sec-${role}${on ? " is-open" : ""}`, "data-section": s.name },
      h("button", { class: "sec-head", type: "button", "aria-expanded": String(on), onclick: () => {
        if (on) unfolded.delete(s.name); else unfolded.add(s.name);
        drawIdea();
      } }, h("span", { class: "sec-icon", "aria-hidden": "true" }, icon),
      h("span", { class: "sec-body" }, h("small", { class: "sec-name" }, s.name), h("b", { class: "thesis" }, s.thesis || "—")),
      h("span", { class: "chev", "aria-hidden": "true" }, on ? "⌃" : "⌄")));
    if (on) {
      block.append(h("div", { class: "sec-text" }, more ? h("p", {}, s.text) : null,
        h("button", { class: "ok-btn", type: "button", onclick: () => { section = s.name; drawAsk(); askField.focus(); } }, `Ask about ${s.name}`)));
    }
    return block;
  }

  function planBlock(p) {
    const plan = p.plan;
    const byId = new Map((plan.tasks || []).map((t) => [t.id, t]));
    const kids = [h("h3", {}, "The plan")];
    kids.push(h("ul", { class: "tasks" }, ...(plan.tasks || []).map((t) => h("li", { class: `task t-${t.state}` },
      h("span", { class: "task-title" }, t.title),
      h("small", { class: "muted" }, [t.tier, (t.after || []).length ? `after ${t.after.map((a) => byId.get(a)?.title || a).join(", ")}` : "",
        TASK_WORDS[t.state] && p.state !== "plan" ? TASK_WORDS[t.state] : "", t.state === "held" && t.note ? t.note : "",
        t.commit ? `commit ${t.commit.slice(0, 7)}` : "", t.state === "failed" && t.error ? t.error : ""].filter(Boolean).join(" · "))))));
    const todos = plan.todos || [];
    if (todos.length) kids.push(h("p", { class: "muted" }, `To-dos for you: ${todos.map((t) => t.title).join(", ")}.`));
    if (plan.estimate && p.state === "plan") kids.push(h("p", { class: "muted" }, `${plan.estimate.tasks} tasks, ${price(plan.estimate)} from Spend.`));
    return h("div", { class: "plan card" }, ...kids);
  }

  function actionsFor(p) {
    const n = p.plan?.estimate?.tasks ?? (p.plan?.tasks || []).length;
    const btn = (label, onclick, cls = "primary") => h("button", { class: `ok-btn ${cls} big`, type: "button", onclick }, label);
    switch (p.state) {
      case "ready": case "asks":
        return btn("Take it to work", () => act("ideas.plan", { slug: p.slug }, "The keeper is planning."));
      case "plan":
        return btn(`Start · ${n} tasks · ${price(p.plan?.estimate)}`, () => act("ideas.start", { slug: p.slug }, "Started."));
      case "working":
        return btn("Stop", () => act("ideas.stop", { slug: p.slug }, "Stopped."), "danger");
      case "failed": {
        const why = p.error || (p.plan?.tasks || []).find((t) => t.state === "failed")?.error || "";
        return h("div", { class: "failed" }, why ? h("p", { class: "warn" }, why) : null,
          btn("Start again", () => act("ideas.start", { slug: p.slug }, "Started again.")));
      }
      default:
        return null;
    }
  }

  // -- from the app ------------------------------------------------------------------------------------------------
  drawPanes();
  drawAsk();
  drawAdd();

  return {
    el,
    sheets: [stopSheet.el],
    // What is acted on only while the town answers: not the + tab (an idea is kept with no signal), not the bar.
    content: () => [paneToday, paneIdeas, paneIdea],
    render(s) {
      title.textContent = s.project || "Orkline";
      const gold = s.hud?.show_gold ? s.hud.gold : "";
      spend.textContent = gold ? `Spend ${gold}` : "";
      if (loading || (seenRev !== undefined && s.ideas_rev === seenRev)) return;
      loading = true;
      load().then(() => (openSlug ? loadPage() : null)).finally(() => { loading = false; });
      if (boardData) seenRev = s.ideas_rev;
    },
    dispose() { clearTimeout(poll); },
  };
}
