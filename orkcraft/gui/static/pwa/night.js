// The Night report on the phone's Today (docs/specs/32-night-gate.md §3): the desktop's same card. Green → *N changes
// ready for main*, the steps in a line each, the cost, Pass to main (a sheet asks once, naming the count) and Details;
// red → it stands in Needs you with what failed and what the check could not fix.

import { h, sheet } from "./util.js";

const usd = (n) => `$${Number(n || 0).toFixed(2)}`;
const hhmm = (iso) => (iso ? String(iso).slice(11, 16) : "");
const changes = (n) => `${n} change${n === 1 ? "" : "s"}`;

export const isRed = (n) => !!n && !n.running && !n.green && !n.passed_at;
export const shown = (n) => !!n && !n.passed_at;

function lead(n) {
  if (n.running) return `The night run is on · since ${hhmm(n.started)}`;
  if (n.green) return n.count ? `${changes(n.count)} ready for main` : "Nothing new for main";
  const red = (n.steps || []).filter((s) => !s.ok).map((s) => s.name);
  return n.error ? `Red: ${n.error}` : `Red: ${red.join(", ") || "the check found what it could not fix"}`;
}

/** `ctx`: the board's {send, flash}; `reload`: read the board again. Returns {card(night), sheets}. */
export function makeNight(ctx, reload) {
  let pending = null;
  let details = false;
  const ask = h("p", {});
  const yes = h("button", { class: "ok-btn primary", type: "button" }, "Pass to main");
  const passSheet = sheet("Pass to main", ask, yes);
  yes.addEventListener("click", async () => {
    const n = pending;
    passSheet.close();
    if (!n) return;
    const r = await ctx.send("gate.pass_night", { date: n.date });
    if (!r.ok || r.result?.error) ctx.flash(r.error || r.result?.error);
    else ctx.flash(`${changes(n.count)} passed to main.`);
    await reload();
  });

  async function runNow() {
    const r = await ctx.send("gate.run_night", {});
    if (!r.ok || r.result?.error) ctx.flash(r.error || r.result?.error);
    else ctx.flash("The night run started.");
    await reload();
  }

  function detailBlock(n) {
    const kids = [h("h3", {}, "What merged into dev since main")];
    for (const c of n.commits || []) {
      kids.push(h("div", { class: "night-commit" }, h("code", { class: "sha" }, c.sha.slice(0, 7)), h("span", {}, c.subject),
        c.idea ? h("small", {}, c.idea) : null));
    }
    if (!(n.commits || []).length) kids.push(h("p", { class: "muted" }, "Nothing."));
    for (const s of (n.steps || []).filter((x) => (x.failed || []).length)) {
      kids.push(h("h3", {}, `${s.name}: failed`), ...s.failed.map((f) => h("code", { class: "night-failed" }, f)));
    }
    return h("div", { class: "night-details" }, ...kids);
  }

  function card(n) {
    const red = isRed(n);
    const state = n.running ? "running" : n.green ? "green" : "red";
    const kids = [
      h("div", { class: "night-head" }, h("b", {}, `Night report · ${n.date}`), h("span", { class: "night-chip" }, state)),
      h("p", { class: "night-lead" }, lead(n)),
      ...(n.steps || []).map((s) => h("div", { class: "night-step", "data-ok": String(!!s.ok) },
        h("span", { class: "night-mark", "aria-hidden": "true" }, s.ok ? "✓" : "✗"), h("b", {}, s.name), h("small", {}, s.summary))),
    ];
    if (red && (n.not_fixed || []).length) {
      kids.push(h("div", { class: "night-notfixed" }, h("b", {}, "The check could not fix"),
        ...n.not_fixed.map((f) => h("small", {}, f))));
    }
    kids.push(h("small", { class: "night-cost" }, `Cost ${usd(n.cost)} of its ${usd(n.budget)} budget`));
    if (n.stale && !n.running) kids.push(h("p", { class: "night-stale" }, "dev moved since the night; run again"));
    const acts = h("div", { class: "row night-acts" });
    if (n.green && !n.running && !n.stale && n.count > 0) {
      acts.append(h("button", { class: "ok-btn primary", type: "button", onclick: () => {
        pending = n;
        ask.textContent = `Pass ${changes(n.count)} to main?`;
        yes.textContent = `Pass ${changes(n.count)}`;
        passSheet.open();
      } }, "Pass to main"));
    }
    const more = h("div", { class: "night-more" });
    const toggle = h("button", { class: "ok-btn", type: "button", "aria-expanded": String(details) }, "Details");
    toggle.addEventListener("click", () => {
      details = !details;
      toggle.setAttribute("aria-expanded", String(details));
      more.replaceChildren(...(details ? [detailBlock(n)] : []));
    });
    if (details) more.append(detailBlock(n));
    acts.append(toggle);
    if (!n.running && (red || n.stale)) acts.append(h("button", { class: "ok-btn", type: "button", onclick: runNow }, "Run now"));
    kids.push(acts, more);
    return h("section", { class: `card night night-${n.passed_at ? "passed" : state}`, "aria-label": "Night report" }, ...kids);
  }

  return { card, sheets: [passSheet.el] };
}
