// The folder an orkspace works in (docs/design/projects.md §4): opened from a land's menu on the War Map, from
// "A folder…" when a new orkspace is made, and by /project. It shows where the orkspace works now and changes it:
// the system's folder dialog, a path pasted, a project the town has already, or the town's own folder. A folder
// with no git asks once, in one plain line, before anything is done to it.
import { useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { html } from "./html.js";
import { town, command, say } from "./link.js";
import { Dialog } from "./dialog.js";

export const projectFor = signal(null);            // the orkspace id whose Project dialog is open

export function ProjectAsked() {
  const id = projectFor.value;
  const t = town.value;
  const o = id && t && t.orkspaces.find((x) => x.id === id);
  if (!o) return null;
  return html`<${ProjectDialog} key=${o.id} o=${o} projects=${t.projects || []} townFolder=${t.repo}
    onClose=${() => { projectFor.value = null; }} />`;
}

function ProjectDialog({ o, projects, townFolder, onClose }) {
  const [typed, setTyped] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [hint, setHint] = useState("");
  const [askGit, setAskGit] = useState(null);       // the folder that has no git yet
  const now = projects.find((p) => p.id === o.project);
  const link = (path, git) => {
    setHint("");
    const args = { orkspace: o.id, path };
    if (git !== undefined) args.git = git;
    return command("project.link", args).then((r) => {
      if (r.state === "ask_git") { setAskGit(r.path); return; }
      setAskGit(null); setTyped(""); onClose();
    }, () => {});
  };
  const use = (project) => command("project.use", { orkspace: o.id, project }).then(onClose, () => {});
  const choose = () => {
    setWaiting(true); setHint("");
    command("project.pick", { start: now ? now.path : townFolder }).then((token) => {
      const poll = () => command("project.picked", { token }).then((r) => {
        if (r.state === "open") { setTimeout(poll, 400); return; }
        setWaiting(false);
        if (r.state === "done") link(r.path);
        else if (r.state === "error") setHint(say("No folder dialog here: paste the folder's path."));
      }, () => setWaiting(false));
      poll();
    }, () => setWaiting(false));
  };
  const others = projects.filter((p) => p.id !== o.project && p.there);
  const where = now ? html`<b>${now.name}</b> <code>${now.path}</code>${!now.there
      ? html` <span class="ok-tone-wait">· ${say("the folder is gone: it works in the town's folder until it is back")}</span>`
      : !now.git ? html` <span class="ok-tone-muted">· ${say("no git: no way back to an earlier state")}</span>` : ""}${now.there
      ? now.guarded ? html` <span class="ok-tone-muted">· ${say("the Security reviewer guards it")}</span>`
        : html` <button class="gui-link" title=${say("Its AI tools get the Security reviewer's hooks, as orkcraft hooks install writes them")}
            onClick=${() => command("project.guard", { orkspace: o.id }).catch(() => {})}>${say("Guard it with the Security reviewer")}</button>` : ""}`
    : html`${say("The town's folder")} <code>${townFolder}</code>`;
  return html`<${Dialog} title=${`${say("Project")}: ${say(o.name)}`} onCancel=${onClose}
      meta=${say("The folder this orkspace's orks work in. Other orkspaces may work in the same one.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>`}>
    <p class="ok-font-status">${say("Works in")}: ${where}</p>
    ${askGit ? html`<div class="gui-section">
        <p class="ok-dialog__text">${say("This folder has no history. Start git here, so Orkline can take you back to any earlier state? Your files stay as they are.")}</p>
        <p class="ok-font-status"><code>${askGit}</code></p>
        <div class="gui-form__row">
          <button class="ok-btn primary" onClick=${() => link(askGit, true)}>${say("Start git")}</button>
          <button class="ok-btn" onClick=${() => link(askGit, false)}>${say("Not now")}</button>
        </div></div>`
    : html`<div class="gui-form__row">
        <button class="ok-btn" disabled=${waiting} onClick=${choose}>${say(waiting ? "Choosing…" : "Choose a folder…")}</button>
        <input class="ok-input" value=${typed} placeholder=${say("or paste a folder's path")} aria-label=${say("Folder path")}
          onInput=${(e) => setTyped(e.target.value)}
          onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter" && typed.trim()) link(typed.trim()); }} />
      </div>
      ${hint && html`<p class="ok-font-status ok-tone-wait">${hint}</p>`}
      ${(others.length > 0 || now) && html`<p class="ok-font-status">${say("Or")}: ${others.map((p, i) => html`${i ? " · " : ""}<button key=${p.id}
          class="gui-link" title=${p.path} onClick=${() => use(p.id)}>${p.name}</button>`)}${now ? html`${others.length ? " · " : ""}<button
          class="gui-link" onClick=${() => use("")}>${say("the town's folder")}</button>` : ""}</p>`}`}
  </${Dialog}>`;
}
