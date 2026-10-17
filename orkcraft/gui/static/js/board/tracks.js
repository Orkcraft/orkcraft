// The goal switch and the ideas of a goal (29a §7, 33 §6): ideas drag to reorder; a click opens the idea's spec in the preview.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { board, track, stateWords } from "./store.js";
import { act as run, preview, showIdea, showGoal } from "../shell/store.js";
import { openDialog } from "../shell/modals.js";

const DRAG = "text/x-board-slug";
const drag = (slug) => (e) => { e.dataTransfer.setData(DRAG, slug); e.dataTransfer.effectAllowed = "move"; };
const takes = (e) => e.dataTransfer.types.includes(DRAG);

const PRIORITY_WORDS = { high: "High", normal: "Normal", low: "Low" };
const GOAL_WORDS = { reading: "reading", asks: "asks you", ready: "ready" };

/** The goals (spec 34 §7): each with its priority and state in words, New goal, Edit; a click opens the goal in the preview and
 *  shows its ideas (a second click shows all). */
export function Goals() {
  const b = board.value;
  return html`<div class="board-goals" aria-label="Goals">
    <h3 class="board-sub kit-band">Goals ${b.tracks.length ? html`<span class="board-count kit-well">${b.tracks.length}</span>` : ""}</h3>
    <ul class="board-list">${b.tracks.map((g) => html`<li key=${g.slug} class=${cls("board-goal", { "is-on": track.value === g.slug })} data-state=${g.state}
      onDragOver=${(e) => takes(e) && e.preventDefault()}
      onDrop=${(e) => { e.preventDefault(); const slug = e.dataTransfer.getData(DRAG);        // an idea dropped on a goal joins it
        if (slug && b.ideas.some((i) => i.slug === slug)) run("ideas.move", { slug, track: g.slug }); }}>
      <button class="board-goal__main" aria-pressed=${track.value === g.slug}
        onClick=${() => { track.value = track.value === g.slug ? "" : g.slug; showGoal(g.slug); }}>
        <b>${g.title}</b>
        <span class="board-goal__meta"><span class="board-prio" data-priority=${g.priority}>${PRIORITY_WORDS[g.priority]}</span>
          ${GOAL_WORDS[g.state] && html`<span class="board-state" data-state=${g.state}>${say(GOAL_WORDS[g.state])}</span>`}
          <span class="ok-tone-muted">${g.count} idea${g.count === 1 ? "" : "s"}</span></span></button>
      <button class="board-link" aria-label=${`Edit goal ${g.title}`} onClick=${() => openDialog("goal", { slug: g.slug })}>Edit</button></li>`)}</ul>
  </div>`;
}

function Card({ i }) {
  const [over, setOver] = useState(false);
  return html`<li class="board-card-row"><button draggable="true" onDragStart=${drag(i.slug)} data-state=${i.state}
    class=${cls("board-card kit-well", { "is-on": preview.value?.slug === i.slug && preview.value?.kind === "idea", "is-over": over })}
    onDragOver=${(e) => { if (takes(e)) { e.preventDefault(); setOver(true); } }} onDragLeave=${() => setOver(false)}
    onDrop=${(e) => { e.preventDefault(); setOver(false); const s = e.dataTransfer.getData(DRAG);
      if (s && s !== i.slug) run("ideas.move", { slug: s, track: i.track, before: i.slug }); }}
    onClick=${() => showIdea(i.slug)}>
    <b class="board-card__title">${i.title}</b>
    ${i.thesis && html`<span class="board-card__thesis">${i.thesis}</span>`}
    <span class="board-card__meta">${i.size && html`<span class="board-size kit-well">${i.size}</span>`}
      <span class="board-prio" data-priority=${i.priority}>${PRIORITY_WORDS[i.priority] || "Normal"}</span>
      <span class="board-state" data-state=${i.state}>${stateWords(i)}</span></span>
  </button>
  ${i.state === "raw" && html`<button class="ok-btn board-card__now" aria-label=${`Process now: ${i.title}`} title=${say("The Taskmaster reads it at once")}
    onClick=${() => run("ideas.read_now", { slug: i.slug })}>Process now</button>`}</li>`;
}

export function Ideas() {
  const b = board.value;
  const ideas = b.ideas.filter((i) => !track.value || i.track === track.value).sort((x, y) => x.order - y.order);
  return html`<section class="board-ideas" aria-label="Ideas">
    <h3 class="board-sub kit-band">Ideas ${ideas.length ? html`<span class="board-count kit-well">${ideas.length}</span>` : ""}</h3>
    ${ideas.length ? html`<ul class="board-list">${ideas.map((i) => html`<${Card} key=${i.slug} i=${i} />`)}</ul>`
      : html`<p class="ok-tone-muted">No idea here yet.</p>`}
  </section>`;
}
