// Improve Orkcraft (gui/fixes.py, docs/design/improve-buildings.md §14): Comment mode, then a press on any part of the
// window says what should change there, for the Alchemist; the comments, and the Mechanic's code fixes from the logs,
// are written as fixes in a copy of Orkcraft's source by this machine's main tool, shown, tried here (Preview: the
// page from the copy) and sent to Orkcraft as a pull request. Comment mode: the mascot's menu, or Ctrl/⌘+Shift+M.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, toast, town } from "./link.js";
import { Dialog } from "./dialog.js";

export const commentMode = signal(false);
export const fixesOpen = signal(false);

const SKIP = ".gui-comment";                     // the mode's own bar, frame and note are never what is commented on

function selectorOf(el) {
  const parts = [];
  for (let e = el; e && e !== document.body && parts.length < 6; e = e.parentElement) {
    let part = e.tagName.toLowerCase();
    if (e.id) part += `#${e.id}`;
    const classes = [...e.classList].filter((c) => !c.startsWith("is-")).slice(0, 3);
    if (classes.length) part += `.${classes.join(".")}`;
    parts.unshift(part);
  }
  return parts.join(" > ");
}

/** What the person pressed, for the Alchemist: where it is and what it is, never what is behind it. */
function whereOf(el) {
  const win = el.closest("[aria-label]");
  const hut = el.closest("[data-id]");
  const t = town.value;
  const b = hut && t && t.buildings.find((x) => x.id === hut.dataset.id);
  const text = (el.innerText || el.getAttribute("aria-label") || el.getAttribute("title") || "").trim().replace(/\s+/g, " ");
  return {
    selector: selectorOf(el), text: text.slice(0, 400), html: el.outerHTML.slice(0, 1500),
    window: win ? win.getAttribute("aria-label") : "", building: b ? `${b.title} (${b.type})` : "",
    look: document.documentElement.dataset.look || "", size: `${window.innerWidth}×${window.innerHeight}`,
  };
}

/** Comment mode: a frame follows the pointer, a press opens a note beside what was pressed. */
export function CommentLayer() {
  const [hover, setHover] = useState(null);
  const [picked, setPicked] = useState(null);       // {el, rect, where}
  const [text, setText] = useState("");
  const on = commentMode.value;
  useEffect(() => {                                  // Ctrl/⌘+Shift+M turns it on and off, anywhere
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === "M" || e.key === "m")) { e.preventDefault(); commentMode.value = !commentMode.value; }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!on) { setHover(null); setPicked(null); return undefined; }
    const mine = (e) => e.target instanceof Element && e.target.closest(SKIP);
    const move = (e) => { if (!picked && !mine(e) && e.target instanceof Element) setHover(e.target.getBoundingClientRect()); };
    const press = (e) => {
      if (mine(e) || !(e.target instanceof Element)) return;
      e.preventDefault(); e.stopPropagation();
      if (e.type !== "click") return;
      setPicked({ rect: e.target.getBoundingClientRect(), where: whereOf(e.target) }); setText("");
    };
    const esc = (e) => { if (e.key === "Escape") { if (picked) setPicked(null); else commentMode.value = false; } };
    document.addEventListener("pointermove", move, true);
    for (const t of ["click", "pointerdown", "mousedown", "pointerup", "mouseup"]) document.addEventListener(t, press, true);
    window.addEventListener("keydown", esc, true);
    return () => {
      document.removeEventListener("pointermove", move, true);
      for (const t of ["click", "pointerdown", "mousedown", "pointerup", "mouseup"]) document.removeEventListener(t, press, true);
      window.removeEventListener("keydown", esc, true);
    };
  }, [on, picked]);
  if (!on) return null;
  const f = (town.value && town.value.fixes) || {};
  const box = (r) => `left:${r.left - 2}px;top:${r.top - 2}px;width:${r.width + 4}px;height:${r.height + 4}px`;
  const send = () => command("fixes.comment", { text, where: picked.where }).then((r) => {
    toast(say(r.said), "information", say("Comment"));
    setPicked(null);
  }, () => {});
  const r = picked && picked.rect;
  const noteAt = r ? `left:${Math.max(8, Math.min(r.left, window.innerWidth - 340))}px;top:${r.bottom + 8 + 180 > window.innerHeight ? Math.max(8, r.top - 188) : r.bottom + 8}px` : "";
  return html`<div class="gui-comment">
    <div class="gui-comment__bar ok-font-status" role="status">
      <b>${say("Comment mode")}</b> · ${say("press the part of the window that should change, and say how. Esc leaves.")}
      <button class="gui-link" onClick=${() => { commentMode.value = false; fixesOpen.value = true; }}>${say(`Improve Orkcraft${f.comments ? ` (${f.comments} waiting)` : ""}`)}</button>
      <button class="gui-link" onClick=${() => { commentMode.value = false; }}>${say("Done")}</button>
    </div>
    ${(r || hover) && html`<div class="gui-comment__frame" style=${box(r || hover)}></div>`}
    ${picked && html`<div class="gui-comment__note" style=${noteAt} role="dialog" aria-label=${say("Comment")}>
      <span class="ok-font-label">${say("What should change here?")}</span>
      <span class="ok-font-status ok-tone-muted">${say(picked.where.window || picked.where.selector)}</span>
      <textarea class="ok-input" rows="4" value=${text} onInput=${(e) => setText(e.target.value)} autoFocus
        onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && text.trim()) send(); }}></textarea>
      <span class="gui-comment__acts">
        <button class="ok-btn" onClick=${() => setPicked(null)}>${say("Cancel")}</button>
        <button class="ok-btn is-primary" disabled=${!text.trim()} onClick=${send}>${say("Send to the Alchemist")}</button>
      </span>
    </div>`}
  </div>`;
}

