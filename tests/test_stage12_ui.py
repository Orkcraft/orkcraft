"""Stage 12 in the app: worktree per orkspace (G), sessions in it, War Map marks, Warder ❓."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm.orcs import Alert
from orkcraft.screens.worktree_modal import WorktreeModal

SIZE = (200, 50)


@pytest.mark.asyncio
async def test_g_creates_a_worktree_sessions_run_there_and_war_map_marks_it(fake_repo: Path):
    (fake_repo / ".gitignore").write_text(".orkcraft/\n", encoding="utf-8")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("escape", "G")
        await pilot.pause()
        assert not isinstance(app.screen, WorktreeModal)            # Main Camp: the repository itself
        lab = ts.new_orkspace(app.scroll, "Auth Core", "void")
        app.desktop.switch_orkspace(lab.id)
        await pilot.pause()
        await pilot.press("escape", "G")
        await pilot.pause()
        assert isinstance(app.screen, WorktreeModal)
        await pilot.click("#wt-create")
        await pilot.pause()
        path = fake_repo / ".orkcraft" / "worktrees" / lab.id
        assert path.is_dir() and not isinstance(app.screen, WorktreeModal)
        g = app.scroll.orkspace(lab.id).git
        assert (g.enabled, g.mode, g.branch) == (True, "worktree", f"orkspace/{lab.id}")
        assert app.session_cwd() == path.resolve()
        (path / "new.md").write_text("x\n", encoding="utf-8")
        app.refresh_worktree_marks()
        app._console.refresh_state(app.focus_state, app.roster)
        await pilot.pause()
        assert app.worktree_marks[lab.id] == f"⎇ orkspace/{lab.id}*"
        started = {}
        import orkcraft.widgets.terminal as term_mod

        class FakeTerminal(term_mod.Terminal):
            def __init__(self, command, cwd=None, env=None, id=None):
                started["cwd"] = cwd
                super().__init__(["true"], cwd=cwd, env=env, id=id)

        import orkcraft.screens.chat_view as cv
        cv.Terminal = FakeTerminal
        try:
            app.chat.action_new_session("claude")
            await pilot.pause()
        finally:
            cv.Terminal = term_mod.Terminal
        assert started["cwd"] == str(path.resolve())
        # remove refuses with uncommitted work, then forced removal keeps the branch
        # (focus is in the new terminal now, which rightly swallows keys — use the action)
        app.action_worktree()
        await pilot.pause()
        await pilot.click("#wt-remove")
        await pilot.pause()
        assert "uncommitted" in str(app.screen.query_one("#wt-error").render())
        await pilot.click("#wt-force")
        await pilot.pause()
        assert not path.exists() and not app.scroll.orkspace(lab.id).git.enabled
        assert app.session_cwd() == fake_repo
        branches = subprocess.run(["git", "branch", "--list", f"orkspace/{lab.id}"], cwd=fake_repo,
                                  capture_output=True, text=True).stdout
        assert f"orkspace/{lab.id}" in branches


@pytest.mark.asyncio
async def test_warder_alert_is_acknowledged(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        alert = Alert(id="warder:x", title="🛡️ Warder blocked: secret", options=[("1", "Acknowledge")],
                      source="warder", ref="warder:x")
        app.answer_alert(alert, "2")
        assert "warder:x" not in app.dismissed          # "keep it on the board"
        app.answer_alert(alert, "1")
        assert "warder:x" in app.dismissed


def test_hooks_in_a_worktree_log_to_the_main_repository(tmp_path: Path):
    main = tmp_path / "main"
    main.mkdir()
    for args in (["init", "-q", "-b", "main"], ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q",
                                                  "--allow-empty", "-m", "i"]):
        subprocess.run(["git", *args], cwd=main, check=True, capture_output=True)
    wt = main / ".orkcraft" / "worktrees" / "lab"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "lab", str(wt)], cwd=main, check=True, capture_output=True)
    for name in ("session.py", "warder.py"):
        spec = importlib.util.spec_from_file_location(name[:-3], Path(__file__).resolve().parents[1] / "orkcraft" / "hooks" / name)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.main_repo(wt) == main.resolve()
        assert mod.main_repo(main) == main
