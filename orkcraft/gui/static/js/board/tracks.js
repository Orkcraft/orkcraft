// The tracks column and the ideas of a track (§7): both drag to reorder; an idea dropped on a track moves there.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { board, track, opened, adding, open, run, ask, stateWords } from "./store.js";

const DRAG = "text/x-board-slug";
const drag = (slug) => (e) => { e.dataTransfer.setData(DRAG, slug); e.dataTransfer.effectAllowed = "move"; };
const takes = (e) => e.dataTransfer.types.includes(DRAG);

export function Tracks() {
  const b = board.value;
  const [over, setOver] = useState("");
  const [making, setMaking] = useState(null);
  const sorted = [...b.tracks].sort((x, y) => x.order - y.order);
  const drop = (t) => (e) => {
    e.preventDefault(); setOver("");
    const slug = e.dataTransfer.getData(DRAG);
    if (!slug || slug === t.slug) return;
    // an idea joins the track; a track goes before this one
    run("ideas.move", b.ideas.some((i) => i.slug === slug) ? { slug, track: t.slug } : { slug, before: t.slug });
  };
  const make = async (e) => {
    e.preventDefault();
    const title = making.trim();
    setMaking(null);
    if (title) { const got = await ask("ideas.track_add", { title }); if (got) track.value = got.slug; await run("ideas.board"); }
  };
  return html`<nav class="board-tracks board-col kit-frame kit-paper" aria-label="Goals">
    <h2 class="board-h board-col__plate kit-plate">Goals</h2>
    <div class="board-col__body">
    <button class=${cls("board-track", { "is-on": !track.value })} onClick=${() => { track.value = ""; }}>
      <span>All ideas</span><span class="board-count kit-well">${b.ideas.length}</span></button>
    ${sorted.map((t) => html`<button key=${t.slug} draggable="true" onDragStart=${drag(t.slug)}
      class=${cls("board-track", { "is-on": track.value === t.slug, "is-over": over === t.slug })}
      onDragOver=${(e) => { if (takes(e)) { e.preventDefault(); setOver(t.slug); } }} onDragLeave=${() => setOver("")}
      onDrop=${drop(t)} onClick=${() => { track.value = t.slug; }} title=${t.about || t.title}>
      <span>${t.title}</span><span class="board-count kit-well">${t.count}</span></button>`)}
    ${making === null ? html`<button class="ok-btn" onClick=${() => setMaking("")}>+ New goal</button>`
      : html`<form class="board-row" onSubmit=${make}><input class="ok-input" autofocus value=${making} aria-label="Name of the goal"
          placeholder="Name of the goal" onInput=${(e) => setMaking(e.target.value)} onKeyDown=${(e) => e.key === "Escape" && setMaking(null)} />
        <button class="ok-btn primary" disabled=${!making.trim()}>Add</button></form>`}
    </div>
  </nav>`;
}

function Card({ i }) {
  const [over, setOver] = useState(false);
  return html`<li><button draggable="true" onDragStart=${drag(i.slug)} data-state=${i.state}
    class=${cls("board-card kit-well", { "is-on": opened.value === i.slug, "is-over": over })}
    onDragOver=${(e) => { if (takes(e)) { e.preventDefault(); setOver(true); } }} onDragLeave=${() => setOver(false)}
    onDrop=${(e) => { e.preventDefault(); setOver(false); const s = e.dataTransfer.getData(DRAG);
      if (s && s !== i.slug) run("ideas.move", { slug: s, track: i.track, before: i.slug }); }}
    onClick=${() => open(i.slug)}>
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
    if (got) { setText(""); adding.value = false; if (got.slug) open(got.slug); }
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
  const t = b.tracks.find((x) => x.slug === track.value);
  const ideas = b.ideas.filter((i) => !track.value || i.track === track.value).sort((x, y) => x.order - y.order);
  return html`<section class="board-ideas" aria-label="Ideas">
    <div class="board-bar kit-band"><h2 class="board-h">${t ? t.title : "All ideas"}</h2>
      ${!adding.value && html`<button class="ok-btn" onClick=${() => { adding.value = true; }}>+ Idea</button>`}</div>
    ${t && t.about && html`<p class="ok-tone-muted">${t.about}</p>`}
    ${adding.value && html`<${Drop} />`}
    ${ideas.length ? html`<ul class="board-list">${ideas.map((i) => html`<${Card} key=${i.slug} i=${i} />`)}</ul>`
      : html`<p class="ok-tone-muted">No idea here yet.</p>`}
  </section>`;
}