const STATE = { writing: "being written…", ready: "written", empty: "nothing changed", failed: "could not be written", sent: "sent" };

function FixRow({ f, preview, login, onDone }) {
  const [more, setMore] = useState("");
  const [pr, setPr] = useState(null);
  const run = (name, args = {}) => command(name, { id: f.id, ...args }).then((r) => { if (r && r.reload) location.reload(); onDone(r); }, () => {});
  return html`<li class=${cls("gui-fixes__fix", `is-${f.state}`)}>
    <span class="ok-font-label">${say(f.title)}</span>
    <span class="ok-font-status ok-tone-muted">${say(`${f.who} · ${STATE[f.state] || f.state}`)}${f.files.length ? ` · ${f.files.length} ${say(f.files.length === 1 ? "file" : "files")}` : ""}</span>
    ${f.comments.length > 1 && html`<ul class="ok-font-status">${f.comments.map((c, i) => html`<li key=${i}>“${c}”</li>`)}</ul>`}
    ${f.said && html`<p class="ok-font-status">${f.said}</p>`}
    ${f.error && html`<p class="ok-font-status ok-tone-error" role="alert">✗ ${say(f.error)}</p>`}
    ${f.pr && html`<p class="ok-font-status">${say("Pull request:")} <a class="gui-link" href=${f.pr} target="_blank" rel="noopener">${f.pr}</a></p>`}
    ${f.diff && html`<details><summary class="ok-font-status">${say("What changes")}</summary><pre class="gui-fixes__diff">${f.diff}</pre></details>`}
    ${pr && html`<div class="gui-fixes__pr">
      <span class="ok-font-label">${say("What leaves this machine")}</span>
      <pre class="gui-fixes__diff">${pr.title}\n\n${pr.body}</pre>
      <span class="gui-comment__acts">
        <button class="ok-btn" onClick=${() => setPr(null)}>${say("Cancel")}</button>
        <button class="ok-btn is-primary" disabled=${!login || f.sending} onClick=${() => { setPr(null); run("fixes.send"); }}>${say(login ? `Send as @${login}` : "Connect GitHub first")}</button>
      </span></div>`}
    <span class="gui-fixes__acts">
      ${f.state === "ready" && f.page && html`<button class="ok-btn" onClick=${() => run("fixes.preview", { id: preview === f.id ? "" : f.id })}>${say(preview === f.id ? "Stop preview" : "Preview")}</button>`}
      ${f.state === "ready" && !pr && html`<button class="ok-btn is-primary" disabled=${f.sending} onClick=${() => command("fixes.pr", { id: f.id }).then(setPr, () => {})}>${say(f.sending ? "Sending…" : "Send as a pull request…")}</button>`}
      ${f.state !== "writing" && f.state !== "sent" && html`<span class="gui-fixes__more">
        <input class="ok-input" placeholder=${say("What else, or what instead?")} value=${more} onInput=${(e) => setMore(e.target.value)} />
        <button class="ok-btn" onClick=${() => { run("fixes.again", { text: more }); setMore(""); }}>${say(f.state === "ready" ? "Change it" : "Write it again")}</button></span>`}
      <button class="gui-link ok-font-status" onClick=${() => run("fixes.drop")}>${say(f.state === "sent" ? "Forget" : "Drop")}</button>
    </span>
  </li>`;
}

