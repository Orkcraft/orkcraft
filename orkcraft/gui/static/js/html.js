// htm over Preact: JSX-like templates with no build step.
import { h } from "preact";
import htm from "htm";

export const html = htm.bind(h);

/** Class names from an object of flags: cls("ok-hut", {"is-alert": true}) → "ok-hut is-alert". */
export function cls(base, flags = {}) {
  return [base, ...Object.entries(flags).filter(([, on]) => on).map(([name]) => name)].join(" ");
}
