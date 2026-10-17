// Review, the third tab (docs/specs/33-v1-shell.md §3, §6, §8): Merge into `dev` ▾ at the top, then the results oldest first,
// one card each. Three answers, on the card and pinned at the foot of the result's screen: Merge (only when the tests are
// green and nothing conflicts), Send back / Fix (one line, required), Drop (quiet, apart, asks first).
import { h, sheet } from "./util.js";
import { steady } from "./shell-util.js";
import { foot } from "./shell-forms.js";

const usd = (n) => (n == null ? "" : `$${n < 10 ? n.toFixed(2) : Math.round(n)}`);
export const isRed = (r) => r.tests.failed > 0 || r.tests.green === false;

/** The tests, in the person's words: "20 / 20 passed" ✓, "10 / 20 failed" ✗ with the first failing names, or no tests ran. */
export function testsWords(r) {
  const t = r.tests, all = t.passed + t.failed;
  if (isRed(r)) return { mark: "✗", text: t.failed ? `${t.failed} / ${all} failed` : "the tests failed", names: (t.failing || []).slice(0, 2), tone: "danger" };
  if (t.passed === 0) return { mark: "", text: "no tests ran", names: [], tone: "muted" };
  return { mark: "✓", text: `${t.passed} / ${all} passed`, names: [], tone: "success" };
}
export const changesWords = (d) => `${d.files} file${d.files === 1 ? "" : "s"}, +${d.added} −${d.removed}`;

/** Why Merge is off, or "": red tests, a conflict, or both. */
export function mergeReason(r) {
  const why = [];
  if (isRed(r)) why.push("Its tests are red");
  if (r.conflict) why.push(r.conflict);
  return why.length ? `${why.join(" · ")}: send it back to fix ${why.length > 1 ? "them" : r.conflict ? "the conflict" : "them"}` : "";
}

export function fixLine(r, into) {
  if (r.conflict) return `Resolve the conflict with ${into}`;
  if (isRed(r)) return `Fix the failing tests${r.tests.failing?.[0] ? `: ${r.tests.failing[0]}` : ""}`;
  return "";
}

export function factsOf(r) {
  const t = testsWords(r);
  return h("dl", { class: "facts" },
    h("dt", {}, "Tests"), h("dd", { class: `is-${t.tone}` }, `${t.mark} ${t.text}`.trim(), t.names.length ? h("small", { class: "muted" }, ` ${t.names.join(", ")}`) : null),
    h("dt", {}, "Changes"), h("dd", {}, changesWords(r.diff)),
    ...(r.cost != null ? [h("dt", {}, "Cost"), h("dd", {}, usd(r.cost))] : []));
}

// What the person has half done on a result — the open line and what is typed, the Drop confirm — kept apart from the DOM, so a
// redraw (the town changed something) puts it back as it was.
const half = new Map();
const halfOf = (r) => { const k = `${r.idea}/${r.task}`; if (!half.has(k)) half.set(k, { line: null }); return half.get(k); };

// Drop's confirm is one sheet for every result (spec 34 §5): it names the result and drops it only at the second press.
const dropText = h("p", {});
const dropYes = h("button", { class: "ok-btn danger big", type: "button" }, "Drop it");
const dropNo = h("button", { class: "ok-btn big", type: "button" }, "Keep it");
export const dropSheet = sheet("Drop this result?", dropText, foot(dropNo, dropYes));
let onDrop = () => {};
dropNo.addEventListener("click", () => dropSheet.close());
dropYes.addEventListener("click", () => { dropSheet.close(); onDrop(); });
function askDrop(r, run) {
  dropText.replaceChildren(h("b", {}, r.title), " will not be merged. Its worktree goes; its branch stays.");
  onDrop = run;
  dropSheet.open();
}

