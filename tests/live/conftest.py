"""The live bench: real tools on real models (docs/testing.md). Skipped without `--live`.

    pytest -m live --live                        # pi on Gemini Flash: needs `pi` and GEMINI_API_KEY
    pytest -m live --live --refresh-fixtures     # … and rewrites tests/fixtures/pi_json_*.jsonl

ORKCRAFT_LIVE_MODEL picks the model (pi's `provider/id`), ORKCRAFT_LIVE_BUDGET the most a run may
spend in USD: once the tests have spent it, the rest are skipped.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orkcraft.env import getenv

MODEL = getenv("LIVE_MODEL", "google/gemini-flash-lite-latest")
BUDGET = float(getenv("LIVE_BUDGET", "0.25"))
FIXTURES = Path(__file__).parent.parent / "fixtures"
SPENT: list[float] = []


def spend(cost: float | None) -> None:
    """What one run cost (None: the tool did not say, which a priced tool must)."""
    assert cost is not None, "a priced tool said nothing of its price"
    SPENT.append(cost)


def pytest_terminal_summary(terminalreporter, config):
    if config.getoption("--live") and SPENT:
        terminalreporter.write_line(f"live bench: {len(SPENT)} runs on {MODEL}, ${sum(SPENT):.4f} spent")


@pytest.fixture(autouse=True)
def within_budget():
    if sum(SPENT) >= BUDGET:
        pytest.skip(f"the live budget is spent (${sum(SPENT):.4f} of ${BUDGET})")


@pytest.fixture
def pi_bin(tmp_path, monkeypatch) -> str:
    """pi, on its own empty settings and sessions (never the person's ~/.pi)."""
    found = getenv("PI_BIN") or shutil.which("pi")
    if not found:
        pytest.skip("pi is not installed (npm install -g @earendil-works/pi-coding-agent) or ORKCRAFT_PI_BIN")
    monkeypatch.setenv("ORKCRAFT_PI_BIN", found)
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "pi-agent"))
    monkeypatch.setenv("PI_TELEMETRY", "0")
    return found


@pytest.fixture
def gemini(pi_bin) -> str:
    """The model the bench runs on; skipped without a key."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not set")
    return MODEL


def run(cmd: list[str], cwd: Path) -> str:
    """stdout of one run of a tool's argv, as orkcraft would start it (no shell, nothing on stdin)."""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stderr[-1000:] or proc.stdout[-1000:]
    return proc.stdout


@pytest.fixture
def record(request, tmp_path):
    """`record(name, stdout)`: with --refresh-fixtures, keeps what a tool printed as
    tests/fixtures/<name>.jsonl, the machine's own paths written as /home/ork/…"""
    def keep(name: str, stdout: str) -> None:
        if not request.config.getoption("--refresh-fixtures"):
            return
        for path, plain in ((str(tmp_path), "/home/ork/project"), (str(Path.home()), "/home/ork")):
            stdout = stdout.replace(path, plain)
        stdout = re.sub(r'[^"\s]*/node_modules/', "/usr/lib/node_modules/", stdout)
        (FIXTURES / f"{name}.jsonl").write_text(stdout, encoding="utf-8")
    return keep
