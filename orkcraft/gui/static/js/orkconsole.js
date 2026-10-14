// ▸ The ork's console, unfolded (docs/design/ork-console.md §7, §9, §14, §19–§21): everything of one ork in one place,
// at the town's foot where its folded console stands (js/slots.js). The host's `ork.console` (core/slots.py) gives it:
//
//   its sessions     the role's sessions as chips (§14), the asking one first: a press shows that session
//   its cart         what it works on, named; a press shows it on its building's card (§21: the talk lives there);
//                    its wait with why, until when and the way past it (§19)
//   its answer       in the order of §20: its questions pinned on top with their answers as buttons, the gist (three
//                    lines; its last paragraph when its AI tool gave none, and it says so), its assumptions, then the
//                    whole text folded — one press opens it, Read in the Inspector for a long one
//   its controls     ⏹ Stop (soft: its run ends where it is, its session kept), then Run again or Drop (§9); its
//                    terminal: Take over a working ork, Hand back, Resume its session — the live terminal under them
//   its history      its runs, newest first, each with its cost where it is known
//
// Fetched while it is unfolded, again whenever the town changes; folded, the snapshot's row is enough.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, act, say } from "./link.js";
import { openBuilding } from "./windows.js";
import { openInLake } from "./lake.js";
import { Terminal } from "./terminal.js";
import { useWaybill, WaybillBody, tokensWord } from "./camp/waybill.js";

export const consoleOrk = signal(null);       // the key of the ork whose console is shown
export const unfolded = signal(false);        // true: the console unfolded (depth 3), else folded (depth 2)
// What a console's cart link asks a building's card to show (§21): {building, id}. A type's card reads it.
export const shownCart = signal(null);
export const consoleTab = signal("now");     // the unfolded console's tab: now | history | tokens | task (I1)
const TABS = [["now", "Now"], ["history", "History"], ["tokens", "Tokens"], ["task", "Task"]];

/** Show the console of the ork `key` ("<building>/<ork>"), folded unless `open`. */
export function showConsole(key, open = false) {
  if (consoleOrk.value !== key) consoleTab.value = "now";
  consoleOrk.value = key;
  if (open) unfolded.value = true;
}

export function closeConsole() {
  consoleOrk.value = null;
  unfolded.value = false;
}

export function money(v) {
  return v ? `$${Number(v).toFixed(2)}` : "";
}

/** The console's data while it is unfolded: asked again when the town changes, one call at a time. */
function useConsole(key, open) {
  const [data, setData] = useState(null);
  const busy = useRef(false), again = useRef(false);
  const snap = town.value;
  useEffect(() => { setData(null); }, [key]);
  useEffect(() => {
    if (!key || !open) return;
    const ask = () => {
      if (busy.current) { again.current = true; return; }
      busy.current = true;
      command("ork.console", { key }).then((d) => setData(d || false), () => {}).finally(() => {
        busy.current = false;
        if (again.current) { again.current = false; ask(); }
      });
    };
    ask();
  }, [key, open, snap]);
  return data;
}

/** The ork's questions, pinned on top (§20): each with its answers as buttons; one question answers at a press,
 *  several fill the field a line each. A draft to post waits for its yes, or for what to change. */
export function Questions({ building, a }) {
  const [text, setText] = useState("");
  const send = (said) => act(building, "answer", { task: a.task, text: said }).then(() => setText(""), () => {});
  const qs = a.questions && a.questions.length ? a.questions : a.question ? [{ text: a.question, options: [] }] : [];
  const pick = (q, o) => (qs.length === 1 ? send(o) : setText((t) => `${t ? `${t}\n` : ""}${q.text} → ${o}`));
  if (a.draft) {
    return html`<section class="gui-orkconsole__asks" aria-label=${say("Waits for your yes")}>
      <b class="ok-tone-fire">${say(`Wants to post to ${a.target || "its place"}`)}</b>
      <pre class="gui-pre gui-orkconsole__draft">${a.draft_text}</pre>
      <div class="ok-row"><button class="ok-btn primary" onClick=${() => send("")}>${say("Post as is")}</button></div>
      <div class="ok-row"><input class="ok-input" value=${text} aria-label=${say("What to change")} placeholder=${say("Or what to change…")}
        onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === "Enter" && text.trim()) send(text); }} />
        <button class="ok-btn" disabled=${!text.trim()} onClick=${() => send(text)}>${say("Send back")}</button></div>
    </section>`;
  }
  return html`<section class="gui-orkconsole__asks" aria-label=${say("Its questions")}>
    ${qs.map((q, i) => html`<div key=${i} class="gui-orkconsole__q"><b>❓ ${q.text}</b>
      ${q.options.length > 0 && html`<div class="ok-row">${q.options.map((o) => html`<button key=${o} class="ok-btn"
        onClick=${() => pick(q, o)}>${o}</button>`)}</div>`}</div>`)}
    <div class="ok-row"><input class="ok-input" value=${text} aria-label=${say("Your answer")} placeholder=${say("Reply…")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === "Enter" && text.trim()) send(text); }} />
      <button class="ok-btn primary" disabled=${!text.trim()} onClick=${() => send(text)}>${say("Reply")}</button></div>
  </section>`;
}

