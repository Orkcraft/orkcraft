"""Stage 12 in the app: worktree per orkspace (G), sessions in it, War Map marks, Warder ❓."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
from pathlib import Path



SIZE = (200, 50)


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
