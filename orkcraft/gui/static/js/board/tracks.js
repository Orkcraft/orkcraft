// The goal switch and the ideas of a goal (29a §7, 33 §6): ideas drag to reorder; a click opens the idea's spec in the preview.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { board, track, adding, ask, stateWords } from "./store.js";
import { act as run, preview, showIdea, refreshShell } from "../shell/store.js";

const DRAG = "text/x-board-slug";
const drag = (slug) => (e) => { e.dataTransfer.setData(DRAG, slug); e.dataTransfer.effectAllowed = "move"; };
const takes = (e) => e.dataTransfer.types.includes(DRAG);

/** The goal shown (docs/design: spec 32 words): a switch when there are several, else its name. */
export function Goals() {
  const b = board.value;
  const sorted = [...b.tracks].sort((x, y) => x.order - y.order);
  const [making, setMaking] = useState(null);
  const make = async (e) => {
    e.preventDefault();
    const title = making.trim();
    setMaking(null);
    if (title) { const got = await ask("ideas.track_add", { title }); if (got) track.value = got.slug; await refreshShell(); }
  };
  const drop = (t) => (e) => {          // an idea dropped on the goal joins it
    e.preventDefault();
    const slug = e.dataTransfer.getData(DRAG);
    if (slug && b.ideas.some((i) => i.slug === slug)) run("ideas.move", { slug, track: t.slug });
  };
  return html`<div class="board-goals" aria-label="Goal">
    ${sorted.length > 1 ? html`<select class="ok-input board-goals__switch" aria-label="Goal" value=${track.value}
        onChange=${(e) => { track.value = e.target.value; }}>
        <option value="">All goals</option>${sorted.map((t) => html`<option key=${t.slug} value=${t.slug}>${t.title} (${t.count})</option>`)}</select>`
      : html`<span class="board-goals__name" onDragOver=${(e) => takes(e) && e.preventDefault()} onDrop=${sorted[0] && drop(sorted[0])}>
        <span class="ok-tone-muted">Your goal:</span> ${sorted[0] ? sorted[0].title : "General"}</span>`}
    ${making === null ? html`<button class="board-link" onClick=${() => setMaking("")}>+ New goal</button>`
      : html`<form class="board-row" onSubmit=${make}><input class="ok-input" autofocus value=${making} aria-label="Name of the goal"
          placeholder="Name of the goal" onInput=${(e) => setMaking(e.target.value)} onKeyDown=${(e) => e.key === "Escape" && setMaking(null)} />
        <button class="ok-btn primary" disabled=${!making.trim()}>Add</button></form>`}
  </div>`;
}

function Card({ i }) {
  const [over, setOver] = useState(false);
  return html`<li><button draggable="true" onDragStart=${drag(i.slug)} data-state=${i.state}
    class=${cls("board-card kit-well", { "is-on": preview.value?.slug === i.slug && preview.value?.kind === "idea", "is-over": over })}
    onDragOver=${(e) => { if (takes(e)) { e.preventDefault(); setOver(true); } }} onDragLeave=${() => setOver(false)}
    onDrop=${(e) => { e.preventDefault(); setOver(false); const s = e.dataTransfer.getData(DRAG);
      if (s && s !== i.slug) run("ideas.move", { slug: s, track: i.track, before: i.slug }); }}
    onClick=${() => showIdea(i.slug)}>
    <b class="board-card__title">${i.title}</b>
    ${i.thesis && html`<span class="board-card__thesis">${i.thesis}</span>`}
    <span class="board-card__meta">${i.size && html`<span class="board-size kit-well">${i.size}</span>`}
      <span class="board-state" data-state=${i.state}>${stateWords(i)}</span></span>
  </button></li>`;
}

function Drop() {
  const [text, setText] = useState("");
  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    const got = await run("ideas.add", { text: text.trim(), ...(track.value ? { track: track.value } : {}) });
    if (got) { setText(""); adding.value = false; if (got.slug) showIdea(got.slug); }
  };
  return html`<form class="board-drop" onSubmit=${send}>
    <textarea class="ok-input" rows="3" autofocus value=${text} aria-label="Your idea" placeholder="Your idea, in a few words or a few lines"
      onInput=${(e) => setText(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(e); else if (e.key === "Escape") adding.value = false; }}></textarea>
    <div class="board-row"><button class="ok-btn primary" disabled=${!text.trim()}>Drop it</button>
      <button type="button" class="ok-btn" onClick=${() => { adding.value = false; }}>Cancel</button></div>
  </form>`;
}

export function Ideas() {
  const b = board.value;
  const ideas = b.ideas.filter((i) => !track.value || i.track === track.value).sort((x, y) => x.order - y.order);
  return html`<section class="board-ideas" aria-label="Ideas">
    <h3 class="board-sub kit-band">Ideas ${ideas.length ? html`<span class="board-count kit-well">${ideas.length}</span>` : ""}</h3>
    ${adding.value && html`<${Drop} />`}
    ${ideas.length ? html`<ul class="board-list">${ideas.map((i) => html`<${Card} key=${i.slug} i=${i} />`)}</ul>`
      : html`<p class="ok-tone-muted">No idea here yet.</p>`}
  </section>`;
}
