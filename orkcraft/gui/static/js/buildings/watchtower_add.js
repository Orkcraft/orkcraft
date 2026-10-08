// 🗼 Add a source, in the Watchtower's own panel over the feed — never a dialog (docs/design/watchtower-quick-add.md
// §4.2): the picker (a pasted link, or a service), then three steps — Log in, What, Check — and Add. The steps'
// state is the worker's (core/workers/watchtower_add.py), so the panel can close while the person makes a token
// and open again on the same step; a typed secret stays in this form until Continue sends it, and is not kept here.
// A source already listed comes back here too: Edit (step 2, its picks ticked) and Log in again (step 1).
// A service Claude Code has a connection for offers a second way at step 1: Claude's connection, no token, a
// paid look every 30 min (§7.3); its step 2 asks what to listen for, how often and the most a day.
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";

const STEPS = [["login", "Log in"], ["what", "What"], ["check", "Check"]];

/** A service's glyph in the frame's gold (icons/services, Simple Icons CC0); Slack, without one, a `#`. */
export function Glyph({ service, big = false }) {
  return html`<span class=${cls(`gui-svc gui-svc--${service}`, { "is-big": big })} aria-hidden="true">${service === "slack" ? "#" : ""}</span>`;
}

function Steps({ step }) {
  const at = STEPS.findIndex(([s]) => s === step);
  return html`<div class="gui-add__steps" aria-label=${say("Steps")}>
    ${STEPS.map(([s, label], i) => html`<span key=${s} class=${cls({ "is-on": i === at, "is-done": i < at })}>
      ${i < at ? "✓" : i + 1} ${label}</span>${i < STEPS.length - 1 ? html`<span class="ok-tone-muted">›</span>` : ""}`)}
  </div>`;
}

function Head({ a }) {
  return html`<div class="gui-add__head"><${Glyph} service=${a.service} big=${true} />
    <div><h3 class="gui-add__title">${a.label}${a.who ? html` <span class="ok-tone-muted">· ${a.who}</span>` : ""}</h3>
      <${Steps} step=${a.step} />
      ${a.editing && html`<p class="ok-tone-muted gui-add__sub">${a.step === "login" ? "Log in again — what it hears stays as it is" : "Changing a source it already hears"}</p>`}</div></div>`;
}

function State({ a }) {
  if (a.busy) return html`<p class="gui-add__busy ok-tone-muted" role="status">${a.busy}</p>`;
  if (a.error) return html`<p class="gui-add__error ok-tone-error" role="alert">✗ ${a.error}</p>`;
  return null;
}

// -- the picker -------------------------------------------------------------------------------------------

function Picker({ id, a, back }) {
  const [link, setLink] = useState("");
  const go = () => link.trim() && act(id, "add_link", { link: link.trim() }).catch(() => {});
  return html`<div class="gui-add">
    <div>
      <h3 class="gui-add__title">Add a source</h3>
      <p class="ok-tone-muted gui-add__sub">Say where to listen. One paste at most, then pick what to hear.</p>
    </div>
    <label class="gui-add__label" for=${`add-link-${id}`}>Paste a link to what you want to hear</label>
    <div class="gui-head">
      <input id=${`add-link-${id}`} class="ok-input" style="flex: 1; width: auto" value=${link}
        placeholder=${say("a repo, a Slack channel, a Jira issue, a Figma file, an e-mail address")}
        onInput=${(e) => setLink(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && go()} />
      <button class="ok-btn primary" disabled=${!link.trim()} onClick=${go}>Continue</button>
    </div>
    <span class="gui-add__label">Or pick a service</span>
    <div class="gui-add__tiles">
      ${(a.services || []).map((s) => html`<button key=${s.id} class="gui-add__tile" onClick=${() => act(id, "add_start", { service: s.id }).catch(() => {})}>
        <span class="gui-add__tile-top"><${Glyph} service=${s.id} />${s.label}</span>
        <span class=${cls("gui-add__mark", { "ok-tone-ok": s.ready })}>${s.mark}</span></button>`)}
    </div>
    <p class="ok-tone-muted gui-add__sub">Tokens stay on this machine, in Logins. No model sees them.</p>
    ${back && html`<button class="ok-btn gui-tower__back" onClick=${back}>← Signals</button>`}
  </div>`;
}

