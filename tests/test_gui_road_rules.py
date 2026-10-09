"""The steward's road rules in the GUI (docs/design/steward-listens.md stage 3): listed under the steward and
never drawn as orks, a rule's own panel, the listen tier with its spend, and *Hand to the steward*."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, roads, tiers


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _with_rule(host: Host) -> tuple[str, str]:
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    ts.add_handler(host.town.scroll, fields, "Boss's mail", kind="steward", orders="Only my boss's mail; one to-do each.")
    ts.subscribe(host.town.scroll, fields, tower, "mail.received", handler="boss_s_mail")
    path = roads.examples_file(host.town.repo_root, fields, "boss_s_mail")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"ts": f"2026-10-07T0{n}:00:00", "inputs": [], "output": f"letter {n}",
                                        "cost_usd": 0.02}) + "\n" for n in range(3)))
    host.refresh_roster()
    return fields, f"{fields}/boss_s_mail"


def test_rules_are_listed_under_the_steward_and_not_drawn_as_orks(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    fields, ref = _with_rule(host)
    b = next(x for x in host.snapshot()["buildings"] if x["id"] == fields)
    assert ref not in [o["ref"] for o in b["garrison"]] and b["rules"] == [{"ref": ref, "name": "Boss's mail", "status": "idle"}]
    info = host.command("info", {"id": fields})
    json.dumps(info)
    [rule] = info["rules"]
    assert rule["name"] == "Boss's mail" and rule["runs"] == 3 and rule["spend"].startswith("🪙 $0.06")
    assert "External listeners" in rule["roads"][0] or "mail" in rule["roads"][0]
    assert ref not in [h["ref"] for h in info["others"]]
    listen = next(u for u in info["steward"]["uses"] if u["id"] == "listen")
    assert listen["work"] and listen["by_goal"] and "$0.06" in listen["spend"]
    road = next(l for l in info["listens"] if l["by"])
    assert road["by"]["kind_label"] == "road rule" and road["by"]["tier"] == "warrior"      # balance: the middle


def test_a_rules_panel_says_its_words_roads_and_runs_and_its_words_change(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    fields, ref = _with_rule(host)
    panel = host.command("info", {"id": fields, "ork": ref})
    assert panel["rule"] and panel["orders"].startswith("Only my boss's mail") and panel["roads"]
    assert [r["output"] for r in panel["recent"]][0] == "letter 2" and "Seasoned" in panel["tier"]
    host.command("ork.orders", {"id": fields, "ork": ref, "orders": "Only the boss; with the deadline."})
    assert host.town.scroll.building(fields).garrison.handler("boss_s_mail").orders == "Only the boss; with the deadline."
    assert panel["own_tier"] == "" and [t for t, _ in panel["tiers"]][-1] == ""
    host.command("ork.orders", {"id": fields, "ork": ref, "orders": "Only the boss.", "tier": "elder"})
    assert host.town.scroll.building(fields).garrison.handler("boss_s_mail").tier == "elder"
    panel = host.command("info", {"id": fields, "ork": ref})
    assert panel["own_tier"] == "elder" and "Veteran" in panel["tier"]                  # the rule's own, over listen's
    host.command("ork.orders", {"id": fields, "ork": ref, "orders": "Only the boss.", "tier": "no such tier"})
    assert host.town.scroll.building(fields).garrison.handler("boss_s_mail").tier == ""


def test_hand_an_agent_to_the_steward_says_what_changes_and_revert_takes_it_back(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    host.town.demo = False
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    b = host.town.scroll.building(fields)
    b.garrison.steward.harness = [{"role": "run", "harness": "claude"}]
    ts.add_handler(host.town.scroll, fields, "Mailman", orders="Summarise each letter.",
                   harness=[{"role": "run", "harness": "claude", "tier": "elder"}])
    ts.subscribe(host.town.scroll, fields, tower, "mail.received", handler="mailman")
    path = roads.examples_file(host.town.repo_root, fields, "mailman")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"inputs": [], "output": "x", "cost_usd": 0.05}) + "\n")
    host.refresh_roster()
    host.town.checkpoint("update", fields, "the mailman")
    ref = f"{fields}/mailman"
    view = host.command("ork.hand", {"id": fields, "ork": ref, "preview": True})
    assert view["tools_now"] == view["tools_then"] == "Claude Code"
    assert "Veteran" in view["tier_now"] and "Seasoned" in view["tier_then"]
    assert view["per_run_now"] == "$0.050" and view["per_run_then"] == "≈ $0.030"
    assert host.town.scroll.building(fields).garrison.handler("mailman").kind == "agent"     # a preview changes nothing
    assert host.command("ork.hand", {"id": fields, "ork": ref}) == ref
    rule = host.town.scroll.building(fields).garrison.handler("mailman")
    assert (rule.kind, rule.harness, rule.orders) == ("steward", [], "Summarise each letter.")
    assert [r.handler for r in host.town.scroll.building(fields).roads] == ["mailman"]       # its roads stay
    with pytest.raises(CommandError):
        host.command("ork.hand", {"id": fields, "ork": ref})                                # only an agent
    assert host.command("building.revert", {"id": fields}) is True
    back = host.town.scroll.building(fields).garrison.handler("mailman")
    assert back.kind == "agent" and back.harness[0]["tier"] == "elder"
    assert tiers.TIERS


def _report_with_script(host: Host, fields: str, source: str) -> str:
    from orkcraft.realm import steward
    path = roads.examples_file(host.town.repo_root, fields, "boss_s_mail")
    path.write_text("".join(json.dumps({"inputs": [{"id": f"T{n}", "title": f"letter {n}"}], "output": f"To-do: letter {n}",
                                        "cost_usd": 0.02}) + "\n" for n in range(5)))
    report = steward.StewardReport(fields, steward.collect(host.town.repo_root, host.town.scroll, fields, sessions=[]))
    report.proposals = [steward.Proposal("demote", "string work", {"orc": "boss_s_mail", "script": source, "reviewed": False})]
    steward.save_report(host.town.repo_root, report)
    return host.command("ork.report", {"id": fields})


def _settled(host: Host, jid: str) -> dict:
    import time
    for _ in range(100):
        job = host.console.jobs.get(jid)
        if job is None or job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("still running")


def test_a_script_the_steward_wrote_replaces_the_rule_only_after_the_council_and_its_replay(fake_repo, isolated_layout_file,
                                                                                          monkeypatch):
    from orkcraft.core import runners
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda p: ("{}", 0.0))
    host = _host(fake_repo)
    fields, ref = _with_rule(host)
    good = "import json, sys\nfor r in json.load(sys.stdin):\n    print(f\"To-do: {r['title']}\")\n"
    jid = _report_with_script(host, fields, good)
    view = host.console.jobs[jid]["view"]["proposals"][0]
    assert view["ready"] and "Council" in view["replay"] and view["script"].startswith("import json")
    rule = host.town.scroll.building(fields).garrison.handler("boss_s_mail")
    host.command("job.accept", {"job": jid, "index": 0})
    job = _settled(host, jid)
    assert rule.kind == "script" and rule.script["reviewed"] is True and rule.orders.startswith("Only my boss")
    assert (fake_repo / rule.script["path"]).read_text() == good
    assert job["view"]["proposals"][0]["applied"] == "Boss's mail turned into a script"

    rule.kind, rule.script, rule.harness = "steward", None, []                       # again, with a script that disagrees
    jid = _report_with_script(host, fields, "print('nothing')\n")
    host.command("job.accept", {"job": jid, "index": 0})
    job = _settled(host, jid)
    assert "the rule stays" in job["view"]["proposals"][0]["replay"] and rule.kind == "steward"
