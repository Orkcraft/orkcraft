// 🌾 The Task board from inside (decisions-2026-10.md §13.2, I2): the dispatcher's booth, entered from Camp
// (js/inside.js). Three boards on its back wall — To do, Doing, Done — with the board's real cards pinned to them: the
// orks' tasks as parchment sheets, the person's own to-dos as light stone slabs whose checkbox is a small cloth flag
// (lowered on To do, raised on Done: a press on it ticks the to-do off or puts it back). The notes hang beside them,
// narrower, folded to their plaque while empty. The boards hang on the wall, above the floor line; the floor stays in
// sight. A card dragged to another board does what moving a card does on the card (`move`); a to-do dragged to Done
// is ticked off, back to To do put back. A click selects a card (its acts over the boards, as on the
// card), a double click opens it. The Taskmaster and the orks at work walk between the boards, tools in hand (the
// inside poses: carry, lens, quill, pin), a bubble over each with its task in two or three words.
// Art: v3's sprites (design-system-v3.md §8): the booth's backdrop and a board's frame from u6-inside, the parchment
// sheet, the stone slab, the bone pin and the cloth flag from u6-cards, the orks from o5. Each piece is one element with
// its own class, so a sprite drops in by CSS alone (`.has-art`); while the manifest is not read, CSS draws them.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, details } from "../link.js";
import { V3, kit, loadKit, has, orkFile } from "../camp/sprites.js";
import { thought } from "../camp/steward.js";
import { selected, pick, dragCard, Marks, Acts, setDialog, planCard, allCards, noteLanes } from "./fields.js";

const sheet = new URL("./fields_inside.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

// The standard lanes in the words of the booth; a lane the person named keeps its name.
const WORD = { todo: "To do", in_progress: "Doing", done: "Done" };
const POSES = ["pin", "lens", "quill"];
// the u6 sprites as CSS variables on the room, so the stylesheet draws them by `.has-art`
const ART = { booth: "booth", board: "board", sheet: "sheet", slab: "slab", pin: "pin",
  "flag-down": "flag-down", "flag-half": "flag-half", "flag-up": "flag-up" };
const artStyle = () => Object.keys(ART).map((k) => `--in-${k}:url(${V3}inside/${ART[k]}.png)`).join(";");          // what an ork does at a board; it carries between them
const STEP_MS = 2600;                            // a walk from one board to the next
// the booth's backdrop in art pixels (u6-inside #2), its floor from this line down: the boards hang above it, the orks
// walk below it
const BOOTH = { w: 200, h: 109, floor: 78 };

/** The whole multiple of the art pixel that fills the room (its height first, then its width), never under ×2. */
function useScale(ref) {
  const [s, setS] = useState(4);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const fit = () => {
      const r = el.parentElement ? el.parentElement.getBoundingClientRect() : el.getBoundingClientRect();
      if (r.width && r.height) setS(Math.max(2, Math.floor(r.height / BOOTH.h), Math.ceil(r.width / BOOTH.w)));
    };
    const ro = new ResizeObserver(fit);
    ro.observe(el.parentElement || el);
    fit();
    return () => ro.disconnect();
  }, []);
  return s;
}

const cut = (s, n = 3) => {
  const w = String(s || "").replace(/\s+/g, " ").trim().split(" ");
  return w.length > n ? `${w.slice(0, n).join(" ")}…` : w.join(" ");
};

/** A card dragged onto a board: a to-do onto Done is ticked off, onto To do put back; anything else moves there. */
function useBoardDrop(id, lane, todos) {
  const [over, setOver] = useState(false);
  return [over, {
    onDragOver: (e) => { if (e.dataTransfer.types.includes("text/x-ork-card")) { e.preventDefault(); setOver(true); } },
    onDragLeave: () => setOver(false),
    onDrop: (e) => {
      e.preventDefault(); setOver(false);
      const card = e.dataTransfer.getData("text/x-ork-card");
      if (!card) return;
      const todo = todos && todos.cards.find((c) => c.id === card);
      if (todo && (lane.id === "done" || lane.id === "todo")) {
        if (todo.done !== (lane.id === "done")) act(id, "check", { card }).catch(() => {});
        return;
      }
      act(id, "move", { card, lane: lane.id }).catch(() => {});
    },
  }];
}

