// The pieces the phone's forms share (docs/specs/34-v1-round-2.md §5): a labelled field, a list of rows to add to and remove from
// (a goal's metrics and links), the priority choice, and the foot a sheet's buttons are pinned in.
import { h } from "./util.js";

export const PRIORITIES = [["high", "High"], ["normal", "Normal"], ["low", "Low"]];

/** A label over its control, with an optional hint under it. */
export function field(label, control, hint) {
  return h("label", { class: "field" }, h("span", { class: "field-label" }, label), control, hint ? h("small", { class: "muted" }, hint) : null);
}

/** A sheet's foot: its buttons, pinned at the bottom of the sheet. */
export const foot = (...buttons) => h("div", { class: "sheet-foot" }, ...buttons);

/** A list of rows the person adds to and removes from. `cols`: [{key, placeholder, aria, grow}] for objects, or one column for plain
 *  strings (`plain`). Returns {el, get(), set(values)}; `get` leaves out the empty rows. */
export function listEditor({ label, one, cols, add, plain = false }) {
  const rows = h("div", { class: "list-rows" });
  const el = h("div", { class: "list-editor", role: "group", "aria-label": label }, h("span", { class: "field-label" }, label), rows);
  let n = 0;
  const addRow = (value) => {
    n += 1;
    const inputs = cols.map((c) => h("input", { class: `ok-input${c.grow === false ? " narrow" : ""}`, type: "text", value: plain ? String(value ?? "") : String(value?.[c.key] ?? ""),
      placeholder: c.placeholder, "aria-label": c.aria ? `${one} ${n}: ${c.aria}` : `${one} ${n}`, "data-key": c.key, maxlength: "300" }));
    const gone = h("button", { class: "ok-btn", type: "button", "aria-label": `Remove ${one.toLowerCase()} ${n}` }, "−");
    const row = h("div", { class: "list-row" }, ...inputs, gone);
    gone.addEventListener("click", () => { row.remove(); if (!rows.children.length) addRow(); });
    rows.append(row);
  };
  const more = h("button", { class: "linkish", type: "button" }, add);
  more.addEventListener("click", () => { addRow(); rows.lastChild.querySelector("input").focus(); });
  el.append(more);
  addRow();
  return {
    el,
    get() {
      return [...rows.children].map((r) => {
        const vals = Object.fromEntries([...r.querySelectorAll("input")].map((i) => [i.dataset.key, i.value.trim()]));
        return plain ? vals[cols[0].key] : vals;
      }).filter((v) => (plain ? v : Object.values(v).some(Boolean)));
    },
    set(values) {
      rows.replaceChildren();
      n = 0;
      for (const v of values && values.length ? values : [undefined]) addRow(v);
    },
  };
}

/** High · Normal · Low as three pills (radio buttons). Returns {el, get(), set(value)}. */
export function prioritySwitch(name = "priority") {
  const inputs = PRIORITIES.map(([id, text]) => h("input", { type: "radio", name, value: id, "aria-label": text }));
  const labels = PRIORITIES.map(([, text], i) => h("label", { class: "pill" }, inputs[i], h("span", {}, text)));
  const el = h("div", { class: "pills", role: "radiogroup", "aria-label": "Priority" }, ...labels);
  const set = (value) => inputs.forEach((i) => { i.checked = i.value === value; i.parentElement.classList.toggle("is-on", i.checked); });
  el.addEventListener("change", () => set(inputs.find((i) => i.checked)?.value));
  set("normal");
  return { el, get: () => inputs.find((i) => i.checked)?.value || "normal", set };
}
