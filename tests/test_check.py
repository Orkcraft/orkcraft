"""`orkcraft check` (realm/check.py, check_cli.py, gui/idle_check.py): the main jobs against a budget, and a quiet
town that calls no model. AI tools are faked."""
from __future__ import annotations

import json

from orkcraft import cli
from orkcraft.core import bench as building_bench
from orkcraft.realm import bench, check


def _r(b: tuple, t: tuple, case: str = "c", n: int = 0, cut: bool = False) -> bench.Report:
    side = lambda name, x: bench.Side(name, seconds=x[0], cost=x[1], passed=x[2])  # noqa: E731
    r = bench.Report(f"2026101{n}-000000-x-{case}", "watchtower", case, building=side("building", b),
                     bare=side("bare", t), series="s")
    r.building.cut = cut
    return r


def test_a_case_passes_in_most_runs_no_worse_and_within_the_budget():
    budget = dict(check.DEFAULTS)
    ok = check.judge([_r((10, 0.1, True), (10, 0.1, True), n=n) for n in range(3)], budget)
    assert ok["ok"] and ok["runs"] == 3 and ok["building"] == 3 and ok["why"] == ""
    one_fail = check.judge([_r((10, 0.1, n != 1), (10, 0.1, True), n=n) for n in range(3)], budget)
    assert not one_fail["ok"] and "worse than the bare AI tool" in one_fail["why"]        # 2/3 against 3/3
    both = check.judge([_r((10, 0.1, n != 1), (10, 0.1, n != 1), n=n) for n in range(3)], budget)
    assert both["ok"]                                                                        # 2 of 3: enough
    slow = check.judge([_r((20, 0.2, True), (10, 0.1, True), n=n) for n in range(3)], budget)
    assert "time +100%" in slow["why"] and "spend +100%" in slow["why"]
    cut = check.judge([_r((10, 0.1, True), (10, 0.1, True), n=0, cut=True)], budget)
    assert "cut at the spend or time limit" in cut["why"]
    assert not check.judge([], budget)["ok"]


def test_the_budget_may_be_set_per_town(tmp_path):
    (tmp_path / check.DIR).mkdir(parents=True)
    (tmp_path / check.DIR / "budgets.json").write_text(json.dumps({"time_over": 1.0, "nonsense": 5}))
    got = check.budgets(tmp_path)
    assert got["time_over"] == 1.0 and "nonsense" not in got and got["repeat"] == 3


def test_the_report_is_green_only_when_every_case_and_idle_are():
    budget = dict(check.DEFAULTS)
    good = check.judge([_r((10, 0.1, True), (10, 0.1, True))], budget)
    mail, wiki = check.SCENARIOS[0], next(s for s in check.SCENARIOS if s.id == "wiki")
    green, text = check.report([{"scenario": mail, "cases": [("on-call", good)]}, {"scenario": wiki, "cases": []}],
                               {"calls": 0, "hours": 8, "by": []}, budget)
    assert green and "**GREEN**" in text and "on-call" in text and "not checked" in text
    red, text = check.report([{"scenario": mail, "cases": [("on-call", good)]}],
                             {"calls": 2, "hours": 8, "by": [["runner · OPTIMIZE_RUNNER", 2]]}, budget)
    assert not red and "**RED**" in text and "2 × runner · OPTIMIZE_RUNNER" in text


def test_the_shipped_cases_of_every_scenario_are_there(tmp_path):
    from orkcraft.design import tokens
    from orkcraft.realm import check_pictures
    for s in check.SCENARIOS:
        for cid in s.cases:
            if s.type == check.PICTURE:
                case = next(c for c in check_pictures.CASES if c["id"] == cid)
                assert (tokens.SYSTEM / case["path"]).is_file(), case
            else:
                assert bench.case(tmp_path, s.type, cid) is not None, (s.id, cid)
    assert check.DEFAULTS["tool"] == "agy" and check.DEFAULTS["tier"] == "novice"        # the cheap one


def test_cli_runs_each_case_its_times_keeps_the_report_and_says_red_or_green(fake_repo, capsys, monkeypatch):
    calls = []

    def run(root, case, tool, tier, building, max_spend, *a, attempt=0, series="", **k):
        calls.append((case.type, case.id, attempt, series))
        r = _r((10, 0.1, case.id != "planted-flaws"), (10, 0.1, True), case.id, attempt)
        return r, root

    monkeypatch.setattr(building_bench, "run", run)
    from orkcraft.gui import idle_check
    monkeypatch.setattr(idle_check, "count", lambda ticks: {"calls": 0, "hours": ticks / 60, "by": []})
    assert cli.main(["--repo", str(fake_repo), "check", "--scenario", "mail", "--repeat", "2"]) == 0
    assert [c[:3] for c in calls[:2]] == [("watchtower", "customer-orders", 0), ("watchtower", "customer-orders", 1)]
    assert len(calls) == 6 and len({c[3] for c in calls}) == 1
    out = capsys.readouterr().out
    assert "**GREEN**" in out and "0 model calls in 8.0 hours" in out and "on agy (novice)" in out
    from orkcraft import check_cli
    folder = check_cli.latest(fake_repo)
    assert "**GREEN**" in (folder / "report.md").read_text() and "How to work through it" in (folder / "README.md").read_text()
    assert (folder / "runs/mail/on-call/run-2/analysis.md").is_file() and (folder / "idle.json").is_file()
    import zipfile
    names = zipfile.ZipFile(folder / "check.zip").namelist()
    assert "README.md" in names and "runs/mail/sales-leads/run-1/report.json" in names
    calls.clear()
    assert cli.main(["--repo", str(fake_repo), "check", "--scenario", "board", "--repeat", "1",
                     "--only", "scenarios"]) == 1                                  # its planted flaws were missed
    assert "**RED**" in capsys.readouterr().out
    assert cli.main(["--repo", str(fake_repo), "check", "--scenario", "nope"]) == 2
    assert cli.main(["--repo", str(fake_repo), "check", "--list"]) == 0 and not calls[2:]