/** Merge · Send back / Fix · Drop for one result. `done()` runs after an answer that took (the screen closes). */
export function resultActions(core, r, done = () => {}) {
  const mine = halfOf(r);
  const into = core.st.review?.into || "dev";
  const reason = mergeReason(r), fix = isRed(r) || Boolean(r.conflict);
  const key = { slug: r.idea, task: r.task };
  const merge = h("button", { class: "ok-btn primary big", type: "button", disabled: Boolean(reason), title: reason || null }, `Merge into ${into}`);
  const back = h("button", { class: "ok-btn", type: "button", "aria-expanded": "false" }, fix ? "Fix" : "Send back");
  const drop = h("button", { class: "linkish", type: "button" }, "Drop…");
  const why = reason ? h("p", { class: "warn why", role: "status" }, reason) : null;
  const line = h("input", { class: "ok-input", type: "text", "aria-label": fix ? "What to fix, in one line" : "Why you send it back, in one line",
    placeholder: "One line: what should change?", maxlength: "1000", enterkeyhint: "send" });
  const go = h("button", { class: "ok-btn primary", type: "submit", disabled: true }, fix ? "Fix" : "Send back");
  const form = h("form", { class: "row back-line", hidden: mine.line === null }, line, go);
  if (mine.line !== null) { line.value = mine.line; go.disabled = !line.value.trim(); back.setAttribute("aria-expanded", "true"); }
  line.addEventListener("input", () => { mine.line = line.value; go.disabled = !line.value.trim(); });
  back.addEventListener("click", () => {
    form.hidden = !form.hidden;
    back.setAttribute("aria-expanded", String(!form.hidden));
    mine.line = form.hidden ? null : fixLine(r, into);
    if (!form.hidden) { line.value = mine.line; go.disabled = !line.value.trim(); line.focus(); }
  });
  merge.addEventListener("click", async () => {
    merge.disabled = true;
    const got = await core.call("ideas.merge", key);
    if (got?.ok) { done(); } else { merge.disabled = Boolean(reason); }
    core.refresh();
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!line.value.trim()) return;
    go.disabled = true;
    const got = await core.call("ideas.back", { ...key, why: line.value.trim() });
    if (got?.ok) { mine.line = null; done(); } else go.disabled = false;
    core.refresh();
  });
  drop.addEventListener("click", () => askDrop(r, async () => {
    const got = await core.call("ideas.drop_task", key);
    if (got?.ok) done();
    core.refresh();
  }));
  return h("div", { class: "result-actions", "data-task": r.task }, why, merge, h("div", { class: "row between" }, back, drop), form);
}

export function makeReview(core) {
  const el = h("section", { class: "pane review", "aria-label": "Review" });
  const fresh = steady(el);
  const branchBody = h("div", { class: "branches" });
  const branchSheet = sheet("Merge into", branchBody);
  const intoBtn = h("button", { class: "ok-btn into", type: "button", "aria-haspopup": "dialog" });
  intoBtn.addEventListener("click", () => { drawBranches(); branchSheet.open(); });

  async function pick(branch) {
    branchSheet.close();
    if (branch !== core.st.review?.into) { await core.call("ideas.into", { branch }); core.refresh(); }
  }
  function drawBranches() {
    const rv = core.st.review;
    const name = h("input", { class: "ok-input", type: "text", "aria-label": "Name of the new branch", placeholder: "Name of the new branch", maxlength: "100" });
    const make = h("button", { class: "ok-btn primary", type: "submit", disabled: true }, "Make it");
    name.addEventListener("input", () => { make.disabled = !name.value.trim(); });
    const form = h("form", { class: "row", hidden: true }, name, make);
    form.addEventListener("submit", (e) => { e.preventDefault(); if (name.value.trim()) pick(name.value.trim()); });
    branchBody.replaceChildren(
      ...(rv?.branches || [rv?.into || "dev"]).map((b) => h("button", { class: `branch${b === rv?.into ? " is-on" : ""}`, type: "button", role: "radio",
        "aria-checked": String(b === rv?.into), onclick: () => pick(b) }, b === rv?.into ? "✓ " : "", b)),
      h("button", { class: "branch", type: "button", onclick: () => { form.hidden = false; name.focus(); } }, "New branch…"), form);
  }

  function card(r) {
    const fact = factsOf(r);
    return h("article", { class: "card result", "data-task": r.task, "data-idea": r.idea },
      h("button", { class: "result-open", type: "button", "aria-label": `${r.title}: open its code`, onclick: () => core.open({ kind: "result", slug: r.idea, task: r.task }) },
        h("b", {}, r.title), h("small", { class: "muted" }, r.idea_title, r.round > 1 ? h("span", { class: "round" }, ` · round ${r.round}`) : null), fact,
        r.conflict ? h("small", { class: "warn" }, `⚠ ${r.conflict}`) : null),
      resultActions(core, r));
  }

  return {
    el,
    sheets: [branchSheet.el, dropSheet.el],
    draw() {
      const rv = core.st.review;
      if (!fresh(JSON.stringify(rv))) return;
      if (!rv) { el.replaceChildren(h("h2", {}, "Review"), h("p", { class: "muted" }, "Loading…")); return; }
      intoBtn.replaceChildren("Merge into ", h("b", {}, rv.into), " ▾");
      el.replaceChildren(h("h2", {}, "Review"), intoBtn,
        rv.results.length ? h("div", { class: "results" }, ...rv.results.map(card))
          : h("p", { class: "muted" }, "Nothing waits at Review. A result lands here when a Grunt's work has been tested."));
    },
  };
}
