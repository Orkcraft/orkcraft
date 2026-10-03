"""🌲 File Forest picks a target, 🗑️ Scroll Dump hands a task its wiki (T1107 stage 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes
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

        assert app.desktop.get_window("dump").query_one(KnowledgeView).status() == "NO WIKI"
        (fake_repo / "llm-wiki").mkdir()
        (fake_repo / "llm-wiki" / "index.md").write_text("# Index\n\n- [Rollback](pages/rollback.md) — how to undo a release\n")
        app.deliver_payload("dump", pipes.Payload(pipes.TEXT, "what is the rollback plan?", "loot", "pit.text", "q"),
                            "q", "what is the rollback plan?")
        [ctx] = [p for p in sent if p.mode == "knowledge.chunks"]
        assert "`llm-wiki/`" in ctx.value and "pages/rollback.md" in ctx.value and "rollback plan" in ctx.value
