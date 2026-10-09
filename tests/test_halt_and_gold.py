"""🛑 Halt All and the run's 🪙 limit reach the buildings that call models on their own."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft.realm import masonry

SIZE = (200, 46)


def _specs(repo: Path) -> None:
    for s in ({"id": "camp", "title": "Barracks", "icon": "🏕", "orc": {"name": "Grunts"}, "type": "barracks"},
              {"id": "fire", "title": "Clan Fire", "icon": "🪔", "orc": {"name": "Chieftain"}, "type": "council",
               "config": {"members": ["Planner:claude"]}},
              {"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": ["agent: shorten it"]}}):
        assert masonry.save_spec(repo, s) == []


def test_halt_all_kills_every_registered_process_and_its_children(tmp_path: Path):
    import subprocess
    import sys
    from orkcraft.realm import halt
    halt.reset()
    done = threading.Event()
    seen: dict = {}

    def work() -> None:
        try:
            halt.run([sys.executable, "-c", "import subprocess, sys, time; "
                      "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"],
                     timeout=30)
        except halt.Halted:
            seen["halted"] = True
        except subprocess.TimeoutExpired:
            seen["timeout"] = True
        done.set()

    threading.Thread(target=work, daemon=True).start()
    for _ in range(100):
        if halt._LIVE:
            break
        threading.Event().wait(0.05)
    seen_before = halt.count()
    assert halt.halt_all() == 1 and halt.stopped_since(seen_before)
    assert done.wait(10) and seen == {"halted": True}
    assert halt.halt_all() == 0                                   # nothing left running


def test_a_short_model_call_stopped_by_the_halt_is_not_a_failure_the_lookout_passes_on():
    from orkcraft.realm import halt, lookout, watch

    def runner(prompt):
        raise halt.Stopped()

    sig = watch.Signal("2026-10-04T09:00:00", "slack", "hi", "body")
    with pytest.raises(halt.Stopped):
        lookout.judge("feedback", [sig], runner)
