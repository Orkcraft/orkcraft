// The board's state (docs/specs/29a-board-focus.md §6–7): what the host last said of the tracks and ideas, which
// idea is open, and the one way to ask the host. The page refreshes on `ideas_rev` and every 10 s while a model runs.
import { signal, batch } from "@preact/signals";
import { command, toast, say } from "../link.js";

export const board = signal(null);          // ideas.board
export const opened = signal("");           // slug of the open idea
export const page = signal(null);           // ideas.page of the open idea
export const track = signal("");            // the track shown ("" = all)
export const adding = signal(false);        // the Drop it field is up

export const BUSY = ["reading", "planning", "working"];

/** A command of the contract; a plain-words error comes back as a toast and a null. */
export async function ask(name, args = {}) {
  try {
    const got = await command(name, args);
    if (got && got.error) { toast(got.error, "error"); return null; }
    return got || {};
  } catch { return null; }
}

let loading = false;
export async function refresh() {
  if (loading) return;
  loading = true;
  try {
    const b = await ask("ideas.board");
    const p = opened.value ? await ask("ideas.page", { slug: opened.value }) : null;
    batch(() => { if (b) board.value = b; if (opened.value) page.value = p; });
  } finally { loading = false; }
}

/** A command, then the board again. */
export async function run(name, args) {
  const got = await ask(name, args);
  await refresh();
  return got;
}

export async function open(slug) {
  opened.value = slug;
  page.value = null;
  if (slug) page.value = await ask("ideas.page", { slug });
}

export function busy() {
  const b = board.value;
  return !!b && b.ideas.some((i) => BUSY.includes(i.state));
}

/** An idea's state in the person's words (§7). */
export function stateWords(i) {
  const p = i.progress || { done: 0, total: 0 };
  return say({ raw: "new", reading: "the keeper is reading", asks: "asks you", ready: "ready", planning: "the keeper is planning",
    plan: "plan ready", working: `working ${p.done}/${p.total}`, done: "done", failed: "needs you" }[i.state] || i.state);
}
