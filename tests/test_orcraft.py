"""Orkcraft core: HUD, roster and passive ❓ alerts, pins, unit orders, viewports, Halt All."""
from __future__ import annotations

import stat
from pathlib import Path

import pytest

from orkcraft.realm.orcs import detect_prompt

SIZE = (200, 50)


# -- pure -------------------------------------------------------------------------------------

def test_detect_prompt_finds_numbered_menu_at_the_bottom():
    screen = [
        "╭──────────────────────────────╮",
        "│ Do you want to make this edit to app.py?",
        "│ ❯ 1. Yes",
        "│   2. Yes, and don't ask again this session",
        "│   3. No, and tell Claude what to do differently",
        "╰──────────────────────────────╯",
        "",
    ]
    question, options = detect_prompt([l.strip("│ ") for l in screen])
    assert "Do you want to make this edit" in question
    assert [k for k, _ in options] == ["1", "2", "3"]
    assert options[1][1].startswith("Yes, and don't ask")


def test_detect_prompt_finds_bracketed_menu():
    screen = [
        "Analyzing changes...",
        "Should we apply this patch?",
        "[1] Apply patch",
        "[2] Discard patch",
    ]
    res = detect_prompt(screen)
    assert res is not None
    question, options = res
    assert "Should we apply this patch" in question
    assert options == [("1", "Apply patch"), ("2", "Discard patch")]


def test_detect_prompt_finds_yes_no_prompts():
    # Prompt on same line
    screen1 = ["Building artifact...", "Do you want to run `git push`? [y/N]"]
    res1 = detect_prompt(screen1)
    assert res1 is not None
    q1, opts1 = res1
    assert "Do you want to run `git push`" in q1
    assert opts1 == [("y", "Yes"), ("n", "No")]

    # Prompt on separate line
    screen2 = ["Delete directory /tmp/scratch?", "[y/N]"]
    res2 = detect_prompt(screen2)
    assert res2 is not None
    q2, opts2 = res2
    assert "Delete directory /tmp/scratch" in q2
    assert opts2 == [("y", "Yes"), ("n", "No")]


def test_detect_prompt_ignores_plain_output_and_broken_numbering():
    assert detect_prompt(["1. only one option", "some output"]) is None
    assert detect_prompt(["1. a", "3. c"]) is None
    assert detect_prompt(["hello", "world"]) is None


# -- helpers ------------------------------------------------------------------------------------


async def _wait_for(pilot, predicate, tries: int = 60):
    for _ in range(tries):
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


# -- TUI --------------------------------------------------------------------------------------------


@pytest.fixture
def menu_cli(tmp_path: Path, monkeypatch) -> Path:
    """A stand-in CLI that asks a numbered question and echoes the answer."""
    script = tmp_path / "fake-claude"
    script.write_text(
        "#!/bin/bash\n"
        "trap 'echo INTERRUPTED' INT\n"
        "echo 'Do you want to proceed?'\necho '❯ 1. Yes'\necho '  2. No'\n"
        "read -n 1 answer\necho \"answer:$answer\"\n"
        "while true; do sleep 0.1; done\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(script))
    monkeypatch.setenv("ORKCRAFT_CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("ORKCRAFT_AGY_HOME", str(tmp_path / "agy"))
    return script
