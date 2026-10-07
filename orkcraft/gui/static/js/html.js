// htm over Preact: JSX-like templates with no build step.
import { h } from "preact";
import htm from "htm";
import { town, say } from "./link.js";

const raw = htm.bind(h);

// A template's own text says today's words (realm/lexicon.py): "Garrison" → "Orks".
// Only the literal text between tags changes — never a tag, an attribute or an interpolated value,
// so what the town's data says (titles, notes, what an ork wrote) stays as written.
const worded = new WeakMap();      // a template's strings → the same strings in today's words

function todayStrings(strings) {
  let inTag = false, quote = null;
  const out = strings.map((s) => {
    let done = "", text = "";
    for (const ch of s) {
      if (inTag) {
        done += ch;
        if (quote) { if (ch === quote) quote = null; }
        else if (ch === '"' || ch === "'") quote = ch;
        else if (ch === ">") inTag = false;
      } else if (ch === "<") {
        done += say(text) + ch; text = ""; inTag = true;
      } else text += ch;
    }
    return done + say(text);
  });
  return out;
}

export function html(strings, ...values) {
  const t = town.value;
  if (!t || !t.words?.length) return raw(strings, ...values);
  let words = worded.get(strings);
  if (!words) { words = todayStrings(strings); worded.set(strings, words); }
  return raw(words, ...values);
}

/** Class names from an object of flags: cls("ok-hut", {"is-alert": true}) → "ok-hut is-alert". */
export function cls(base, flags = {}) {
  if (typeof flags === "string") return flags ? `${base} ${flags}` : base;     // a class name of its own, not flags
  return [base, ...Object.entries(flags).filter(([, on]) => on).map(([name]) => name)].join(" ");
}
