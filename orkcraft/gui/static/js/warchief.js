// The Warchief's line (docs/design/calm-town.md §4): one input at the town's bottom middle, the way to build,
// to command and to ask. `/` or Ctrl+K focuses it from anywhere, Esc leaves it, ↑ walks its history.
//
//   empty    hints over it that follow the town's state, by rules, no model (`hints`)
//   /word    the commands, completed as typed; one runs at once, with no model (`COMMANDS`)
//   @name    names a building; the building open in the panel stands in the line as a chip already
//   words    go to the Warchief (core/workers/town_hall.py `ask`); its answer unrolls over the line, the
//            last few messages, and its whole chat is the Town Hall's Chat tab
//
// Its cards (the work it gave a specialist: a plan, a building, a road, an ork, a change) stand in its
// answers, Build / Cancel / Undo on them (js/buildings/town_hall.js `Card`, core/warchief.py). A press over
// the line never takes the focus from the field, so what it shows stays put under the mouse.
// While it is left alone the line says what wants a decision first: an ork's question (§8).
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { act, command, details, town, say } from "./link.js";
import { opened, openBuilding } from "./windows.js";
import { building as buildOpen, laying, demolishing } from "./build.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";
import { HALL, hallTab } from "./tent.js";
import { Message } from "./buildings/town_hall.js";
import { WarchiefHead } from "./icons.js";

const THREAD = 3;                          // the last messages shown over the line
const HISTORY = 30;                        // lines ↑ walks back through
const SEEN_MS = 45_000;                    // an answer stays over the line this long after it came

export const line = signal({ text: "", about: [], focus: 0 });   // about: building ids named as chips; focus: a tick
const history = [];

function input() {
  return document.querySelector(".gui-warchief__input");
}

/** Put a building in the line as a chip and focus it (the hut's menu: Ask the Warchief about it). */
export function mention(b) {
  const l = line.value;
  line.value = { ...l, about: l.about.includes(b.id) ? l.about : [...l.about, b.id], focus: l.focus + 1 };
}

/** Fill the line with words and focus it (a hint that needs more words). */
export function fill(text) {
  line.value = { ...line.value, text, focus: line.value.focus + 1 };
}

