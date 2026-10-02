"""⚒️ The Forge: branches, their pull requests, and the merge.

The hut lists the freshest branches with their PR badge and +/− lines; the open building lists
every branch on the left and its last commits and diff stat on the right. A look every 30 s,
off the UI thread; between two looks it sends `git.commit`, `git.pr_opened`, `git.pr_merged`.

⚒ Merge (or a cart naming a branch) tests the branch with `test_cmd` and squash-merges it into
the base (realm/forge.py) without asking — `c` in the open building turns on a confirmation
first (the `confirm` setting). Success sends `forge.merged`; conflicts or red tests send
`forge.conflict` (a road can take them to the Council). No CI here.
"""
from __future__ import annotations

import threading
import webbrowser

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import forge, gitinfo
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 30.0


class GitView(TypedView):
    TYPE = "forge"
    BINDINGS = [Binding("c", "toggle_confirm", "Confirm merges on/off")]
    merger = staticmethod(forge.merge)            # tests swap the merge here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.snap: gitinfo.Snapshot | None = None
        self.merging = ""
        self.last_merge: forge.Result | None = None
        self._looking = False

    def compose_body(self) -> ComposeResult:
        yield Static("", id="git-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="git-branches", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="git-detail", markup=False)

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- looking --------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        if self._looking:
            return
        self._looking = True
        self.run_worker(self._look, thread=True, exclusive=True, group="git-look")

    def _look(self) -> None:
        snap = gitinfo.snapshot(self._get_repo_root(), str(self.config.get("base", "")))
        try:
            self.app.call_from_thread(self.apply_snapshot, snap)
        except Exception:
            self._looking = False

    def apply_snapshot(self, snap: gitinfo.Snapshot) -> None:
        self._looking = False
        for event_id, text in gitinfo.changes(self.snap, snap):
            self.emit(event_id, text, text.split(":", 1)[0])
        self.snap = snap
        self._render_list()

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
        t.append(gitinfo.detail(self._get_repo_root(), snap.base, b.name))
        try:
            self.query_one("#git-detail", Static).update(t)
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        snap = self.snap
        if snap is None:
            return ["⎇ looking…"]
        if snap.error:
            return [f"⚠ {snap.error[:40]}"]
        rows = [b for b in snap.branches if b.name != snap.base] or snap.branches
        lines = [f"⚒ merging {self.merging}…"] if self.merging else []
        if self.last_merge is not None and not self.merging:
            m = self.last_merge
            lines.append(f"✓ {m.branch} merged" if m.ok else f"✗ {m.branch}: {m.error}")
        for b in rows[:4]:
            bits = [b.name]
            if b.pr is not None:
                bits.append(b.pr.badge)
            if b.files:
                bits.append(b.change)
            lines.append(" ".join(bits))
        return lines or ["no branches"]

    # -- the merge ----------------------------------------------------------------------------

    @property
    def base(self) -> str:
        return self.snap.base if self.snap else str(self.config.get("base") or "main")

    def merge(self, branch: str) -> bool:
        """Test and squash-merge `branch` into the base — at once, or after a yes when `confirm` is on."""
        if self.merging:
            self.app.notify(f"already merging {self.merging}", title="⚒️ The Forge")
            return False
        if branch == self.base:
            self.app.notify(f"{branch} is the base", title="⚒️ The Forge")
            return False
        if self.config.get("confirm"):
            tests = self.config.get("test_cmd")
            self.app.push_screen(Confirm(f"⚒ Squash-merge {branch} into {self.base}?",
                                         f"tests first: {tests}" if tests else "no test command set"),
                                 lambda yes: self._merge(branch) if yes else None)
            return True
        self._merge(branch)
        return True

    def _merge(self, branch: str) -> None:
        self.merging = branch
        self._render_list()
        repo, base, tests, app = self._get_repo_root(), self.base, str(self.config.get("test_cmd") or ""), self.app
        merger = type(self).merger

        def work() -> None:
            try:
                res = merger(repo, branch, base, tests)
            except Exception as e:  # git trouble of every kind ends this merge, not the app
                res = forge.Result(False, branch, base, error=str(e)[:300])
            try:
                app.call_from_thread(self.merged, res)
            except Exception:
                self.merging = ""

        threading.Thread(target=work, daemon=True, name=f"forge-{self.building_id}").start()

    def merged(self, res: forge.Result) -> None:
        self.merging = ""
        self.last_merge = res
        if res.ok:
            self.emit("forge.merged", res.text(), f"{res.branch} → {res.base}")
            self.app.notify(f"{res.branch} → {res.base} {res.commit[:8]}", title="⚒️ Merged")
        else:
            self.emit("forge.conflict", res.text(), f"{res.branch}: {res.error}")
            self.app.notify(res.error, title=f"⚒️ {res.branch} not merged", severity="warning")
        self.refresh_data()

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart naming a branch is a merge order (e.g. from a Barracks' pool.done)."""
        names = {b.name for b in self.snap.branches} if self.snap else set()
        text = f"{payload.title}\n{payload.value}"
        branch = next((n for n in sorted(names, key=len, reverse=True) if n != self.base and n in text), None)
        if branch:
            self.merge(branch)

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
        b = next((x for x in self.snap.branches if x.name == name), None) if self.snap and name else None
        if b is None or b.pr is None or not b.pr.url:
            self.app.notify(f"{name or 'this branch'}: no pull request to open", title="⎇ Git")
            return True
        try:
            webbrowser.open(b.pr.url)
        except Exception:
            pass
        self.app.notify(b.pr.url, title=f"⎇ {b.pr.badge}")
        return True
