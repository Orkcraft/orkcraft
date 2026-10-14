// The town on the phone (docs/design/mobile.md §10), as a phone's home screen: what wants the person stands as
// tiles at the top — a building whose ork asks opens to its question and its answers, one tile open at a time;
// no tile, no Answers — then the buildings of the orkspace the phone shows (its tabs, when the town has more
// than one): those in trouble and at work as rows, every quiet one as a mark with its name, in a grid, a block
// per chain of linked buildings in the order the work flows (links.js). A tap on a row or a mark says what the
// building is doing and what it takes from and sends to, and offers its quick actions; a long press lights its
// neighbours. Its window opens on the computer.

import { h, minutes, sheet, fenced, SPACE } from "./util.js";
import { mark } from "./icons.js";
import { chains, links } from "./links.js";
import { makeCamp } from "./camp.js";

const TROUBLE = new Set(["ERROR", "NO WIKI"]);
const AT_WORK = new Set(["WORKING", "BUSY", "PENDING", "EDITING"]);
const LONG_WAIT_S = 600;                 // a question waiting longer than this is said in the warning's colour
const PRESS_MS = 450;                    // a press this long lights a building's neighbours

/** What a building is now: "asks" | "trouble" | "work" | "quiet". */
export function kind(b, asked) {
  if (b.alert || b.state === "ASKS" || asked.has(b.id)) return "asks";
  if (TROUBLE.has(b.state)) return "trouble";
  if (AT_WORK.has(b.state)) return "work";
  return "quiet";
}

// The questions answered from this phone (id → {said, kept}), till the town's update takes them away. `kept`: given
// with no signal, kept on the phone and sent when it returns (app.js `deliver`).
const answered = new Map();

/** The orkspace the phone shows: the one picked on this phone, else the desktop's open one. The pick is the
 *  phone's own: it never moves the desktop's town. */
export function chosenSpace(s) {
  const all = s.orkspaces || [];
  let id = "";
  try { id = localStorage.getItem(SPACE) || ""; } catch { /* the desktop's */ }
  return all.find((o) => o.id === id) || all.find((o) => o.id === s.active_orkspace) || all[0] || null;
}

function pickSpace(id) {
  try { localStorage.setItem(SPACE, id); } catch { /* this run only: the next town update forgets it */ }
}

/** `ctx`: {send, deliver, flash, rerender}. Returns the parts the app lays out, `render(town)` and `open(id)`: a
 *  building's card as a sheet from the foot. */
