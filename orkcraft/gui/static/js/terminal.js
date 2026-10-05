// An ork's session drawn by xterm.js. The bytes are the host's (core/sessions.py): a terminal shows
// what the session printed so far (`term.replay`), then each chunk as it comes; what is typed goes back
// as `term.input`, and the terminal's size as `term.resize`. xterm.js (~340 KB) loads the first
// time a terminal opens, never with the page.
import { signal, effect } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html } from "./html.js";
import { command, onTerminal, online } from "./link.js";

const shown = signal(new Set());           // the session keys drawn on this page: the host sends only those
let xterm = null;

function load() {
  xterm ||= Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit")]);
  return xterm;
}

effect(() => {
  const keys = [...shown.value];
  if (online.value) command("term.attach", { keys }).catch(() => {});
});

function show(key, on) {
  const next = new Set(shown.value);
  if (on) next.add(key); else next.delete(key);
  shown.value = next;
}

/** The terminal's colours are the look's tokens (design-system/tokens.css), read off the page. */
function theme(el) {
  const css = getComputedStyle(el);
  const v = (name) => css.getPropertyValue(name).trim() || undefined;
  return { background: v("--panel-inset"), foreground: v("--ink"), cursor: v("--frame-focus"),
           selectionBackground: v("--selection"), cursorAccent: v("--panel-inset") };
}

export function Terminal({ sessionKey }) {
  const ref = useRef(null);
  useEffect(() => {
    let term = null, fit = null, ro = null, off = null, stop = null, gone = false, size = "";
    const el = ref.current;
    load().then(([{ Terminal: XTerm }, { FitAddon }]) => {
      if (gone) return;
      const css = getComputedStyle(el);
      term = new XTerm({
        fontFamily: css.getPropertyValue("--font-mono").trim() || "monospace", fontSize: 13,
        cursorBlink: true, scrollback: 5000, theme: theme(el), allowProposedApi: false,
      });
      fit = new FitAddon();
      term.loadAddon(fit);
      term.open(el);
      const resize = () => {
        try { fit.fit(); } catch { return; }
        const now = `${term.cols}x${term.rows}`;
        if (now !== size) {
          size = now;
          command("term.resize", { key: sessionKey, cols: term.cols, rows: term.rows }).catch(() => {});
        }
      };
      ro = new ResizeObserver(resize);
      ro.observe(el);
      resize();
      term.onData((data) => command("term.input", { key: sessionKey, data }).catch(() => {}));
      off = onTerminal(sessionKey, (kind, bytes) => {
        if (kind === 1) term.reset();
        term.write(bytes);
      });
      show(sessionKey, true);
      // As it stands now, and again after the link comes back (what came meanwhile was missed).
      stop = effect(() => { if (online.value) command("term.replay", { key: sessionKey }).catch(() => {}); });
      term.focus();
    });
    return () => {
      gone = true;
      show(sessionKey, false);
      if (off) off();
      if (stop) stop();
      if (ro) ro.disconnect();
      if (term) term.dispose();
    };
  }, [sessionKey]);
  return html`<div ref=${ref} class="gui-term" onClick=${(e) => e.currentTarget.querySelector("textarea")?.focus()}></div>`;
}
