// The window's own errors go to the host as crash reports (core/crashes.py, docs/crash-reports.md), which
// sends them only after a yes and only as file, function and line of Orkcraft's scripts. A few per page.
import { command } from "./link.js";

const MAX = 10;
let sent = 0;

function report(message, stack) {
  if (sent >= MAX) return;
  sent += 1;
  command("crash.window", { message: String(message || "").slice(0, 2000), stack: String(stack || "").slice(0, 8000) })
    .catch(() => {});
}

export function watchErrors() {
  window.addEventListener("error", (e) => {
    if (e.error || e.message) report(e.error ? `${e.error.name}: ${e.error.message}` : e.message, e.error && e.error.stack);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const r = e.reason;
    if (r && r.refused) return;                             // a command the town refused (js/link.js): not a crash
    report(r instanceof Error ? `${r.name}: ${r.message}` : String(r), r && r.stack);
  });
}
