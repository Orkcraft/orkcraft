"""Fakes for the Barracks tests: the task's git and the steward's model call."""
from __future__ import annotations


class FakeGit:
    """No real branches: every task 'has' a commit, the tests pass, nothing is pushed."""

    def __init__(self, commits: int = 1, tests: tuple[bool, str] = (True, ""), pr: str = "",
                 files: tuple[str, ...] = ("app.py",)):
        self.commits, self.tests, self.pr, self.files = commits, tests, pr, files
        self.prepared, self.published, self.cuts, self.merges, self.checks = [], [], [], [], []
        self.conflicts: set[str] = set()      # branches whose merge conflicts (once each)

    def base_of(self, repo_root, configured=""):
        return configured or "main"

    def prepare(self, workdir, branch, base):
        self.prepared.append((branch, base))

    def diff(self, workdir, base, branch):
        return self.commits, "".join(f"diff --git a/{f} b/{f}\n+ a change\n" for f in self.files) if self.commits else ""

    def test(self, workdir, command, cancel):
        return self.tests

    def cut(self, repo_root, branch, base):
        self.cuts.append((branch, base))

    def merge(self, repo_root, into, branch, message):
        if branch in self.conflicts:
            self.conflicts.discard(branch)
            return False, "conflicts in app.py"
        self.merges.append((into, branch))
        return True, "merged"

    def check(self, repo_root, branch, command, cancel, where):
        self.checks.append(branch)
        return self.tests

    def publish(self, workdir, branch, base, title, body):
        self.published.append((branch, base, title))
        return (self.pr, "pull request opened") if self.pr else ("", "no remote: the branch stays local")


class Steward:
    """A scripted steward: answers questions with `answers` (else ASK), plans with `plans` (else SIMPLE),
    reviews with `verdicts` (else ACCEPT)."""

    def __init__(self, verdicts=(), answers=(), plans=()):
        self.verdicts, self.answers, self.plans, self.prompts = list(verdicts), list(answers), list(plans), []
        self.models = []

    def __call__(self, harness, prompt, workdir, cancel, model):
        self.prompts.append(prompt)
        self.models.append(model)
        if "PLAN the task" in prompt:
            return (self.plans.pop(0) if self.plans else "SIMPLE"), 0.02
        if "asks\n\n" in prompt:
            return (f"ANSWER: {self.answers.pop(0)}" if self.answers else "ASK"), 0.01
        return (self.verdicts.pop(0) if self.verdicts else "ACCEPT"), 0.01
