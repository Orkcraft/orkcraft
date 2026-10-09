"""Window manager tests: pure geometry plus Pilot-driven move/resize/snap/persist."""
from __future__ import annotations

import json
from pathlib import Path


from orkcraft import scroll as ts
from orkcraft.realm.buildings import presets, registry

SIZE = (120, 40)


# -- geometry -------------------------------------------------------------------


def test_persist_roundtrip_and_rejects_garbage(tmp_path: Path):
    pr = presets(registry())
    path = tmp_path / "sub" / ".orkcraft.json"
    s = ts.default_scroll(pr)
    assert ts.save(path, s) == []
    loaded, problems = ts.load(path, pr)
    assert problems == [] and loaded.to_dict()["buildings"] == s.to_dict()["buildings"]
    path.write_text("not json", encoding="utf-8")
    loaded, problems = ts.load(path, pr)
    assert any("invalid-" in p for p in problems)
    path.write_text(json.dumps({"version": 999, "windows": {}}), encoding="utf-8")
    loaded, problems = ts.load(path, pr)
    assert any("invalid-" in p for p in problems)


# -- TUI ------------------------------------------------------------------------
