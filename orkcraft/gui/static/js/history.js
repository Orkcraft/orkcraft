// An orkspace's History (docs/design/projects.md §6, §7.3): one timeline, newest first, of the map's checkpoints
// (a building raised, changed, copied, a road laid, the map renamed or given another project) and the snapshots of
// its project's files taken before and after an ork worked there — and going back to one of them. The map goes back
// as a whole: buildings raised since come down, the others get back their orks and settings. The files go back as
// they were, the current ones saved first. Other orkspaces stay as they are. Opened from a land's menu and /history.
import { useEffect, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { html } from "./html.js";
import { town, command, say, toast } from "./link.js";
import { Dialog } from "./dialog.js";

export const historyFor = signal(null);            // the orkspace id whose History is open

export function HistoryAsked() {
  const id = historyFor.value;
  const t = town.value;
  const o = id && t && t.orkspaces.find((x) => x.id === id);
  if (!o) return null;
  return html`<${HistoryDialog} key=${o.id} o=${o} onClose=${() => { historyFor.value = null; }} />`;
}

function said(r) {
  const parts = [];
  if (r.files) parts.push(say("the files are back as they were"));
  if (r.back.length) parts.push(`${r.back.length} ${say(r.back.length === 1 ? "building" : "buildings")} ${say("back as they were")}`);
  if (r.removed.length) parts.push(`${say("demolished")}: ${r.removed.join(", ")}`);
  if (r.elsewhere.length) parts.push(`${say("left on their other map")}: ${r.elsewhere.join(", ")}`);
  return parts.join(" · ");
}

function HistoryDialog({ o, onClose }) {
  const [list, setList] = useState(null);
  const [asking, setAsking] = useState(null);       // the row the person wants to go back to
  const load = () => command("history.list", { orkspace: o.id }).then(setList, () => setList({ rows: [], files: false }));
  useEffect(() => { load(); }, [o.id]);
  const rows = list && list.rows;
  const back = (row, what) => command("history.revert", { orkspace: o.id, sha: row.sha, what, files: row.type === "files" ? row.sha : row.files })
    .then((r) => {
    toast(`${say(o.name)} ${say("is back to")} ${row.when}. ${said(r)}`, "information", say("History"));
    setAsking(null); load();
  }, () => setAsking(null));
  return html`<${Dialog} title=${`${say("History")}: ${say(o.name)}`} wide onCancel=${onClose}
      meta=${say(list && !list.files
        ? "Every change of this map, newest first. Its project has no git, so its files have no snapshots: going back changes the map only."
        : "Every change of this map and its project's files, newest first. Going back changes this orkspace only; your current files are saved first.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>`}>
    ${rows === null ? html`<p class="ok-font-status ok-tone-muted">${say("Reading the history…")}</p>`
      : rows.length === 0 ? html`<p class="ok-font-status ok-tone-muted">${say("No changes kept yet: the next change of this map starts its history.")}</p>`
      : html`<ul class="gui-rows gui-history">${rows.map((r, i) => html`<li key=${r.sha} class="gui-history__row">
          <span class="gui-history__when ok-font-mono">${r.when}</span>
          <span class="gui-history__what">${r.type === "files"
            ? html`<span class="gui-history__tag">${say("files")}</span> ${r.what}${r.changed_n
              ? html` <span class="ok-tone-muted" title=${r.changed.join("\n")}>· ${r.changed_n} ${say(r.changed_n === 1 ? "file changed" : "files changed")}</span>` : ""}`
            : html`<span class="gui-history__tag">${say("map")}</span> ${r.building ? html`<b>${say(r.building)}</b> · ` : ""}${r.what}`}</span>
          ${i === 0 ? html`<span class="ok-tone-muted ok-font-status">${say("now")}</span>`
            : asking === r.sha ? html`<span class="gui-history__ask">
                ${r.type === "files" ? html`<button class="ok-btn danger" onClick=${() => back(r, "files")}>${say("Files back")}</button>`
                  : r.files ? html`<button class="ok-btn danger" onClick=${() => back(r, "map")}>${say("The map")}</button>
                      <button class="ok-btn danger" onClick=${() => back(r, "files")}>${say("The files")}</button>
                      <button class="ok-btn danger" onClick=${() => back(r, "both")}>${say("Both")}</button>`
                  : html`<button class="ok-btn danger" onClick=${() => back(r, "map")}>${say("Go back")}</button>`}
                <button class="ok-btn" onClick=${() => setAsking(null)}>${say("Cancel")}</button></span>`
            : html`<button class="ok-btn" title=${say(r.type === "files"
                ? "The project's files as they were then; your current files are saved first, so you can come back to them"
                : "This moment: the map as it was right after this change, its project's files as they were then, or both")}
                onClick=${() => setAsking(r.sha)}>${say("Back to this")}</button>`}
        </li>`)}</ul>`}
  </${Dialog}>`;
}
