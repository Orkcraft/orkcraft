// The Board pane, on the left (docs/specs/33-v1-shell.md §6): the goal (a switch when there are several), New idea,
// Today (Needs you, then to-dos), the ideas in order with their state in words. A click opens the preview.
import { html } from "../html.js";
import { board, adding } from "../board/store.js";
import { Today } from "../board/today.js";
import { Goals, Ideas } from "../board/tracks.js";

export function BoardPane() {
  const b = board.value;
  return html`<section class="shell-pane shell-board" aria-label="Board">
    <header class="shell-pane__head"><h2>Board</h2>
      <button class="ok-btn primary" onClick=${() => { adding.value = true; }}>New idea</button></header>
    <div class="shell-pane__body">
      ${b ? html`<${Goals} /><${Today} /><${Ideas} />` : html`<p class="ok-tone-muted">Opening the board…</p>`}
    </div>
  </section>`;
}