export function makeTown(ctx) {
  const camp_ = makeCamp({ open: (b) => about(b), name: (b) => name(b) });
  const summary = h("p", { class: "summary" });
  const tiles = h("div", { class: "tiles" });
  const answers = fenced({ class: "asking", "aria-labelledby": "answers-h" }, h("h2", { id: "answers-h" }, "Answers"), summary, tiles);
  const spaces = h("div", { class: "ok-tabs spaces", role: "tablist", "aria-label": "Orkspaces", hidden: true });
  const rows = h("div", { class: "rows" });
  const grid = h("div", { class: "blocks", "aria-label": "Quiet buildings" });
  const lit = h("p", { class: "lit muted", "aria-live": "polite", hidden: true });
  const quietHead = h("h3", { class: "quiet-head" }, "Quiet");
  const town = fenced({ class: "quiet", "aria-labelledby": "buildings-h" }, h("h2", { id: "buildings-h" }, "Buildings"),
    spaces, rows, quietHead, lit, grid);
  const info = sheet("");
  const infoBody = h("div", { class: "info" });
  info.el.querySelector(".sheet-in").append(infoBody);
  let open = null;                       // the key of the tile that is open; null: the longest-waiting one
  let camp = true;
  let byId = new Map();
  let roads = { into: new Map(), from: new Map() };
  let asks = new Map();                  // building id → its questions: its sheet answers them too

  // A building's card as a sheet from the foot (color-pass.md §6c), headed by its mark, over the dimmed camp.
  let shown = { id: "", key: "" };       // the building whose sheet is open, and its questions then
  const sheetKey = (id) => (asks.get(id) || []).map((a) => `${a.id}:${answered.has(a.id)}`).join(",");
  function about(b) {
    info.title(b.title_plain || b.title);
    shown = { id: b.id, key: sheetKey(b.id) };
    const k = kind(b, asks);
    infoBody.replaceChildren(
      h("div", { class: "info-mark" }, mark(b.type, camp)),
      h("p", {}, k === "quiet" ? "Quiet: nothing waits on it now." : `Now: ${(b.state || k).toLowerCase()}.`),
      ...(asks.get(b.id) || []).map((a) => (a.questions ? poolQuestion(a, ctx, false) : question(a, ctx, true))),
      ...near(b.id).map(([label, ids]) => h("p", {}, h("b", {}, label), ids.map((id) => name(byId.get(id))).join(", "))),
      ...quick(b),
      h("p", { class: "muted" }, "Its window opens on the computer."));
    info.open();
  }

  // Its quick actions, as its card on the desktop has them (mobile.py `quick`): one that takes a line of text
  // asks for it here; one that reaches outside the camp asks once more; the rest do it on a tap.
  function quick(b) {
    const acts = b.quick || [];
    if (!acts.length) return [];
    const msg = h("p", { class: "warn", role: "status", hidden: true });
    const form = h("div", { class: "q-form", hidden: true });
    const buttons = acts.map((a) => h("button", { class: "ok-btn", type: "button", onclick: () => choose(a) }, a.label));
    const say = (text, warn = false) => { msg.textContent = text; msg.className = warn ? "warn" : "done"; msg.hidden = false; };
    async function press(a, value = "") {
      buttons.forEach((x) => { x.disabled = true; });
      const r = await ctx.send("building.input", { id: b.id, input: a.id, ...(value ? { value } : {}) });
      buttons.forEach((x) => { x.disabled = false; });
      if (!r.ok) { say(r.error || "It was not done.", true); return false; }
      form.hidden = true;
      say(typeof r.result === "string" && r.result ? r.result : `${a.label}: done.`);
      ctx.flash?.(`${name(b)}: ${a.label}`);
      return true;
    }
    function choose(a) {
      msg.hidden = true;
      if (a.takes === "text") {
        const text = h("textarea", { class: "ok-input", rows: "3", maxlength: "4000", "aria-label": a.label, placeholder: a.label });
        const go = h("button", { class: "ok-btn primary", type: "button" }, a.label);
        go.addEventListener("click", async () => { if (text.value.trim() && await press(a, text.value.trim())) text.value = ""; });
        form.replaceChildren(text, h("div", { class: "row" }, go));
      } else if (a.ask) {
        form.replaceChildren(h("p", {}, `${a.label}: it reaches outside the camp or takes work in at once.`),
          h("div", { class: "row" }, h("button", { class: "ok-btn danger", type: "button", onclick: () => press(a) }, a.label),
            h("button", { class: "ok-btn", type: "button", onclick: () => { form.hidden = true; } }, "Cancel")));
      } else {
        press(a);
        return;
      }
      form.hidden = false;
      form.querySelector("textarea")?.focus();
    }
    return [h("h3", {}, "Quick actions"), h("div", { class: "row q-acts" }, ...buttons), form, msg];
  }

  // What a building takes from and sends to, by its roads: [[label, ids]] for the ones it has.
  function near(id) {
    const out = [];
    const takes = [...new Set(roads.from.get(id) || [])].filter((x) => byId.has(x));
    const sends = [...new Set(roads.into.get(id) || [])].filter((x) => byId.has(x));
    if (takes.length) out.push(["Takes from: ", takes]);
    if (sends.length) out.push(["Sends to: ", sends]);
    return out;
  }

  // A long press on a row or a mark lights the building's neighbours and dims the rest; letting go puts the
  // town back. The tap after it does nothing, so the press never opens the sheet too.
  let pressTimer = 0;
  let pressed = false;
  function light(id) {
    const ids = new Set(near(id).flatMap(([, xs]) => xs));
    for (const el of document.querySelectorAll("[data-b]")) {
      el.classList.toggle("is-near", ids.has(el.dataset.b));
      el.classList.toggle("is-focus", el.dataset.b === id);
    }
    document.documentElement.classList.add("lighting");
    const b = byId.get(id);
    lit.textContent = near(id).map(([label, xs]) => label + xs.map((x) => name(byId.get(x))).join(", ")).join(" · ")
      || `${name(b)}: no road to or from it.`;
    lit.hidden = false;
  }
  function unlight() {
    document.documentElement.classList.remove("lighting");
    for (const el of document.querySelectorAll(".is-near, .is-focus")) el.classList.remove("is-near", "is-focus");
    lit.hidden = true;
  }
  // Letting go anywhere (or the town redrawn under the finger) puts the town back.
  document.addEventListener("pointerup", () => { clearTimeout(pressTimer); if (pressed) unlight(); });
  document.addEventListener("pointercancel", () => { clearTimeout(pressTimer); if (pressed) unlight(); });

  function pressable(el, b) {
    el.dataset.b = b.id;
    el.addEventListener("pointerdown", (e) => {
      if (e.button > 0) return;
      pressed = false;
      clearTimeout(pressTimer);
      pressTimer = setTimeout(() => { pressed = true; navigator.vibrate?.(20); light(b.id); }, PRESS_MS);
    });
    const end = () => { clearTimeout(pressTimer); if (pressed) unlight(); };
    for (const ev of ["pointerup", "pointercancel", "pointerleave"]) el.addEventListener(ev, end);
    el.addEventListener("contextmenu", (e) => e.preventDefault());
    el.addEventListener("click", (e) => { if (pressed) { pressed = false; e.preventDefault(); return; } about(b); });
    return el;
  }

  const name = (b) => (b.title_plain || b.title);

  // A tile per building that asks, and one per question of no building the phone knows (its ork's name and
  // the Barracks' mark); `key` keeps which one is open across the town's updates.
  function tile(key, b, alerts) {
    const isOpen = open === key;
    const longest = Math.max(0, ...alerts.map((a) => a.waited || 0));
    const who = alerts.map((a) => a.who).filter(Boolean)[0] || "An ork";
    const head = h("button", { class: "tile-head", type: "button", "aria-expanded": String(isOpen),
      onclick: () => { open = isOpen ? "" : key; ctx.rerender(); } },
      h("span", { class: "tile-mark" }, mark(b ? b.type : "barracks", camp)),
      h("span", { class: "tile-name" }, b ? name(b) : who,
        h("small", { class: longest > LONG_WAIT_S ? "warn" : "muted" },
          !alerts.length ? "asks" : b ? `${who}${alerts.length > 1 ? ` +${alerts.length - 1}` : ""} · waiting ${minutes(longest)}`
            : `waiting ${minutes(longest)}`)),
      h("span", { class: "chev", "aria-hidden": "true" }, isOpen ? "▾" : "▸"));
    return h("article", { class: `tile asks${isOpen ? " is-open" : ""}` }, head,
      isOpen && h("div", { class: "tile-body" }, ...(alerts.length ? alerts.map((a) => (a.questions ? poolQuestion(a, ctx, alerts.length > 1 || !b)
        : question(a, ctx, alerts.length > 1 || !b)))
        : [h("p", { class: "muted" }, "It asks at the computer.")])));
  }

  function row(b, k) {
    return pressable(h("button", { class: `row-b ${k}`, type: "button" },
      h("span", { class: "tile-mark" }, mark(b.type, camp)),
      h("span", { class: "tile-name" }, name(b)),
      h("span", { class: `state ${k}` }, k === "trouble" ? (b.state || "error").toLowerCase() : "at work")), b);
  }

  function render(s) {
    camp = s.look !== "office";
    const alerts = [...(s.alerts || []), ...(s.pool_questions || [])];
    const buildings = s.buildings || [];
    for (const id of answered.keys()) if (!alerts.some((a) => a.id === id)) answered.delete(id);
    byId = new Map(buildings.map((b) => [b.id, b]));
    roads = links(s.roads);
    const asking = new Map();            // building id → its questions, the longest wait first (as `alerts` come)
    const loose = [];                    // questions of no building the phone knows
    for (const a of alerts) {
      if (a.building && byId.has(a.building)) {
        if (!asking.has(a.building)) asking.set(a.building, []);
        asking.get(a.building).push(a);
      } else loose.push(a);
    }
    for (const b of buildings) if (kind(b, asking) === "asks" && !asking.has(b.id)) asking.set(b.id, []);
    asks = asking;
    // An open sheet follows its building's questions (one answered there, one come or gone), nothing else: what is
    // typed in it stays.
    if (info.el.open && shown.id && byId.has(shown.id) && sheetKey(shown.id) !== shown.key) about(byId.get(shown.id));
    const entries = [...loose.map((a) => [`a:${a.id}`, null, [a]]), ...[...asking].map(([id, qs]) => [id, byId.get(id), qs])]
      .sort((x, y) => Math.max(0, ...y[2].map((a) => a.waited || 0)) - Math.max(0, ...x[2].map((a) => a.waited || 0)));
    if (open === null || (open && !entries.some(([key]) => key === open))) open = entries[0]?.[0] || null;
    const space = chosenSpace(s);

    const n = alerts.length;
    camp_.render(s, buildings.filter((b) => !(space && (s.orkspaces || []).length > 1) || new Set(space.buildings).has(b.id)), asking);
    const longest = Math.max(0, ...alerts.map((a) => a.waited || 0));
    summary.textContent = n ? `${n === 1 ? "An ork waits" : `${n} orks wait`} on you, the longest ${minutes(longest)}.`
      : "No ork is waiting on you.";
    summary.classList.toggle("asks", n > 0);
    summary.classList.toggle("long", longest > LONG_WAIT_S);
    tiles.replaceChildren(...entries.map(([key, b, qs]) => tile(key, b, qs)));
    answers.el.hidden = !entries.length;    // nobody asks: no Answers at all

    // The orkspace's buildings (every building, in a town of one or of none known); the questions stay the
    // whole town's, whatever orkspace they come from.
    const all = s.orkspaces || [];
    spaces.hidden = all.length < 2;
    spaces.replaceChildren(...(all.length < 2 ? [] : all.map((o) => h("button", { class: `ok-tab${o === space ? " is-active" : ""}`,
      type: "button", role: "tab", "aria-selected": String(o === space),
      onclick: () => { pickSpace(o.id); ctx.rerender(); } },
      o.icon && camp ? h("span", { "aria-hidden": "true" }, o.icon) : null, o.name,
      o.questions ? h("span", { class: "q-dot", "aria-label": `${o.questions} asking` }, String(o.questions)) : null))));
    const inSpace = space && all.length > 1 ? new Set(space.buildings) : null;
    const here = buildings.filter((b) => !inSpace || inSpace.has(b.id));
    const shown = here.filter((b) => b.id !== s.widget?.id);   // the widget's board stands open (fields.js)
    const trouble = shown.filter((b) => kind(b, asking) === "trouble");
    const work = shown.filter((b) => kind(b, asking) === "work");
    rows.replaceChildren(...trouble.map((b) => row(b, "trouble")), ...work.map((b) => row(b, "work")));
    rows.hidden = !trouble.length && !work.length;
    const quiet = shown.filter((b) => kind(b, asking) === "quiet");
    quietHead.textContent = `Quiet · ${quiet.length}`;
    quietHead.hidden = !quiet.length;
    const quietIds = new Set(quiet.map((b) => b.id));
    // A chain with one quiet building left in the grid (the rest ask, are in trouble or at work) stands with the
    // ones no road touches: a block of one says nothing.
    const groups = chains(here.map((b) => b.id), s.roads).map((g) => ({ ...g, ids: g.ids.filter((id) => quietIds.has(id)) }));
    const single = new Set(groups.filter((g) => g.linked && g.ids.length === 1).map((g) => g.ids[0]));
    const blocks = groups.filter((g) => g.linked && g.ids.length > 1);
    const rest = quiet.map((b) => b.id).filter((id) => single.has(id) || groups.some((g) => !g.linked && g.ids.includes(id)));
    if (rest.length) blocks.push({ linked: false, ids: rest });
    grid.replaceChildren(...blocks.map((g) => h("ul", { class: `grid${g.linked ? " linked" : ""}` },
      ...g.ids.map((id, i) => {
        const b = byId.get(id);
        const fed = g.linked && i > 0 && (roads.into.get(g.ids[i - 1]) || []).includes(id);   // the one before sends to it
        return h("li", { class: fed ? "fed" : "" }, pressable(h("button", { class: "cell", type: "button",
          "aria-label": `${name(b)}, quiet` },
          h("span", { class: "cell-mark" }, mark(b.type, camp)), h("span", { class: "cell-name" }, name(b))), b));
      }))));
  }

  const openId = (id) => { const b = byId.get(id); if (b) about(b); };
  return { parts: [camp_.el, answers.el, town.el, info.el], render, open: openId };
}