// -- 1 · Log in --------------------------------------------------------------------------------------------

function Login({ id, a }) {
  const [values, setValues] = useState({ ...(a.prefill || {}) });
  const set = (k, v) => setValues({ ...values, [k]: v });
  const fields = (a.fields || []).filter((f) => !(f.key === "site" && a.link && a.link.site && a.link.service !== "gmail"));
  const ready = fields.every((f) => f.optional || (values[f.key] || "").trim())
    && (a.service !== "github" || (values.token || "").trim());
  const send = () => ready && !a.busy && act(id, "add_login", { values }).catch(() => {});
  return html`<div class="gui-add">
    <${Head} a=${a} />
    ${a.kept.length > 0 && html`<div class="gui-add__kept">
      <span class="gui-add__label">Already logged in on this machine</span>
      ${a.kept.map((k) => html`<button key=${k.account} class="ok-btn" onClick=${() => act(id, "add_use", { account: k.account }).catch(() => {})}>Use ${k.who}</button>`)}
      <span class="ok-tone-muted gui-add__sub">or log in with another account below</span></div>`}
    ${a.note && html`<p class="gui-add__sub">${a.note}</p>`}
    ${a.how.length > 0 && html`<ol class="gui-add__how">
      ${a.how.map((h, i) => html`<li key=${i}>${h.text}${h.url && html` — <a href=${h.url} target="_blank" rel="noopener noreferrer">${say("open")} ↗</a>`}</li>`)}
    </ol>`}
    ${a.link && a.link.site && a.service !== "gmail" && html`<p class="ok-tone-muted gui-add__sub">${a.link.site}${a.link.says ? ` · ${a.link.says}` : ""}</p>`}
    ${fields.map((f) => {
      const v = values[f.key] || "";
      const off = v && f.shape && !new RegExp(f.shape).test(v.trim());
      return html`<div key=${f.key} class="gui-add__field">
        <label class="gui-add__label" for=${`add-${f.key}-${id}`}>${f.label}</label>
        <input id=${`add-${f.key}-${id}`} class="ok-input" type=${f.secret ? "password" : "text"} autocomplete="off"
          placeholder=${f.placeholder} value=${v} onInput=${(e) => set(f.key, e.target.value)} onKeyDown=${(e) => e.key === "Enter" && send()} />
        ${off && html`<p class="gui-add__hint ok-tone-wait">⚠ ${f.shape_says}</p>`}
      </div>`;
    })}
    ${a.claude && html`<${ViaClaude} id=${id} c=${a.claude} />`}
    <${State} a=${a} />
    <div class="gui-add__foot">
      <button class="ok-btn" onClick=${() => act(id, "add_back").catch(() => {})}>← Back</button>
      ${a.service === "github" && html`<button class="ok-btn" disabled=${!!a.busy} onClick=${() => act(id, "add_again").catch(() => {})}>Check gh again</button>`}
      <button class="ok-btn primary" disabled=${!ready || !!a.busy} onClick=${send}>Continue</button>
    </div>
  </div>`;
}

