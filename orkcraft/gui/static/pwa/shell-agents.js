// Agents, the second tab (docs/specs/33-v1-shell.md §6, §8; spec 34 §3): a block per role — the Taskmaster says what it waits on or
// reads, the Grunt and the agents of your own are a card per live task, each with its idea's title small, and Edit — with + Add agent
// at the top; under them the Task types, each with the agent that does it and New agent… to make one from there. A card opens its
// task on its own screen.
import { h } from "./util.js";
import { steady } from "./shell-util.js";
import { makeAgentSheet } from "./shell-agent.js";

const GRUNT = { running: ["working", "↻"], testing: ["testing", ""], review: ["at Review", ""], ready: ["queued", ""], held: ["held", "⏳"],
  failed: ["needs you", "⚠"] };
const NEW = "__new__";

export function gruntWords(c) {
  const [word, mark] = GRUNT[c.state] || [c.state, ""];
  if (c.state === "held") return c.note || "held";
  if (c.state === "ready" && c.note) return "stopped";
  return mark ? `${word} ${mark}` : word;
}

const usd = (n) => (n ? ` · $${n < 10 ? n.toFixed(2) : Math.round(n)} today` : "");

export function makeAgents(core) {
  const el = h("section", { class: "pane agents", "aria-label": "Agents" });
  const fresh = steady(el);
  const sheetOf = makeAgentSheet(core);
  const modelWords = (r) => (core.st.roles?.models || []).find((m) => m.id === r.model)?.label || r.model || "the task's own tier";

  function head(role) {
    return h("div", { class: "role-head" }, h("h3", {}, role.name),
      h("button", { class: "linkish", type: "button", "aria-label": `Edit ${role.name}`, onclick: () => sheetOf.open(role.role) }, "Edit"),
      h("small", { class: "muted role-facts" }, `${modelWords(role)}${role.role === "taskmaster" ? "" : ` · up to ${role.max_parallel}`}${usd(role.spend_today)}`));
  }

  function taskmaster(role) {
    const chips = role.chips || [];
    const lead = chips.find((c) => c.state !== "waiting");
    const open = (c) => core.open(c.goal ? { kind: "goal", slug: c.goal } : { kind: "idea", slug: c.idea });
    const said = (c) => `${c.state === "talking" ? "talking about" : c.state} “${c.title}”`;
    const line = role.state === "waiting" && role.waits_on
      ? h("button", { class: "card chip is-wait", type: "button", onclick: () => core.open({ kind: "idea", slug: role.waits_on.idea }) }, role.waits_on.text)
      : lead ? h("button", { class: "card chip is-live", type: "button", onclick: () => open(lead) },
        h("span", { class: "spin", "aria-hidden": "true" }, "↻"), ` ${said(lead)}`)
        : h("p", { class: "muted" }, "Nothing to do.");
    return h("div", { class: "role", "data-role": "taskmaster" }, head(role), line);
  }

  function worker(role, done) {
    const chips = role.chips || [];
    const mine = done.filter((d) => (d.role || "grunt") === role.role);
    return h("div", { class: "role", "data-role": role.role === "grunt" ? "grunt" : "agent", "data-slug": role.role }, head(role),
      (role.kinds || []).length ? h("small", { class: "muted" }, `Does: ${role.kinds.join(", ")}`) : null,
      chips.length ? h("ul", { class: "chips" }, ...chips.map((c) => h("li", {},
        h("button", { class: `card chip is-${c.state}`, type: "button", "data-state": c.state,
          onclick: () => core.open({ kind: "task", slug: c.idea, task: c.task }) },
        h("span", { class: "chip-state" }, gruntWords(c)), h("b", {}, c.title), h("small", { class: "muted" }, c.idea_title)))))
        : h("p", { class: "muted" }, "No task runs now."),
      mine.length ? h("details", { class: "done-today" }, h("summary", {}, `Done today (${mine.length})`),
        h("ul", { class: "chips" }, ...mine.map((d) => h("li", {}, h("button", { class: "card chip is-done", type: "button",
          onclick: () => core.open({ kind: "task", slug: d.idea, task: d.task }) }, d.title))))) : null);
  }

  /** Which agent does each type of task; New agent… opens Add agent and gives it the type. */
  function kinds() {
    const data = core.st.roles;
    if (!data) return null;
    const doers = data.roles.filter((r) => r.slug !== "taskmaster");
    return h("div", { class: "role kinds", "data-role": "kinds" }, h("h3", {}, "Task types"),
      ...data.kinds.map((k) => {
        const pick = h("select", { class: "ok-input", "aria-label": `Agent for ${k.label}` },
          ...doers.map((r) => h("option", { value: r.slug }, r.name)), h("option", { value: NEW }, "New agent…"));
        pick.value = k.role;
        pick.addEventListener("change", async () => {
          if (pick.value === NEW) { pick.value = k.role; sheetOf.open("", k.kind); return; }
          if (await core.call("ideas.kind_set", { kind: k.kind, role: pick.value })) core.refresh();
        });
        return h("label", { class: "kind-row", "data-kind": k.kind }, h("span", {}, k.label), pick);
      }));
  }

  return {
    el,
    sheets: [sheetOf.el],
    draw() {
      const a = core.st.agents;
      if (!fresh(JSON.stringify([a, core.st.roles]))) return;
      if (!a) { el.replaceChildren(h("h2", {}, "Agents"), h("p", { class: "muted" }, "Loading…")); return; }
      el.replaceChildren(h("div", { class: "pane-head" }, h("h2", {}, "Agents"),
        h("button", { class: "ok-btn primary", type: "button", onclick: () => sheetOf.open() }, "+ Add agent")),
      ...a.roles.map((r) => (r.role === "taskmaster" ? taskmaster(r) : worker(r, a.done_today || []))), kinds());
    },
  };
}
