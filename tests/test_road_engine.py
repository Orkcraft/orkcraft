"""Road engine and chain executor (T1098 stage 2): source filter, snapshots, rerun, restart."""
from __future__ import annotations

import threading
import time

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import chains, roads
from orkcraft.realm.pipes import Payload

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "loot": {"title": "Loot Chest", "icon": "📦", "orc": "Quartermaster", "role": "files", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
}
NODES = {"T1001": {"type": "task", "status": "done", "title": "Ship it"},
         "T1002": {"type": "task", "status": "todo", "title": "Plan it"},
         "C1003": {"type": "context", "subtype": "personal", "title": "Private"}}


def node(nid: str, source: str = "forge") -> Payload:
    return Payload(kind="node", value=nid, source=source, mode="on_selection_change")


def report(text: str, source: str = "forge") -> Payload:
    return Payload(kind="text", value=text, source=source, mode="on_task_completed", title="report")


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class Rig:
    def __init__(self, scroll: ts.TownScroll, runner=None, budget: bool = True) -> None:
        self.scroll, self.clock = scroll, Clock()
        self.delivered: list[tuple[str, Payload]] = []
        self.outputs: list[tuple[str, str, str]] = []
        self.runs: list[roads.HandlerRun] = []
        import tempfile
        self.repo = __import__("pathlib").Path(tempfile.mkdtemp(prefix="orkcraft-engine-"))
        self.engine = roads.Engine(
            lambda: self.scroll, self.repo,
            deliver=lambda t, p: self.delivered.append((t, p)),
            on_output=lambda t, orc, title, md, *_: self.outputs.append((t, orc.id, md)),
            on_run=self.runs.append,
            meta=lambda p: dict(NODES.get(p.value, {})),
            budget_ok=lambda: budget, clock=self.clock,
            agent_runner=runner or (lambda *a: ("", None)),
        )


def wait_for(pred, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > end:
            raise AssertionError("timed out")
        time.sleep(0.01)


# -- chains ------------------------------------------------------------------------------------------

def test_chain_ops():
    recs = [{"id": "T1", "status": "done", "title": "fix login (#12)"},
            {"id": "T2", "status": "todo", "title": "docs"},
            {"id": "T3", "status": "done", "title": "cache (#40)"}]
    r = chains.run_chain([
        {"op": "filter", "field": "status", "cmp": "eq", "value": "done"},
        {"op": "extract", "field": "title", "regex": r"#(\d+)", "as": "pr"},
        {"op": "sort", "by": "pr", "desc": True},
        {"op": "template", "md": "- {id} PR {pr} {{raw}}"},
    ], recs)
    assert r.ok and r.markdown == "- T3 PR 40 {raw}\n- T1 PR 12 {raw}"
    assert chains.run_chain([{"op": "group", "by": "status"}], recs).records == \
        [{"status": "done", "count": 2}, {"status": "todo", "count": 1}]
    assert chains.run_chain([{"op": "count", "as": "n"}], recs).markdown == "- n: 3"
    assert chains.run_chain([{"op": "pick", "fields": ["id"]}, {"op": "limit", "n": 1}], recs).markdown == "- id: T1"
    assert chains.run_chain([{"op": "template", "md": "{id}"}, {"op": "join", "sep": ", "}], recs).markdown == "T1, T2, T3"
    assert chains.run_chain([{"op": "filter", "field": "id", "cmp": "in", "value": ["T2"]}], recs).records == [recs[1]]
    # placeholders are field names only: no attribute access, no format spec
    assert chains.run_chain([{"op": "template", "md": "{id.__class__} {id!r} {id}"}], recs[:1]).markdown == \
        "{id.__class__} {id!r} T1"
    bad = chains.run_chain([{"op": "filter", "field": "id", "cmp": "matches", "value": "("}], recs)
    assert not bad.ok and "op 1 (filter)" in bad.error


# -- plain roads and the source filter -----------------------------------------------------------------

def test_plain_road_delivers_and_filter_turns_carts_back():
    scroll = ts.default_scroll(PRESETS)
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", {"node_status": ["done"]})
    ts.subscribe(scroll, "loot", "forge", "on_task_completed")
    rig = Rig(scroll)
    assert rig.engine.has_roads("forge", "on_selection_change") and not rig.engine.has_roads("loot", "on_stream")
    [cart] = rig.engine.emit(node("T1001"))
    assert cart.status == roads.DELIVERED and rig.delivered == [("scrying", node("T1001"))]
    [cart] = rig.engine.emit(node("T1002"))
    assert cart.status == roads.FILTERED and cart.detail == "status todo" and len(rig.delivered) == 1
    [cart] = rig.engine.emit(report("done"))
    assert (cart.target, cart.status) == ("loot", roads.DELIVERED)
    assert rig.engine.emit(node("T1001", source="loot")) == []       # no road from the chest
    assert [c.status for c in rig.engine.carts] == ["delivered", "filtered", "delivered"]


def test_filter_keys():
    p = Payload("file", "loot/pipes/a.md", "loot", "on_selection_change", "a")
    assert roads.passes({"path_prefix": ["loot/"]}, p, {}) == (True, "")
    assert roads.passes({"path_prefix": ["src/"]}, p, {})[0] is False
    assert roads.passes({"node_type": ["task"]}, p, {})[0] is True          # not a node: ignored
    assert roads.passes({"match": "pipes/a"}, p, {})[0] is True
    assert roads.passes({"outcome": ["halted"]}, report("x"), {"outcome": "done"}) == (False, "outcome done")
    assert roads.passes({"exclude_personal": True}, node("C1003"), NODES["C1003"]) == (False, "personal node")


# -- handlers ------------------------------------------------------------------------------------------

def test_chain_handler_reruns_on_every_event_with_the_whole_snapshot():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Scribe", kind="chain",
                   chain=[{"op": "template", "md": "{road}: {value} {status}"}, {"op": "join", "sep": " | "}])
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="scribe")
    ts.subscribe(scroll, "scrying", "loot", "on_task_completed", handler="scribe")
    rig = Rig(scroll)
    [cart] = rig.engine.emit(node("T1001"))
    assert cart.status == roads.SENT and cart.detail == "Scribe"
    assert rig.outputs == [("scrying", "scribe", "forge-selection: T1001 done")]   # the other road never fired
    rig.engine.emit(report("all green", source="loot"))
    assert rig.outputs[-1][2] == "forge-selection: T1001 done | loot-task: all green "
    rig.engine.emit(node("T1002"))                                         # the forge road's value is replaced
    assert rig.outputs[-1][2] == "forge-selection: T1002 todo | loot-task: all green "
    assert [r.outcome for r in rig.runs] == ["done"] * 3 and rig.delivered == []
    # an unsubscribed road leaves the snapshot
    ts.unsubscribe(scroll, "scrying", "loot-task")
    rig.engine.emit(node("T1001"))
    assert rig.outputs[-1][2] == "forge-selection: T1001 done"


