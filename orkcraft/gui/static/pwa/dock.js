// The bar at the screen's foot, where the thumb is (docs/design/mobile.md §10): Ask, Drop and More open sheets
// over the town, and Stop all stops on a hold, or a tap and a second tap elsewhere on the screen. The town's
// first screen keeps the questions; what a phone does now and then waits one tap down here.

import { h, randomId, sheet } from "./util.js";

const FILE_LIMIT = 5 * 1024 * 1024;     // as views/pit.py FILE_LIMIT
const HOLD_MS = 1200;                    // Stop all held this long stops every ork
export const LOOKS = [["camp", "Camp"], ["office", "Office"], ["shift", "By the shift"]];

/** `ctx`: {send, flash, building(type), device(), unpair(), shared} — what the app gives the bar. */
export function makeDock(ctx) {
  // -- the Warchief --
  const chat = h("div", { class: "chat", "aria-live": "polite" });
  const ask = h("input", { id: "ask", class: "input", placeholder: "Ask the Warchief…", maxlength: "2000",
    enterkeyhint: "send", autofocus: true, "aria-label": "Ask the Warchief" });
  const askBtn = h("button", { class: "btn primary", type: "button" }, "Ask");
  let chatTimer = 0;
  async function readChat() {
    clearTimeout(chatTimer);
    const r = await ctx.send("mobile.chat", { limit: 6 });
    if (!r.ok) return;
    const c = r.result;
    chat.replaceChildren(...c.chat.map((m) => h("div", { class: `msg${m.error ? " warn" : ""}` },
      h("span", { class: "who" }, m.who === "user" ? "You" : (c.warchief || "Warchief")),
      h("p", {}, m.text || ""), m.offer && h("p", { class: "muted" }, "It offers a card: answer it at the computer."))),
      c.thinking ? h("p", { class: "muted" }, "Thinking…") : "");
    if (c.thinking && askSheet.el.open) chatTimer = setTimeout(readChat, 3000);
  }
  async function askWarchief() {
    const text = ask.value.trim();
    const hall = ctx.building("town_hall");
    if (!text || !hall) return;
    askBtn.disabled = true;
    const r = await ctx.send("act", { id: hall.id, act: "ask", args: { text } });
    askBtn.disabled = false;
    if (!r.ok) { ctx.flash(r.error); return; }
    ask.value = "";
    readChat();
  }
  askBtn.addEventListener("click", askWarchief);
  ask.addEventListener("keydown", (e) => { if (e.key === "Enter") askWarchief(); });
  const askSheet = sheet("Warchief", h("div", { class: "row" }, ask, askBtn), chat);

  // -- Drop file here --
  const drop = h("textarea", { id: "drop", class: "input", rows: "4", placeholder: "A link or a text", maxlength: "20000",
    "aria-label": "A link or a text" });
  drop.value = ctx.shared || "";
  const file = h("input", { id: "drop-file", type: "file", class: "file", "aria-label": "A file" });
  const dropBtn = h("button", { class: "btn primary", type: "button" }, "Drop");
  dropBtn.addEventListener("click", async () => {
    const pit = ctx.building("pit");
    if (!pit) return;
    const f = file.files?.[0];
    if (!f && !drop.value.trim()) return;
    if (f && f.size > FILE_LIMIT) { ctx.flash("The file is over 5 MB: drop it at the computer."); return; }
    dropBtn.disabled = true;
    // The client id makes a retry drop once (views/pit.py `once`).
    const r = f
      ? await ctx.send("act", { id: pit.id, act: "drop_file", args: { name: f.name, data: await base64(f), client_id: randomId() } })
      : await ctx.send("act", { id: pit.id, act: "drop", args: { text: drop.value.trim(), client_id: randomId() } });
    dropBtn.disabled = false;
    if (!r.ok) { ctx.flash(r.error); return; }
    ctx.flash("Dropped.");
    drop.value = "";
    file.value = "";
    dropSheet.close();
  });
  const dropSheet = sheet("Drop file here", drop, h("div", { class: "row" }, file, dropBtn));

  // -- More: the look, notices, this phone --
  // The look is the person's, one for the desktop and the phone (you.look; docs/design/portrait.md §3).
  const looks = h("div", { class: "looks", role: "group", "aria-label": "Look" },
    ...LOOKS.map(([look, label]) => h("button", { class: "btn quiet", type: "button", "data-look": look,
      onclick: async () => { const r = await ctx.send("you.look", { look }); if (!r.ok) ctx.flash(r.error); } }, label)));
  const notify = h("button", { class: "btn quiet", type: "button" }, "Notify me while it is open");
  notify.addEventListener("click", async () => { notify.hidden = (await Notification.requestPermission()) !== "default"; });
  if (!("Notification" in window) || Notification.permission !== "default") notify.hidden = true;
  const phone = h("p", { class: "muted" });
  const moreSheet = sheet("More",
    h("h3", {}, "Look"), looks, h("p", { class: "muted" }, "The same on the computer: it is one setting."),
    notify, phone,
    h("button", { class: "btn quiet", type: "button", onclick: () => { moreSheet.close(); ctx.unpair(); } }, "Unpair here"));

  // -- Stop all --
  const stop = h("button", { class: "btn danger stop", type: "button",
    "aria-label": "Stop all: hold it, or tap it and confirm" }, h("span", {}, "Stop all"), h("small", {}, "hold"));
  const really = h("button", { class: "btn danger", type: "button" }, "Stop every ork");
  const stopSheet = sheet("Stop all",
    h("p", {}, "Every ork at work stops now: their sessions are interrupted and their processes ended."),
    really, h("p", { class: "muted" }, "Holding Stop all does the same without this step."));
  async function halt() {
    stopSheet.close();
    stop.disabled = really.disabled = true;
    const r = await ctx.send("halt");
    stop.disabled = really.disabled = false;
    ctx.flash(r.ok ? `Stopped: ${r.result} session(s)` : r.error);
  }
  really.addEventListener("click", halt);
  let timer = 0;
  let held = false;
  const release = () => { clearTimeout(timer); stop.classList.remove("holding"); };
  stop.addEventListener("pointerdown", (e) => {
    if (e.button > 0) return;
    held = false;
    stop.classList.add("holding");
    timer = setTimeout(() => { held = true; release(); navigator.vibrate?.(60); halt(); }, HOLD_MS);
  });
  for (const ev of ["pointerup", "pointerleave", "pointercancel"]) stop.addEventListener(ev, release);
  stop.addEventListener("contextmenu", (e) => e.preventDefault());   // a long press is ours, not the browser's menu
  // A tap (or a screen reader's activation) asks first, with its button up the screen, away from this one.
  stop.addEventListener("click", () => { if (held) { held = false; return; } stopSheet.open(); });

  const askBtnDock = h("button", { class: "btn", type: "button", onclick: () => { askSheet.open(); readChat(); } }, "Ask");
  const dropBtnDock = h("button", { class: "btn", type: "button", onclick: () => dropSheet.open() }, "Drop");
  const el = h("nav", { class: "dock", "aria-label": "Actions" }, h("div", { class: "dock-in" },
    askBtnDock, dropBtnDock,
    h("button", { class: "btn", type: "button", onclick: () => moreSheet.open() }, "More"), stop));

  return {
    el,
    sheets: [askSheet.el, dropSheet.el, moreSheet.el, stopSheet.el],
    render(town) {
      askBtnDock.hidden = !ctx.building("town_hall");
      dropBtnDock.hidden = !ctx.building("pit");
      const chosen = town.portrait?.look || town.look;
      for (const b of looks.children) b.classList.toggle("is-on", b.dataset.look === chosen);
    },
    phone(version) {
      phone.textContent = `This phone: ${ctx.device()?.name || ""}${version ? ` · Orkcraft ${version}` : ""}`;
    },
    openDrop() { if (ctx.building("pit")) dropSheet.open(); },
  };
}

function base64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}
