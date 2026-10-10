// 🧪 The Test bench (docs/design/test-bench.md §2). Closed: the building it tests and its last run, passed or not.
// Open: which building, when more than one road comes in, then the bench itself (js/bench.js) for it. A road into
// the Test bench says what it tests; a road out of it, where its reports and findings go.
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { BenchView } from "../bench.js";

const sheet = new URL("./lab.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.subject) {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Nothing to test")}</div>
      <div class="gui-hut__text ok-tone-muted">${say("Pull a road from a building into it")}</div>
    </div>`;
  }
  const last = c.last;
  const tone = !last ? "" : last.passed === true ? "ok-tone-ok" : last.passed === false ? "ok-tone-error" : "";
  return html`<div class="gui-hut__body-in">
    <div class=${cls("gui-hut__big", tone)}>${last ? say(last.verdict.split(",")[0]) : say("No run yet")}<small>${last ? last.case : ""}</small></div>
    <div class="gui-hut__foot"><span>${say(`Tests ${c.subject.title}`)}${c.count > 1 ? ` +${c.count - 1}` : ""}</span>
      ${c.targets > 0 && html`<span class="gui-hut__when">${say(`→ ${c.targets} road${c.targets === 1 ? "" : "s"}`)}</span>`}</div>
  </div>`;
}

function Window({ id, data }) {
  const subjects = data.subjects || [];
  if (!subjects.length) {
    return html`<div class="lab-empty">
      <p class="ok-font-body">${say("The Test bench tests the building whose road comes into it, or a whole chain.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("One building: pull a road from it (the Agent pool, External listeners, the Task board…) into the Test bench.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("A chain: pull a road with “test case” from the Test bench into the chain's first building, and a road from its last building back into the Test bench.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("Any other road out of it takes its reports and findings where they should go.")}</p>
    </div>`;
  }
  const pick = data.subject || subjects[0].id;
  return html`<div class="lab-window">
    ${subjects.length > 1 && html`<label class="gui-field lab-pick"><span class="ok-font-label">${say("Tests")}</span>
      <select class="ok-input" value=${pick} onChange=${(e) => act(id, "pick", { id: e.target.value })}>
        ${subjects.map((s) => html`<option key=${s.id} value=${s.id}>${say(s.title)} · ${say(s.word)}</option>`)}</select></label>`}
    <${BenchView} key=${pick} id=${pick} lab=${id} />
  </div>`;
}

/** The window: one pane, the bench of the building it tests. */
export function panes(id, data) {
  return { main: () => html`<${Window} id=${id} data=${data} />` };
}

/** Run the first case from its Info or closed card. */
export function quick(id, action) {
  if (action === "lab.run") { act(id, "lab.run"); return true; }
  return false;
}