// `/` or Ctrl+K: the line, from anywhere but a field, a terminal or a dialog.
window.addEventListener("keydown", (e) => {
  const k = (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k");
  if (!k || document.querySelector(".gui-modal")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  const el = input();
  if (!el) return;
  e.preventDefault();
  el.focus();
  if (e.key === "/" && !el.value) fill("/");
});

// -- the town: buildings by name, the hall's chat -------------------------------------------------------

function here() {
  const t = town.value;
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  return t.buildings.filter((b) => ids.has(b.id) && b.id !== HALL);
}

const norm = (s) => say(s || "").toLowerCase().replace(/\s+/g, " ").trim();

/** The building a word names: its id, its title or the start of its title (case aside). */
function named(word) {
  const w = norm(word).replace(/^@/, "");
  if (!w) return null;
  const all = town.value.buildings;
  return all.find((b) => b.id === w) || all.find((b) => norm(b.title) === w) || all.find((b) => norm(b.title).startsWith(w)) || null;
}

/** "@Forge @Pit rest" → [Forge, Pit] and "rest"; names may hold spaces when the chip wrote them whole. */
function takeNames(text, about) {
  const found = about.map((id) => town.value.buildings.find((b) => b.id === id)).filter(Boolean);
  let rest = text;
  const titles = town.value.buildings.map((b) => say(b.title)).sort((a, b) => b.length - a.length);
  for (;;) {
    const m = rest.match(/@(\S+)/);
    if (!m) break;
    const at = rest.indexOf(m[0]);
    const whole = titles.find((t) => rest.slice(at + 1, at + 1 + t.length).toLowerCase() === t.toLowerCase());
    const word = whole || m[1];
    const b = named(word);
    if (!b) break;
    if (!found.includes(b)) found.push(b);
    rest = (rest.slice(0, at) + rest.slice(at + 1 + word.length)).replace(/\s+/g, " ");
  }
  return { found, rest: rest.trim() };
}

function hall() {
  const d = details.value[HALL];
  return (d && d.data) || null;
}

function ask(text, about) {
  const t = town.value;
  const names = about.map((id) => t.buildings.find((b) => b.id === id)).filter(Boolean);
  const said = names.length ? `${names.map((b) => `@${say(b.title)}`).join(" ")} ${text}` : text;
  return act(HALL, "ask", { text: said, about: names.map((b) => b.id) });
}

// -- the commands: no model, at once ---------------------------------------------------------------------

function amongFor(to) {
  return here().map((b) => b.id).concat(HALL).filter((id) => id !== to);
}

/** The command words and what each does; `args` the rest of the line, `bs` the buildings it names. */
export const COMMANDS = [
  { word: "build", args: "[what]", about: "raise a building: the catalog, or the one named",
    run: (rest) => {
      const types = buildTypes.value;
      const t = rest && types && types.find((x) => x.id === rest.toLowerCase() || norm(x.title) === norm(rest));
      if (t) return command("town.build", { type: t.id }).then((id) => id && openBuilding(id), () => {});
      buildOpen.value = rest ? { need: rest } : true;
      return null;
    } },
  { word: "road", args: "@from @to", about: "lay a road: from one building into another, or into one",
    run: (rest, bs) => {
      if (bs.length >= 2) laying.value = { from: bs[0].id, to: bs[1].id };
      else if (bs.length === 1) laying.value = { from: null, to: bs[0].id, among: amongFor(bs[0].id) };
      else return "Name the building the road goes into: /road @Forge";
      return null;
    } },
  { word: "recruit", args: "@building what it does", about: "hire an ork: the Recruiter picks the cheapest that can",
    run: (rest, bs) => {
      if (!bs.length) return "Name the building: /recruit @Forge reads new tickets";
      if (!rest) { openBuilding(bs[0].id, "info"); return null; }
      return command("building.recruit_ask", { id: bs[0].id, prompt: rest }).catch(() => {});
    } },
  { word: "open", args: "@building", about: "open a building in the panel",
    run: (rest, bs) => (bs.length ? (openBuilding(bs[0].id), null) : "Name the building: /open @Forge") },
  { word: "demolish", args: "@building", about: "take a building down (it asks first)",
    run: (rest, bs) => (bs.length ? ((demolishing.value = bs[0].id), null) : "Name the building: /demolish @Forge") },
  { word: "orders", args: "", about: "the orks' questions", run: () => { openOrders(); return null; } },
  { word: "halt", args: "", about: "stop every ork at work", run: () => command("halt").catch(() => {}) },
  { word: "orkspace", args: "name", about: "go to an orkspace, or make a new one",
    run: (rest) => {
      if (!rest) return "Name it: /orkspace Billing";
      const o = town.value.orkspaces.find((x) => norm(x.name) === norm(rest));
      return o ? command("orkspace.select", { id: o.id }).catch(() => {}) : command("orkspace.new", { name: rest }).catch(() => {});
    } },
  { word: "sessions", args: "", about: "the War Tent: every session, its terminal",
    run: () => { hallTab.value = "sessions"; openBuilding(HALL, "work"); return null; } },
  { word: "audit", args: "", about: "the Warder, the Pathfinder and the Treasurer look over the town",
    run: () => act(HALL, "audit").catch(() => {}) },
  { word: "settings", args: "", about: "how freely the orks decide", run: () => { settingsOpen.value = true; return null; } },
  { word: "new", args: "", about: "a fresh chat with the Warchief", run: () => act(HALL, "forget").catch(() => {}) },
];

const buildTypes = signal(null);           // the catalog, asked once for /build

function commandOf(text) {
  const m = text.match(/^\/(\S*)\s*(.*)$/s);
  if (!m) return null;
  const word = m[1].toLowerCase();
  return { word, rest: m[2], cmd: COMMANDS.find((c) => c.word === word) || null };
}

// -- hints: the town's state, by rules -------------------------------------------------------------------

const STARTERS = ["I want my pull requests reviewed", "Sort my inbox into tasks", "Tell me when CI breaks and why"];

/** Three or four hints for the town as it is: {label, run} or {label, text} (fills the line). */
export function hints() {
  const t = town.value;
  const out = [];
  if (t.alerts.length) out.push({ label: `❓ ${say("Answer")} ${t.alerts.length} ${t.alerts.length === 1 ? "question" : "questions"}`, run: () => openOrders() });
  const b = opened.value.active && opened.value.active !== HALL && t.buildings.find((x) => x.id === opened.value.active);
  const name = b && say(b.title);
  if (b) {
    out.push({ label: say(`Add an ork to ${name}`), text: `/recruit @${name} ` });
    out.push({ label: say(`Connect ${name} to…`), run: () => { laying.value = { from: null, to: b.id, among: amongFor(b.id) }; } });
    out.push({ label: say(`What did ${name} do today?`), ask: `What did it do today?`, about: [b.id] });
  } else if (!here().length) {
    for (const s of STARTERS) out.push({ label: s, ask: s });
    out.push({ label: say("Pick a building from the catalog"), run: () => { buildOpen.value = true; } });
  } else {
    if (t.hud.gold_level === "warn" || t.hud.gold_level === "over") out.push({ label: say("Where does the gold go?"), ask: "Where does the gold go?" });
    out.push({ label: say("What happened today?"), ask: "What happened in the town today?" });
    out.push({ label: say("Build something new"), text: "I want " });
    out.push({ label: say("Connect two buildings"), text: "/road @" });
  }
  return out.slice(0, 4);
}

// -- the line ---------------------------------------------------------------------------------------

function Chip({ b, onDrop }) {
  return html`<span class="gui-warchief__chip ok-font-status">@${say(b.title)}
    <button class="gui-tab__close" aria-label=${say(`Not about ${b.title}`)} onClick=${onDrop}>×</button></span>`;
}

/** What stands over the line: the hints, the commands as typed, the buildings an @ may name. */
function Over({ text, onPick }) {
  const c = commandOf(text);
  if (c && !text.includes(" ")) {
    const list = COMMANDS.filter((x) => x.word.startsWith(c.word));
    return html`<ul class="ok-list__items gui-warchief__list" role="listbox">
      ${list.map((x) => html`<li key=${x.word} class="ok-item" role="option" onPointerDown=${(e) => { e.preventDefault(); onPick({ text: `/${x.word} ` }); }}>
        <span class="ok-font-mono">/${x.word}</span> <span class="ok-tone-muted">${x.args}</span><span class="meta">${say(x.about)}</span></li>`)}
      ${!list.length && html`<li class="ok-tone-muted">${say("No such command — a line without / goes to the Warchief")}</li>`}
    </ul>`;
  }
  const at = text.match(/@([^@\s]*)$/);
  if (at) {
    const w = at[1].toLowerCase();
    const list = here().filter((b) => norm(b.title).startsWith(w) || b.id.startsWith(w)).slice(0, 8);
    return list.length ? html`<ul class="ok-list__items gui-warchief__list" role="listbox">
      ${list.map((b) => html`<li key=${b.id} class="ok-item" role="option"
          onPointerDown=${(e) => { e.preventDefault(); onPick({ text: text.slice(0, text.length - at[0].length) + `@${say(b.title)} ` }); }}>
        @${say(b.title)}</li>`)}</ul>` : null;
  }
  if (text) return null;
  return html`<div class="gui-warchief__hints">${hints().map((h, i) => html`<button key=${i} class="ok-btn gui-warchief__hint"
      onPointerDown=${(e) => { e.preventDefault(); onPick(h); }}>${h.label}</button>`)}</div>`;
}

function Thread({ data }) {
  const box = useRef(null);
  const chat = data.chat.slice(-THREAD);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [data.chat.length, data.thinking]);
  if (!chat.length && !data.thinking) return null;
  return html`<ul class="gui-rows gui-warchief__thread" ref=${box}>
    ${chat.map((m, i) => html`<${Message} key=${data.chat.length - chat.length + i} m=${m} name=${data.warchief} />`)}
    ${data.thinking && html`<li class="ok-font-status ok-tone-wait">${say(`${data.warchief} is answering…`)}</li>`}
  </ul>`;
}

/** What wants a decision first, while the line is left alone: an ork's question, else the spend at its
 *  limit. Always mounted: a part before the field that comes and goes would move the field, and a moved
 *  field loses its focus. */
function Speaks({ hidden }) {
  const t = town.value;
  const a = t.alerts[0];
  if (hidden) return null;
  if (a) {
    return html`<button class="gui-warchief__speaks ok-font-status ok-tone-fire" title=${a.title}
        onPointerDown=${(e) => e.preventDefault()} onClick=${() => openOrders(a.id)}>
      ❓ ${a.who ? `${a.who}: ` : ""}${a.title} · <u>${say("answer")}</u></button>`;
  }
  const news = t.growth && t.growth.news.length ? t.growth.news[t.growth.news.length - 1] : null;
  if (news) {                                  // what grew (docs/design/growth.md §3): said once, then seen
    const seen = () => command("growth.seen", { id: news.id }).catch(() => {});
    const go = () => {
      seen();
      if (news.building) openBuilding(news.building, "info");
      else settingsOpen.value = true;
    };
    return html`<span class="gui-warchief__speaks ok-font-status gui-warchief__news">
      <button class="gui-link" title=${say(news.text)} onPointerDown=${(e) => e.preventDefault()} onClick=${go}>
        ${news.icon} ${say(news.text)}</button>
      <button class="gui-link" title=${say("Seen")} aria-label=${say("Seen")} onPointerDown=${(e) => e.preventDefault()}
        onClick=${seen}>✕</button></span>`;
  }
  const level = t.hud.gold_level;
  if (t.hud.show_gold && (level === "warn" || level === "over")) {
    return html`<button class="gui-warchief__speaks ok-font-status ok-tone-wait" title=${say("Ask where the gold goes")}
        onPointerDown=${(e) => e.preventDefault()} onClick=${() => ask("Where does the gold go, and what can spend less?", []).catch(() => {})}>
      ⚠ ${say(level === "over" ? "Spend is over its limit" : "Spend is near its limit")} (${t.hud.gold}) · <u>${say("where does it go?")}</u></button>`;
  }
  return null;
}

export function WarchiefLine() {
  const t = town.value;
  const l = line.value;
  const ref = useRef(null);
  const [focused, setFocused] = useState(false);
  const [shown, setShown] = useState(0);         // when the last answer came (it stays over the line a while)
  const [said, setSaid] = useState("");          // what a command answered (a word on how to use it)
  const [back, setBack] = useState(-1);          // where ↑ is in the history
  const data = hall();
  const b = t.buildings.find((x) => x.id === HALL);
  const chips = l.about.map((id) => t.buildings.find((x) => x.id === id)).filter(Boolean);
  const open = opened.value.active;
  const auto = open && open !== HALL && !l.about.includes(open) ? t.buildings.find((x) => x.id === open) : null;

  useEffect(() => { if (l.focus && ref.current) ref.current.focus(); }, [l.focus]);
  useEffect(() => { if (focused && buildTypes.value === null) command("town.catalog").then((x) => { buildTypes.value = x; }, () => {}); }, [focused]);
  const n = data ? data.chat.length : 0;
  const seen = useRef(null);                     // the chat's length when the page first had it: older words stay folded
  useEffect(() => {
    if (!data) return;
    if (seen.current === null) { seen.current = n; return; }
    if (n > seen.current || data.thinking) setShown(Date.now());
    seen.current = n;
  }, [n, data && data.thinking]);
  useEffect(() => {
    if (!shown) return undefined;
    const id = setTimeout(() => setShown(0), SEEN_MS);
    return () => clearTimeout(id);
  }, [shown]);

  const set = (text) => { line.value = { ...line.value, text }; setSaid(""); };
  const clear = () => { line.value = { ...line.value, text: "", about: [] }; setBack(-1); };

  function pick(h) {
    if (h.run) { h.run(); return; }
    if (h.ask) { ask(h.ask, h.about || (auto ? [auto.id] : [])).catch(() => {}); clear(); return; }
    set(h.text);
    if (ref.current) ref.current.focus();
  }

  function send(value) {                       // the field's own value: a render may not have caught up yet
    const text = value.trim();
    if (!text) return;
    history.unshift(text);
    history.length = Math.min(history.length, HISTORY);
    const c = commandOf(text);
    if (c) {
      if (!c.cmd) { setSaid(say(`No command /${c.word} — / lists them`)); return; }
      const { found, rest } = takeNames(c.rest, [...l.about, ...(auto ? [auto.id] : [])]);
      const r = c.cmd.run(rest, found);
      if (typeof r === "string") { setSaid(say(r)); return; }
      clear();
      if (ref.current) ref.current.blur();
      return;
    }
    const { found, rest } = takeNames(text, [...l.about, ...(auto ? [auto.id] : [])]);
    ask(rest || text, found.map((x) => x.id)).catch(() => {});
    clear();
  }

  function key(e) {
    if (e.key === "Enter") { e.preventDefault(); send(e.currentTarget.value); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (l.text) set(""); else e.currentTarget.blur(); }
    else if (e.key === "ArrowUp" && history.length && (!l.text || back >= 0)) {
      e.preventDefault();
      const i = Math.min(back + 1, history.length - 1);
      setBack(i); set(history[i]);
    } else if (e.key === "ArrowDown" && back >= 0) {
      e.preventDefault();
      const i = back - 1;
      setBack(i); set(i >= 0 ? history[i] : "");
    } else if (e.key === "Backspace" && !l.text && l.about.length) {
      line.value = { ...l, about: l.about.slice(0, -1) };
    } else if (e.key === "Tab" && e.currentTarget.value.startsWith("/") && !e.currentTarget.value.includes(" ")) {
      const c = COMMANDS.find((x) => x.word.startsWith(e.currentTarget.value.slice(1).toLowerCase()));
      if (c) { e.preventDefault(); set(`/${c.word} `); }
    }
  }

  if (!b) return null;
  const name = data ? data.warchief : say("Warchief");
  const thread = !!data && (focused || !!shown || data.thinking);
  return html`<div class=${cls("gui-warchief", { "is-focused": focused, "is-alert": t.alerts.length > 0 })}>
    ${focused || thread || !!said ? html`<div key="over" class="ok-win gui-warchief__over"
        onMouseDown=${(e) => { if (!e.target.closest("input, textarea, select")) e.preventDefault(); }}>
      <div class="ok-win__frame"><div class="ok-win__body">
        ${thread && html`<${Thread} data=${data} />`}
        ${said && html`<p class="ok-font-status ok-tone-wait gui-warchief__said">${said}</p>`}
        ${focused && html`<${Over} text=${l.text} onPick=${pick} />`}
      </div></div></div>` : null}
    <div key="bar" class="gui-warchief__bar">
      <button class="gui-warchief__face" title=${say(`${b.title}: the ${name}'s whole chat, the hall`)} aria-label=${say(b.title)}
        onClick=${() => { hallTab.value = "chat"; openBuilding(HALL, "work"); }}>
        <${WarchiefHead} state=${b.alert ? "waiting" : data && data.thinking ? "busy" : ""} />
        ${b.alert && html`<span class="ok-word gui-warchief__ask">?</span>`}
      </button>
      <${Speaks} hidden=${focused || !!l.text || chips.length > 0} />
      ${auto ? html`<span class="gui-warchief__chip is-auto ok-font-status" title=${say("The building open in the panel")}>@${say(auto.title)}</span>` : null}
      ${chips.map((x) => html`<${Chip} key=${x.id} b=${x} onDrop=${() => { line.value = { ...l, about: l.about.filter((id) => id !== x.id) }; }} />`)}
      <input ref=${ref} class="ok-input gui-warchief__input" value=${l.text} aria-label=${say(`Ask the ${name}`)}
        placeholder=${say(`Ask the ${name}… or / for commands`)}
        onInput=${(e) => set(e.target.value)} onKeyDown=${key}
        onFocus=${() => setFocused(true)} onBlur=${() => { setFocused(false); setSaid(""); }} />
      ${data && data.thinking && html`<span class="gui-hut__spin" role="img" title=${say(`${name} is answering`)}></span>`}
    </div>
  </div>`;
}