/** The cloth flag: lowered on To do, half up on Doing, raised on Done. A to-do's is its checkbox. */
function Flag({ at, onTick, done }) {
  const cl = cls("fields-in__flag", `is-${at}`);
  if (!onTick) return html`<span class=${cl} aria-hidden="true"><i></i></span>`;
  return html`<button type="button" class=${cl} title=${say(done ? "Put it back on my to-dos" : "Tick it off")}
    aria-label=${say(done ? "Put it back on my to-dos" : "Tick it off")} aria-pressed=${done ? "true" : "false"}
    onClick=${(e) => { e.stopPropagation(); onTick(); }} onDblClick=${(e) => e.stopPropagation()}><i></i></button>`;
}

const flagAt = (laneId) => (laneId === "done" ? "up" : laneId === "in_progress" ? "half" : "down");

/** One card pinned to a board: a parchment sheet (a task, a note) or a stone slab (my to-do, with its flag). */
function Pinned({ id, card, laneId, todo, sel, onOpen, onMark, tilt }) {
  const done = todo ? !!card.done : laneId === "done";
  return html`<div class=${cls("fields-in__card", todo ? "is-slab" : "is-sheet", { "is-selected": sel, "is-done": done })}
      data-card=${card.id} data-color=${card.color || undefined} style=${`--tilt:${tilt}deg`} draggable="true"
      onDragStart=${dragCard(card.id)} onClick=${() => pick(id, card.id)} onDblClick=${() => onOpen(card)}>
    <span class="fields-in__pin" aria-hidden="true"></span>
    <span class="fields-in__title">${card.title}${card.new ? html`<span class="ok-word gui-new"> new</span>` : ""}</span>
    <${Marks} card=${card} onMark=${onMark} />
    <${Flag} at=${todo ? (done ? "up" : "down") : flagAt(laneId)} done=${done}
      onTick=${todo ? () => act(id, "check", { card: card.id }).catch(() => {}) : null} />
  </div>`;
}

const tiltOf = (cid) => { let h = 0; for (const ch of cid) h = (h * 31 + ch.charCodeAt(0)) | 0; return ((h % 5) + 5) % 5 - 2; };

/** One board on the back wall: its plaque, its cards, + New at its foot. */
function Board({ id, lane, todos, mine, sel, onOpen, onMark, onAdd, addLabel, notes, folded, onFold, children }) {
  const [over, drop] = useBoardDrop(id, lane, todos);
  const cards = lane.cards.map((c) => ({ c, todo: false })).concat(mine.map((c) => ({ c, todo: true })));
  const word = say(WORD[lane.id] || lane.label);
  if (folded) {
    return html`<section class=${cls("fields-in__board is-notes is-folded", { "gui-drop": over })} data-lane=${lane.id} ...${drop}
        aria-label=${word}>
      <button type="button" class="fields-in__plaque fields-in__fold" aria-expanded="false" title=${say(`Unfold ${word}`)}
        onClick=${onFold}><span>${word}</span><b>${cards.length}</b></button>
    </section>`;
  }
  return html`<section class=${cls("fields-in__board", { "is-notes": notes, "gui-drop": over })} data-lane=${lane.id} ...${drop}
      aria-label=${word}>
    <header class="fields-in__plaque"><span>${word}</span>${onFold && html`<button type="button" class="fields-in__fold-btn"
      aria-expanded="true" title=${say(`Fold ${word}`)} aria-label=${say(`Fold ${word}`)} onClick=${onFold}>‹</button>`}<b>${cards.length}</b></header>
    <div class="fields-in__cards">
      ${cards.map(({ c, todo }) => html`<${Pinned} key=${c.id} id=${id} card=${{ ...c, column: todo ? todos.id : lane.id }} laneId=${lane.id}
        todo=${todo} sel=${c.id === sel} onOpen=${onOpen} onMark=${onMark} tilt=${tiltOf(c.id)} />`)}
      ${!cards.length && html`<p class="fields-in__empty">${say(notes ? "No notes yet" : "Nothing here")}</p>`}
    </div>
    <div class="fields-in__foot">
      ${onAdd && html`<button type="button" class="fields-in__add" onClick=${onAdd}>${say(addLabel)}</button>`}${children}
    </div>
  </section>`;
}

