// An orkspace's History (docs/design/projects.md §6): the map's checkpoints, newest first — a building raised,
// changed, copied, a road laid, the map renamed or given another project — and going back to one of them. The map
// goes back as a whole: buildings raised since come down, the others get back their orks and settings. Other
// orkspaces and the project's files stay as they are. Opened from a land's menu on the War Map and by /history.
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
  if (r.back.length) parts.push(`${r.back.length} ${say(r.back.length === 1 ? "building" : "buildings")} ${say("back as they were")}`);
  if (r.removed.length) parts.push(`${say("demolished")}: ${r.removed.join(", ")}`);
  if (r.elsewhere.length) parts.push(`${say("left on their other map")}: ${r.elsewhere.join(", ")}`);
  return parts.join(" · ");
}

function HistoryDialog({ o, onClose }) {
  const [rows, setRows] = useState(null);
  const [asking, setAsking] = useState(null);       // the row the person wants to go back to
  const load = () => command("history.list", { orkspace: o.id }).then(setRows, () => setRows([]));
  useEffect(() => { load(); }, [o.id]);
  const back = (row) => command("history.revert", { orkspace: o.id, sha: row.sha }).then((r) => {
    toast(`${say(o.name)} ${say("is back to")} ${row.when}. ${said(r)}`, "information", say("History"));
    setAsking(null); load();
  }, () => setAsking(null));
  return html`<${Dialog} title=${`${say("History")}: ${say(o.name)}`} wide onCancel=${onClose}
      meta=${say("Every change of this map, newest first. Going back changes this map only: other orkspaces and the project's files stay as they are.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>`}>
    ${rows === null ? html`<p class="ok-font-status ok-tone-muted">${say("Reading the history…")}</p>`
      : rows.length === 0 ? html`<p class="ok-font-status ok-tone-muted">${say("No changes kept yet: the next change of this map starts its history.")}</p>`
      : html`<ul class="gui-rows gui-history">${rows.map((r, i) => html`<li key=${r.sha} class="gui-history__row">
          <span class="gui-history__when ok-font-mono">${r.when}</span>
          <span class="gui-history__what">${r.building ? html`<b>${say(r.building)}</b> · ` : ""}${r.what}</span>
          ${i === 0 ? html`<span class="ok-tone-muted ok-font-status">${say("now")}</span>`
            : asking === r.sha ? html`<span class="gui-history__ask">
                <button class="ok-btn danger" onClick=${() => back(r)}>${say("Go back")}</button>
                <button class="ok-btn" onClick=${() => setAsking(null)}>${say("Cancel")}</button></span>`
            : html`<button class="ok-btn" title=${say("The map as it was right after this change: buildings raised since come down, the others get back their orks and settings")}
                onClick=${() => setAsking(r.sha)}>${say("Back to this")}</button>`}
        </li>`)}</ul>`}
  </${Dialog}>`;
}
