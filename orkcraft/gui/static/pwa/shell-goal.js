// A goal on the phone (docs/specs/34-v1-round-2.md §1, §7): the New goal / Edit goal sheet — a title, a description, the metrics
// (what is measured and the target), a priority, the links to documents, a deadline — and the goal's own screen (its
// Description, the Taskmaster's Summary, the Metrics, the Links, the Open questions with a box to answer). Saving sends the
// goal to the Taskmaster at once.
import { h, sheet } from "./util.js";
import { field, foot, listEditor, prioritySwitch } from "./shell-forms.js";

export const GOAL_STATE = { reading: "the Taskmaster is reading", asks: "asks you", ready: "ready" };
export const PRIORITY_WORDS = { high: "High", normal: "Normal", low: "Low" };
const isUrl = (l) => /^[a-z][a-z0-9+.-]*:\/\//i.test(l);

export function makeGoalSheet(core) {
  const title = h("input", { class: "ok-input", type: "text", "aria-label": "Title", placeholder: "What you want to reach", maxlength: "120", required: true });
  const about = h("textarea", { class: "ok-input", rows: "3", "aria-label": "Description", placeholder: "A few lines: what it is for", maxlength: "20000" });
  const metrics = listEditor({ label: "Metrics", one: "Metric", add: "+ Add a metric",
    cols: [{ key: "name", placeholder: "What is measured: weekly installs", aria: "what is measured" }, { key: "target", placeholder: "Target: 50", aria: "the target", grow: false }] });
  const priority = prioritySwitch();
  const links = listEditor({ label: "Links", one: "Link", add: "+ Add a link", plain: true, cols: [{ key: "link", placeholder: "docs/plan.md · https://…" }] });
  const deadline = h("input", { class: "ok-input", type: "date", "aria-label": "Deadline" });
  const save = h("button", { class: "ok-btn primary big", type: "submit", disabled: true }, "Save goal");
  const cancel = h("button", { class: "ok-btn big", type: "button" }, "Cancel");
  const form = h("form", { class: "sheet-form" }, field("Title", title), field("Description", about), metrics.el,
    h("div", { class: "field" }, h("span", { class: "field-label" }, "Priority"), priority.el), links.el,
    field("Deadline (optional)", deadline), foot(cancel, save));
  const sh = sheet("New goal", form);
  let slug = "";
  title.addEventListener("input", () => { save.disabled = !title.value.trim(); });
  cancel.addEventListener("click", () => sh.close());
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!title.value.trim()) return;
    save.disabled = true;
    const got = await core.call("ideas.goal_save", { ...(slug ? { slug } : {}), title: title.value.trim(), about: about.value, priority: priority.get(),
      deadline: deadline.value, metrics: metrics.get().filter((m) => m.name), links: links.get() });
    save.disabled = !title.value.trim();
    if (!got?.slug) return;
    sh.close();
    core.st.track = got.slug;
    core.refresh();
    core.open({ kind: "goal", slug: got.slug });
  });
  return {
    el: sh.el,
    open(which = "") {
      slug = which;
      const g = which ? (core.st.board?.tracks || []).find((t) => t.slug === which) : null;
      sh.title(g ? "Edit goal" : "New goal");
      title.value = g?.title || "";
      about.value = g?.about || "";
      deadline.value = g?.deadline || "";
      priority.set(g?.priority || "normal");
      metrics.set((g?.metrics || []).map((m) => ({ name: m.name, target: m.target })));
      links.set(g?.links || []);
      save.disabled = !title.value.trim();
      sh.open();
      title.focus();
    },
  };
}

/** The goal's screen: returns the nodes of its body (the preview puts them in). `act` is the preview's own (it flashes and reads again). */
export function goalBody(g, core, act, asked, setAsked) {
  const words = GOAL_STATE[g.state];
  const field_ = h("textarea", { class: "ok-input", id: "answer-field", rows: "2", maxlength: "20000", "aria-label": "Answer the Taskmaster", placeholder: "Answer the Taskmaster…" });
  field_.value = asked;
  field_.addEventListener("input", () => setAsked(field_.value));
  const send = h("button", { class: "ok-btn", type: "button" }, "Send");
  send.addEventListener("click", async () => {
    const text = field_.value.trim();
    if (!text) return;
    send.disabled = true;
    const r = await act("ideas.say", { slug: g.slug, text, goal: true }, "Sent: the Taskmaster answers in a moment.");
    send.disabled = false;
    if (r) { setAsked(""); field_.value = ""; }
  });
  const sec = (name, ...kids) => h("section", { class: "goal-sec", "aria-label": name }, h("h3", {}, name), ...kids);
  return [
    h("p", { class: "muted" }, [words || "not read yet", PRIORITY_WORDS[g.priority], g.deadline ? `by ${g.deadline}` : ""].filter(Boolean).join(" · ")),
    g.error && g.state === "raw" ? h("p", { class: "warn" }, g.error) : null,
    sec("Description", h("p", { class: "brief" }, g.description || "No description yet.")),
    sec("Summary", h("p", { class: "brief" }, g.summary || (g.state === "reading" ? "The Taskmaster is reading the goal…" : "Not written yet."))),
    sec("Metrics", g.metrics.length ? h("div", { class: "metrics" }, ...g.metrics.map((m) => h("div", { class: "card metric" }, h("b", {}, m.name),
      h("small", {}, `Target: ${m.target || "—"}`), h("small", { class: "muted" }, m.how ? `Counted: ${m.how}` : "How it is counted: not said yet")))) : h("p", { class: "muted" }, "No metric yet.")),
    sec("Links", g.links.length ? h("ul", { class: "links" }, ...g.links.map((l) => h("li", {}, isUrl(l)
      ? h("a", { href: l, target: "_blank", rel: "noopener noreferrer" }, l)
      : h("button", { class: "linkish", type: "button", onclick: () => core.open({ kind: "doc", slug: g.slug, path: l }) }, l)))) : h("p", { class: "muted" }, "No link.")),
    sec("Open questions", g.questions.length ? h("ul", { class: "links" }, ...g.questions.map((q) => h("li", {}, q)))
      : h("p", { class: "muted" }, g.state === "ready" ? "The Taskmaster has no question." : "No question yet."),
    h("div", { class: "ask" }, h("div", { class: "row" }, field_, send))),
    (g.talk || []).length ? h("div", { class: "talk" }, ...g.talk.slice(-6).map((t) => h("div", { class: `turn ${t.who}` },
      h("span", { class: "who" }, t.who === "you" ? "You" : "The Taskmaster"), h("p", {}, t.text)))) : null,
  ].filter(Boolean);
}
