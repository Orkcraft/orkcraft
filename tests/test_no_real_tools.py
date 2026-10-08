"""A test never runs the machine's own agent CLIs or gh (tests/conftest.py hides them): on a machine that
has Claude Code, a test that forgot to fake it would run a real, paid agent on the web."""
from __future__ import annotations

import shutil

from orkcraft.realm import harnesses


def test_no_real_agent_cli_nor_gh_is_on_the_path():
    tools = [h.default_bin for h in harnesses.REGISTRY.values()] + ["gh"]
    assert {t: shutil.which(t) for t in tools if shutil.which(t)} == {}