def test_failing_chain_and_held_script():
    scroll = ts.default_scroll(PRESETS)
    broken = ts.add_handler(scroll, "scrying", "Broken", kind="chain", chain=[{"op": "count"}])
    # the contract refuses a bad regex; the executor must still fail safely on one
    broken.chain = [{"op": "filter", "field": "value", "cmp": "matches", "value": "[a-"}]
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="broken")
    ts.add_handler(scroll, "loot", "Tally", kind="script", script={"path": ".orkcraft/scripts/tally.py"})
    ts.subscribe(scroll, "loot", "forge", "on_selection_change", handler="tally")
    rig = Rig(scroll)
    carts = {c.target: c for c in rig.engine.emit(node("T1001"))}
    assert carts["loot"].status == roads.HELD and "missing" in carts["loot"].detail
    outcomes = {r.orc_id: (r.outcome, r.error) for r in rig.runs}
    assert outcomes["broken"][0] == "error" and "op 1" in outcomes["broken"][1]
    assert outcomes["tally"] == ("held", "the script file is missing")
    assert rig.outputs == []


def test_a_reviewed_script_runs_and_a_hybrid_escalates():
    """T1108 stage 11: scripts run once reviewed and unchanged; a hybrid's exit 3 wakes its agent."""
    import hashlib

    scroll = ts.default_scroll(PRESETS)
    prompts = []
    rig = Rig(scroll, runner=lambda harness, prompt, *a: (prompts.append(prompt) or "agent says hi", 0.01))
    src = ("import json, sys\nrecs = json.load(sys.stdin)\nvals = [r.get('id') or '' for r in recs]\n"
           "print('ids: ' + ', '.join(vals))\nsys.exit(3 if 'T1002' in vals else 0)\n")
    path = rig.repo / ".orkcraft" / "scripts" / "ids.py"
    path.parent.mkdir(parents=True)
    path.write_text(src)
    sha = hashlib.sha256(src.encode()).hexdigest()
    ts.add_handler(scroll, "loot", "Ids", kind="script", script={"path": ".orkcraft/scripts/ids.py", "sha256": sha})
    ts.subscribe(scroll, "loot", "forge", "on_selection_change", handler="ids")
    carts = {c.target: c for c in rig.engine.emit(node("T1001"))}
    assert carts["loot"].status == roads.HELD and "review" in carts["loot"].detail       # not reviewed yet
    scroll.building("loot").garrison.handler("ids").script["reviewed"] = True
    rig.engine.emit(node("T1001"))
    wait_for(lambda: any(r.orc_id == "ids" and r.outcome == "done" for r in rig.runs))
    assert rig.outputs[-1] == ("loot", "ids", "ids: T1001")
    # exit 3 from a plain script is an error; from a hybrid, its agent takes over
    rig.engine.emit(node("T1002"))
    wait_for(lambda: sum(r.orc_id == "ids" for r in rig.runs if r.outcome != "held") >= 2)
    assert [r for r in rig.runs if r.orc_id == "ids"][-1].outcome == "error"
    ids = scroll.building("loot").garrison.handler("ids")
    ids.kind, ids.harness, ids.run = "hybrid", [{"role": "run", "harness": "claude"}], {"quiet_s": 0}
    rig.engine.emit(node("T1002"))
    wait_for(lambda: rig.outputs[-1][2] == "agent says hi")
    assert "ids: T1002" in prompts[-1]                                                  # the script's finding
    path.write_text(src + "# changed\n")                                               # changed after review
    carts = {c.target: c for c in rig.engine.emit(node("T1001"))}
    assert carts["loot"].status == roads.HELD and "changed since" in carts["loot"].detail


