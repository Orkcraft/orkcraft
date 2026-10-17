// The v1 shell's state (docs/specs/33-v1-shell.md §5–§7): what the host last said of the board (js/board/store.js), of
// Review and of Agents, and which one thing the preview shows. A refresh runs when the town says the ideas changed and
// every 10 s while a model or a task runs; the open task's log is read again every 5 s while it runs.
import { signal, batch } from "@preact/signals";
import { command } from "../link.js";
import { ask, board, opened, page, BUSY } from "../board/store.js";

export const preview = signal(null);       // null | {kind: "idea"|"plan"|"task"|"result", slug, task?, todo?}
export const review = signal(null);        // ideas.review_list
export const agents = signal(null);        // ideas.agents
export const detail = signal(null);        // the preview's own data: {task} (ideas.task) · {task, diff} (a result)
export const tab = signal("board");        // the narrow layout's tab (below 1 024 px the shell is the phone's layout)

const LIVE = ["running", "testing"];

/** What the open preview reads besides the idea's page: a task, or a result's task and its code. */
async function detailFor(p) {
  if (!p || (p.kind !== "task" && p.kind !== "result")) return null;
  const [task, diff] = await Promise.all([ask("ideas.task", { slug: p.slug, task: p.task }),
    p.kind === "result" ? ask("ideas.diff", { slug: p.slug, task: p.task }) : null]);
  return { task, diff };
}

let loading = false;
export async function refreshShell() {
  if (loading) return;
  loading = true;
  try {
    const p = preview.value;
    const [b, r, a, d, pg] = await Promise.all([ask("ideas.board"), ask("ideas.review_list"), ask("ideas.agents"), detailFor(p),
      p && (p.kind === "idea" || p.kind === "plan") ? ask("ideas.page", { slug: p.slug }) : null]);
    batch(() => {
      if (b) board.value = b;
      if (r) review.value = r;
      if (a) agents.value = a;
      if (preview.value === p) { if (p) detail.value = d; if (pg) page.value = pg; }
    });
  } finally { loading = false; }
}

/** A command, then everything again. */
export async function act(name, args) {
  const got = await ask(name, args);
  await refreshShell();
  return got;
}

/** What the person opened, for the day's analysis (docs/specs/33-v1-shell.md §9): the host's one loggable event. */
export function logOpened(what, ref) {
  command("ideas.log", { event: "opened", what, ref: String(ref || ""), device: "desktop" }).catch(() => {});
}

export function show(p) {
  if (p) logOpened(p.kind === "plan" && p.todo ? "todo" : p.kind, p.task ? `${p.slug}/${p.task}` : p.todo ? `${p.slug}/${p.todo}` : p.slug);
  batch(() => {
    preview.value = p;
    detail.value = null;
    page.value = null;
    opened.value = p && (p.kind === "idea" || p.kind === "plan") ? p.slug : "";
  });
  if (p) refreshShell();
}
export const showIdea = (slug) => show({ kind: "idea", slug });
export const showPlan = (slug, todo = "") => show({ kind: "plan", slug, todo });
export const showTask = (slug, task) => show({ kind: "task", slug, task });
export const showResult = (slug, task) => show({ kind: "result", slug, task });
export const closePreview = () => show(null);

/** Something a model or a task does now: the shell looks again every 10 s. */
export function busy() {
  const b = board.value, a = agents.value;
  return !!(b && b.ideas.some((i) => BUSY.includes(i.state))) || !!(a && a.roles.some((r) => (r.chips || []).some((c) => LIVE.includes(c.state))));
}

// The Agents pane's size and whether it is hidden are kept per machine; the layout works without storage.
const KEY = "orkline.shell.agents";
export function readLayout() {
  try {
    const got = JSON.parse(localStorage.getItem(KEY) || "{}");
    return { h: Number.isFinite(got.h) ? got.h : 0, hidden: got.hidden === true };
  } catch { return { h: 0, hidden: false }; }
}
export function writeLayout(layout) {
  try { localStorage.setItem(KEY, JSON.stringify(layout)); } catch { /* the layout still works */ }
}
export const agentsLayout = signal(readLayout());   // {h: px, 0 = a third of the centre, hidden}
export function setLayout(change) {
  agentsLayout.value = { ...agentsLayout.value, ...change };
  writeLayout(agentsLayout.value);
}
