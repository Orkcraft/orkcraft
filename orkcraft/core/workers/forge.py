"""⚒️ The Forge's work: the branches, their pull requests, their tests and the merge.

`refresh()` looks at the repository in a thread (realm/gitinfo.py); between two looks it sends
`git.commit`, `git.pr_opened`, `git.pr_merged`. `merge(branch)` tests the branch with `test_cmd`
and squash-merges it into the base (realm/forge.py) in a thread: success sends `forge.merged`,
conflicts or red tests `forge.conflict`. A cart naming a branch is a merge order — at once, or,
with `confirm` on, it waits for the person's yes (`asking`). `test(branch)` runs the tests alone.

The branch the person looks at (`picked`) has its commits and files read at once and its pull
request's comments fetched from GitHub (`gh`) in a thread. Every merge is kept (`merges`), so a
branch shows its conflicts and how they were settled.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from orkcraft.core.workers import Worker
from orkcraft.realm import forge, gitinfo

GIT_TIMEOUT_S = 30
COMMITS = 20
FILES = 200
DIFF_LIMIT = 400_000          # characters of a diff opened in Lake
MERGES = 30                   # merges kept, newest last


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "git failed").strip()[:200])
    return out.stdout


def pr_comments(repo: Path, number: int, runner=subprocess.run) -> list[dict] | None:
    """A pull request's comments and reviews, oldest first: [{author, body, at, state}]; None when
    `gh` is missing or cannot answer."""
    if runner is subprocess.run and shutil.which("gh") is None:
        return None
    try:
        out = runner(["gh", "pr", "view", str(number), "--json", "comments,reviews"],
                     cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    rows = []
    for c in data.get("comments") or ():
        rows.append({"author": str((c.get("author") or {}).get("login", "")), "body": str(c.get("body", "")),
                     "at": str(c.get("createdAt", "")), "state": ""})
    for r in data.get("reviews") or ():
        if not r.get("body") and r.get("state") in (None, "", "COMMENTED"):
            continue
        rows.append({"author": str((r.get("author") or {}).get("login", "")), "body": str(r.get("body", "")),
                     "at": str(r.get("submittedAt", "")), "state": str(r.get("state", "")).lower()})
    return sorted(rows, key=lambda x: x["at"])


class ForgeWorker(Worker):
    TYPE = "forge"
    merger = staticmethod(forge.merge)            # tests swap the merge here
    tester = staticmethod(forge.run_tests)        # … the test run
    pr_runner = None                              # … and `gh` (None: the real one)

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.snap: gitinfo.Snapshot | None = None
        self.merging = ""
        self.last_merge: forge.Result | None = None
        self.merges: list[tuple[str, forge.Result]] = []      # (when, result), newest last
        self.asking = ""                       # a branch a road brought, waiting for the person's yes
        self.testing: set[str] = set()
        self.tests: dict[str, dict] = {}       # branch → {ok, output, at}
        self.picked = ""                       # the branch the person looks at
        self.commits: list[dict] = []          # the picked branch's: [{hash, subject, when}]
        self.files: list[dict] = []            # … and its files against the base: [{path, added, removed}]
        self.comments: dict[str, list[dict] | None] = {}      # branch → its PR's comments (None: gh cannot say)
        self._looking = False

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    @property
    def base(self) -> str:
        return self.snap.base if self.snap else str(self.config.get("base") or "main")

    def branch(self, name: str) -> gitinfo.Branch | None:
        return next((b for b in self.snap.branches if b.name == name), None) if self.snap else None

    def refresh(self) -> None:
        """Look at the repository again (in a thread): the branches, their changes and PRs."""
        if self._looking:
            return
        self._looking = True
        repo, base = self.repo_root, str(self.config.get("base", ""))

        def work() -> None:
            try:
                snap = gitinfo.snapshot(repo, base)
            except Exception as e:           # the look ends, the building stays
                snap = gitinfo.Snapshot(base or "main", error=str(e)[:200])
            self.town.call(self.apply_snapshot, snap)

        threading.Thread(target=work, daemon=True, name=f"forge-look-{self.building_id}").start()

    def apply_snapshot(self, snap: gitinfo.Snapshot) -> None:
        self._looking = False
        for event_id, text in gitinfo.changes(self.snap, snap):
            self.emit(event_id, text, text.split(":", 1)[0])
        self.snap = snap
        if self.picked and self.branch(self.picked) is None:
            self.picked = ""
        if self.picked:
            self._read_picked()
        self.changed()

    def status(self) -> str:
        if self.merging or self.testing:
            return "WORKING"
        if self.snap is not None and self.snap.error:
            return "ERROR"
        return ""

    # -- the branch the person looks at -----------------------------------------------------------

    def pick(self, name: str) -> None:
        """Look at `name`: its commits and files now, its PR's comments from GitHub in a thread."""
        if self.branch(name) is None:
            raise ValueError(f"no branch {name!r}")
        self.picked = name
        self._read_picked()
        self.changed()
        b = self.branch(name)
        if b.pr is not None:
            self.fetch_comments(name, b.pr.number)

    def _read_picked(self) -> None:
        repo, base, name = self.repo_root, self.base, self.picked
        against = name != base and base != "HEAD"
        try:
            rows = _git(repo, "log", "--format=%h%x09%s%x09%cr", f"-{COMMITS}",
                        f"{base}..{name}" if against else name).splitlines()
            self.commits = [dict(zip(("hash", "subject", "when"), r.split("\t", 2))) for r in rows if r.count("\t") >= 2]
            self.files = []
            if against:
                for row in _git(repo, "diff", "--numstat", f"{base}...{name}").splitlines()[:FILES]:
                    added, removed, path = (row.split("\t", 2) + ["", ""])[:3]
                    self.files.append({"path": path, "added": int(added) if added.isdigit() else 0,
                                       "removed": int(removed) if removed.isdigit() else 0})
        except (RuntimeError, OSError, subprocess.SubprocessError):
            self.commits, self.files = [], []

    def fetch_comments(self, name: str, number: int) -> None:
        repo, runner = self.repo_root, type(self).pr_runner

        def work() -> None:
            got = pr_comments(repo, number, *([runner] if runner else []))
            self.town.call(self._got_comments, name, got)

        threading.Thread(target=work, daemon=True, name=f"forge-pr-{self.building_id}").start()

    def _got_comments(self, name: str, got: list[dict] | None) -> None:
        self.comments[name] = got
        self.changed()

    def diff(self, name: str) -> str:
        """The branch's changes against the base, as a unified diff (to open in Lake)."""
        if self.branch(name) is None:
            raise ValueError(f"no branch {name!r}")
        if name == self.base:
            return ""
        text = _git(self.repo_root, "diff", f"{self.base}...{name}")
        return text if len(text) <= DIFF_LIMIT else text[:DIFF_LIMIT] + "\n… (cut)\n"

    def pr_url(self, name: str) -> str:
        b = self.branch(name)
        return b.pr.url if b is not None and b.pr is not None else ""

    def merges_of(self, name: str) -> list[tuple[str, forge.Result]]:
        return [(at, r) for at, r in self.merges if r.branch == name]

    # -- the tests and the merge --------------------------------------------------------------------

    def test(self, name: str) -> bool:
        """Run `test_cmd` on the branch in a throw-away worktree (realm/forge.py), in a thread."""
        cmd = str(self.config.get("test_cmd") or "")
        if not cmd:
            self.toast("no test command set — say it in the settings", severity="warning")
            return False
        if self.branch(name) is None or name in self.testing:
            return False
        self.testing.add(name)
        self.changed()
        repo, tester = self.repo_root, type(self).tester

        def work() -> None:
            try:
                ok, out = tester(repo, name, cmd)
            except Exception as e:           # a broken test run is a red one
                ok, out = False, str(e)[:2000]
            self.town.call(self._tested, name, ok, out)

        threading.Thread(target=work, daemon=True, name=f"forge-test-{self.building_id}").start()
        return True

    def _tested(self, name: str, ok: bool, output: str) -> None:
        self.testing.discard(name)
        self.tests[name] = {"ok": ok, "output": output, "at": time.strftime("%H:%M")}
        self.toast(f"{name}: tests {'passed' if ok else 'failed'}", severity="information" if ok else "warning")
        self.changed()

    def merge(self, branch: str) -> bool:
        """Test and squash-merge `branch` into the base, now (the face asked the person first)."""
        if self.merging:
            self.toast(f"already merging {self.merging}")
            return False
        if branch == self.base:
            self.toast(f"{branch} is the base")
            return False
        if self.asking == branch:
            self.asking = ""
        self.merging = branch
        self.changed()
        repo, base, tests = self.repo_root, self.base, str(self.config.get("test_cmd") or "")
        merger = type(self).merger

        def work() -> None:
            try:
                res = merger(repo, branch, base, tests)
            except Exception as e:  # git trouble of every kind ends this merge, not the town
                res = forge.Result(False, branch, base, error=str(e)[:300])
            self.town.call(self.merged, res)

        threading.Thread(target=work, daemon=True, name=f"forge-{self.building_id}").start()
        return True

    def merged(self, res: forge.Result) -> None:
        self.merging = ""
        self.last_merge = res
        self.merges = (self.merges + [(time.strftime("%Y-%m-%d %H:%M"), res)])[-MERGES:]
        if res.tests:
            self.tests[res.branch] = {"ok": res.error != "tests failed", "output": res.tests, "at": time.strftime("%H:%M")}
        if res.ok:
            self.emit("forge.merged", res.text(), f"{res.branch} → {res.base}")
            self.toast(f"{res.branch} → {res.base} {res.commit[:8]}", title="⚒️ Merged")
        else:
            self.emit("forge.conflict", res.text(), f"{res.branch}: {res.error}")
            self.toast(res.error, title=f"⚒️ {res.branch} not merged", severity="warning")
        self.changed()
        self.refresh()

    def decline(self) -> None:
        """The person said no to the merge a road asked for."""
        self.asking = ""
        self.changed()

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart naming a branch is a merge order (e.g. from a Barracks' pool.done): at once, or
        with `confirm` on, after the person's yes."""
        names = {b.name for b in self.snap.branches} if self.snap else set()
        text = f"{payload.title}\n{payload.value}"
        branch = next((n for n in sorted(names, key=len, reverse=True) if n != self.base and n in text), None)
        if not branch:
            return
        if self.config.get("confirm"):
            self.asking = branch
            self.toast(f"{branch} waits for your yes to merge", title=f"⚒️ {self.title}")
            self.changed()
            return
        self.merge(branch)

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

    def hut_lines(self, widths: list[int]) -> list[str]:
        snap = self.snap
        if snap is None:
            return ["⎇ looking…"]
        if snap.error:
            return [f"⚠ {snap.error[:40]}"]
        rows = [b for b in snap.branches if b.name != snap.base]
        prs = sum(1 for b in snap.branches if b.pr is not None)
        last = ("merging " + self.merging + "…" if self.merging else
                "—" if self.last_merge is None else
                f"✓ {self.last_merge.branch}" if self.last_merge.ok else f"✗ {self.last_merge.branch}")
        gate = "CONFIRM" if self.config.get("confirm") else "OPEN"
        test = "set" if self.config.get("test_cmd") else "none"
        return [f"base: {snap.base}", f"branches: {len(rows)} · PRs: {prs}", f"tests: {test}",
                f"last: {last}", f"changes: {rows[0].change if rows and rows[0].files else '—'}", f"gate: {gate}"]