/** An ork's sprite in a pose, its frames stepped in CSS; a plain stand-in while the sheet is not cut. */
function Pose({ pose }) {
  const file = `orks/inside/${pose}.png`;
  const s = kit.value && kit.value[file];
  if (!s) return html`<span class="fields-in__body is-stand-in" data-pose=${pose}></span>`;
  const f = orkFile(file, 2);                               // drawn at ×2: on a dense screen, its cut at one to one
  return html`<span class=${cls("fields-in__body", { "is-hd": f.hd })} data-pose=${pose}
    style=${`--w:${s.w}px;--h:${s.h}px;--frames:${s.frames};background-image:url(${f.url})`}></span>`;
}

/** The orks of the booth: each walks to a board, works there a while, walks on; its bubble its task. */
function Walkers({ orks, boards }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), STEP_MS);
    return () => clearInterval(t);
  }, []);
  return html`<div class="fields-in__floor">${orks.map((o, i) => {
    const n = Math.max(boards, 1), seat = (k) => ((k + i * 2) % n + n) % n;
    const here = seat(Math.floor(tick / 2) + i), before = seat(Math.floor((tick - 1) / 2) + i);
    const walking = tick % 2 === 1 && here !== before;
    const x = ((here + 0.5) / n) * 100 + (i % 2 ? 6 : -6);
    return html`<div key=${o.key} class=${cls("fields-in__ork", { "is-walking": walking, "is-left": here < before, "is-steward": o.steward })}
        style=${`left:${x}%;left:round(${x}%, 1px)`} data-ork=${o.key} title=${say(`${o.name}: ${o.task}`)}>
      <span class="fields-in__bubble">${say(cut(o.task))}</span>
      <${Pose} pose=${walking ? "carry" : POSES[(tick + i) % POSES.length]} />
      <span class="fields-in__name">${say(o.name)}</span>
    </div>`;
  })}</div>`;
}

/** The Taskmaster's bubble: what it asks or why it stopped, as outside; else how many orders wait on To do. */
function stewardTask(b, data) {
  if (b.alert || b.signal || b.paused) return thought(b);
  const todo = data.lanes.find((ln) => ln.id === "todo");
  return todo && todo.cards.length ? `${todo.cards.length} to dispatch` : "Waiting for work";
}

/** The orks in the booth: the Taskmaster, then each ork at work on a Doing card (the steward is not one of them). */
function orksOf(b, data) {
  const doing = (data.lanes.find((ln) => ln.id === "in_progress") || { cards: [] }).cards;
  const busy = (b.garrison || []).filter((o) => o.kind !== "steward" && !o.lead);
  return [{ key: "steward", name: b.ork_name || "Taskmaster", task: stewardTask(b, data), steward: true },
    ...busy.slice(0, 4).map((o, i) => ({ key: o.ref || `ork${i}`, name: o.name,
      task: doing[i] ? doing[i].title : o.status === "busy" ? "At work" : "Waiting for work" }))];
}

/** The room: the selected card's acts, the three boards and the notes on its wall, the floor the orks walk. */
export function Room(b) {
  loadKit();
  return html`<${Booth} b=${b} />`;
}

