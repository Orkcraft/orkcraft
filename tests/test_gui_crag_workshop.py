"""🪨 Tally Crag and 🛠 Workshop in the GUI (docs/design/building-views.md §3, track B6): their workers,
what each of the three views gets, and their acts."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import catalog, checkpoint, metrics, pipes, workshop

NOW = dt.datetime(2026, 10, 5, 12, 0)


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id) or {      # a Workshop is only made from scratch
        "id": type_id, "type": type_id, "title": "Workshop", "icon": "🛠️", "orc": {"name": "Tinker"}}
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    return built.id


def test_a_chart_line_reads_back_as_it_was_written():
    c, why = metrics.parse_chart("Spend today = spend 1h warn 1 crit 5 command")
    assert why == "" and (c.title, c.source, c.window, c.warn, c.crit, c.show) == ("Spend today", "spend", "1h", 1, 5, "command")
    assert metrics.parse_chart(metrics.chart_line(c))[0] == c
    assert metrics.parse_chart("cpu horizontal full")[0].shows_in("full")
    assert not metrics.parse_chart("cpu full")[0].shows_in("command")
    assert metrics.parse_chart("orcs")[0].name == "busy orks"                  # what a person reads
    assert metrics.parse_chart("weather 1h")[1] and metrics.parse_chart("cpu sometimes")[1]
    spec = {"id": "c", "type": "crag", "config": {"charts": ["spend 24h all", "cpu soon"]}}
    assert any("charts" in e for e in catalog.validate(spec))


def test_the_crag_is_a_dashboard_each_chart_where_it_shows(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    bid = _raised(host, "crag", charts=["Spend = spend 24h warn 1 crit 5 all", "Runs = runs 24h command",
                                        "Load = cpu 1h horizontal full"])
    w = host.town.worker(bid)
    sent = []
    host.town.emit_typed = lambda b, ev, value, title="", *a: sent.append((ev, value)) or True
    metrics.record_run(fake_repo, "camp", "done", 1.5, 1000)
    w.refresh()
    assert sent and sent[0][0] == "charts.threshold" and "warning" in sent[0][1]
    w.refresh()
    assert len(sent) == 1                                              # once per climb
    assert w.crossings()[0]["chart"] == "Spend" and w.crossings()[0]["level"] == "warning"

    snap = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)
    assert snap["page"] and [c["title"] for c in snap["card"]["charts"]] == ["Spend"]        # closed: all only
    assert "now" not in snap["card"]["charts"][0] and snap["card"]["charts"][0]["level"] == 1
    assert snap["card"]["last"]["chart"] == "Spend" and snap["card"]["last"]["level"] == "warning"
    data = host.detail(bid)["data"]
    assert [c["show"] for c in data["charts"]] == ["all", "command", "full"]
    assert data["charts"][0]["now"] == 1.5 and data["crossings"] and data["errors"] == []
    assert [p["id"] for p in host.detail(bid)["ui"]["panes"] if "id" in p] == ["head", "charts", "crossings"]

    # command: Next brings the next chart shown there to the front, Flip turns it over (the quick actions)
    assert data["front"] == 0
    host.command("building.quick", {"id": bid, "action": "crag.next"})
    assert host.detail(bid)["data"]["front"] == 1
    host.command("building.quick", {"id": bid, "action": "crag.next"})
    assert host.detail(bid)["data"]["front"] == 0                     # `full only` is never in front
    host.command("building.quick", {"id": bid, "action": "crag.flip"})
    assert host.detail(bid)["data"]["charts"][0]["orientation"] == "horizontal"

    # full: where a chart shows, the window over every chart
    host.command("act", {"id": bid, "act": "show", "args": {"chart": 2, "show": "all"}})
    assert host.town.custom_specs[bid]["config"]["charts"][2].endswith(" all")
    assert host.command("act", {"id": bid, "act": "window", "args": {"window": "7d"}}) == "7d"
    assert {c["window"] for c in host.detail(bid)["data"]["charts"]} == {"7d"}
    for bad in ({"chart": 9, "show": "all"}, {"chart": 0, "show": "nowhere"}):
        with pytest.raises(CommandError):
            host.command("act", {"id": bid, "act": "show", "args": bad})
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "window", "args": {"window": "1y"}})


def test_an_old_crag_keeps_its_one_chart_and_next_charts_the_next_source(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    bid = _raised(host, "crag", source="spend")
    w = host.town.worker(bid)
    assert [c.source for c in w.charts()] == ["spend"] and w.mini_status() == ["spend $0.00"]
    host.command("building.quick", {"id": bid, "action": "crag.next"})
    assert host.town.custom_specs[bid]["config"]["source"] == "tokens"
    w.receive(pipes.Payload(pipes.TEXT, "temperature 21.5", "pit", "pit.text"), "", "")
    assert json.loads((w.state_dir / "samples.jsonl").read_text().splitlines()[-1])["value"] == 21.5


def _workshop(host: Host, repo: Path, **config) -> str:
    bid = _raised(host, "workshop", runtime="python", layout="card", **config)
    workshop.save_script(repo, bid, "python", "import json, sys\ncart = json.load(sys.stdin)\n"
                         "if not cart['value']:\n    sys.exit(4)\n"
                         "print(json.dumps({'words': len(cart['value'].split())}))\n")
    workshop.save_blueprint(repo, bid, {"mocks": [workshop.cart("pit.text", "pit", "a b"),
                                                  workshop.cart("pit.text", "pit", "")]})
    return bid


def _wait(fn, s: float = 10.0) -> bool:
    end = time.monotonic() + s
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(0.05)
    return False


def test_the_workshop_runs_tests_and_shows_its_runs(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    bid = _workshop(host, fake_repo, schedule="every 15m")
    w = host.town.worker(bid)
    with pytest.raises(CommandError):                          # no cart yet
        host.command("building.quick", {"id": bid, "action": "workshop.run"})
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card == {"running": False, "mark": "", "outcome": "", "at": "", "schedule": "every 15m", "said": "", "runs": 0}

    host.town.deliver(bid, pipes.Payload(pipes.TEXT, "red green blue", "pit", "pit.text"), "", "")
    assert _wait(lambda: bool(w.runs) and not w.running)
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card["mark"] == "✓" and card["outcome"] == "done" and '"words": 3' in card["said"] and card["runs"] == 1
    data = host.detail(bid)["data"]
    run = data["runs"][0]
    assert run["sent"] == "workshop.done" and run["code"] == 0 and run["input"] == "red green blue"
    assert run["shape"] == {"kind": "card", "fields": [["words", "3"]]}
    assert data["script"] == f".orkcraft/scripts/{bid}/main.py" and data["has_cart"]

    assert host.command("building.quick", {"id": bid, "action": "workshop.run"})
    assert _wait(lambda: len(w.runs) == 2 and not w.running)
    assert host.command("building.quick", {"id": bid, "action": "workshop.test"}) == {"passed": 2, "total": 2}
    data = host.detail(bid)["data"]
    assert [r["outcome"] for r in data["tests"]] == ["done", "alert"] and data["tested_at"]
    assert all(r["sent"] == "" for r in data["tests"])                  # a test sends nothing


def test_a_workshop_script_is_checked_before_it_is_kept(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    bid = _workshop(host, fake_repo)
    w = host.town.worker(bid)
    assert "line" in w.save_script("def broken(:\n")
    assert w.save_script("print('ok')\n") == "" and w.source() == "print('ok')\n"
    w.last_tick = NOW
    assert not w.tick(NOW + dt.timedelta(minutes=30))                  # no schedule: never by itself