/** Step 1's other way: the connection Claude Code already has — no token, but a model run each look. */
function ViaClaude({ id, c }) {
  const ok = c.status === "connected";
  return html`<div class="gui-add__claude">
    <span class="gui-add__label">Or use Claude's connection</span>
    ${ok ? html`<p class="gui-add__sub">No token. It looks every 30 min, and each look is a model run you pay for (about $0.05).</p>
        <div class="gui-add__foot" style="justify-content: flex-start">
          <button class="ok-btn" onClick=${() => act(id, "add_claude").catch(() => {})}>Use Claude's connection</button></div>`
      : html`<p class="gui-add__sub ok-tone-wait">In Claude, ${c.status} — run /mcp in Claude Code, then open this again.</p>`}
  </div>`;
}

// -- 2 · What ----------------------------------------------------------------------------------------------

/** Step 2 through Claude: what to listen for, how often, the most it may spend a day. */
function Ask({ id, a }) {
  const [ask, setAsk] = useState(a.ask || "");
  const [every, setEvery] = useState(a.every_min || 30);
  const [ceiling, setCeiling] = useState(String(a.ceiling ?? 0.5));
  const check = () => act(id, "add_ask", { ask, every, ceiling: parseFloat(ceiling) || 0 }).catch(() => {});
  return html`<div class="gui-add">
    <${Head} a=${a} />
    <div class="gui-add__field"><label class="gui-add__label" for=${`add-ask-${id}`}>What Claude looks for</label>
      <input id=${`add-ask-${id}`} class="ok-input" value=${ask} onInput=${(e) => setAsk(e.target.value)} /></div>
    <div class="gui-add__field"><label class="gui-add__label" for=${`add-every-${id}`}>How often</label>
      <select id=${`add-every-${id}`} class="ok-input" value=${every} onChange=${(e) => setEvery(parseInt(e.target.value, 10))}>
        ${[10, 15, 30, 60, 120].filter((m) => m >= (a.every_min_least || 10)).map((m) => html`<option key=${m} value=${m}>${say(`every ${m} min`)}</option>`)}
      </select></div>
    <div class="gui-add__field"><label class="gui-add__label" for=${`add-ceiling-${id}`}>The most it spends a day, in dollars</label>
      <input id=${`add-ceiling-${id}`} class="ok-input" inputmode="decimal" value=${ceiling} onInput=${(e) => setCeiling(e.target.value)} />
      <p class="ok-tone-muted gui-add__sub">Past it the source waits until tomorrow. Each look's cost shows in Spend.</p></div>
    <p class="ok-tone-muted gui-add__sub">Claude may use only the connection's read tools: nothing it reads can make it write or send.</p>
    <${State} a=${a} />
    <div class="gui-add__foot">
      <button class="ok-btn" onClick=${() => act(id, "add_back").catch(() => {})}>← Back</button>
      <button class="ok-btn primary" disabled=${!!a.busy} onClick=${check}>Check</button>
    </div>
  </div>`;
}

function What({ id, a }) {
  const [picks, setPicks] = useState(a.picks || []);
  const [aboutMe, setAboutMe] = useState(a.about_me !== false);
  const [folder, setFolder] = useState(a.folder || "INBOX");
  const [me, setMe] = useState(a.me || "");
  const [whole, setWhole] = useState(!!a.everything);
  const [intent, setIntent] = useState(a.intent || "");
  const [find, setFind] = useState("");
  const [links, setLinks] = useState("");
  const [want, setWant] = useState(a.want || "");
  useEffect(() => setPicks(a.picks || []), [JSON.stringify(a.picks)]);
  const toggle = (k) => setPicks(picks.includes(k) ? picks.filter((x) => x !== k) : [...picks, k]);
  const shown = (a.options || []).filter((o) => !find || o.label.toLowerCase().includes(find.toLowerCase()));
  const check = () => act(id, "add_what", { picks, about_me: aboutMe, folder, me, everything: whole, intent, want }).catch(() => {});
  const picking = !whole || a.service === "github";            // Everything needs no list (GitHub's repos still add their events)
  return html`<div class="gui-add">
    <${Head} a=${a} />
    ${a.everything_says && html`<label class="ok-check gui-add__switch"><input type="checkbox" checked=${whole}
      onChange=${(e) => setWhole(e.target.checked)} /><i>${whole ? "✓" : ""}</i>${a.everything_says}</label>`}
    ${a.whole_team && html`<label class="ok-check gui-add__switch is-off" title=${say("Figma has no list of a team's comments to ask: it needs a public address to push to")}><input type="checkbox" disabled /><i></i>${a.whole_team}</label>`}
    ${whole && a.asks_intent && html`<div class="gui-add__field">
      <label class="gui-add__label" for=${`add-intent-${id}`}>Everything in ${a.label} is a lot — say what you listen for, or keep everything</label>
      <input id=${`add-intent-${id}`} class="ok-input" value=${intent} placeholder=${say("e.g. user feedback about the app — empty lets everything through")}
        onInput=${(e) => setIntent(e.target.value)} /></div>`}
    ${a.about_me_says && !whole && html`<label class="ok-check gui-add__switch"><input type="checkbox" checked=${aboutMe}
      onChange=${(e) => setAboutMe(e.target.checked)} /><i>${aboutMe ? "✓" : ""}</i>${a.about_me_says}</label>`}
    ${a.service === "gmail" && !whole && html`<div class="gui-add__field"><label class="gui-add__label" for=${`add-folder-${id}`}>Folder</label>
      <input id=${`add-folder-${id}`} class="ok-input" value=${folder} onInput=${(e) => setFolder(e.target.value)} /></div>`}
    ${a.service === "figma" && html`<div class="gui-add__field"><label class="gui-add__label" for=${`add-files-${id}`}>Figma file or team links</label>
      <div class="gui-head"><input id=${`add-files-${id}`} class="ok-input" style="flex: 1; width: auto" value=${links}
        placeholder="figma.com/design/… or figma.com/files/team/…" onInput=${(e) => setLinks(e.target.value)} />
        <button class="ok-btn" disabled=${!links.trim()} onClick=${() => act(id, "add_files", { links }).then(() => setLinks(""), () => {})}>Add links</button></div></div>`}
    ${a.service === "discord" && html`<div class="gui-add__field">
      <span class="gui-add__label">Invite the bot</span>
      <p class="gui-add__sub">It hears only the servers it is in — open the link, pick your server, Authorize; then List again.
        ${a.invite && html` <a href=${a.invite} target="_blank" rel="noopener noreferrer">${say("Invite it")} ↗</a>`}</p>
      <div class="gui-add__foot" style="justify-content: flex-start"><button class="ok-btn" disabled=${!!a.busy} onClick=${() => act(id, "add_again").catch(() => {})}>List again</button></div>
      <label class="gui-add__label" for=${`add-me-${id}`}>Me — to tell mentions of you</label>
      <input id=${`add-me-${id}`} class="ok-input" value=${me} placeholder=${say("your user id, or a link to a message you wrote")}
        onInput=${(e) => setMe(e.target.value)} /></div>`}
    ${a.picks_of && a.service !== "figma" && picking && html`<span class="gui-add__label">${{ repos: "Repos — their events", channels: "Channels", projects: "Projects — their events", spaces: "Spaces" }[a.picks_of]}</span>`}
    ${picking && (a.options || []).length > 8 && html`<input class="ok-input" placeholder=${say("Search")} value=${find} onInput=${(e) => setFind(e.target.value)} />`}
    ${picking && shown.length > 0 && html`<ul class="gui-add__options">
      ${shown.map((o) => html`<li key=${o.id}><label class="ok-check"><input type="checkbox" checked=${picks.includes(o.id)}
        onChange=${() => toggle(o.id)} /><i>${picks.includes(o.id) ? "✓" : ""}</i>${o.label}</label>
        ${o.meta && html`<span class="ok-tone-muted gui-add__meta">${o.meta}</span>`}</li>`)}
    </ul>`}
    ${picking && a.picks_of && !a.busy && !(a.options || []).length && a.service !== "figma" && html`<p class="ok-tone-muted gui-add__sub">Nothing to pick here.</p>`}
    ${(a.wants || []).length > 0 && html`<div class="gui-add__field">
      <label class="gui-add__label" for=${`add-want-${id}`}>What do you want done with these?</label>
      <select id=${`add-want-${id}`} class="ok-input" value=${want} onChange=${(e) => setWant(e.target.value)}>
        ${a.wants.map((w) => html`<option key=${w.id} value=${w.id}>${say(w.label)}</option>`)}
        <option value="">${say("Nothing set — the agent pool decides")}</option>
      </select>
      <p class="ok-tone-muted gui-add__sub">${say("It goes with each one: a reply is drafted and waits for your yes, a code change becomes a pull request, a keep goes to the wiki.")}</p></div>`}
    <${State} a=${a} />
    <div class="gui-add__foot">
      <span class="ok-tone-muted gui-add__sub">${picking && picks.length ? `${picks.length} picked` : ""}</span>
      <button class="ok-btn" onClick=${() => act(id, "add_back").catch(() => {})}>← Back</button>
      <button class="ok-btn primary" disabled=${!!a.busy} onClick=${check}>Check</button>
    </div>
  </div>`;
}

// -- 3 · Check --------------------------------------------------------------------------------------------

function Check({ id, a, done }) {
  const bad = !!a.error;
  return html`<div class="gui-add">
    <${Head} a=${a} />
    <div class=${cls("gui-add__verdict", { "is-bad": bad })}>
      <span class=${cls("gui-add__icon", bad ? "ok-tone-error" : "ok-tone-ok")}>${bad ? "✗" : "✓"}</span>
      <div>
        <b>${bad ? `${a.label} did not answer as it should` : `It hears ${a.label}`}</b>
        ${bad && html`<p class="ok-tone-error gui-add__sub">${a.error}</p>`}
        <dl class="gui-add__kv">
          <dt>As</dt><dd>${a.who}</dd>
          <dt>Hears</dt><dd>${a.says}</dd>
          <dt>Listens for</dt><dd>${a.listens_for || "everything passes"}</dd>
          ${!bad && a.found >= 0 && html`<dt>Found now</dt><dd>${a.found} — marked seen, not sent</dd>`}
          <dt>Checks</dt><dd>${a.every}</dd>
        </dl>
      </div>
    </div>
    ${!bad && html`<p class="ok-tone-muted gui-add__sub">From now on each new one becomes a signal.</p>`}
    ${a.busy && html`<${State} a=${a} />`}
    <div class="gui-add__foot">
      <button class="ok-btn" onClick=${() => act(id, "add_back").catch(() => {})}>← Back</button>
      <button class="ok-btn primary" disabled=${bad || !!a.busy} onClick=${() => act(id, "add_save").then(done, () => {})}>${a.editing ? "Keep it" : `Add ${a.label}`}</button>
    </div>
  </div>`;
}

const awaited = new Set();          // building ids whose steps were just started elsewhere (Edit, Log in again)

/** Edit or Log in again a listed source: the steps start at the worker, and the pane waits for them
 *  instead of opening the picker over them while the panel's data catches up. */
export function editSource(id, source, login) {
  awaited.add(id);
  return act(id, "edit", { source, login }).catch((e) => { awaited.delete(id); throw e; });
}

/** The pane over the feed: opens the picker when nothing is under way; `done` goes back to the signals. */
export function AddPane({ id, d, done }) {
  const a = d.adding;
  if (a) awaited.delete(id);
  useEffect(() => { if (!a && !awaited.has(id)) act(id, "add_open").catch(() => {}); }, [!a]);
  const close = () => act(id, "add_close").then(done, done);
  const back = d.sources.length ? close : null;
  const keys = (e) => {
    if (e.key !== "Escape" || e.target.tagName === "INPUT") return;
    e.stopPropagation();
    if (a && a.step !== "pick") act(id, "add_back").catch(() => {});
    else if (back) back();
  };
  if (!a) return html`<p class="ok-tone-muted">${say("Opening…")}</p>`;
  return html`<div class="gui-add__pane" onKeyDown=${keys}>
    ${a.step === "pick" ? html`<${Picker} id=${id} a=${a} back=${back} />`
      : a.step === "login" ? html`<${Login} key=${a.service} id=${id} a=${a} />`
      : a.step === "what" && a.via ? html`<${Ask} key=${`${a.service}-claude`} id=${id} a=${a} />`
      : a.step === "what" ? html`<${What} key=${a.service} id=${id} a=${a} />`
      : html`<${Check} id=${id} a=${a} done=${done} />`}
  </div>`;
}
