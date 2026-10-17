// Add agent / Edit agent on the phone (docs/specs/34-v1-round-2.md §3): a name, a model, how many may work at once, an instruction
// added to every task prompt of that agent. An agent of your own can be deleted (its task types go back to Grunt, said first);
// Taskmaster and Grunt can be edited, not deleted. `assign`: a task type to give a new agent to.
import { h, sheet } from "./util.js";
import { field, foot } from "./shell-forms.js";

export function makeAgentSheet(core) {
  const name = h("input", { class: "ok-input", type: "text", "aria-label": "Name", placeholder: "Docs scribe", maxlength: "40", required: true });
  const model = h("select", { class: "ok-input", "aria-label": "Model" });
  const many = h("select", { class: "ok-input", "aria-label": "At most at once" }, ...[1, 2, 3, 4, 5, 6, 7, 8].map((n) => h("option", { value: String(n) }, String(n))));
  const instruction = h("textarea", { class: "ok-input", rows: "5", "aria-label": "Instruction", placeholder: "Added to every task this agent does", maxlength: "4000" });
  const note = h("p", { class: "muted", hidden: true });
  const save = h("button", { class: "ok-btn primary big", type: "submit", disabled: true }, "Save agent");
  const cancel = h("button", { class: "ok-btn big", type: "button" }, "Cancel");
  const del = h("button", { class: "linkish", type: "button" }, "Delete…");
  const sureText = h("p", { class: "warn" });
  const sureBtn = h("button", { class: "ok-btn danger big", type: "button" }, "Delete agent");
  const keep = h("button", { class: "ok-btn big", type: "button" }, "Keep it");
  const sure = h("div", { class: "sure", hidden: true }, sureText, sureBtn, keep);
  const form = h("form", { class: "sheet-form" }, field("Name", name), field("Model", model), field("At most at once", many), field("Instruction", instruction),
    note, h("div", {}, del), sure, foot(cancel, save));
  const sh = sheet("Add agent", form);
  let slug = "", assign = "";
  name.addEventListener("input", () => { save.disabled = !name.value.trim(); });
  cancel.addEventListener("click", () => sh.close());
  del.addEventListener("click", () => {
    const mine = (core.st.roles?.kinds || []).filter((k) => k.role === slug).map((k) => k.label.toLowerCase());
    sureText.textContent = `${mine.length ? `Its task types (${mine.join(", ")}) go back to Grunt.` : "No task type uses it."} Delete ${name.value}?`;
    sure.hidden = false;
    del.hidden = true;
  });
  keep.addEventListener("click", () => { sure.hidden = true; del.hidden = false; });
  sureBtn.addEventListener("click", async () => {
    const got = await core.call("ideas.role_drop", { slug });
    if (got?.ok) { sh.close(); core.refresh(); }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!name.value.trim()) return;
    save.disabled = true;
    const got = await core.call("ideas.role_save", { ...(slug ? { slug } : {}), name: name.value.trim(), model: model.value, max_parallel: Number(many.value), instruction: instruction.value });
    if (got?.slug && assign) await core.call("ideas.kind_set", { kind: assign, role: got.slug });
    save.disabled = !name.value.trim();
    if (got?.slug) { sh.close(); core.refresh(); }
  });
  return {
    el: sh.el,
    open(which = "", kind = "") {
      slug = which;
      assign = kind;
      const data = core.st.roles, r = which ? (data?.roles || []).find((x) => x.slug === which) : null;
      sh.title(r ? "Edit agent" : "Add agent");
      name.value = r?.name || "";
      model.replaceChildren(...(data?.models || []).filter((m) => m.id || r?.slug === "grunt").map((m) => h("option", { value: m.id }, m.label)));
      model.value = r ? r.model : "warrior";
      many.value = String(r?.max_parallel || 2);
      instruction.value = r?.instruction || "";
      note.hidden = !assign;
      note.textContent = assign ? `It will do every task of the type “${assign}”.` : "";
      del.hidden = !r || r.builtin;
      sure.hidden = true;
      save.disabled = !name.value.trim();
      sh.open();
      name.focus();
    },
  };
}
