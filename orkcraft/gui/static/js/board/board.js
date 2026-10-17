// The board, in focus (docs/specs/29a-board-focus.md §1, §7): when the snapshot's `focus` is "board" the window is
// this and a thin top bar — Stop all and today's spend — and nothing else of the town.
import { useEffect } from "preact/hooks";
import { html } from "../html.js";
import { town, command, say } from "../link.js";
import { board, opened, busy, refresh } from "./store.js";
import { Today } from "./today.js";
import { Tracks, Ideas } from "./tracks.js";
import { Idea } from "./idea.js";

const sheet = new URL("./board.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

function TopBar() {
  const t = town.value, hud = t.hud || {};
  const spend = hud.show_gold ? hud.gold : hud.lumber;
  return html`<header class="board-top">
    <span class="board-top__brand">Orkline</span>
    <span class="board-top__spacer"></span>
    <span class="board-top__spend" title="What was spent today">Spend ${spend ?? "—"}</span>
    <button class="gui-hud__stop kit-btn is-teal" title=${say("Stop every ork, script and browser at once")}
      onClick=${() => command("halt").catch(() => {})}>Stop all</button>
  </header>`;
}

export function Board() {
  const t = town.value;
  // Fresh when the town says the ideas changed, and every 10 s while a model runs (§7).
  useEffect(() => { refresh(); }, [t.ideas_rev]);
  useEffect(() => {
    const id = setInterval(() => { if (busy()) refresh(); }, 10000);
    return () => clearInterval(id);
  }, []);
  return html`<div class="board">
    <${TopBar} />
    ${board.value ? html`<main class=${`board-main${opened.value ? " has-idea" : ""}`}>
      <${Tracks} /><div class="board-mid"><${Today} /><${Ideas} /></div>${opened.value && html`<${Idea} />`}</main>`
      : html`<main class="board-main"><p class="ok-tone-muted">Opening the board…</p></main>`}
  </div>`;
}
