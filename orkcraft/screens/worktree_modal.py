"""⎇ Worktree of an orkspace: create one on a branch, or show / unlink / remove the linked one.

The git work is done by `realm/worktrees.py` (fixed arguments, refusals with git's own message);
this modal only collects the branch and shows what git said. It dismisses with True when the
orkspace's worktree changed (the app then saves the Town Scroll).
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from orkcraft import scroll as ts
from orkcraft.realm import worktrees as wt


class WorktreeModal(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "close", "Close")]
    DEFAULT_CSS = """
    WorktreeModal { align: center middle; }
    WorktreeModal > Vertical { width: 72; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    WorktreeModal .wt-title { text-style: bold; color: $accent; padding-bottom: 1; }
    WorktreeModal .wt-error { color: $error; padding-top: 1; }
    WorktreeModal Horizontal { height: auto; padding-top: 1; }
    WorktreeModal Button { margin-right: 1; }
    """

    def __init__(self, scroll: ts.TownScroll, repo_root: Path, orkspace_id: str) -> None:
        super().__init__()
        self.scroll = scroll
        self.repo_root = repo_root
        self.orkspace_id = orkspace_id
        self.ork = scroll.orkspace(orkspace_id)
        self.linked = bool(self.ork and self.ork.git.enabled and self.ork.git.mode == "worktree")
        self._force_offered = False

    def compose(self) -> ComposeResult:
        name = self.ork.name if self.ork else self.orkspace_id
        with Vertical():
            yield Label(Text(f"⎇ Worktree · {name}"), classes="wt-title")
            if self.linked:
                yield Static(Text(self._describe()), id="wt-info")
                with Horizontal():
                    yield Button("Unlink (keep folder)", id="wt-unlink")
                    yield Button("Remove worktree", variant="warning", id="wt-remove")
                    yield Button("Close", id="wt-close")
            else:
                yield Static(Text("Sessions of this orkspace will run in their own checkout on this branch\n"
                                  f"(folder .orkcraft/worktrees/{self.orkspace_id}; an existing branch is reused)."))
                yield Label("Branch")
                yield Input(value=f"orkspace/{self.orkspace_id}", id="wt-branch")
                yield Label("Start from (for a new branch)")
                yield Input(value="HEAD", id="wt-base")
                with Horizontal():
                    yield Button("Create", variant="primary", id="wt-create")
                    yield Button("Cancel", id="wt-close")
            yield Static("", id="wt-error", classes="wt-error", markup=False)

    def _describe(self) -> str:
        git = self.ork.git
        path = (self.repo_root / git.path).resolve()
        try:
            st = wt.status(path)
            state = f"{st.changes} uncommitted change(s)" if st.dirty else "clean"
        except (wt.WorktreeError, OSError):
            state = "folder missing"
        return f"branch  {git.branch}\nfolder  {git.path}\nstate   {state}"

    def _error(self, text: str) -> None:
        self.query_one("#wt-error", Static).update(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._create()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "wt-create":
            self._create()
        elif bid == "wt-unlink":
            wt.unlink(self.scroll, self.orkspace_id)
            self.dismiss(True)
        elif bid in ("wt-remove", "wt-force"):
            self._remove(force=bid == "wt-force")
        else:
            self.dismiss(False)

    def _create(self) -> None:
        if self.linked:
            return
        branch = self.query_one("#wt-branch", Input).value.strip()
        base = self.query_one("#wt-base", Input).value.strip() or "HEAD"
        try:
            path = wt.create(self.repo_root, self.orkspace_id, branch, base)
            wt.link(self.scroll, self.orkspace_id, self.repo_root, path, branch)
        except (wt.WorktreeError, OSError) as e:
            self._error(str(e))
            return
        self.dismiss(True)

    def _remove(self, force: bool) -> None:
        path = (self.repo_root / self.ork.git.path).resolve()
        try:
            if path.exists():
                wt.remove(self.repo_root, path, force=force)
        except wt.WorktreeError as e:
            self._error(str(e))
            if not force and not self._force_offered and "uncommitted" in str(e):
                self._force_offered = True
                self.query_one(Horizontal).mount(
                    Button("Remove anyway (discard that work)", variant="error", id="wt-force"))
            return
        wt.unlink(self.scroll, self.orkspace_id)
        self.dismiss(True)

    def action_close(self) -> None:
        self.dismiss(False)
