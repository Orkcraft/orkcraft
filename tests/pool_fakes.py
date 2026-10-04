"""Fakes for the Barracks tests: the task's git and the steward's model call."""
from __future__ import annotations


class FakeGit:
    """No real branches: every task 'has' a commit, the tests pass, nothing is pushed."""

    def __init__(self, commits: int = 1, tests: tuple[bool, str] = (True, ""), pr: str = ""):
        self.commits, self.tests, self.pr = commits, tests, pr
        self.prepared, self.published = [], []

    def base_of(self, repo_root, configured=""):
        return configured or "main"

    def prepare(self, workdir, branch, base):
        self.prepared.append((branch, base))

    def diff(self, workdir, base, branch):
        return self.commits, "+ a change\n" if self.commits else ""

    def test(self, workdir, command, cancel):
        return self.tests

    def publish(self, workdir, branch, base, title, body):
        self.published.append((branch, base, title))
        return (self.pr, "pull request opened") if self.pr else ("", "no remote: the branch stays local")


class Steward:
    """A scripted steward: answers questions with `answers` (else ASK), reviews with `verdicts` (else ACCEPT)."""

    def __init__(self, verdicts=(), answers=()):
        self.verdicts, self.answers, self.prompts = list(verdicts), list(answers), []

    def __call__(self, harness, prompt, workdir, cancel, model):
        self.prompts.append(prompt)
        if "asks\n\n" in prompt:
            return (f"ANSWER: {self.answers.pop(0)}" if self.answers else "ASK"), 0.01
        return (self.verdicts.pop(0) if self.verdicts else "ACCEPT"), 0.01
