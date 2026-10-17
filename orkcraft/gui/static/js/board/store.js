// The board's state (docs/specs/29a-board-focus.md §6–7): what the host last said of the goals and ideas, the page of
// the open idea, and the one way to ask the host. The v1 shell (js/shell/store.js) refreshes it with Review and Agents.
import { signal, batch } from "@preact/signals";
import { command, toast, say } from "../link.js";

export const board = signal(null);          // ideas.board
export const opened = signal("");           // slug of the idea in the preview (the shell sets it)
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

export function busy() {
  const b = board.value;
  return !!b && b.ideas.some((i) => BUSY.includes(i.state));
}

/** An idea's state in the person's words (§7). */
export function stateWords(i) {
  const p = i.progress || { done: 0, total: 0 };
  return say({ raw: "new", reading: "the Taskmaster is reading", asks: "asks you", ready: "ready", planning: "the Taskmaster is planning",
    plan: "plan ready", working: `working ${p.done}/${p.total}`, done: "done", failed: "needs you" }[i.state] || i.state);
}