def test_agent_waits_for_quiet_and_coalesces_a_burst():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", orders="summarise", run={"quiet_s": 30})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    prompts: list[tuple[str, str, dict]] = []

    def runner(harness, prompt, repo, env, cancel):
        prompts.append((harness, prompt, env))
        return "## summary", 0.02

    rig = Rig(scroll, runner)
    for nid in ("T1001", "T1002", "T1001"):
        rig.engine.emit(node(nid))
        rig.clock.t += 10
    rig.engine.tick()
    assert prompts == []                       # 10 s since the last event < 30 s
    rig.clock.t += 25
    rig.engine.tick()
    wait_for(lambda: rig.runs)
    assert len(prompts) == 1 and rig.outputs == [("scrying", "seer", "## summary")]
    harness, prompt, env = prompts[0]
    assert harness == "main" and "summarise" in prompt and '"id":"T1001"' in prompt and '"value"' not in prompt
    assert env["ORKCRAFT_ORC"] == "scrying/seer"
    assert rig.runs[0].cost_usd == pytest.approx(0.02)
    last = rig.runs[0].trail[-1]                                    # what the chain says of this hop afterwards
    assert last.building == "scrying" and last.model == "main" and last.run == rig.runs[0].run_id and last.ms == 0
    [example] = roads.read_examples(rig.repo, "scrying", "seer")
    assert example["output"] == "## summary" and example["inputs"][0]["value"] == "T1001"


def test_personal_nodes_never_reach_an_agent():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", run={"quiet_s": 0})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    ts.add_handler(scroll, "loot", "Scribe", kind="chain", chain=[{"op": "count"}])
    ts.subscribe(scroll, "loot", "forge", "on_selection_change", handler="scribe")
    rig = Rig(scroll, lambda *a: ("x", None))
    carts = {c.target: c for c in rig.engine.emit(node("C1003"))}
    assert carts["scrying"].status == roads.FILTERED and "model" in carts["scrying"].detail
    assert carts["loot"].status == roads.SENT                 # a chain is local code, no model


def test_harness_scheme_runs_steps_in_order():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Pair", run={"quiet_s": 0},
                   harness=[{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}])
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed", handler="pair")
    calls = []

    def runner(harness, prompt, repo, env, cancel):
        calls.append((harness, prompt))
        return f"out of {harness}", 0.01

    rig = Rig(scroll, runner)
    rig.engine.emit(report("tests failed"))
    wait_for(lambda: rig.runs)
    assert [h for h, _ in calls] == ["agy", "claude"]
    assert "Produce the result" in calls[0][1] and "out of agy" in calls[1][1] and "Check the previous" in calls[1][1]
    assert rig.outputs[-1][2] == "out of claude" and rig.runs[0].cost_usd == pytest.approx(0.02)


