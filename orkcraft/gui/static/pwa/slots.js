// 🥩 The orks at work or asking on the phone (core/slots.py, the compact snapshot's `slots`; ork-console.md §8), as
// the desktop's HUD opens them: a sheet from the foot with Stop all as its first row, then one row per ork, waiting
// first — its mark, its line, how long, its spend. ⏹ stops one ork softly where a phone may (an Agent pool's ork);
// a row that asks says its question waits in Answers. A tap on a row opens its building's card.

import { h, minutes, sheet } from "./util.js";

/** `ctx`: {send, flash, open(buildingId)}. Returns {sheet, open(), render(town)}. */
export function makeSlots(ctx) {
  const head = h("p", { class: "muted" });
  const list = h("ul", { class: "slots" });
  const stopAll = h("button", { class: "ok-btn danger", type: "button" }, "Stop all");
  const s = sheet("Orks at work", head,
    h("div", { class: "slots-stop" }, stopAll, h("span", { class: "muted" }, "stops every ork, script and browser at once")),
    list);
  let armed = false;
  stopAll.addEventListener("click", async () => {
    if (!armed) {                          // two taps, as the bar's: a tap in a pocket stops nothing
      armed = true;
      stopAll.textContent = "Stop every ork";
      setTimeout(() => { armed = false; stopAll.textContent = "Stop all"; }, 4000);
      return;
    }
    armed = false;
    stopAll.textContent = "Stop all";
    const r = await ctx.send("halt");
    ctx.flash(r.ok ? `Stopped: ${r.result} session(s)` : r.error);
  });

  function render(town) {
    const camp = town.look !== "office";
    const sl = town.slots || { rows: [] };
    head.textContent = `${sl.working ?? 0}/${sl.limit ?? 0} at work${sl.asks ? ` · ${sl.asks} wait for you` : ""}`;
    list.replaceChildren(...(sl.rows || []).map((r) => {
      const stop = r.stop && h("button", { class: "ok-btn", type: "button", "aria-label": `Stop ${r.name}`, onclick: async (e) => {
        e.stopPropagation();
        const got = await ctx.send("act", { id: r.stop.id, act: "stop_ork", args: { ork: r.stop.ork } });
        ctx.flash(got.ok ? `${r.name} stops where it is.` : got.error);
      } }, "⏹ Stop");
      const more = [r.spend ? `$${Number(r.spend).toFixed(2)}` : "", r.tool, r.since_s ? minutes(r.since_s) : ""].filter(Boolean).join(" · ");
      return h("li", { class: `slot ${r.asks ? "asks" : ""}` },
        h("button", { class: "slot-line", type: "button", onclick: () => { if (r.building) { s.close(); ctx.open(r.building); } } },
          h("span", { class: "slot-mark", "aria-hidden": "true" }, camp ? r.mark : r.word),
          h("span", {}, r.line, r.asks ? h("small", { class: "warn" }, " · its question waits in Answers") : null,
            more ? h("small", { class: "muted" }, ` · ${more}`) : null)),
        stop);
    }), ...((sl.rows || []).length ? [] : [h("li", { class: "muted" }, "No ork is at work.")]));
  }

  return { sheet: s.el, open: () => s.open(), render };
}