function Booth({ b }) {
  const id = b.id;
  const ref = useRef(null);
  const scale = useScale(ref);
  const [unfolded, setUnfolded] = useState({});
  useEffect(() => { act(id, "seen").catch(() => {}); }, [id]);
  const d = details.value[id];
  const data = d && d.data;
  if (!data || !data.lanes) return html`<p class="fields-in__opening" ref=${ref}>${say("Opening…")}</p>`;
  if (data.error) return html`<p class="ok-tone-error" ref=${ref}>⚠ ${data.error}</p>`;
  const parts = !!data.todos;
  const cards = allCards(data);
  const found = cards.find((c) => c.id === selected.value[id]);
  const sel = found && { ...found, mine: parts };
  const open = (card) => setDialog(id, { card });
  const mark = (what, card) => setDialog(id, { [what]: card.id });
  const tasks = data.lanes.filter((ln) => ln.kind === "task");
  const notes = data.mode === "notes" ? [] : noteLanes(data);
  const boards = tasks.length ? tasks : noteLanes(data);
  const todos = data.todos;
  // the person's to-dos stand on To do while open, on Done once ticked off
  const mineOn = (ln, k) => {
    if (!todos || !tasks.length) return [];
    const first = boards.some((x) => x.id === "todo") ? ln.id === "todo" : k === 0;
    const last = boards.some((x) => x.id === "done") ? ln.id === "done" : k === boards.length - 1;
    return todos.cards.filter((c) => (c.done ? last : first));
  };
  const addOn = (ln, k) => {
    if (!tasks.length) return { label: "+ New note", run: () => setDialog(id, { lane: ln }) };
    if (k === 0) return { label: "+ New task", run: () => setDialog(id, { lane: { ...ln, kind: "task" } }) };
    return null;
  };
  const art = has("inside/booth.png") && has("inside/sheet.png");
  // a notes lane sits narrow by the boards, folded to its plaque while it is empty (a press unfolds or folds it)
  const isFolded = (ln) => (ln.id in unfolded ? !unfolded[ln.id] : !ln.cards.length);
  const fold = (ln) => setUnfolded({ ...unfolded, [ln.id]: isFolded(ln) });
  const shelf = tasks.length ? notes : [];
  const cols = boards.map(() => "minmax(0, 1fr)").concat(shelf.map((ln) => (isFolded(ln) ? "44px" : "minmax(0, 0.75fr)"))).join(" ");
  const mineBtn = todos && tasks.length > 0 && html`<button type="button" class="fields-in__add is-mine"
    onClick=${() => setDialog(id, { lane: { id: todos.id, label: todos.label, kind: "mine" } })}>${say("+ My to-do")}</button>`;
  const geo = `--s:${scale};--floor:${(BOOTH.h - BOOTH.floor) * scale}px;--booth-w:${BOOTH.w * scale}px;--booth-h:${BOOTH.h * scale}px`;
  return html`<div class=${cls("fields-in", { "has-art": art })} data-id=${id} ref=${ref}
      style=${art ? `${artStyle()};${geo}` : geo}>
    <div class="fields-in__wall">
      ${sel && html`<${Acts} id=${id} sel=${sel} lanes=${tasks} setDialog=${(x) => setDialog(id, x)}
        onPlan=${(card) => planCard(id, card)} wiki=${data.wiki} sendsItself=${data.settle !== null && data.settle !== undefined} />`}
      <div class="fields-in__boards" style=${`grid-template-columns:${cols}`}>
        ${boards.map((ln, k) => {
          const add = addOn(ln, k);
          return html`<${Board} key=${ln.id} id=${id} lane=${ln} todos=${todos} mine=${mineOn(ln, k)} sel=${sel && sel.id}
            onOpen=${open} onMark=${mark} onAdd=${add && add.run} addLabel=${add && add.label}>${k === 0 && mineBtn}</${Board}>`;
        })}
        ${shelf.map((ln) => html`<${Board} key=${ln.id} id=${id} lane=${ln} todos=${todos} mine=${[]} sel=${sel && sel.id} notes=${true}
          folded=${isFolded(ln)} onFold=${() => fold(ln)}
          onOpen=${open} onMark=${mark} onAdd=${() => setDialog(id, { lane: ln })} addLabel="+ New note" />`)}
      </div>
    </div>
    <${Walkers} orks=${orksOf(b, data)} boards=${boards.length} />
  </div>`;
}
