"""⚒️ The Forge: branches, their pull requests, and the merge.

The hut lists the freshest branches with their PR badge and +/− lines; the open building lists
every branch on the left and its last commits and diff stat on the right. A look every 30 s,
off the UI thread; between two looks it sends `git.commit`, `git.pr_opened`, `git.pr_merged`.

⚒ Merge (or a cart naming a branch) tests the branch with `test_cmd` and squash-merges it into
the base (realm/forge.py) without asking — `c` in the open building turns on a confirmation
first (the `confirm` setting). Success sends `forge.merged`; conflicts or red tests send
`forge.conflict` (a road can take them to the Council). No CI here.

The looks, the tests and the merge are the building's worker's (core/workers/forge.py); the view
draws the branches, asks before a merge and holds the keys and the timer.
"""
from __future__ import annotations

import webbrowser

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.forge import ForgeWorker
from orkcraft.realm import forge, gitinfo
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 30.0


class GitView(TypedView):
    TYPE = "forge"
    UI_PANES = {"head": "#git-head", "branches": "#git-branches", "detail": "#git-detail-pane", "settings": "#git-head"}
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm merges on/off")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._asked = ""

    @property
    def worker(self) -> ForgeWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def snap(self) -> gitinfo.Snapshot | None:
        return self.worker.snap

    @property
    def merging(self) -> str:
        return self.worker.merging

    @property
    def last_merge(self) -> forge.Result | None:
        return self.worker.last_merge

    @property
    def base(self) -> str:
        return self.worker.base

    def apply_snapshot(self, snap: gitinfo.Snapshot) -> None:
        self.worker.apply_snapshot(snap)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def status(self) -> str:
        return self.worker.status()

    def compose_body(self) -> ComposeResult:
        yield Static("", id="git-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="git-branches", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="git-detail-pane"):
                yield Static("", id="git-detail", markup=False, classes="-as-written")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- looking --------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()
        asking = self.worker.asking
        if asking and asking != self._asked:          # a road brought a branch: ask before merging it
            self._asked = asking
            self._confirm(asking, lambda yes: self.worker.merge(asking) if yes else self.worker.decline())
        elif not asking:
            self._asked = ""

    def _render_list(self) -> None:
        snap = self.snap
        if snap is None or not self.is_mounted:
            return
        try:
            head, lst = self.query_one("#git-head", Static), self.query_one("#git-branches", OptionList)
        except Exception:
            return
        if snap.error:
            head.update(Text(f"⚠ {snap.error}", style="yellow"))
        else:
            prs = "" if snap.prs_known else " · PRs: install and log in to `gh` to see them"
            confirm = "on" if self.config.get("confirm") else "off"
            busy = f" · ⚒ merging {self.merging}…" if self.merging else ""
            head.update(Text(f"base {snap.base} · {len(snap.branches)} branches{prs} · confirm before merge: {confirm} (c)"
                             f"{busy}", style="dim"))
        keep = self.selected_branch()
        lst.clear_options()
        for b in snap.branches:
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("● " if b.current else "  ", style="bold green")
            row.append(b.name, style="bold" if b.current else "")
            if b.pr is not None:
                style = {"MERGED": "magenta", "CLOSED": "red", "DRAFT": "dim"}.get(b.pr.state, "green")
                row.append(f"  {b.pr.badge}", style=style)
            if b.files:
                row.append(f"  +{b.added}", style="green")
                row.append(f"−{b.removed}", style="red")
            if b.ahead or b.behind:
                row.append(f"  ↑{b.ahead} ↓{b.behind}", style="dim")
            lst.add_option(Option(row, id=b.name))
        names = [b.name for b in snap.branches]
        if names:
            lst.highlighted = names.index(keep) if keep in names else 0
            self._show_detail(names[lst.highlighted])

    def selected_branch(self) -> str | None:
        try:
            lst = self.query_one("#git-branches", OptionList)
        except Exception:
            return None
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return None
        return lst.get_option_at_index(lst.highlighted).id

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "git-branches" and event.option.id:
            event.stop()
            self._show_detail(event.option.id)

    def _show_detail(self, name: str) -> None:
        snap = self.snap
        b = next((x for x in snap.branches if x.name == name), None) if snap else None
        if b is None:
            return
        t = Text()
        t.append(f"⎇ {b.name}\n", style="bold")
        if b.pr is not None:
            t.append(f"PR {b.pr.badge} {b.pr.state.lower()} — {b.pr.title}\n{b.pr.url}\n", style="cyan")
        elif snap.prs_known and b.name != snap.base:
            t.append("no pull request\n", style="dim")
        if b.name != snap.base:
            t.append(f"{b.ahead} ahead, {b.behind} behind {snap.base}; {b.files} files {b.change}\n", style="dim")
        t.append("\n")
        t.append(gitinfo.detail(self.worker.repo_root, snap.base, b.name))
        try:
            self.query_one("#git-detail", Static).update(t)
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    # -- the merge ----------------------------------------------------------------------------

    def _confirm(self, branch: str, done) -> None:
        tests = self.config.get("test_cmd")
        self.app.push_screen(Confirm(f"⚒ Squash-merge {branch} into {self.base}?",
                                     f"tests first: {tests}" if tests else "no test command set"), done)

    def merge(self, branch: str) -> bool:
        """Test and squash-merge `branch` into the base — at once, or after a yes when `confirm` is on."""
        if self.merging:
            self.app.notify(f"already merging {self.merging}", title="⚒️ The Forge")
            return False
        if branch == self.base:
            self.app.notify(f"{branch} is the base", title="⚒️ The Forge")
            return False
        if self.config.get("confirm"):
            self._confirm(branch, lambda yes: self.worker.merge(branch) if yes else None)
            return True
        return self.worker.merge(branch)

    def action_toggle_confirm(self) -> None:
        if self.save_config({"confirm": not self.config.get("confirm")}):
            self._render_list()

    def quick_action(self, action_id: str) -> bool:
        if action_id == "forge.merge":
            name = self.selected_branch()
            if name:
                self.merge(name)
            else:
                self.app.notify("pick a branch first", title="⚒️ The Forge")
            return True
        if action_id != "git.open_pr":
            return False
        name = self.selected_branch()
        b = self.worker.branch(name) if name else None
        if b is None or b.pr is None or not b.pr.url:
            self.app.notify(f"{name or 'this branch'}: no pull request to open", title="⎇ Git")
            return True
        try:
            webbrowser.open(b.pr.url)
        except Exception:
            pass
        self.app.notify(b.pr.url, title=f"⎇ {b.pr.badge}")
        return True