/** A question, its last lines and its answers; `who` says who asks and how long (a tile of one question of
 *  a building says it in its head already). */
export function question(a, ctx, who = true) {
  const msg = h("p", { class: "warn", hidden: true });
  const answer = (name, args, said, buttons) => give(a, ctx, name, args, said, buttons, msg);
  const buttons = [];
  for (const [key, label] of a.options || []) {
    buttons.push(h("button", { class: "ok-btn", type: "button",
      onclick: () => answer("orders.answer", { id: a.id, key }, label || key, buttons) }, label || key));
  }
  if (a.advice) {
    buttons.push(h("button", { class: "ok-btn primary", type: "button",
      onclick: () => answer("orders.follow", { id: a.id }, "as the Advisor suggests", buttons) }, "Follow the Advisor"));
  }
  if (answered.has(a.id)) return said(a.id, h("h3", { class: "title" }, a.title));
  return h("div", { class: "question" },
    who && h("p", { class: (a.waited || 0) > LONG_WAIT_S ? "warn" : "muted" }, `${a.who || "An ork"} · waiting ${minutes(a.waited || 0)}`),
    h("h3", { class: "title" }, a.title),
    (a.context || []).length > 0 && h("pre", {}, a.context.join("\n")),
    a.advice && h("p", { class: "advice" }, `The Advisor suggests ${a.advice.key}: ${a.advice.why}`),
    h("div", { class: "answers" }, buttons), msg);
}

