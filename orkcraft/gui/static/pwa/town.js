// The town on the phone (docs/design/mobile.md §10), as a phone's home screen: what wants the person stands as
// tiles at the top — a building whose ork asks opens to its question and its answers, one tile open at a time —
// then the buildings in trouble and at work as rows, then every quiet building as a mark with its name, in a
// grid. A tap on a row or a mark says what the building is doing; its window opens on the computer.

import { h, minutes, sheet } from "./util.js";
import { mark } from "./icons.js";

const TROUBLE = new Set(["ERROR", "NO WIKI"]);
const AT_WORK = new Set(["WORKING", "BUSY", "PENDING", "EDITING"]);
const LONG_WAIT_S = 600;                 // a question waiting longer than this is said in the warning's colour

/** What a building is now: "asks" | "trouble" | "work" | "quiet". */
export function kind(b, asked) {
  if (b.alert || b.state === "ASKS" || asked.has(b.id)) return "asks";
  if (TROUBLE.has(b.state)) return "trouble";
  if (AT_WORK.has(b.state)) return "work";
  return "quiet";
}

/** `ctx`: {send}. Returns the parts the app lays out and `render(town)`. */
export function makeTown(ctx) {
  const summary = h("p", { class: "summary" });
  const tiles = h("div", { class: "tiles" });
  const rows = h("div", { class: "rows" });
  const grid = h("ul", { class: "grid", "aria-label": "Quiet buildings" });
  const quietHead = h("h2", {}, "Buildings");
  const info = sheet("");
  const infoBody = h("div", { class: "info" });
  info.el.querySelector(".sheet-in").append(infoBody);
  let open = null;                       // the key of the tile that is open; null: the longest-waiting one
  let camp = true;

  function about(b) {
    info.title(camp ? b.title : (b.title_plain || b.title));
    const k = kind(b, new Set());
    infoBody.replaceChildren(
      h("div", { class: "info-mark" }, mark(b.type, camp)),
      h("p", {}, k === "quiet" ? "Quiet: nothing waits on it now." : `Now: ${(b.state || k).toLowerCase()}.`),
      h("p", { class: "muted" }, "Its window opens on the computer: the phone shows the town and answers its questions."));
    info.open();
  }

  const name = (b) => (camp ? b.title : (b.title_plain || b.title));

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
      isOpen && h("div", { class: "tile-body" }, ...(alerts.length ? alerts.map((a) => question(a, ctx, alerts.length > 1 || !b))
        : [h("p", { class: "muted" }, "It asks at the computer.")])));
  }

  function row(b, k) {
    return h("button", { class: `row-b ${k}`, type: "button", onclick: () => about(b) },
      h("span", { class: "tile-mark" }, mark(b.type, camp)),
      h("span", { class: "tile-name" }, name(b)),
      h("span", { class: `state ${k}` }, k === "trouble" ? (b.state || "error").toLowerCase() : "at work"));
  }

  function render(s) {
    camp = s.look !== "office";
    const alerts = s.alerts || [];
    const buildings = s.buildings || [];
    const byId = new Map(buildings.map((b) => [b.id, b]));
    const asking = new Map();            // building id → its questions, the longest wait first (as `alerts` come)
    const loose = [];                    // questions of no building the phone knows
    for (const a of alerts) {
      if (a.building && byId.has(a.building)) {
        if (!asking.has(a.building)) asking.set(a.building, []);
        asking.get(a.building).push(a);
      } else loose.push(a);
    }
    for (const b of buildings) if (kind(b, asking) === "asks" && !asking.has(b.id)) asking.set(b.id, []);
    const entries = [...loose.map((a) => [`a:${a.id}`, null, [a]]), ...[...asking].map(([id, qs]) => [id, byId.get(id), qs])]
      .sort((x, y) => Math.max(0, ...y[2].map((a) => a.waited || 0)) - Math.max(0, ...x[2].map((a) => a.waited || 0)));
    if (open === null || (open && !entries.some(([key]) => key === open))) open = entries[0]?.[0] || null;

    const n = alerts.length;
    const longest = Math.max(0, ...alerts.map((a) => a.waited || 0));
    summary.textContent = n ? `${n === 1 ? "An ork waits" : `${n} orks wait`} on you, the longest ${minutes(longest)}.`
      : "No ork is waiting on you.";
    summary.classList.toggle("asks", n > 0);
    summary.classList.toggle("long", longest > LONG_WAIT_S);
    tiles.replaceChildren(...entries.map(([key, b, qs]) => tile(key, b, qs)));

    const trouble = buildings.filter((b) => kind(b, asking) === "trouble");
    const work = buildings.filter((b) => kind(b, asking) === "work");
    rows.replaceChildren(...trouble.map((b) => row(b, "trouble")), ...work.map((b) => row(b, "work")));
    rows.hidden = !trouble.length && !work.length;
    const quiet = buildings.filter((b) => kind(b, asking) === "quiet");
    quietHead.textContent = `Quiet · ${quiet.length}`;
    grid.replaceChildren(...quiet.map((b) => h("li", {}, h("button", { class: "cell", type: "button",
      "aria-label": `${name(b)}, quiet`, onclick: () => about(b) },
      h("span", { class: "cell-mark" }, mark(b.type, camp)), h("span", { class: "cell-name" }, name(b))))));
  }

  return {
    parts: [
      h("section", { class: "card asking", "aria-labelledby": "answers-h" }, h("h2", { id: "answers-h" }, "Answers"), summary, tiles),
      rows,
      h("section", { class: "card quiet" }, quietHead, grid),
      info.el,
    ],
    render,
  };
}

/** A question, its last lines and its answers; `who` says who asks and how long (a tile of one question of
 *  a building says it in its head already). */
export function question(a, ctx, who = true) {
  const msg = h("p", { class: "warn", hidden: true });
  const answer = async (name, args, buttons) => {
    buttons.forEach((b) => { b.disabled = true; });
    const r = await ctx.send(name, args);
    if (!r.ok) {
      msg.textContent = r.error;
      msg.hidden = false;
      buttons.forEach((b) => { b.disabled = false; });
    }
  };
  const buttons = [];
  for (const [key, label] of a.options || []) {
    buttons.push(h("button", { class: "btn", type: "button", onclick: () => answer("orders.answer", { id: a.id, key }, buttons) }, label || key));
  }
  if (a.advice) {
    buttons.push(h("button", { class: "btn primary", type: "button", onclick: () => answer("orders.follow", { id: a.id }, buttons) }, "Follow the Advisor"));
  }
  return h("div", { class: "question" },
    who && h("p", { class: (a.waited || 0) > LONG_WAIT_S ? "warn" : "muted" }, `${a.who || "An ork"} · waiting ${minutes(a.waited || 0)}`),
    h("h3", { class: "title" }, a.title),
    (a.context || []).length > 0 && h("pre", {}, a.context.join("\n")),
    a.advice && h("p", { class: "advice" }, `The Advisor suggests ${a.advice.key}: ${a.advice.why}`),
    h("div", { class: "answers" }, buttons), msg);
}
