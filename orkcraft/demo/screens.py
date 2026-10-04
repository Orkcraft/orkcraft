"""Screenshots of the eight showcase orkspaces (orkcraft --demo DIR --demo-screens OUT).

Headless: every canvas gets real events through the road engine (so carts, chain outputs and
the 📥 panes are the real thing). Three shots per canvas in the town view: the map of
huts with carts caught mid-road, the first road selected (its label and card), and the first
road's receiver opened over the map. PNGs are rendered with the pre-installed Chromium when it
is there; SVGs always.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from orkcraft.demo.scenarios import SCENARIOS, SEL, SETS
from orkcraft.realm.pipes import Payload
from orkcraft.widgets.road_layer import road_key

SIZE = (200, 52)
CHROMIUM = [os.environ.get("ORKCRAFT_CHROMIUM", ""), "/opt/pw-browsers/chromium", "chromium", "chromium-browser",
            "google-chrome"]


# What a finished session reports on each "task completed" road (target → text).
TASK_TEXT = {
    "oauth_lab": "patch applied in feat/oauth-flow · 1 failing: test_refresh_reuse_revokes_family",
    "oauth_vault": "review approved · 2 nits resolved",
    "qa_spire": "checkout.spec.ts › promo code AUTUMN25 · expected 200, got 500",
    "qa_vault": "screenshot diff 4.7 % on the pay step · trace.zip attached",
    "arch_wiki": "C4 level 2 exported · ADR-014 status updated",
    "ds_watch": "wireframe step 2 · error state",
    "tk_loot": "Style Dictionary build · 64 tokens → css, tailwind, ts, android",
    "tk_radar": "Button, Input, Card previewed with radius 6",
    "pm_forge": "PRD · One-click export — draft 3 ready",
    "pm_vault": "2 stories · 6 acceptance criteria",
    "dc_board": "feat/oauth-flow blocked: security review 2 d",
    "dc_loot": "week 40 · 6 events · 2 blockers",
    "solo_growth": "shipped feat/stripe-billing · +412 −37 · deploy v1.8.0",
    "solo_sentry": "deploy v1.8.0 → prod · 14:03 POST /api/checkout 500 StripeInvalidRequest",
    "solo_loot": "launch copy published · HN + Product Hunt drafts",
}


def _payload(sc: dict, source: str, target: str, event: str, n: int) -> Payload:
    if (source, event) in sc.get("payloads", {}):          # typed buildings (the dashboard set)
        from orkcraft.demo.dashboard import payload_of
        return payload_of(sc, source, event)
    if event == SEL:
        # the nodes this source building actually lists (its graph_nodes tag / type)
        b = next(x for x in sc["buildings"] if x["id"] == source)
        params = next((d["params"] for d in b["data"] if d["source"] == "graph_nodes"), {})
        mine = [x for x in sc["nodes"] if (x.get("tag") or sc["id"]) == params.get("tag", sc["id"])
                and x["type"] == params.get("type", x["type"])] or sc["nodes"]
        nid = mine[n % len(mine)]["id"]
        return Payload("node", nid, source, event)          # like the desktop: no title, meta fills it
    b = next(x for x in sc["buildings"] if x["id"] == source)
    text = TASK_TEXT.get(target, b["summary"])
    return Payload("text", text, source, event, f"{b['orc']['name']} · task completed")


async def _run(root: Path, out: Path, scenarios: list[dict] = SCENARIOS) -> list[Path]:
    from orkcraft.app import OrkcraftApp

    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=SIZE) as pilot:
        for _ in range(5):
            await pilot.pause()
        app.desktop.traffic_changed = lambda: None          # carts move only when we tick them
        for i, sc in enumerate(scenarios, 1):
            await pilot.press(f"f{i}")
            for _ in range(4):
                await pilot.pause()
            app.desktop.traffic.clear()
            if app.desktop._traffic_timer is not None:
                app.desktop._traffic_timer.pause()
            app.desktop.set_active(None)
            for n in (2, 1, 0):                               # three waves; the last one carries each list's first item
                for target, source, event, *_ in sc["roads"]:
                    app.roads.emit(_payload(sc, source, target, event, n))
                for _ in range(4):
                    app.desktop.traffic.tick()
            agents = [t for t, hs in sc.get("handlers", {}).items() if any(h["kind"] in ("agent", "hybrid") for h in hs)]
            if agents:
                app.desktop.traffic.flash_coin(agents[0])
            app.refresh_roster()
            app.desktop.refresh_huts()
            for _ in range(4):
                await pilot.pause()
            name = f"{i:02d}-{sc['id']}"
            paths.append(Path(app.save_screenshot(filename=f"{name}.svg", path=str(out))))
            target = sc["roads"][0][0]
            road = app.scroll.building(target).roads[0]
            app.select_road(road_key(target, road.id))
            for _ in range(4):
                await pilot.pause()
            paths.append(Path(app.save_screenshot(filename=f"{name}-road.svg", path=str(out))))
            app.set_focus_state("neutral")
            receiver = app.desktop.get_window(target)
            if receiver is not None:                          # the receiver opened, its 📥 pane filled
                app.desktop.focus_window(receiver)
                app.set_focus_state("building", building_id=target)
                for _ in range(4):
                    await pilot.pause()
                paths.append(Path(app.save_screenshot(filename=f"{name}-open.svg", path=str(out))))
            app.desktop.set_active(None)
            app.set_focus_state("neutral")
        if scenarios is SCENARIOS:
            paths += await _features(app, pilot, root, out)
    return paths


async def _until(pilot, cond, tries: int = 60) -> bool:
    for _ in range(tries):
        await pilot.pause(0.05)
        if cond():
            return True
    return False


async def _features(app, pilot, root: Path, out: Path) -> list[Path]:
    """The mechanisms: roster + War Map, Recruiter, Mason & Artisan, steward, Halt All."""
    import orkcraft.app as app_mod
    from orkcraft.demo import features as ft
    from orkcraft.screens.build_flow import BuildPreview
    from orkcraft.screens.orc_flow import RecruitPreview, StewardView

    shots: list[Path] = []

    async def shot(name: str) -> None:
        for _ in range(4):
            await pilot.pause()
        shots.append(Path(app.save_screenshot(filename=f"{name}.svg", path=str(out))))

    saved = (app_mod.RECRUIT_RUNNER, app_mod.BUILD_RUNNER, app_mod.STEWARD_RUNNER)
    try:
        # 1 · every orc of a canvas and which canvases wait for you (❓ on the War Map)
        await pilot.press("f7")
        app.set_focus_state("neutral")
        app.desktop.set_active(None)
        app.refresh_roster()
        await shot("10-roster-and-war-map")

        # 2 · the Recruiter: a description becomes a handler, the cheapest kind, with its reason
        await pilot.press("f1")
        app_mod.RECRUIT_RUNNER = ft.runner_of([ft.RECRUITER_ANSWER])
        app.recruit_from_prompt("oauth_spire", "when I pick a done task in the Forge, show one line: id and title")
        if await _until(pilot, lambda: isinstance(app.screen, RecruitPreview)):
            await shot("11-recruiter-preview")
            await pilot.press("escape")

        # 3 · Mason & Artisan: a window from a prompt, validated as data
        app_mod.BUILD_RUNNER = ft.runner_of([ft.MASON_ANSWER, ft.ARTISAN_ANSWER])
        app._start_build("CI watch: open feature tasks next to the failing tests")
        if await _until(pilot, lambda: isinstance(app.screen, BuildPreview)):
            await shot("12-mason-artisan-preview")
            await pilot.press("escape")

        # 4 · the steward: free metrics find a repetitive agent, the proposed chain is replayed
        ft.seed_steward_examples(root)
        app_mod.STEWARD_RUNNER = ft.runner_of([ft.STEWARD_PROPOSAL])
        await pilot.press("f7")
        app.watch_building("dc_loot", interactive=True)
        if await _until(pilot, lambda: isinstance(app.screen, StewardView)):
            await shot("13-steward-proposal")
            await pilot.press("escape")

        # 5 · Halt All: three running sessions halted at once
        for i in range(3):
            app.chat.deploy("horn", ["sleep", "30"], "claude", f"ork {i + 1}")
        await pilot.pause(0.5)
        app.action_halt()
        await shot("14-halt-all")
    finally:
        app_mod.RECRUIT_RUNNER, app_mod.BUILD_RUNNER, app_mod.STEWARD_RUNNER = saved
    return shots


def _png(svg: Path) -> Path | None:
    exe = next((c for c in CHROMIUM if c and (Path(c).exists() or shutil.which(c))), None)
    if exe is None:
        return None
    png = svg.with_suffix(".png")
    try:
        subprocess.run([exe, "--headless", "--no-sandbox", "--disable-gpu", f"--screenshot={png}",
                        "--window-size=2000,1330", svg.resolve().as_uri()],
                       capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return png if png.exists() else None


def take(root: Path, out: Path, set_name: str = "main") -> list[Path]:
    svgs = asyncio.run(_run(Path(root), Path(out), SETS[set_name]))
    return svgs + [p for p in (_png(s) for s in svgs) if p is not None]
