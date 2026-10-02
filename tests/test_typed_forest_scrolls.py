"""🌲 File Forest picks a target, 🗑️ Scroll Dump finds fragments (T1107 stage 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes, shelves
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.files_view import FilesView
from orkcraft.screens.typed.knowledge_view import KnowledgeView

HANDBOOK = """# Handbook

## Release checklist
Tag the release, write the changelog, publish to PyPI, announce it.

## Onboarding
Read the town map and the roads. Ask the Chieftain.

## Rollback
Yank the release and tag again when the smoke test fails after a release.
"""


def test_chunks_and_search(fake_repo: Path):
    (fake_repo / "docs" / "handbook.md").write_text(HANDBOOK)
    chunks = shelves.chunks_of(fake_repo, "docs/handbook.md")
    assert [c.heading for c in chunks] == ["Release checklist", "Onboarding", "Rollback"]
    base = shelves.scan_base(fake_repo, "docs")
    found = shelves.search(fake_repo, [base], "how do we release and roll back?")
    assert found and found[0].heading in ("Release checklist", "Rollback")
    assert "Onboarding" not in [c.heading for c in found]
    assert shelves.search(fake_repo, [base], "the and of") == []           # only stop words
    long = "## Big\n" + "\n\n".join(f"paragraph {i} " + "word " * 60 for i in range(10))
    (fake_repo / "docs" / "big.md").write_text(long)
    assert all(len(c.text) <= shelves.CHUNK_CHARS for c in shelves.chunks_of(fake_repo, "docs/big.md"))
    few = shelves.search(fake_repo, [shelves.scan_base(fake_repo, "docs")], "paragraph word", k=10, budget=1500)
    assert sum(len(c.text) for c in few) <= 1500 + shelves.CHUNK_CHARS
    assert "### docs/handbook.md § Rollback" in shelves.fragments_markdown("x", [c for c in chunks if c.heading == "Rollback"])


@pytest.mark.asyncio
async def test_the_forest_picks_and_the_scrolls_answer(fake_repo: Path, monkeypatch):
    (fake_repo / "docs" / "handbook.md").write_text(HANDBOOK)
    for s in ({"id": "woods", "title": "Forest", "icon": "🌲", "orc": {"name": "Woodcutter"}, "type": "forest"},
              {"id": "dump", "title": "Scrolls", "icon": "🗑️", "orc": {"name": "Scroll Scrapper"}, "type": "scrolls"}):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "woods", "files.selected")
    ts.subscribe(app.scroll, "town_hall", "dump", "knowledge.chunks")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        forest = app.desktop.get_window("woods").query_one(FilesView)
        forest.pick(fake_repo / "src" / "app.py")
        assert (sent[-1].kind, sent[-1].mode, sent[-1].value) == ("file", "files.selected", "src/app.py")
        assert "🎯 app.py" in forest.mini_status()

        dump = app.desktop.get_window("dump").query_one(KnowledgeView)
        app.deliver_payload("dump", pipes.Payload(pipes.TEXT, "what is the rollback plan?", "loot", "pit.text", "q"),
                            "q", "what is the rollback plan?")
        [chunks] = [p for p in sent if p.mode == "knowledge.chunks"]
        assert "§ Rollback" in chunks.value and "Onboarding" not in chunks.value
        app.desktop.focus_window(app.desktop.get_window("dump"))
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"onboarding", "enter")
        await pilot.pause()
        assert dump.last_query == "onboarding" and "§ Onboarding" in sent[-1].value
