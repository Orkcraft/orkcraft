// htm over Preact: JSX-like templates with no build step.
import { h } from "preact";
import htm from "htm";
// A template's own text is written in today's words (realm/lexicon.py), never an old Camp spelling:
// tests/test_gui_wording.py reads every template. What the town's data says goes through say().
export const html = htm.bind(h);

/** Class names from an object of flags: cls("ok-hut", {"is-alert": true}) → "ok-hut is-alert". */
export function cls(base, flags = {}) {
  if (typeof flags === "string") return flags ? `${base} ${flags}` : base;     // a class name of its own, not flags
  return [base, ...Object.entries(flags).filter(([, on]) => on).map(([name]) => name)].join(" ");
}
