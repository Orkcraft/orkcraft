// New idea (docs/specs/34-v1-round-2.md §2): one short text and the goal it belongs to (the goal open on the board, or
// General). Process now saves it and the Taskmaster reads it at once; Later saves it for the batch. Closing the dialog
// with text in it saves it as Later (never lost); closing it empty saves nothing.
import { useState } from "preact/hooks";
import { html } from "../html.js";
import { say } from "../link.js";
import { board, track } from "../board/store.js";
import { act, showIdea } from "./store.js";
import { Modal, closeDialog } from "./modals.js";

export function IdeaDialog() {
  const goals = board.value?.tracks || [];
  const [text, setText] = useState("");
  const [goal, setGoal] = useState(track.value || "general");
  const [busy, setBusy] = useState(false);
  const send = async (now) => {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    const got = await act("ideas.add", { text: t, now, ...(goal && goal !== "general" ? { track: goal } : {}) });
    setBusy(false);
    if (got?.slug) { closeDialog(); showIdea(got.slug); }
  };
  const close = async () => {                 // closed with text in it: saved as Later
    const t = text.trim();
    closeDialog();
    if (t) await act("ideas.add", { text: t, now: false, ...(goal && goal !== "general" ? { track: goal } : {}) });
  };
  return html`<${Modal} title="New idea" onClose=${close}
    foot=${html`<button type="button" class="ok-btn" disabled=${!text.trim() || busy} onClick=${() => send(false)}
        title="Save it now; the Taskmaster reads it in the next round">Later</button>
      <button type="button" class="ok-btn primary" disabled=${!text.trim() || busy} onClick=${() => send(true)}
        title=${say("Save it and the Taskmaster reads it at once")}>Process now</button>`}>
    <div class="shell-form">
      <label class="shell-field"><span class="ok-font-label">Your idea</span>
        <textarea class="ok-input" rows="4" autofocus value=${text} aria-label="Your idea" placeholder="Your idea, in a few words or a few lines"
          onInput=${(e) => setText(e.target.value)}
          onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(true); } }}></textarea></label>
      <label class="shell-field"><span class="ok-font-label">Belongs to goal</span>
        <select class="ok-input" aria-label="Goal" value=${goal} onChange=${(e) => setGoal(e.target.value)}>
          ${goals.map((g) => html`<option key=${g.slug} value=${g.slug}>${g.title}</option>`)}
          ${!goals.some((g) => g.slug === "general") && html`<option value="general">General</option>`}</select></label>
      <p class="ok-font-status ok-tone-muted">${say("Process now: the Taskmaster reads it at once. Later: it waits for the next round. Closing this with text in it saves it as Later.")}</p>
    </div>
  <//>`;
}
