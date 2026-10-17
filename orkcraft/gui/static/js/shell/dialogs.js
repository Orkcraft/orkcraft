// Which dialog is open (shell/modals.js `dialog`), drawn over the shell on its dimmed backdrop.
import { html } from "../html.js";
import { dialog } from "./modals.js";
import { GoalDialog } from "./goaldialog.js";
import { IdeaDialog } from "./ideadialog.js";
import { AgentDialog } from "./agentdialog.js";
import { SettingsDialog } from "./settings.js";
import { PairDialog } from "./pair.js";
import { IntoDialog, DropDialog } from "./review.js";

const KINDS = { goal: GoalDialog, idea: IdeaDialog, agent: AgentDialog, settings: SettingsDialog, pair: PairDialog, into: IntoDialog, drop: DropDialog };

export function Dialogs() {
  const d = dialog.value;
  const View = d && KINDS[d.kind];
  return View ? html`<${View} key=${d.kind + (d.props.slug || d.props.assign || "")} ...${d.props} />` : null;
}