def test_a_handler_run_carries_the_trail_of_its_carts_and_adds_its_own_hop():
    from orkcraft.realm import pipes
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Pair", run={"quiet_s": 0},
                   harness=[{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}])
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed", handler="pair")
    outs = []
    rig = Rig(scroll, lambda *a: ("ok", 0.01, 500))
    rig.engine._on_output = lambda t, orc, title, md, trail, ref: outs.append((trail, ref))
    before = pipes.hop("forge", "smith", "task", worktree=".orkcraft/worktrees/auth", outcome="done")
    rig.engine.emit(Payload("text", "tests failed", "forge", "on_task_completed", "report", (before,), "T1001"))
    wait_for(lambda: outs)
    [(trail, ref)] = outs
    assert ref == "T1001" and trail[0] == before and len(trail) == 2
    own = trail[1]
    assert (own.building, own.orc, own.kind, own.tokens, own.outcome) == ("scrying", "pair", "agent", 1000, "done")
    assert own.cost == pytest.approx(0.02) and rig.runs[0].trail == trail
    assert pipes.trail_totals(trail) == (1000, pytest.approx(0.02))


def test_new_event_restarts_a_running_agent_with_the_fresh_snapshot():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", run={"quiet_s": 0, "restart_on_new": True})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    started = threading.Event()
    seen = []

    def runner(harness, prompt, repo, env, cancel):
        seen.append("T1002" in prompt)
        if len(seen) == 1:
            started.set()
            if cancel.wait(3):
                raise InterruptedError("restarted")
        return "fresh", None

    rig = Rig(scroll, runner)
    rig.engine.emit(node("T1001"))
    assert started.wait(2)
    rig.engine.emit(node("T1002"))                 # interrupts the first run
    wait_for(lambda: len(rig.runs) == 2)
    assert [r.outcome for r in rig.runs] == ["interrupted", "done"]
    assert seen == [False, True] and rig.outputs == [("scrying", "seer", "fresh")]


def test_without_restart_a_busy_agent_runs_again_after_finishing():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", run={"quiet_s": 0, "restart_on_new": False})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    gate = threading.Event()
    prompts = []

    def runner(harness, prompt, repo, env, cancel):
        prompts.append(prompt)
        gate.wait(3)
        return "ok", None

    rig = Rig(scroll, runner)
    rig.engine.emit(node("T1001"))
    wait_for(lambda: prompts)
    rig.engine.emit(node("T1002"))
    gate.set()
    wait_for(lambda: rig.runs)
    rig.engine.tick()
    wait_for(lambda: len(rig.runs) == 2)
    assert [r.outcome for r in rig.runs] == ["done", "done"] and "T1002" in prompts[1]


def test_no_gold_no_agent_and_errors_are_reported():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", run={"quiet_s": 0})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    called = []
    rig = Rig(scroll, lambda *a: called.append(1) or ("x", None), budget=False)
    rig.engine.emit(node("T1001"))
    assert called == [] and rig.runs[0].outcome == "no_gold"

    def boom(*a):
        raise RuntimeError("claude not found")

    rig2 = Rig(scroll, boom)
    rig2.engine.emit(node("T1001"))
    wait_for(lambda: rig2.runs)
    assert (rig2.runs[0].outcome, rig2.runs[0].error) == ("error", "claude not found") and rig2.outputs == []


def test_harness_commands_are_read_only_or_sandboxed(tmp_path):
    claude = roads._harness_cmd("claude", "hi", tmp_path)
    assert claude[:2] == ["claude", "-p"] and "Read,Grep,Glob" in claude and "Bash,Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch" in claude
    agy = roads._harness_cmd("agy", "hi", tmp_path)
    assert agy[agy.index("--add-dir") + 1] == str(tmp_path) and "--sandbox" in agy
    assert "--dangerously-skip-permissions" not in agy and "--effort" not in agy
    with pytest.raises(RuntimeError, match="not wired"):
        roads._harness_cmd("pipeline:product-studio/pipelines/sprint.json", "hi", tmp_path)
    assert roads._result_of('{"result": "ok", "total_cost_usd": 0.5}') == ("ok", 0.5, None)
    assert roads._result_of("plain text") == ("plain text", None, None)
    usage = '{"result": "ok", "total_cost_usd": 0.5, "usage": {"input_tokens": 10, "output_tokens": 5, ' \
            '"cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200}}'
    assert roads._result_of(usage) == ("ok", 0.5, 1215)                 # every token, cache included


def test_run_agent_interrupts_the_process(tmp_path, monkeypatch):
    monkeypatch.setattr(roads, "_harness_cmd", lambda h, p, w, m="", web=False: ["sleep", "30"])
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    t0 = time.monotonic()
    with pytest.raises(InterruptedError):
        roads.run_agent("claude", "hi", tmp_path, {}, cancel)
    assert time.monotonic() - t0 < 5


# -- in the app ---------------------------------------------------------------------------------------

