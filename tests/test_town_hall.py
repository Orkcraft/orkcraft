"""🏰 Town Hall (T1105 stage 4): the audit's rules, the hall on every canvas, its tabs."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import audit, masonry
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.town_hall import TownHallView

SIZE = (200, 46)

MAIL = {"id": "inbox", "title": "Inbox", "icon": "📬", "orc": {"name": "Courier"}, "type": "mail",
        "config": {"host": "imap.example.com", "user_env": "MAIL_USER", "password_env": "hunter2-plain"}}


def _app(fake_repo: Path) -> OrkcraftApp:
    assert masonry.save_spec(fake_repo, MAIL) == []
    return OrkcraftApp(repo_root=fake_repo, auto_commit=False)


def test_audit_flags_secrets_lonely_buildings_and_spend(fake_repo: Path):
    app = _app(fake_repo)
    report = audit.run(fake_repo, app.scroll, dict(app.custom_specs), spent_usd=19.0, limit_usd=20.0)
    warder = report.of("warder")
    assert any("password_env" in f.text and f.severity == "high" and f.building == "inbox" for f in warder)
    if "inbox" in {b.id for b in app.scroll.buildings_in(app.scroll.active_orkspace_id)}:
        assert any(f.building == "inbox" for f in report.of("pathfinder"))
    assert any("$19.00" in f.text and f.severity == "warn" for f in report.of("treasurer"))
    assert not any(f.building == TOWN_HALL for f in report.findings)
    audit.save(fake_repo, report)
    again = audit.load(fake_repo)
    assert again is not None and again.summary() == report.summary()
    assert "### 🛡 Warder" in report.markdown()


def test_an_env_var_name_is_not_a_secret(fake_repo: Path):
    spec = dict(MAIL, config={"host": "imap.example.com", "user_env": "MAIL_USER", "password_env": "MAIL_PASSWORD"})
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    assert not audit._security(fake_repo, {"inbox": spec})
    assert audit._security(fake_repo, {"inbox": dict(spec, config={"note": "sk-" + "a" * 24})})
    script = {"id": "s", "title": "Sweeper", "type": "agent", "config": {"harness": "script", "skill": "make clean"}}
    camp = {"id": "c", "title": "Camp", "type": "pool", "config": {"worktrees": False}}
    found = audit._security(fake_repo, {"s": script, "c": camp})
    assert any("make clean" in f.text for f in found) and any(f.severity == "warn" and "share" in f.text for f in found)
    forge = {"id": "f", "title": "Forge", "type": "forge", "config": {}}
    assert any("without tests" in f.text for f in audit._security(fake_repo, {"f": forge}))
    assert not audit._security(fake_repo, {"f": dict(forge, config={"test_cmd": "pytest -q"})})
    assert app.scroll is not None


@pytest.mark.asyncio
async def test_the_hall_has_sessions_and_limits_tabs_and_shows_the_audit(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        for _ in range(3):
            await pilot.pause()
        view = app.desktop.get_window(TOWN_HALL).query_one(TownHallView)
        await pilot.press(str(app.desktop.get_window(TOWN_HALL).number))   # opening it lands on the Hall,
        await pilot.pause()                                                  # not on a list in a hidden tab
        assert view.query_one("#hall-tabs").active == "hall-tab-hall"
        assert view.query_one("#chat-view") is app._sessions_window().query_one("#chat-view")
        assert view.query_one("#hall-tabs").active == "hall-tab-sessions"     # asking for sessions shows them
        assert view.query_one("#limits-view")
        assert "not audited yet" in str(view.query_one("#hall-body").render())
        view.show_tab("limits")
        app.run_audit()
        await pilot.pause()
        assert view.query_one("#hall-tabs").active == "hall-tab-hall"      # the audit brings its tab up
        assert "Last audit" in str(view.query_one("#hall-body").render())
        assert (fake_repo / ".orkcraft" / "audit" / "latest.json").exists()


@pytest.mark.asyncio
async def test_the_hall_cannot_be_demolished_and_stands_on_every_canvas(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        lab = ts.new_orkspace(app.scroll, "Lab", "ice")
        app.desktop.switch_orkspace(lab.id)
        await pilot.pause()
        hall = app.desktop.get_window(TOWN_HALL)
        assert app.desktop.in_view(hall) and hall.display
        assert app.scroll.building(TOWN_HALL).demolished is False


@pytest.mark.asyncio
async def test_an_old_scroll_with_chat_and_limits_still_opens(fake_repo: Path, isolated_layout_file: Path):
    import json

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.desktop.save()
    data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    loot = next(b for b in data["buildings"] if b["id"] == "loot")
    for old in ("chat", "limits"):
        b = json.loads(json.dumps(loot))
        b.update(id=old, title=old.title(), preset_ref=f"core:{old}", roads=[])
        data["buildings"].append(b)
        for ork in data["orkspaces"]:
            if "loot" in ork["buildings"]:
                ork["buildings"].append(old)
    isolated_layout_file.write_text(json.dumps(data), encoding="utf-8")

    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert app2.desktop.get_window(TOWN_HALL) is not None
        assert app2.desktop.get_window("loot") is not None
