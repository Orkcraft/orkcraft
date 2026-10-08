"""🪨 Tally Crag and 📦 Loot Vault (T1107 stage 8): bars, sources, thresholds, the stored ledger."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, metrics, pipes, roads, vault
from orkcraft.screens.typed.crag_view import CragView
from orkcraft.screens.typed.generator_view import GeneratorView
from orkcraft.widgets import bars

NOW = dt.datetime(2026, 10, 2, 12, 0)


def test_bars():
    assert bars.vbars([0, 4, 8], height=2).plain.splitlines() == ["  █", " ██"]
    assert bars.vbars([0, 1, 8], height=1).plain == " ▁█"
    h = bars.hbars([("claude", 50.0), ("agy", 100.0)], width=30, scale=100).plain.splitlines()
    assert h[0].startswith("claude") and h[0].endswith(" 50") and h[1].count("█") == 2 * h[0].count("█")
    assert len(bars.vbars(list(range(40)), 3, 10).plain.splitlines()[0]) == 10      # merged to the width
    assert bars.fmt(1234) == "1.2k" and bars.fmt(0.123) == "0.12" and bars.fmt(None) == "—"
    red = bars.hbars([("x", 90.0)], 30, 100, warn=50, crit=80)
    assert any(span.style == "bold red" for span in red.spans)


def test_metrics_sources(tmp_path: Path):
    repo, state = tmp_path, tmp_path / ".orkcraft" / "crag" / "c"
    for h, b, cost, out in ((9, "camp", 0.5, "done"), (10, "camp", 0.25, "error"), (11, "council", 1.0, "done"),
                            (1, "old", 9.0, "done")):
        when = NOW.replace(hour=h) if b != "old" else NOW - dt.timedelta(days=3)
        metrics.record_run(repo, b, out, cost, 1000, now=when)
    s = metrics.series("spend", repo, state, "24h", NOW)
    assert s.now == 1.75 and s.parts[0] == ("council", 1.0) and len(s.buckets) == 24
    assert dict(s.parts)["camp"] == 0.75 and "old" not in dict(s.parts)
    assert metrics.series("runs", repo, state, "24h", NOW).note == "2 ✓ · 1 ✗"
    assert metrics.series("spend", repo, state, "7d", NOW).now == 10.75
    metrics.sample(state, "limits", 40, "claude 5h", now=NOW - dt.timedelta(minutes=30))
    metrics.sample(state, "limits", 72, "claude 5h", now=NOW)
    metrics.sample(state, "limits", 10, "agy day", now=NOW)
    lim = metrics.series("limits", repo, state, "1h", NOW)
    assert lim.scale == 100 and lim.parts == [("agy day", 10.0), ("claude 5h", 72.0)] and lim.now == 72
    for m, v in ((50, 0.5), (55, 1.5), (59, 1.0)):
        metrics.sample(state, "cpu", v, now=NOW.replace(hour=11, minute=m))
    cpu = metrics.series("cpu", repo, state, "1h", NOW)
    assert cpu.parts == [("now", 1.0), ("avg", 1.0), ("max", 1.5)]
    assert metrics.series("tasks", repo, state, tasks={"To Do": 3, "Done": 1}).now == 4
    assert metrics.first_number("build took 12,5 s") == 12.5 and metrics.first_number("none") is None


def test_vault_store(fake_repo: Path):
    state = fake_repo / ".orkcraft" / "loot" / "vault"
    trail = (pipes.hop("camp", "grub", "agent", 12000, 0.08, now=NOW), pipes.hop("council", "", "agent", 40000, 0.16, now=NOW))
    item = vault.store(fake_repo, "vault", state, "text", "run ./deploy.sh $1 prod", "Release plan", "council", NOW,
                       trail=trail, ref="T-7")
    assert item.path == "loot/vault/20261002-120000-release-plan.md"
    assert (item.cost, item.tokens, item.ref) == (0.24, 52000, "T-7")      # the trail's, not the `$1` in the text
    assert "_from council · 2026-10-02 12:00_" in (fake_repo / item.path).read_text()
    f = vault.store(fake_repo, "vault", state, "file", "README.md", "", "pit", NOW)
    assert (f.path, f.title, f.cost) == ("README.md", "README.md", None) and f.bytes > 0
    assert [x.path for x in vault.stored(state)] == ["README.md", item.path]
    assert vault.stored(state)[1].hops == trail
    assert vault.store(fake_repo, "vault", state, "text", "costs $5", "Copy", "pit", NOW).cost is None


@pytest.mark.asyncio
async def test_the_crag_carves_and_warns_and_the_vault_keeps(fake_repo: Path, monkeypatch):
    for s in ({"id": "crag", "title": "Crag", "icon": "🪨", "orc": {"name": "Crag Carver"}, "type": "crag",
               "config": {"source": "spend", "warn": 1.0, "crit": 5.0}},
              {"id": "vault", "title": "Vault", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot"}):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "crag", "charts.threshold")
    ts.subscribe(app.scroll, "town_hall", "vault", "loot.stored")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        crag = app.desktop.get_window("crag").query_one(CragView)
        assert crag.mini_status()[0] == "spend 0 $"
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.on_handler_run(roads.HandlerRun("camp", "grub", "agent", "r1", 0, 0, outcome="done", cost_usd=1.5))
        crag.refresh_data()
        assert crag.series.now == 1.5 and [p.mode for p in sent] == ["charts.threshold"]
        assert "warning" in sent[-1].value
        crag.refresh_data()
        assert len(sent) == 1                                          # once per climb, not every look
        assert crag.quick_action("crag.flip") and app.custom_specs["crag"]["config"]["orientation"] == "horizontal"
        assert crag.quick_action("crag.next") and crag.source == "tokens"
        crag.sample()
        assert (crag.state_dir / "samples.jsonl").exists()

        vault_view = app.desktop.get_window("vault").query_one(GeneratorView)
        hop = pipes.hop("council", "chief", "agent", 3000, 0.30)
        app.deliver_payload("vault", pipes.Payload(pipes.TEXT, "the decision", "council", "team.artifact_ready",
                                                   "Release plan", (hop,), "R-1"), "Release plan", "the decision")
        stored = [p for p in sent if p.mode == "loot.stored"]
        assert stored and stored[0].value.startswith("loot/vault/") and (fake_repo / stored[0].value).exists()
        assert (stored[0].trail, stored[0].ref) == ((hop,), "R-1")         # the chain travels on
        assert vault_view.stored[0].cost == 0.30 and vault_view.stored[0].tokens == 3000
        assert "📦 1 stored" in vault_view.mini_status()


def test_money_is_written_as_the_hud_writes_it():
    """Metrics wrote "0 $" beside the HUD's "$0.00" (ui.md U21)."""
    from orkcraft.core.workers.crag import with_unit
    assert with_unit(0, "$") == "$0.00" and with_unit(12.5, "$") == "$12.50"
    assert with_unit(3, "tasks") == "3 tasks" and with_unit(None, "$") == "$—" and with_unit(1500, "") == "1.5k"
