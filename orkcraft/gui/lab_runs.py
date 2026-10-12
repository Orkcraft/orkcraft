"""🧪 A Test bench building's own work in the GUI (docs/design/test-bench.md §10): the first cases written from its goal,
a case or all of them run against the bare AI tool, and what to change in the buildings for the goal.

    host.bench.lab.generate(w, subject)      an agent writes the cases (a thread; they land in the building's state)
    host.bench.lab.run(w, subject, ids)      `orkcraft bench chain` in a process of its own, its cases from a file
    host.bench.lab.propose(w, subject)       an agent reads the code and the last tests and proposes changes
    host.bench.lab.tasks(w, subject, …)      the ticked proposals as tasks: of an Agent pool, or down its roads

What the runs said is kept by the building as each case ends (core/workers/lab.py `reported`); after Run all, the
proposals are written again by themselves.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import sys
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import orkcraft
from orkcraft.core import keeper, runners
from orkcraft.core.workers.lab import CODE
from orkcraft.gui import lab_export
from orkcraft.realm import (bench, bench_review, cassette, code_overlay, github_app, halt, harnesses, jobs, lab_cases, lab_envs,
                            lab_pr, lexicon, steward, tiers)

TIER_FLAG = {"laborer": "novice", "warrior": "seasoned", "elder": "veteran"}
BUSY = {"generate": "writing cases", "env": "writing an environment", "set": "writing a case set",
        "try": "trying a change", "pr": "sending the pull request"}
STOP_BEHIND = 3                  # a series of this many cases or more stops when the building is behind on its first 3


class LabError(Exception):
    """A step the Test bench refuses; its text is shown to the person."""


class LabRuns:
    def __init__(self, engine) -> None:
        self.engine = engine                     # gui/bench.py Bench: its jobs, its process following
        self.host = engine.host
        self.busy: dict[str, str] = {}           # "<lab>:<subject>" → what it is doing: generate | propose

    def key(self, w, subject: dict) -> str:
        return f"{w.building_id}:{subject['id']}"

    def job(self, w):
        return self.engine.jobs.get(f"lab:{w.building_id}")

    # -- the first cases ------------------------------------------------------------------------------------------

    def _agent(self, w, subject: dict, what: str, prompt: str, done, tier: str = "", bare: bool = False,
               workdir: Path | None = None) -> None:
        """One call to the bench's AI tool on its own thread; `tier` a lighter model for a light ask, `bare` an empty
        folder to work in (the ask needs no file: nothing is read, no token spent looking round the source)."""
        key = self.key(w, subject)
        if key in self.busy:
            raise LabError(f"It is already {BUSY.get(self.busy[key], 'thinking')}")
        self.busy[key] = what
        tool = str(w.state["settings"].get("tool") or "main")
        model = tiers.resolve(tool, tier) if tier else ""
        model = "" if model in tiers.TIERS else model            # a tool with no model for the tier: its own

        def work() -> None:
            text, error = "", ""
            try:
                if workdir is not None:                   # it changes files there: the bench's copy of the package
                    text = jobs.run_work(tool, prompt, workdir, threading.Event(), model)[0]
                elif bare:
                    with tempfile.TemporaryDirectory(prefix="orkcraft-lab-") as empty:
                        text = jobs.run_read(tool, prompt, Path(empty), threading.Event(), model)[0]
                else:
                    text = jobs.run_read(tool, prompt, bench_review.source_dir(), threading.Event(), model)[0]
            except (RuntimeError, OSError) as e:
                error = str(e)[:300] or type(e).__name__
            self.host.town.call(finish, text, error)

        def finish(text: str, error: str) -> None:
            self.busy.pop(key, None)
            if error:
                self.host.town.toast(error, title="Test bench", severity="error")
            else:
                done(text)
            w.changed()

        threading.Thread(target=work, daemon=True, name=f"lab-{what}").start()
        w.changed()

    def generate(self, w, subject: dict) -> None:
        if not w.state["goal"].strip():
            raise LabError("Write the goal of the testing first")
        entries = w.entries(subject)
        have = [c["title"] for c in w.cases_of(subject["id"])]
        about = w.flow_spec(subject)["about"]

        def done(text: str) -> None:
            cases = lab_cases.parse_cases(text, entries)
            if not cases:
                self.host.town.toast("The agent's answer held no case", title="Test bench", severity="warning")
                return
            n = w.add_cases(subject["id"], cases)
            self.host.town.toast(f"{n} case{'s' if n != 1 else ''} written for the goal", title="Test bench")

        self._agent(w, subject, "generate", lab_cases.case_prompt(w.state["goal"], about, entries, have), done,
                    tier="laborer", bare=True)

    # -- environments and case sets (docs/design/improve-buildings.md §5.2) -----------------------------------------

    def make_env(self, w, subject: dict, about: str) -> None:
        """An environment written from the person's words: one call, once; its files kept beside the building."""
        if len(about.strip()) < 10:
            raise LabError("Say in a sentence what the environment is")

        def done(text: str) -> None:
            got = lab_envs.parse_env(text)
            if got is None:
                self.host.town.toast("The agent's answer held no files", title="Test bench", severity="warning")
                return
            env = w.add_env(got[0], about, got[1])
            self.host.town.toast(f"Environment {env['name']}: {env['files']} files", title="Test bench")

        self._agent(w, subject, "env", lab_envs.env_prompt(about), done, tier="warrior", bare=True)

    def make_set(self, w, subject: dict, env_id: str, what: str, count: int) -> None:
        """A case set: what its cases do in one environment, and how many — written in one call to a light model."""
        env = w.env(env_id)
        if env is None:
            raise LabError("No such environment")
        if len(what.strip()) < 5:
            raise LabError("Say what the cases of the set do")
        case_set = lab_envs.new_set(env_id, what, count)
        entries = w.entries(subject)
        prompt = lab_envs.set_prompt(w.state["goal"], w.flow_spec(subject)["about"], entries, env, what,
                                     case_set["count"])

        def done(text: str) -> None:
            cases = lab_cases.parse_cases(text, entries)[:case_set["count"]]
            if not cases:
                self.host.town.toast("The agent's answer held no case", title="Test bench", severity="warning")
                return
            n = w.add_set(subject["id"], case_set, cases)
            self.host.town.toast(f"A case set of {n} in {env['name']}", title="Test bench")

        self._agent(w, subject, "set", prompt, done, tier="laborer", bare=True)

    # -- the virtual building (docs/design/improve-buildings.md §5.3) ---------------------------------------------

    def _target(self, w, subject: dict, p: dict, building: str) -> str:
        """The building a proposal is tried on: the one asked for, else the one its `where` names, else the first."""
        ids = subject.get("chain") or [subject["id"]]
        if building in ids:
            return building
        where = (p.get("where") or "").lower()
        return next((b for b in ids if self.host.town.title_of(b).lower() in where or b in where), ids[0])

    def try_change(self, w, subject: dict, proposal_id: str, building: str = "", after=None) -> None:
        """A proposal tried on the virtual building: settings and prompts through the building's keeper (a checked
        change of its spec, kept by the bench), code in the bench's own copy of the package. The town's building
        keeps what it has until Save changes."""
        p = next((x for x in (w.state["proposals"].get(subject["id"]) or {}).get("items") or [] if x["id"] == proposal_id),
                 None)
        if p is None:
            raise LabError("No such proposal")
        if p["area"] == "roads":
            raise LabError("Roads change on the map and in its setup, not on the virtual building")
        if p["area"] == CODE:
            self._try_code(w, subject, p)
            return
        bid = self._target(w, subject, p, building)
        spec = w.virtual_spec(subject["id"], bid)
        if not spec:
            raise LabError("That building keeps no settings here")
        town = self.host.town
        request = f"{p['title']}. {p['detail']}" + (f" (where: {p['where']})" if p.get("where") else "") + \
            (f" It should: {p['effect']}" if p.get("effect") else "")
        key = self.key(w, subject)
        if key in self.busy:
            raise LabError(f"It is already {BUSY.get(self.busy[key], 'thinking')}")
        self.busy[key] = "try"
        snapshot, others = copy.deepcopy(town.scroll), set(town.custom_specs) - {bid}

        def work() -> None:
            got = keeper.ask(town.repo_root, spec, snapshot, bid, request, existing_ids=others,
                             runner=steward.runner_for(snapshot.building(bid), "keeper", runners.KEEPER_RUNNER))
            town.call(finish, got)

        def finish(got: keeper.Proposal) -> None:
            self.busy.pop(key, None)
            if got.error:
                town.toast(f"The keeper could not: {got.error}"[:300], title="Test bench", severity="error")
            elif not got.changes:
                town.toast(f"Nothing to change in {town.title_of(bid)}: {got.answer or got.why}"[:300], title="Test bench")
            else:
                w.add_change(subject["id"], {
                    "id": f"v{uuid.uuid4().hex[:6]}", "proposal": p["id"], "title": p["title"], "building": bid,
                    "kind": got.kind, "after": got.after, "why": got.why or p["title"],
                    "diff": got.diff(keeper.subject_of(spec)), "cost": got.cost_usd,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
                town.toast(f"Tried on the virtual {town.title_of(bid)}: {p['title']}"[:200], title="Test bench")
            w.changed()
            if after is not None:
                after(not got.error and got.changes)

        threading.Thread(target=work, daemon=True, name="lab-try").start()
        w.changed()

    def _try_code(self, w, subject: dict, p: dict) -> None:
        """A code proposal: an agent changes the bench's copy of the package; the diff is kept as one change."""
        spec = w.flow_spec(subject)
        files = sorted({f for b in spec["buildings"] for f in bench_review._files(b["type"], code_overlay.package())})
        prompt = code_overlay.code_prompt(p["title"], p["detail"], p.get("where", ""), p.get("effect", ""), files)
        state_dir = w.state_dir

        def done(text: str) -> None:
            code_overlay.keep(state_dir, p["title"])
            touched = code_overlay.changed(state_dir)
            if not touched:
                self.host.town.toast("The agent changed no code", title="Test bench", severity="warning")
                return
            w.state.setdefault("virtual", {}).setdefault(subject["id"], [])
            w.state["virtual"][subject["id"]] = [c for c in w.changes_of(subject["id"]) if c["kind"] != CODE] + [{
                "id": "code", "proposal": p["id"], "title": "Code", "building": "", "kind": CODE, "files": touched,
                "why": "; ".join(dict.fromkeys([*(c["why"] for c in w.changes_of(subject["id"]) if c["kind"] == CODE),
                                                p["title"]]))[:600],
                "diff": code_overlay.diff(state_dir), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}]
            w.keep()
            self.host.town.toast(f"Code changed for the bench's runs: {', '.join(touched[:3])}", title="Test bench")

        try:
            pkg = code_overlay.ensure(state_dir)
        except (OSError, RuntimeError) as e:
            raise LabError(f"The bench could not copy the package: {e}") from None
        self._agent(w, subject, "try", prompt, done, workdir=pkg.parent)

    def drop_code(self, w, subject: dict) -> None:
        code_overlay.drop(w.state_dir)
        w.state.setdefault("virtual", {})[subject["id"]] = [c for c in w.changes_of(subject["id"]) if c["kind"] != CODE]
        w.keep()

    # -- a pull request (docs/design/improve-buildings.md §4) --------------------------------------------------------

    def pr_preview(self, w, subject: dict) -> dict:
        """Exactly what would leave the machine: the title, the body and the diff; whether it may go yet."""
        code = next((c for c in w.changes_of(subject["id"]) if c["kind"] == CODE), None)
        if code is None:
            raise LabError("Only a code change goes to Orkcraft as a pull request")
        metric = lab_cases.metric_of(w.state["goal"])
        cases, results = w.cases_of(subject["id"]), w.results_of(subject["id"])
        rows = lab_pr.with_change(cases, results, code["at"])
        ok, why = lab_pr.ready(cases, results, code["at"], metric)
        sets = [{**cs, "env_name": (w.env(cs["env"]) or {}).get("name", "")} for cs in w.sets_of(subject["id"])]
        data = [f"{self.host.town.title_of(c['building'])}: {c['title']}" for c in w.changes_of(subject["id"])
                if c["kind"] != CODE]
        body = lab_pr.body(w.state["goal"], w.flow_spec(subject)["about"], code["why"], metric, sets, rows,
                           code["files"], data)
        acct = github_app.account()
        return {"ready": ok, "why": why, "title": lab_pr.title(code["why"]), "body": body,
                "diff": code_overlay.diff(w.state_dir), "login": acct["login"] if acct else "",
                "sent": (w.state.get("prs") or {}).get(subject["id"], "")}

    def send_pr(self, w, subject: dict) -> None:
        got = self.pr_preview(w, subject)
        if not got["ready"]:
            raise LabError(got["why"])
        if not got["login"]:
            raise LabError("Connect GitHub first: the mascot's menu → GitHub")
        key = self.key(w, subject)
        if key in self.busy:
            raise LabError(f"It is already {BUSY.get(self.busy[key], 'thinking')}")
        self.busy[key] = "pr"
        changes = lab_pr.files(w.state_dir)
        branch = f"improve/{subject['type'].replace(':', '-')}-{time.strftime('%Y%m%d-%H%M%S')}"
        town = self.host.town

        def work() -> None:
            try:
                url, error = github_app.send(changes, got["title"], got["body"], branch), ""
            except github_app.GithubError as e:
                url, error = "", str(e)
            town.call(finish, url, error)

        def finish(url: str, error: str) -> None:
            self.busy.pop(key, None)
            if error:
                town.toast(error, title="GitHub", severity="error")
            else:
                w.state.setdefault("prs", {})[subject["id"]] = url
                w.keep()
                town.toast(f"Pull request opened: {url}", title="GitHub")
            w.changed()

        threading.Thread(target=work, daemon=True, name="lab-pr").start()
        w.changed()

    # -- running ------------------------------------------------------------------------------------------------

    def run(self, w, subject: dict, case_ids: list[str] | None = None, then_propose: bool = False,
            then=None) -> None:
        if not subject.get("can_run", True):
            raise LabError("Runs come to this building later")
        if (job := self.job(w)) and not job.done:
            raise LabError("A run is on: stop it first")
        cases = [c for c in w.cases_of(subject["id"]) if not case_ids or c["id"] in case_ids]
        if not cases:
            raise LabError("No case to run: write the goal and make the cases, or add one")
        s = w.state["settings"]
        spec = w.flow_spec(subject)
        folder = self.engine.root / bench.BENCH / "lab" / w.building_id
        folder.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        chain_file, cases_file = folder / f"scheme-{stamp}.json", folder / f"cases-{stamp}.json"
        chain_file.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        cases_file.write_text(json.dumps([asdict(lab_cases.to_case(c, spec["about"], bool(s.get("judge")),
                                                                  w.state["goal"], w.files_for(subject["id"], c)))
                                          for c in cases], ensure_ascii=False), encoding="utf-8")
        argv = [sys.executable, "-m", "orkcraft", "--repo", str(self.engine.root), "bench", "chain",
                "--chain-file", str(chain_file), "--cases-file", str(cases_file),
                "--case", "all" if len(cases) > 1 else cases[0]["id"],
                "--tool", str(s.get("tool") or "main"), "--max-spend", str(float(s.get("max_spend") or 2.0))]
        if s.get("tier") in TIER_FLAG:
            argv += ["--tier", TIER_FLAG[s["tier"]]]
        if len(cases) >= 2 * STOP_BEHIND:
            argv += ["--stop-behind", str(STOP_BEHIND)]
        if s.get("bare_tool") and s["bare_tool"] != s.get("tool"):
            argv += ["--bare-tool", str(s["bare_tool"])]
        if s.get("bare_tier") in TIER_FLAG:
            argv += ["--bare-tier", TIER_FLAG[s["bare_tier"]]]
        repeat = int(s.get("repeat") or lab_cases.REPEAT)
        if repeat > 1:
            argv += ["--repeat", str(min(repeat, bench.REPEAT_MAX))]
        from orkcraft.gui.bench import Job
        label = cases[0]["title"] if len(cases) == 1 else f"every case ({len(cases)})"
        job = Job("run", "chain", label, subject=subject["id"],
                  then=then or ((lambda: self._propose_quietly(w, subject)) if then_propose else None))
        try:
            code = code_overlay.env(w.state_dir) if any(c["kind"] == CODE for c in w.changes_of(subject["id"])) else {}
            code.update(self._cassette(w, subject, cases, folder, stamp))
            job.proc = subprocess.Popen(argv, cwd=self.engine.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True,
                                        env={**os.environ, "PYTHONUNBUFFERED": "1", **code})
        except OSError as e:
            raise LabError(f"The run did not start: {e}") from None
        halt.started(job.proc, f"{w.building_id}/bench", agent=True)
        self.engine.jobs[f"lab:{w.building_id}"] = job
        threading.Thread(target=self.engine._follow, args=(job,), daemon=True, name="lab-run").start()
        w.changed()

    def _cassette(self, w, subject: dict, cases: list[dict], folder: Path, stamp: int) -> dict:
        """The run's MCP servers as cassette proxies (realm/cassette.py): the set's cassette when every case is of one
        set, else the scheme's own; {} when the person has no local server Claude Code knows."""
        from orkcraft.realm import mcp
        repo = self.engine.root
        names = [x.id for x in mcp.found(Path.home(), repo) if "claude" in x.tools and mcp.launch(x.id, repo=repo)]
        if not names:
            return {}
        sets = {c.get("set") for c in cases}
        tape = lab_envs.cassette_path(w.state_dir, subject["id"], sets.pop() if len(sets) == 1 else "")
        conf = folder / f"mcp-{stamp}.json"
        conf.write_text(json.dumps(cassette.config(names, tape, repo)), encoding="utf-8")
        return {"ORKCRAFT_MCP_CONFIG": str(conf)}

    def stop(self, w) -> None:
        job = self.job(w)
        if job and not job.done:
            job.cancel.set()
            try:
                os.killpg(job.proc.pid, 15)
            except (ProcessLookupError, PermissionError, AttributeError):
                pass

    # -- what to change -------------------------------------------------------------------------------------------

    def _propose_quietly(self, w, subject: dict) -> None:
        try:
            self.propose(w, subject)
        except LabError:
            pass

    def propose(self, w, subject: dict, after=None) -> None:
        spec = w.flow_spec(subject)
        base = bench_review.source_dir()
        files = sorted({f for b in spec["buildings"] for f in bench_review._files(b["type"], base)})
        roads = [f"{r['source']} → {r['target']} ({r['event']})" for r in spec.get("roads") or []]
        results = w.results_of(subject["id"])
        lines = [lab_cases.result_line(c, results[c["id"]]) for c in w.cases_of(subject["id"]) if c["id"] in results]
        prompt = lab_cases.propose_prompt(w.state["goal"] or lab_cases.DEFAULT_GOAL, spec["about"], files, roads, lines,
                                          lab_export.findings(self.engine.root, w, subject))

        def done(text: str) -> None:
            w.set_proposals(subject["id"], lab_cases.parse_proposals(text))
            if after is not None:
                after()

        self._agent(w, subject, "propose", prompt, done)

    def tasks(self, w, subject: dict, picks: list[str], pool: str) -> int:
        items = [p for p in (w.state["proposals"].get(subject["id"]) or {}).get("items") or [] if p["id"] in picks]
        if not items:
            raise LabError("Tick the proposals to make tasks of")
        made = 0
        for p in items:
            title = f"{subject['title']}: {p['title']}"
            body = (f"From the Test bench, for the goal: {w.state['goal'] or '—'} (Orkcraft {orkcraft.__version__}).\n\n"
                    f"{p['detail']}\n\nWhere: {p['where'] or '—'}\n\nWhat it should do: {p['effect'] or '—'}\n\n"
                    f"Kind of change: {p['area']}.")
            if pool == "@roads":
                made += int(w.finding(title, body))
            else:
                pw = self.host.town.worker(pool) if self.host.type_of(pool) == "barracks" else None
                if pw is None:
                    raise LabError("Pick an Agent pool for the tasks")
                made += int(pw.new_task(title, body) is not None)
        self.host.town.toast(f"{made} task{'s' if made != 1 else ''} sent", title="Test bench")
        return made

    # -- what the runs said, to hand over (gui/lab_export.py) ----------------------------------------------------

    def _lab_of(self, lab_id: str):
        if self.host.type_of(lab_id) != "lab":
            return None
        return self.host.town.worker(lab_id)

    def pack(self, lab_id: str) -> tuple[str, bytes] | None:
        """The zip of what the Test bench `lab_id` tests now: its latest runs, every call, the recommendations."""
        w = self._lab_of(lab_id)
        s = w.subject() if w is not None else None
        return lab_export.pack(self.engine.root, w, s) if s is not None else None

    def recommend(self, w, subject: dict) -> None:
        """The tech review of each building it tests, reading these runs (not the type's shipped cases)."""
        runs = lab_export.runs_text(self.engine.root, w, subject, calls=True)[:60_000]
        for _bid, kind in lab_export.types_of(w, subject):
            if not self.engine.reviewing.get((kind, "tech")):
                self.engine.start_review(kind, "tech", str(w.state["settings"].get("tool") or "main"), runs)

    def recommendations(self, w, subject: dict) -> list[dict]:
        """Each building type it tests: its tech review's findings and whether it is on now."""
        out = []
        for bid, kind in lab_export.types_of(w, subject):
            kept = bench_review.load(self.engine.root, kind, "tech")
            out.append({"type": kind, "word": lexicon.term(kind), "at": kept.get("at", ""),
                        "running": bool(self.engine.reviewing.get((kind, "tech"))),
                        "findings": [{**f, "who": e.get("title") or role} for role, e in (kept.get("roles") or {}).items()
                                     for f in e.get("findings") or []],
                        "errors": [e.get("error") for e in (kept.get("roles") or {}).values() if e.get("status") == "failed"]})
        return out

    def tools(self) -> list[dict]:
        on = [t for t, c in self.host.town.machine.tools.items() if c.enabled and harnesses.get(t)]
        return [{"id": "main", "title": "Main tool"}] + [{"id": t, "title": harnesses.need(t).title} for t in on]

    @staticmethod
    def tiers() -> list[dict]:
        return [{"id": "", "title": "Its own"}] + [{"id": t, "title": tiers.TIER_LABELS[t]} for t in tiers.TIERS[::-1]]