// An answer given: sent now, or kept on the phone with no signal and sent when it returns (app.js `deliver`).
async function give(a, ctx, name, args, said, buttons, msg) {
  buttons.forEach((b) => { b.disabled = true; });
  const r = ctx.deliver ? await ctx.deliver(name, args, `${a.who || "An ork"}: ${said}`) : await ctx.send(name, args);
  if (!r.ok) {
    msg.textContent = r.error;
    msg.hidden = false;
    buttons.forEach((b) => { b.disabled = false; });
    return;
  }
  answered.set(a.id, { said, kept: Boolean(r.kept) });   // said at once; the question leaves with the town's next update
  ctx.flash?.(r.kept ? `Kept: ${said}. It is sent when the signal returns.` : `Answered: ${said}`);
  ctx.rerender?.();
}

function said(id, ...head) {
  const { said: what, kept } = answered.get(id);
  return h("div", { class: "question" }, ...head, h("p", { class: kept ? "warn" : "done", role: "status" },
    kept ? `Kept: ${what}. It is sent when the signal returns.` : `Answered: ${what}. The ork goes on.`));
}

/** An Agent pool ork's questions (A2: pinned on top of its task), with their context: the task they are pinned
 *  on, why it waits (and when the steward decides it), the assumptions the ork made. Each question's answers are
 *  one tap (one question) or picked into the line; the line is sent as the answer. */
