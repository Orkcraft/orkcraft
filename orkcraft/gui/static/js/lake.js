// Lake, the town's one viewer (docs/design/building-views.md §2): any building opens a document or a
// file here with a click on its mark. Until the Lake window lands (track L), it shows the document in a
// Lake building when the town has one, else says so.
import { command } from "./link.js";
import { showBuilding } from "./windows.js";

/** Open a document in Lake: `{path}` a file of the project, `{url}` a page, `{text}` text as it is; `from`
 *  is the building it came from (its keeper answers on a selection). */
export function openInLake({ path, url, text, title = "", from = "" } = {}) {
  const kind = path ? "file" : "text";
  const value = path || url || text || "";
  return command("lake.open", { kind, value, title, from }).then((id) => { if (id) showBuilding(id); }, () => {});
}
