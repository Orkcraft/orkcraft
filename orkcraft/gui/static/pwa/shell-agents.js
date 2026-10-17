// Agents, the second tab (docs/specs/33-v1-shell.md §6, §8): a block per role — the Taskmaster says what it waits on or reads,
// the Grunts are a card per live task, each with its idea's title small. A card opens its task on its own screen.
import { h } from "./util.js";
import { steady } from "./shell-util.js";

const GRUNT = { running: ["working", "↻"], testing: ["testing", ""], review: ["at Review", ""], ready: ["queued", ""], held: ["held", "⏳"],
  failed: ["needs you", "⚠"] };

export function gruntWords(c) {
  const [word, mark] = GRUNT[c.state] || [c.state, ""];
  if (c.state === "held") return c.note || "held";
  if (c.state === "ready" && c.note) return "stopped";
  return mark ? `${word} ${mark}` : word;
}

export function makeAgents(core) {
  const el = h("section", { class: "pane agents", "aria-label": "Agents" });
  const fresh = steady(el);

  function taskmaster(role) {
    const chips = role.chips || [];
    const lead = chips.find((c) => c.state !== "waiting");
    const said = (c) => `${c.state === "talking" ? "talking about" : c.state} “${c.title}”`;
    const line = role.state === "waiting" && role.waits_on
      ? h("button", { class: "card chip is-wait", type: "button", onclick: () => core.open({ kind: "idea", slug: role.waits_on.idea }) }, role.waits_on.text)
      : lead ? h("button", { class: "card chip is-live", type: "button", onclick: () => core.open({ kind: "idea", slug: lead.idea }) },
        h("span", { class: "spin", "aria-hidden": "true" }, "↻"), ` ${said(lead)}`)
        : h("p", { class: "muted" }, "Nothing to do.");
    return h("div", { class: "role", "data-role": "taskmaster" }, h("h3", {}, role.name), line);
  }

  function grunts(role, done) {
    const chips = role.chips || [];
    return h("div", { class: "role", "data-role": "grunt" }, h("h3", {}, role.name),
      chips.length ? h("ul", { class: "chips" }, ...chips.map((c) => h("li", {},
        h("button", { class: `card chip is-${c.state}`, type: "button", "data-state": c.state,
          onclick: () => core.open({ kind: "task", slug: c.idea, task: c.task }) },
        h("span", { class: "chip-state" }, gruntWords(c)), h("b", {}, c.title), h("small", { class: "muted" }, c.idea_title)))))
        : h("p", { class: "muted" }, "No task runs now."),
      done.length ? h("details", { class: "done-today" }, h("summary", {}, `Done today (${done.length})`),
        h("ul", { class: "chips" }, ...done.map((d) => h("li", {}, h("button", { class: "card chip is-done", type: "button",
          onclick: () => core.open({ kind: "task", slug: d.idea, task: d.task }) }, d.title))))) : null);
  }

  return {
    el,
    draw() {
      const a = core.st.agents;
      if (!fresh(JSON.stringify(a))) return;
      if (!a) { el.replaceChildren(h("h2", {}, "Agents"), h("p", { class: "muted" }, "Loading…")); return; }
      el.replaceChildren(h("h2", {}, "Agents"), ...a.roles.map((r) => (r.role === "taskmaster" ? taskmaster(r) : grunts(r, a.done_today || []))));
    },
  };
}