def test_a_quiet_town_calls_no_model():
    from orkcraft.gui import idle_check
    got = idle_check.count(30)
    assert got["calls"] == 0 and got["hours"] == 0.5


def _png(w: int, h: int, fill: bytes = b"") -> bytes:
    import struct
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", w, h) + fill


def test_a_picture_passes_when_redrawn_at_its_size_and_judged_well(tmp_path):
    from orkcraft.realm import check_pictures, painter
    case = check_pictures.CASES[0]
    ref = check_pictures.size(_system(case["path"]).read_bytes())

    def painted(size, same=False):
        def runner(tool, prompt, folder, cancel, model):
            data = (folder / "reference.png").read_bytes() if same else _png(*size, b"new")
            (folder / painter.OUT).write_bytes(data)
            return "done", 0.0, 0, ""
        return runner

    judge = lambda p, w: '{"score": 8, "notes": "red roof, same style"}' if (w / "out.png").is_file() else "{}"   # noqa: E731
    good = check_pictures.run(case, "agy", "", tmp_path / "a", runner=painted(ref), judge=judge)
    assert check_pictures.passed(good, 6) and good["score"] == 8 and (tmp_path / "a" / "judge.json").is_file()
    twice = check_pictures.run(case, "agy", "", tmp_path / "b", runner=painted((ref[0] * 2, ref[1] * 2)), judge=judge)
    assert check_pictures.passed(twice, 6)
    wrong = check_pictures.run(case, "agy", "", tmp_path / "c", runner=painted((7, 7)), judge=judge)
    assert not wrong["size_ok"] and not check_pictures.passed(wrong, 6)
    same = check_pictures.run(case, "agy", "", tmp_path / "d", runner=painted(ref, same=True), judge=judge)
    assert not same["changed"]
    none = check_pictures.run(case, "agy", "", tmp_path / "e", runner=lambda *a: ("", 0.0, 0, ""), judge=judge)
    assert "made no picture" in none["error"]
    j = check.judge_pictures([good, good, wrong], dict(check.DEFAULTS))
    assert j["ok"] and j["building"] == 2
    j = check.judge_pictures([good, wrong, none], dict(check.DEFAULTS))
    assert not j["ok"] and "passed 1 of 3" in j["why"]


def _system(path):
    from orkcraft.design import tokens
    return tokens.SYSTEM / path


def test_the_test_bench_runs_the_check_and_serves_its_folder(fake_repo, isolated_layout_file, monkeypatch):
    import io
    import subprocess
    import time
    import urllib.request
    import zipfile
    from orkcraft.gui import check_runs
    from orkcraft.gui.host import Host
    from orkcraft.gui.server import Server
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    try:
        lab = host.command("town.build", {"type": "lab"})
        host.detail(lab)
        assert host.detail(lab)["data"]["check"]["last"] == {}
        seen = {}
        real = subprocess.Popen

        def popen(argv, **kw):
            seen["argv"] = argv
            folder = fake_repo / check.DIR / "20261011-120000"
            folder.mkdir(parents=True)
            (folder / "results.json").write_text('{"green": false}')
            (folder / "report.md").write_text("# Orkcraft check\n\n**RED**\n")
            with zipfile.ZipFile(folder / "check.zip", "w") as z:
                z.writestr("README.md", "read me first")
            (fake_repo / check.DIR / "latest.txt").write_text("20261011-120000")
            return real(["sh", "-c", "echo 'Mail sorted · run 1'; exit 1"], **kw)    # red is not a failure

        monkeypatch.setattr(check_runs.subprocess, "Popen", popen)
        host.command("act", {"id": lab, "act": "check_run", "args": {}})
        assert seen["argv"][-1] == "check"
        for _ in range(100):
            c = host.detail(lab)["data"]["check"]
            if c["job"]["done"]:
                break
            time.sleep(0.05)
        assert c["job"]["lines"] == ["Mail sorted · run 1"] and not c["job"]["error"]
        assert c["last"]["stamp"] == "20261011-120000" and c["last"]["green"] is False and "**RED**" in c["last"]["report"]
        assert c["last"]["told"] == {"scenarios": [], "changes": []}
        server = Server(host)
        server.start_thread()
        try:
            with urllib.request.urlopen(f"{server.origin}/api/check/latest?t={server.token}", timeout=5) as r:
                assert "orkcraft-check-20261011-120000.zip" in r.headers["Content-Disposition"]
                assert zipfile.ZipFile(io.BytesIO(r.read())).read("README.md") == b"read me first"
        finally:
            server.stop()
    finally:
        host.close()