/** The answer read in the order of §20, after its questions: the gist, the assumptions, the whole text folded. */
function Answer({ building, cart, a }) {
  const [open, setOpen] = useState(false);
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  return html`<section class="gui-orkconsole__answer" aria-label=${say("Its answer")}>
    ${a.gist && html`<p class="gui-orkconsole__gist">${a.gist.split("\n").map((ln, i) => html`<span key=${i}>${ln}</span>`)}</p>`}
    ${a.gist && a.gist_from === "last paragraph" && html`<p class="ok-tone-muted gui-orkconsole__note">${say("No gist given: its last paragraph.")}</p>`}
    ${a.error && a.error !== "stopped" && html`<p class="ok-tone-error">✖ ${a.error}</p>`}
    ${a.assumptions.length > 0 && html`<details class="gui-orkconsole__fold" open>
      <summary>${say(plural(a.assumptions.length, "assumption"))}</summary>
      <ul class="gui-rows">${a.assumptions.map((x, i) => html`<li key=${i}>${x}</li>`)}</ul></details>`}
    ${a.text && html`<details class="gui-orkconsole__fold" open=${open} onToggle=${(e) => setOpen(e.currentTarget.open)}>
      <summary>${say("The whole text")}</summary>
      ${open && html`<pre class="gui-pre gui-orkconsole__text">${a.text}</pre>
        <button class="ok-btn" onClick=${() => openInLake({ text: a.text, title: cart ? cart.title : say("Its answer"), from: building })}>
          ${say("Read in the Inspector")}</button>`}</details>`}
  </section>`;
}

/** Its terminal (§7: the terminal is the truth): Take over a working ork, Hand back, or Resume its session; the
 *  live terminal under them once it runs. */
function TerminalPart({ building, ork, t }) {
  const s = (town.value.sessions || []).find((x) => x.key === t.key) || null;
  const call = (name) => act(building, name, { ork }).catch(() => {});
  return html`<section class="gui-orkconsole__term" aria-label=${say("Its terminal")}>
    <div class="ok-row">
      ${t.working && !t.by_hand && html`<button class="ok-btn" title=${say("Stop its run where it is and go on in a terminal on its worktree")}
        onClick=${() => call("take_over")}>${say("Take over")}</button>`}
      ${t.by_hand && html`<button class="ok-btn primary" title=${say("Close the terminal: the steward reviews what is in its worktree")}
        onClick=${() => call("hand_back")}>${say("Hand back to review")}</button>`}
      ${!t.working && !(s && s.running) && html`<button class="ok-btn" title=${say("Its last session, on its worktree")}
        onClick=${() => call("terminal")}>${t.resumable ? say("Resume its session") : say("Open its terminal")}</button>`}
      ${s && !s.running && html`<span class="ok-tone-muted">${say("Its session has ended")}${s.exit_code ? ` · ${s.exit_code}` : ""}</span>`}
    </div>
    ${s && s.running && html`<div class="gui-orkconsole__xterm"><${Terminal} key=${s.key} sessionKey=${s.key} /></div>`}
  </section>`;
}

const RUN_MARK = { done: "✓", failed: "✖", asked: "❓", working: "💭", reviewing: "⌛", queued: "·" };

/** Its runs, newest first, each with its cost where it is known. */
function History({ d, building }) {
  if (!d.history.length) return html`<p class="ok-tone-muted">${say("No runs yet.")}</p>`;
  const t = d.totals;
  return html`<section aria-label=${say("Its history")}>
    <p class="ok-font-status ok-tone-muted">${say("History")}${t ? ` · ✓${t.done} ✖${t.failed}${t.cost ? ` · ${money(t.cost)}` : ""}${t.tokens ? ` · ${Math.round(t.tokens / 1000)}k ${say("tokens")}` : ""}` : ""}</p>
    <ul class="gui-rows gui-orkconsole__runs">${d.history.map((r) => html`<li key=${r.id} class="gui-orkconsole__run">
      <span title=${r.status}>${r.stopped ? "■" : RUN_MARK[r.status] || "·"}</span>
      <button class="gui-link" title=${r.gist || r.title} onClick=${() => { shownCart.value = { building, id: r.id }; }}>${r.title}</button>
      <span class="ok-tone-muted">${[r.dropped ? say("dropped") : r.stopped ? say("stopped by you") : "",
        r.assumptions ? `${r.assumptions} ${say(r.assumptions === 1 ? "assumption" : "assumptions")}` : "",
        r.warm ? "♻" : ""].filter(Boolean).join(" · ")}</span>
      <span class="gui-slots__num">${r.cost ? money(r.cost) : "—"}</span></li>`)}</ul>
  </section>`;
}

