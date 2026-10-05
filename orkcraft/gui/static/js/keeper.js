// The keeper of a building (docs/design/building-views.md §2): the person says in plain words what the
// building should do — its rules, its charts, its briefs, a task on a selection in Lake — and the keeper
// writes it. Until the keeper lands (track K), the host says so.
import { command } from "./link.js";

/** Ask a building's keeper: `request` in plain words, `selection` what was selected in Lake (optional). */
export function askKeeper(buildingId, request, selection = null) {
  return command("keeper.ask", { id: buildingId, request, selection }).catch(() => null);
}
