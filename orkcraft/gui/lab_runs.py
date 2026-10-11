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

import json
import os
import subprocess
import tempfile
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path

import orkcraft
from orkcraft.realm import bench, bench_review, halt, harnesses, jobs, lab_cases, lab_envs, tiers

TIER_FLAG = {"laborer": "novice", "warrior": "seasoned", "elder": "veteran"}
BUSY = {"generate": "writing cases", "env": "writing an environment", "set": "writing a case set"}
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

    def _agent(self, w, subject: dict, what: str, prompt: str, done, tier: str = "", bare: bool = False) -> None:
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
                if bare:
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

    # -- running ------------------------------------------------------------------------------------------------

    def run(self, w, subject: dict, case_ids: list[str] | None = None, then_propose: bool = False) -> None:
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
        from orkcraft.gui.bench import Job
        label = cases[0]["title"] if len(cases) == 1 else f"every case ({len(cases)})"
        job = Job("run", "chain", label, subject=subject["id"],
                  then=(lambda: self._propose_quietly(w, subject)) if then_propose else None)
        try:
            job.proc = subprocess.Popen(argv, cwd=self.engine.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        except OSError as e:
            raise LabError(f"The run did not start: {e}") from None
        halt.started(job.proc, f"{w.building_id}/bench", agent=True)
        self.engine.jobs[f"lab:{w.building_id}"] = job
        threading.Thread(target=self.engine._follow, args=(job,), daemon=True, name="lab-run").start()
        w.changed()

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

    def propose(self, w, subject: dict) -> None:
        spec = w.flow_spec(subject)
        base = bench_review.source_dir()
        files = sorted({f for b in spec["buildings"] for f in bench_review._files(b["type"], base)})
        roads = [f"{r['source']} → {r['target']} ({r['event']})" for r in spec.get("roads") or []]
        results = w.results_of(subject["id"])
        lines = [lab_cases.result_line(c, results[c["id"]]) for c in w.cases_of(subject["id"]) if c["id"] in results]
        prompt = lab_cases.propose_prompt(w.state["goal"], spec["about"], files, roads, lines)
        self._agent(w, subject, "propose", prompt, lambda text: w.set_proposals(subject["id"], lab_cases.parse_proposals(text)))

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

    def tools(self) -> list[dict]:
        on = [t for t, c in self.host.town.machine.tools.items() if c.enabled and harnesses.get(t)]
        return [{"id": "main", "title": "Main tool"}] + [{"id": t, "title": harnesses.need(t).title} for t in on]

    @staticmethod
    def tiers() -> list[dict]:
        return [{"id": "", "title": "Its own"}] + [{"id": t, "title": tiers.TIER_LABELS[t]} for t in tiers.TIERS[::-1]]