/** What its runs spent: its totals, then each run's tokens and spend; a number no run recorded says so. */
function Tokens({ d }) {
  const t = d.totals, none = html`<span class="ok-tone-muted">${say("not recorded")}</span>`;
  return html`<section aria-label=${say("Its tokens")}>
    <p class="ok-font-status">${say("In all")}: ${t && t.tokens ? `${tokensWord(t.tokens)} ${say("tokens")}` : none}
      · ${t && t.cost ? money(t.cost) : none}</p>
    ${d.history.length ? html`<table class="gui-orkconsole__tokens"><tbody>${d.history.map((r) => html`<tr key=${r.id}>
      <td>${r.title}</td><td>${r.tokens ? tokensWord(r.tokens) : none}</td><td>${r.cost ? money(r.cost) : none}</td></tr>`)}</tbody></table>`
      : html`<p class="ok-tone-muted">${say("No runs yet.")}</p>`}
  </section>`;
}

/** The task it works on, as its waybill: where it stopped, the tokens, the time. */
function Task({ building, cart }) {
  const d = useWaybill(cart ? { building, task: cart.id } : null);
  if (!cart) return html`<p class="ok-tone-muted">${say("No task now.")}</p>`;
  return html`<section aria-label=${say("Its task")}><p class="gui-orkconsole__cart">«${cart.title}»</p><${WaybillBody} d=${d} /></section>`;
}

/** The unfolded console's body (§7, depth 3), under the folded console's head. */
export function Unfolded({ orkKey, r }) {
  const d = useConsole(orkKey, true);
  if (d === null) return html`<p class="ok-tone-muted">${say("Opening…")}</p>`;
  if (d === false) return html`<p class="ok-tone-muted">${say("Nothing more is known of this ork.")}</p>`;
  const building = d.row.building_id;
  const ork = d.row.name;
  const cart = d.cart;
  const a = d.answer;
  const asks = r && r.answer && r.answer.kind === "pool" ? r.answer : a && (a.questions.length || a.question || a.draft)
    ? { ...a, task: cart && cart.id } : null;
  const go = (name) => act(building, name, { task: cart.id }).catch(() => {});
  const tab = consoleTab.value;
  const tabs = html`<nav class="ok-tabs gui-orkconsole__tabs" role="tablist" aria-label=${say("Its console")}>${TABS.map(([id, word]) =>
    html`<button key=${id} type="button" role="tab" aria-selected=${tab === id} class=${cls("ok-tab", { "is-active": tab === id })}
      onClick=${() => { consoleTab.value = id; }}>${say(word)}</button>`)}</nav>`;
  if (tab === "history") return html`<div class="gui-orkconsole__body">${tabs}<${History} d=${d} building=${building} /></div>`;
  if (tab === "tokens") return html`<div class="gui-orkconsole__body">${tabs}<${Tokens} d=${d} /></div>`;
  if (tab === "task") return html`<div class="gui-orkconsole__body">${tabs}<${Task} building=${building} cart=${cart} /></div>`;
  return html`<div class="gui-orkconsole__body">${tabs}
    ${d.sessions.length > 1 && html`<nav class="gui-orkconsole__sessions" aria-label=${say(`${d.role}: its sessions`)}>
      <span class="ok-tone-muted">${say(d.role)}</span>
      ${d.sessions.map((s) => html`<button key=${s.key} class=${cls("pool-chip", `is-${s.state}`, { "is-this": s.this })}
        title=${say(s.line)} aria-pressed=${s.this} onClick=${() => { consoleOrk.value = s.key; }}>
        <span class="pool-chip__mark">${s.mark}</span> ${s.name}</button>`)}</nav>`}
    ${cart && html`<p class="gui-orkconsole__cart">${say("On")} <button class="gui-link" title=${say("Show it on its building's card")}
        onClick=${() => { shownCart.value = { building, id: cart.id }; }}>«${cart.title}»</button>
      ${cart.cost ? html` <span class="ok-tone-muted">· ${money(cart.cost)}</span>` : ""}
      ${cart.pr && html` · <a class="gui-link" href=${cart.pr} target="_blank" rel="noreferrer">PR ↗</a>`}</p>`}
    ${asks && html`<${Questions} building=${building} a=${asks} />`}
    ${cart && cart.wait && !asks && html`<p class="ok-tone-muted">⏳ ${cart.wait.line}
      ${cart.wait.skip && cart.wait.skip.act !== "open" && html` <button class="ok-btn"
        onClick=${() => act(building, cart.wait.skip.act, cart.wait.skip.args).catch(() => {})}>${say(cart.wait.skip.label)}</button>`}</p>`}
    ${cart && cart.stopped && html`<div class="ok-row"><span class="ok-tone-muted">■ ${say("Stopped by you")}</span>
      <button class="ok-btn primary" title=${say("Its session goes on where it stopped")} onClick=${() => go("run_again")}>${say("Run again")}</button>
      <button class="ok-btn" title=${say("Closed as dropped: it does not run again")} onClick=${() => go("drop")}>${say("Drop")}</button></div>`}
    ${a && html`<${Answer} building=${building} cart=${cart} a=${a} />`}
    ${d.terminal && html`<${TerminalPart} building=${building} ork=${ork} t=${d.terminal} />`}
  </div>`;
}