export function poolQuestion(q, ctx, who = true) {
  const msg = h("p", { class: "warn", hidden: true });
  const head = [
    who && h("p", { class: (q.waited || 0) > LONG_WAIT_S ? "warn" : "muted" }, `${q.who || "An ork"} · waiting ${minutes(q.waited || 0)}`),
    q.cart && h("p", { class: "pinned" }, h("b", {}, "On: "), q.cart),
  ];
  if (answered.has(q.id)) return said(q.id, ...head);
  const line = h("input", { class: "ok-input", maxlength: "2000", enterkeyhint: "send", "aria-label": "Your answer", placeholder: "Reply…" });
  const reply = h("button", { class: "ok-btn primary", type: "button" }, "Reply");
  const buttons = [reply];
  const send = (text) => give(q, ctx, "act", { id: q.building, act: "answer", args: { task: q.task, text } }, text, buttons, msg);
  const one = q.questions.length === 1;
  const blocks = q.questions.map((x) => h("div", { class: "pool-q" }, h("h3", { class: "title" }, x.text),
    x.options.length > 0 && h("div", { class: "answers" }, ...x.options.map((o) => {
      const b = h("button", { class: "ok-btn", type: "button",
        onclick: () => (one ? send(o) : (line.value = `${line.value ? `${line.value}\n` : ""}${x.text} → ${o}`)) }, o);
      buttons.push(b);
      return b;
    }))));
  reply.addEventListener("click", () => { if (line.value.trim()) send(line.value.trim()); });
  line.addEventListener("keydown", (e) => { if (e.key === "Enter" && line.value.trim()) send(line.value.trim()); });
  return h("div", { class: "question pool" }, ...head, ...blocks,
    q.wait && h("p", { class: "muted" }, q.wait),
    q.assumptions ? h("p", { class: "muted" }, `${q.assumptions} assumption${q.assumptions === 1 ? "" : "s"} marked: read them at the computer.`) : null,
    h("div", { class: "row" }, line, reply), msg);
}