/** The comments waiting and the fixes, newest first. */
export function FixesDialog() {
  const [s, setS] = useState(null);
  const open = fixesOpen.value;
  const t = town.value;
  const load = () => command("fixes.state").then(setS, () => {});
  const sig = t && t.fixes ? `${t.fixes.comments}/${t.fixes.writing}/${t.fixes.ready}/${t.fixes.preview}` : "";
  useEffect(() => { if (open) load(); }, [open, sig]);
  if (!open) return null;
  const close = () => { fixesOpen.value = false; };
  const meta = s && (s.kind === "worktree"
    ? "Orkcraft runs from a git checkout: each fix is written in a worktree of it, with its CLAUDE.md and its tests."
    : "Each fix is written in a copy of the package as installed (no tests there). Run Orkcraft from a git checkout to have them run.");
  return html`<${Dialog} title=${say("Improve Orkcraft")} wide onCancel=${close} meta=${meta && say(meta)}
      actions=${html`<button class="ok-btn" onClick=${close}>${say("Close")}</button>`}>
    ${!s ? html`<p class="ok-font-status">${say("Loading…")}</p>` : html`
      <section class="gui-fixes">
        <span class="ok-font-label">${say("Comments for the Alchemist")}</span>
        ${s.comments.length === 0 && html`<p class="ok-font-status ok-tone-muted">${say("None waits. Comment mode (Ctrl/⌘+Shift+M, or the mascot's menu): press any part of the window and say what should change.")}${" "}
          <button class="gui-link" onClick=${() => { commentMode.value = true; close(); }}>${say("Comment mode")}</button></p>`}
        <ul class="gui-fixes__list">${s.comments.map((c) => html`<li key=${c.id} class="ok-font-status">“${c.text}”
          <span class="ok-tone-muted"> — ${c.where.window || c.where.selector || ""}</span>
          <button class="gui-link" onClick=${() => command("fixes.drop_comment", { id: c.id }).then(setS, () => {})}>${say("Drop")}</button></li>`)}</ul>
        ${s.comments.length > 0 && html`<p><button class="ok-btn is-primary" onClick=${() => command("fixes.ask").then(setS, () => {})}>${say(`Ask the Alchemist (${s.comments.length})`)}</button></p>`}
        <span class="ok-font-label">${say("Fixes")}</span>
        ${s.fixes.length === 0 && html`<p class="ok-font-status ok-tone-muted">${say("None yet. The Alchemist writes them from comments; the Mechanic from the code findings in Improve's logs (Write the fix).")}</p>`}
        <ul class="gui-fixes__list">${s.fixes.map((f) => html`<${FixRow} key=${f.id} f=${f} preview=${s.preview} login=${s.login} onDone=${(r) => r && r.fixes && setS(r)} />`)}</ul>
        ${!s.login && html`<p class="ok-font-status ok-tone-wait">${say("A pull request goes through GitHub: connect it in the mascot's menu → GitHub.")}</p>`}
      </section>`}
  </${Dialog}>`;
}
