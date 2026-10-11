// GitHub in the mascot's menu (gui/github.py, docs/design/improve-buildings.md §4): connected once through the
// Orkcraft Improve app, so a Test bench can send what it improved to Orkcraft as a pull request. Connect shows
// GitHub's code and opens github.com/login/device; it stands connected once the code is typed there. Not on the
// person's account yet: Install opens the app's page (it pushes to their fork there).
import { useEffect, useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say, town } from "./link.js";

export function GithubAccount() {
  const [g, setG] = useState(null);
  const look = (check = false) => command("github.status", { check }).then(setG, () => {});
  useEffect(() => { look(true); }, [town.value]);              // a snapshot after the sign-in brings it in
  useEffect(() => {
    if (!g || !g.waiting) return undefined;
    const t = setInterval(() => look(), 3000);
    return () => clearInterval(t);
  }, [g && g.waiting && g.waiting.code]);
  if (!g) return null;
  const connect = () => command("github.connect").then((x) => {
    setG(x);
    if (x.waiting) window.open(x.waiting.uri, "_blank", "noopener");
  }, () => {});
  return html`<div class="gui-field gui-github" aria-label=${say("GitHub")}>
    <span class="ok-font-label">${say("GitHub")}</span>
    ${g.login ? html`<p class="ok-font-status">${say(`Connected as @${g.login}.`)}
        <button class="gui-link" onClick=${() => command("github.disconnect").then(setG, () => {})}>${say("Disconnect")}</button></p>
        ${g.installed === false && html`<p class="ok-font-status ok-tone-wait">${say("Install the Orkcraft Improve app on your account: it pushes to your fork of Orkcraft there.")}
          <a class="gui-link" href=${g.install} target="_blank" rel="noopener">${say("Install")}</a></p>`}`
      : g.waiting ? html`<p class="ok-font-status">${say("Type this code at GitHub:")} <b class="gui-github__code">${g.waiting.code}</b>
          <a class="gui-link" href=${g.waiting.uri} target="_blank" rel="noopener">${say("Open GitHub")}</a>
          <button class="gui-link" onClick=${() => command("github.cancel").then(setG, () => {})}>${say("Cancel")}</button></p>`
      : html`<p class="ok-font-status ok-tone-muted">${say("A Test bench sends what it improved to Orkcraft as a pull request, with the tests that show it.")}
          <button class="ok-btn" onClick=${connect}>${say("Connect GitHub")}</button></p>`}
    ${g.error && html`<p class="ok-font-status ok-tone-error" role="alert">✗ ${say(g.error)}</p>`}
  </div>`;
}
