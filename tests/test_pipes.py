"""Rally pipes: loops in a scroll, capabilities and the safe payload helpers."""
from __future__ import annotations

import os
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import pipes

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "loot": {"title": "Loot Chest", "icon": "📦", "orc": "Quartermaster", "role": "files", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
    "town_hall": {"title": "War Tent", "icon": "💬", "orc": "Peon", "role": "sessions", "category": "core"},
}


def test_validate_reports_a_loop_written_by_hand():
    scroll = ts.default_scroll(PRESETS)
    data = scroll.to_dict()
    by_id = {b["id"]: b for b in data["buildings"]}
    by_id["forge"]["roads"] = [{"id": "r", "from": "loot", "event": "on_selection_change", "handler": None}]
    by_id["loot"]["roads"] = [{"id": "r", "from": "forge", "event": "on_selection_change", "handler": None}]
    assert any("loop" in p for p in ts.validate(data))


def test_modes_follow_what_targets_accept():
    assert pipes.modes_for("forge", "scrying") == [pipes.ON_SELECTION, pipes.ON_TASK]
    assert pipes.modes_for("loot", "scrying") == [pipes.ON_SELECTION, pipes.ON_TASK]
    assert pipes.modes_for("forge", "loot") == [pipes.ON_TASK]       # the chest keeps reports only
    assert pipes.modes_for("forge", "farm") == []                    # the farm receives nothing
    assert pipes.modes_for("scrying", "loot") == [pipes.ON_TASK]
    assert pipes.modes_for("scrying", "scrying") == []
    assert pipes.accepts("scrying") and not pipes.accepts("forge")


def test_file_payload_stays_inside_the_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "loot").mkdir(parents=True)
    (repo / "loot" / "note.md").write_text("# Hi\n", encoding="utf-8")
    (repo / "loot" / "run.py").write_text("print('x')\n", encoding="utf-8")
    (repo / "loot" / "blob.bin").write_bytes(b"\0\1\2")
    (repo / "loot" / "big.txt").write_bytes(b"a" * (pipes.FILE_LIMIT_BYTES + 1))
    secret = tmp_path / "secret.env"
    secret.write_text("TOKEN=1\n", encoding="utf-8")
    os.symlink(secret, repo / "loot" / "link.env")

    assert pipes.read_file_payload(repo, "loot/note.md") == ("📄 loot/note.md", "# Hi\n")
    title, body = pipes.read_file_payload(repo, "loot/run.py")
    assert body.startswith("```py\n") and "print('x')" in body
    assert "Binary" in pipes.read_file_payload(repo, "loot/blob.bin")[1]
    assert "too big" in pipes.read_file_payload(repo, "loot/big.txt")[1]
    for escape in ("../secret.env", str(secret), "loot/link.env"):
        title, body = pipes.read_file_payload(repo, escape)
        assert title.startswith("🚫") and "TOKEN" not in body


def test_task_report_and_loot_file(tmp_path: Path):
    title, md = pipes.task_report("Coder", "Forge", ["", "step 1", "  ", "done ```x```"])
    assert title == "🧌 Coder · Forge — task completed"
    assert "step 1" in md and md.count("````") == 2
    path = pipes.write_loot(tmp_path, "../../etc", title, md)
    assert path.parent == tmp_path / "loot" / "pipes" and path.name.endswith("-______etc.md")
    assert path.read_text(encoding="utf-8").startswith("# 🧌 Coder")
    second = pipes.write_loot(tmp_path, "../../etc", title, md)
    assert second != path


def test_the_trail_adds_up_and_reads():
    import datetime as dt
    t0 = dt.datetime(2026, 10, 4, 12, 0)
    a = pipes.hop("barracks", "scribe", "agent", 12000, 0.08, now=t0)
    b = pipes.hop("council", "chief", "agent", 40000, 0.31, now=t0 + dt.timedelta(minutes=1))
    c = pipes.hop("mill", "", "chain", now=t0 + dt.timedelta(minutes=2))
    assert pipes.trail_totals((a, b, c)) == (52000, 0.39)
    assert pipes.trail_totals((c,)) == (None, None)
    assert pipes.merge_trails((b, a), (a, c)) == (a, b, c)          # each hop once, in order of time
    line = pipes.trail_line((a, b), {"barracks": "Barracks", "council": "Council"})
    assert line == "Barracks 12k tok $0.08 → Council 40k tok $0.31 = 52k tok $0.39"
    p = pipes.Payload(pipes.TEXT, "doc", "barracks", pipes.ON_TASK, ref="D-1", trail=(a,))
    assert p.trail == (a,) and p.ref == "D-1"
    assert p == pipes.Payload(pipes.TEXT, "doc", "barracks", pipes.ON_TASK, ref="D-1")   # the trail is not identity
    assert pipes.trail_of([a.as_dict(), {"nope": 1}, "x"]) == (a,)
