"""⛏️ The Mine's work (docs/design/mine.md): one research at a time — a plan, a search on every tool that can
search the web (each alone), the check, rounds over what is open, the person's decisions on what stays
disputed, the report.

    plan ─▶ search (each tool alone) ─▶ group + check ─▶ rounds (more sources, a debate) ─▶ Answers ─▶ report

A research is a dict (realm/research.py) kept in `.orkcraft/mine/<id>/<research id>.json`, its report beside
it as `.md`. What arrives while one runs waits in the queue. The money it may spend is its `limit` (never
past what is left of `month_limit`); a research stopped by it says so on top of its report. A disputed
finding waits in Answers (`orders_alert`), one at a time, up to `wait_answers`; then the report goes out
with the unanswered ones as disputed. The report goes to the Wiki's inbox (`wiki`), back by a return road
(its `ref`) and out as `mine.reported`. Repeats are the Calendar's to show (realm/drumbeat.py `jobs`):
`repeats` in its config, run by `tick`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import threading
import uuid
from collections import deque
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.realm import catalog, halt, harnesses, pipes, research, roads

KEEP = 100                            # researches it keeps
INPUT_LIMIT = 4000                    # what of a cart becomes the question and its brief
LIMIT_USD, MONTH_USD = 3.0, 30.0
ROUNDS, MIN_MODELS, MIN_DOMAINS = 3, 2, 2
WAIT = "3d"
_SPAN = re.compile(r"^\s*(\d+)\s*([hd])\s*$")


def span(text: str, default: str = WAIT) -> dt.timedelta:
    """`3d`, `12h` as a time span (the default's when it is neither)."""
    m = _SPAN.match(text or "") or _SPAN.match(default)
    return dt.timedelta(hours=int(m[1]) * (24 if m[2] == "d" else 1))


def _simulated(tool: str, prompt: str) -> str:
    """The showcase sandbox: agents never run there — a canned answer of the shape each prompt asks for."""
    if '"sub"' in prompt and "Do not search" in prompt:
        return json.dumps({"sub": [{"q": "What is it?", "answer_if": "a definition"}]})
    if '"groups"' in prompt:
        return json.dumps({"groups": [[1, 2]], "conflicts": []})
    if '"verdicts"' in prompt:
        return json.dumps({"verdicts": []})
    return json.dumps({"findings": [{"sub": 1, "claim": "(demo — simulated) a researcher would have found this",
                                     "sources": [{"url": f"https://example.{'org' if tool == 'claude' else 'com'}/demo",
                                                  "title": "demo"}]}]})


class MineWorker(Worker):
    TYPE = "mine"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.researches: list[dict] = []           # newest first
        self.queue: deque[dict] = deque()
        self.running: dict | None = None
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.last_tick: dt.datetime | None = None
        self._repeats_done: dict[str, str] = {}
        self._halts = halt.count()

    # -- settings ---------------------------------------------------------------------------------

    def _num(self, key: str, default: float) -> float:
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def limit(self) -> float:
        return self._num("limit", LIMIT_USD)

    @property
    def month_limit(self) -> float:
        return self._num("month_limit", MONTH_USD)

    @property
    def rounds(self) -> int:
        return int(self._num("rounds", ROUNDS))

    @property
    def min_models(self) -> int:
        return int(self._num("min_models", MIN_MODELS))

    @property
    def min_domains(self) -> int:
        return int(self._num("min_domains", MIN_DOMAINS))

    @property
    def repeats(self) -> list[dict]:
        """Its repeats, `{every, limit, question}` (config lines `<every> | <limit> | <question>`)."""
        return [r for r in (research.parse_repeat(x) for x in self.config.get("repeats") or []) if r]

    def _machine(self):
        machine = getattr(self.town, "machine", None)
        if machine is None:
            from orkcraft.realm import builders
            machine = builders._machine()
        return machine

    def web_tools(self) -> list[str]:
        """Every tool that is on and can search the web, in the registry's order."""
        machine = self._machine()
        on = {t for t, c in (getattr(machine, "tools", None) or {}).items() if getattr(c, "enabled", False)}
        return [h.id for h in harnesses.REGISTRY.values() if h.web and h.id in on]

    def tools(self) -> list[str]:
        """The tools that search: its `tools` (the ones of them that can), else every tool on with the web."""
        named = [str(t) for t in self.config.get("tools") or []]
        if named:
            return [t for t in named if (h := harnesses.get(t)) is not None and h.web]
        return self.web_tools()

    def main_tool(self) -> str:
        from orkcraft.realm import builders
        _b, tool = self._steward_of()
        return tool if tool and tool != harnesses.MAIN else builders.main_tool(self._machine())

    # -- the researches on disk -------------------------------------------------------------------

    def _file(self, rid: str, ext: str = "json") -> Path:
        return self.state_dir / f"{rid}.{ext}"

    def save(self, r: dict) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self._file(r["id"]).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            self.toast(f"not kept: {e}", severity="error")

    def load(self) -> None:
        out = []
        for path in self.state_dir.glob("*.json") if self.state_dir.is_dir() else []:
            if path.name == "repeats.json":
                continue
            try:
                r = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(r, dict) and r.get("id"):
                out.append(r)
        out.sort(key=lambda r: r.get("created", ""), reverse=True)
        for old in out[KEEP:]:
            for ext in ("json", "md"):
                self._file(old["id"], ext).unlink(missing_ok=True)
        self.researches = out[:KEEP]
        try:
            self._repeats_done = json.loads((self.state_dir / "repeats.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._repeats_done = {}

    def start(self) -> None:
        self.load()
        for r in self.researches:            # what ran when the town closed does not go on by itself
            if r.get("status") in ("planning", "searching", "checking", "round"):
                r.update(status="stopped", stopped="Stopped: the town closed while it ran")
                self.save(r)
        self.changed()

    def get(self, rid: str) -> dict | None:
        return next((r for r in self.researches if r["id"] == rid), None)

    def report_text(self, r: dict) -> str:
        try:
            return self._file(r["id"], "md").read_text(encoding="utf-8")
        except OSError:
            return ""

    # -- money --------------------------------------------------------------------------------------

    def month_spent(self, now: dt.datetime | None = None) -> float:
        month = (now or self.clock()).strftime("%Y-%m")
        return round(sum(float(r.get("cost") or 0.0) for r in self.researches
                         if str(r.get("created", "")).startswith(month)), 4)

    def left(self, r: dict) -> float:
        """What this research may still spend: its limit, never past what is left of the month."""
        return min(float(r.get("limit") or self.limit) - float(r.get("cost") or 0.0),
                   self.month_limit - self.month_spent())

    def clock(self) -> dt.datetime:
        return dt.datetime.now()

    # -- asking -------------------------------------------------------------------------------------

    def estimate(self) -> tuple[float, float]:
        return research.estimate(max(len(self.tools()), 1), self.rounds)

    def ask(self, question: str, must: list[str] = (), skip: list[str] = (), limit: float | None = None,
            trigger: str = "manual", trail: tuple = (), ref: str = "", repeat: str = "") -> str:
        """Start a research (or queue it behind the one running). Its id; ValueError when it cannot start."""
        question = " ".join((question or "").split())[:INPUT_LIMIT]
        if not question:
            raise ValueError("Write the question")
        tools = self.tools()
        if not tools and not self.simulated:
            raise ValueError("No AI tool that can search the web is on — turn on Claude Code, Codex or Hermes")
        cap = self.limit if limit is None else min(float(limit), self.month_limit)
        if cap <= 0:
            raise ValueError("The limit is $0")
        if self.month_limit - self.month_spent() <= 0:
            raise ValueError(f"This month's limit (${self.month_limit:.2f}) is spent")
        r = {"id": uuid.uuid4().hex[:10], "question": question, "must": [m for m in must if m.strip()][:10],
             "skip": [s for s in skip if s.strip()][:10], "limit": round(cap, 2),
             "tools": tools or ["claude"], "created": self.clock().isoformat(timespec="seconds"),
             "status": "queued", "trigger": trigger, "plan": [], "findings": [], "groups": [], "conflicts": [],
             "round": 0, "cost": 0.0, "per_tool": {}, "trail": list(trail), "ref": ref, "repeat": repeat}
        with self.lock:
            self.researches.insert(0, r)
            self.queue.append(r)
        self.save(r)
        if self.running is None:
            self._next()
        else:
            self.changed()
        return r["id"]

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart is a question: its title, its text the brief (the first line when it has no title)."""
        text = payload.value
        if payload.kind == pipes.FILE:
            try:
                text = (self.repo_root / payload.value).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = markdown or payload.value
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        question = title.strip() or (lines[0] if lines else "")
        brief = [ln for ln in lines if ln != question][:5]
        try:
            self.ask(question, must=brief, trigger="road", trail=tuple(payload.trail), ref=payload.ref)
        except ValueError as e:
            self.toast(str(e), severity="warning")

    # -- the cycle -----------------------------------------------------------------------------------

    def _next(self) -> None:
        with self.lock:
            if self.running is not None or not self.queue:
                return
            r = self.running = self.queue.popleft()
        self.cancel, self._halts = threading.Event(), halt.count()
        self.changed()
        threading.Thread(target=self._work, args=(r, self.cancel), daemon=True,
                         name=f"mine-{self.building_id}").start()

    def _call(self, r: dict, tool: str, prompt: str, use: str, web: bool, cancel: threading.Event) -> str:
        """One model call on `tool` for the steward's `use`, its cost counted on the research and the tool."""
        if cancel.is_set():
            raise InterruptedError("stopped")
        if self.left(r) <= 0:
            raise _Limit()
        if not self.simulated and not self.town.budget_ok():
            raise _Limit("🪙 The town's budget is spent")
        if self.simulated:
            return _simulated(tool, prompt)
        model = harnesses.model_on(tool, self.steward_pick(use).tier or self.steward_pick(use).model)
        with tempfile.TemporaryDirectory(prefix="orkcraft-mine-") as empty:
            text, cost, _tokens = roads.run_agent(tool, prompt, Path(empty), {}, cancel, model, web=web)
        with self.lock:
            r["cost"] = round(float(r.get("cost") or 0.0) + float(cost or 0.0), 4)
            t = r["per_tool"].setdefault(tool, {"mind": research.mind(tool, model), "cost": 0.0, "error": ""})
            t["cost"] = round(t["cost"] + float(cost or 0.0), 4)
            t["model"] = model
        return text

    def _status(self, r: dict, status: str) -> None:
        r["status"] = status
        self.save(r)
        self.changed()

    def _work(self, r: dict, cancel: threading.Event) -> None:
        try:
            self._plan(r, cancel)
            self._search(r, cancel)
            self._group(r, cancel)
            # Fewer tools than a confirmed finding needs minds: another round of searching could never confirm one,
            # it would only spend (docs/design/mine.md: with one tool, nothing can be confirmed).
            while r["round"] < self.rounds and research.open_groups(r) and len(r["tools"]) >= self.min_models:
                r["round"] += 1
                self._status(r, "round")
                if r.get("conflicts") and research.disputes(r) and r["round"] % 2 == 0:
                    self._debate(r, cancel)
                else:
                    self._more(r, research.open_groups(r), cancel)
                self._group(r, cancel)
        except _Limit as e:
            r["stopped"] = str(e) or self._limit_words(r)
        except InterruptedError:
            r["stopped"] = "Stopped by Stop all"
        except Exception as e:                       # a research that fails says why; the queue goes on
            r["error"] = f"{type(e).__name__}: {e}"[:400]
        self.town.call(self._after_cycle, r)

    def _limit_words(self, r: dict) -> str:
        n = research.counts(r)[research.DISPUTED]
        return f"Stopped at the limit (${float(r.get('limit') or 0):.2f})" + (f": {n} findings still disputed" if n else "")

    def _plan(self, r: dict, cancel: threading.Event) -> None:
        self._status(r, "planning")
        answer = self._call(r, self.main_tool(), research.plan_prompt(r["question"], r["must"], r["skip"]),
                            "plan", False, cancel)
        r["plan"] = research.parse_plan(answer, r["question"])
        self.save(r)

    def _parallel(self, r: dict, job, cancel: threading.Event) -> None:
        """`job(tool)` on every tool at once; a tool that fails is noted, the others go on; the limit stops all."""
        errors: list[BaseException] = []

        def one(tool: str) -> None:
            try:
                job(tool)
            except (_Limit, InterruptedError) as e:
                errors.append(e)
            except Exception as e:
                with self.lock:
                    t = r["per_tool"].setdefault(tool, {"mind": research.mind(tool), "cost": 0.0, "error": ""})
                    t["error"] = str(e)[:200]
        threads = [threading.Thread(target=one, args=(t,), daemon=True) for t in r["tools"]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.save(r)
        self.changed()
        for e in errors:
            raise e

    def _search(self, r: dict, cancel: threading.Event) -> None:
        self._status(r, "searching")
        prompt = research.search_prompt(r["question"], r["plan"], r["skip"])

        def job(tool: str) -> None:
            answer = self._call(r, tool, prompt, "search", True, cancel)
            found = research.parse_findings(answer, r["per_tool"].get(tool, {}).get("mind") or research.mind(tool),
                                            tool, 0, len(r["plan"]))
            with self.lock:
                r["findings"].extend(found)
        self._parallel(r, job, cancel)
        if not r["findings"]:
            raise RuntimeError("no tool brought a finding with a source")

    def _more(self, r: dict, groups: list[dict], cancel: threading.Event) -> None:
        prompt = research.more_prompt(r["question"], groups, research.seen_domains(r))
        rnd = r["round"]

        def job(tool: str) -> None:
            answer = self._call(r, tool, prompt, "search", True, cancel)
            found = research.parse_findings(answer, r["per_tool"].get(tool, {}).get("mind") or research.mind(tool),
                                            tool, rnd, len(r["plan"]))
            with self.lock:
                r["findings"].extend(found)
        self._parallel(r, job, cancel)

    def _debate(self, r: dict, cancel: threading.Event) -> None:
        sides = [g for pair in research.disputes(r) for g in pair]
        sides = list({g["id"]: g for g in sides}.values())
        for g in sides:
            g["sources"] = research.sources_of(r, g)
        prompt = research.debate_prompt(r["question"], sides)
        rnd = r["round"]

        def job(tool: str) -> None:
            answer = self._call(r, tool, prompt, "search", True, cancel)
            verdicts = research.parse_verdicts(answer, len(sides))
            mind = r["per_tool"].get(tool, {}).get("mind") or research.mind(tool)
            with self.lock:
                research.apply_verdicts(r, sides, verdicts, mind, tool, rnd)
        try:
            self._parallel(r, job, cancel)
        finally:
            for g in sides:
                g.pop("sources", None)
        research.check(r, self.min_models, self.min_domains)
        self.save(r)

    def _group(self, r: dict, cancel: threading.Event) -> None:
        """Group the findings (one light call; by their words when it fails) and check them."""
        self._status(r, "checking")
        live = [i for i, f in enumerate(r["findings"]) if not f.get("withdrawn")]
        findings = [r["findings"][i] for i in live]
        parsed = None
        if len(findings) > 1:
            try:
                parsed = research.parse_groups(self._call(r, self.main_tool(), research.group_prompt(
                    r["question"], findings), "check", False, cancel), len(findings))
            except (_Limit, InterruptedError):
                raise
            except Exception:
                parsed = None
        groups, conflicts = parsed or (research.group_by_rules(findings), [])
        research.regroup(r, [[live[i] for i in g] for g in groups], conflicts)
        research.check(r, self.min_models, self.min_domains)
        self.save(r)
        self.changed()

    def _after_cycle(self, r: dict) -> None:
        """Back on the town's thread: ask the person what stays disputed, else write the report."""
        with self.lock:
            self.running = None
        if r.get("error") or r.get("stopped") == "Stopped by Stop all":
            self._finish(r)
        elif research.disputes(r):
            r["waiting_since"] = self.clock().isoformat(timespec="seconds")
            self._status(r, "waiting")
            self.emit("mine.asked", f"{len(research.disputes(r))} disputed — {r['question']}", r["question"],
                      trail=tuple(r.get("trail") or ()), ref=r.get("ref", ""))
        else:
            self._finish(r)
        if not halt.stopped_since(self._halts):
            self._next()

    # -- the person decides (§6) --------------------------------------------------------------------

    def waiting(self) -> list[dict]:
        return [r for r in self.researches if r.get("status") == "waiting"]

    def orders_alert(self):
        for r in self.waiting():
            pairs = research.disputes(r)
            if not pairs:
                continue
            a, b = pairs[0]

            def side(g: dict) -> str:
                srcs = ", ".join(research.domain(s["url"]) for s in research.independent(research.sources_of(r, g))[:4])
                return f"{', '.join(research.minds_of(r, g))}: {g['claim']} ({srcs})"
            more = len(pairs) - 1
            return (f"{r['id']}:{a['id']}:{b['id']}", f"⛏️ Disputed: {r['question'][:80]}",
                    [side(a), "against", side(b)] + ([f"{more} more disputed after this one"] if more else []),
                    [("more", "Search more"), ("a", f"Accept: {a['claim'][:60]}"), ("b", f"Accept: {b['claim'][:60]}"),
                     ("keep", "Keep it disputed")])
        return None

    def answer_alert(self, key: str) -> str | None:
        """`key` is the answer to the first open question (`orders_alert`)."""
        alert = self.orders_alert()
        if alert is None:
            return None
        rid, a, b = alert[0].split(":")
        return self.decide(rid, int(a), int(b), "keep" if key == "dismiss" else key)

    def decide(self, rid: str, a: int, b: int, answer: str) -> str | None:
        """The person's answer on one dispute: accept a side, keep it disputed, or search more on it."""
        r = self.get(rid)
        if r is None:
            return None
        by = {g["id"]: g for g in r["groups"]}
        ga, gb = by.get(a), by.get(b)
        if ga is None or gb is None:
            return None
        if answer == "more":
            if self.left(r) <= 0:
                self.toast("This research's limit is spent", severity="warning")
                return None
            with self.lock:
                if self.running is not None:
                    self.toast("Another research runs — answer this one again when it is done", severity="warning")
                    return None
                self.running = r
            r["status"] = "round"
            self.save(r)
            self.cancel, self._halts = threading.Event(), halt.count()
            threading.Thread(target=self._more_on, args=(r, [ga, gb], self.cancel), daemon=True).start()
            self.changed()
            return None
        if answer in ("a", "b"):
            win, lose = (ga, gb) if answer == "a" else (gb, ga)
            win["decided"], lose["decided"] = "accept", "reject"
        else:
            ga["decided"] = gb["decided"] = "keep"
        research.check(r, self.min_models, self.min_domains)
        if not research.disputes(r):
            self._finish(r)
        else:
            self.save(r)
            self.changed()
        return None

    def _more_on(self, r: dict, groups: list[dict], cancel: threading.Event) -> None:
        try:
            r["round"] += 1
            self._more(r, groups, cancel)
            self._group(r, cancel)
        except _Limit as e:
            r["stopped"] = str(e) or self._limit_words(r)
        except InterruptedError:
            r["stopped"] = "Stopped by Stop all"
        except Exception as e:
            r["error"] = f"{type(e).__name__}: {e}"[:400]
        self.town.call(self._after_cycle, r)

    # -- the report (§7) ----------------------------------------------------------------------------

    def _finish(self, r: dict) -> None:
        prev = next((o for o in self.researches if o is not r and o.get("status") == "done"
                     and o.get("repeat") and o.get("repeat") == r.get("repeat")), None)
        if prev is not None:
            r["changes"] = research.changes(prev, r) or ["Nothing changed since the last time"]
        md = research.report(r) if not r.get("error") else f"# {r['question']}\n\n> **Failed:** {r['error']}\n"
        r["ended"] = self.clock().isoformat(timespec="seconds")
        r["counts"] = research.counts(r)
        r["sources"] = research.per_tool(r)
        try:
            self._file(r["id"], "md").write_text(md, encoding="utf-8")
        except OSError:
            pass
        r["status"] = "failed" if r.get("error") else "done"      # done only once its report is there to read
        quiet = prev is not None and r["changes"] == ["Nothing changed since the last time"]
        if not r.get("error") and not quiet:
            r["wiki_note"] = self._to_wiki(r, md)
        self.save(r)
        trail = tuple(r.get("trail") or ()) + (pipes.hop(self.building_id, "researcher", "agent",
                                                         cost=r.get("cost") or None,
                                                         outcome="error" if r.get("error") else "done",
                                                         since=r["created"], run=r["id"]),)
        c = r["counts"]
        if r.get("error"):
            self.emit("mine.failed", r["error"], r["question"], trail=trail, ref=r.get("ref", ""))
        else:
            value = r.get("wiki_note") or str(self._file(r["id"], "md").relative_to(self.repo_root))
            self.emit("mine.reported", value, f"{r['question'][:80]} · ✓ {c['confirmed']} ⚠ {c['disputed']}",
                      trail=trail, ref=r.get("ref", ""), want="know")
        if r.get("cost") or r.get("error"):
            delivery.ran(self.town, roads.HandlerRun(self.building_id, "researcher", "agent", r["id"], 0.0, 0.0,
                                                     outcome="error" if r.get("error") else "done",
                                                     error=r.get("error", ""), cost_usd=r.get("cost") or 0.0,
                                                     trail=trail, ref=r.get("ref", "")))
        self.changed()

    def wiki_id(self) -> str | None:
        """The Wiki its reports go to: its `wiki`, else the only one in the town; None for none."""
        named = self.config.get("wiki")
        if named == "":
            return None
        ids = [bid for bid, spec in self.town.custom_specs.items() if catalog.migrate(spec).get("type") == "scrolls"]
        if named in ids:
            return named
        return ids[0] if len(ids) == 1 else None

    def _to_wiki(self, r: dict, md: str) -> str:
        wid = self.wiki_id()
        w = self.town.worker(wid) if wid else None
        if w is None or not hasattr(w, "keep_file"):
            return ""
        try:
            return w.keep_file(f"research-{r['question']}", research.front_matter(r, self.clock()) + md, "research")
        except (ValueError, OSError) as e:
            self.toast(f"not kept in the Wiki: {e}", severity="warning")
            return ""

    # -- the clock: repeats and answers that did not come ------------------------------------------

    def tick(self, now: dt.datetime | None = None) -> None:
        from orkcraft.realm import watch
        now = now or self.clock()
        for r in self.waiting():                       # past `wait_answers`: out with what is left disputed
            since = dt.datetime.fromisoformat(r.get("waiting_since") or r["created"])
            if now - since >= span(str(self.config.get("wait_answers") or WAIT)):
                for a, b in research.disputes(r):
                    a["decided"] = b["decided"] = "keep"
                research.check(r, self.min_models, self.min_domains)
                self._finish(r)
        if not self._calendar():
            return
        for rep in self.repeats:
            expr, key = str(rep.get("every") or ""), repeat_key(rep)
            if not watch.schedule_ok(expr):
                continue
            last = self._repeats_done.get(key)
            since = dt.datetime.fromisoformat(last) if last else (self.last_tick or now)
            if watch.cron_due(expr, since, now):
                self._repeats_done[key] = now.isoformat(timespec="seconds")
                self._save_repeats()
                try:
                    self.ask(str(rep["question"]), limit=rep.get("limit"), trigger="repeat", repeat=key)
                except (ValueError, TypeError) as e:
                    self.toast(f"repeat not started: {e}", severity="warning")
        self.last_tick = now

    def _save_repeats(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "repeats.json").write_text(json.dumps(self._repeats_done), encoding="utf-8")
        except OSError:
            pass

    def _calendar(self) -> bool:
        """A repeat runs only in a town with a Calendar, where it shows (§8)."""
        return any(catalog.migrate(s).get("type") == "war_drum" for s in self.town.custom_specs.values())

    def set_repeat(self, question: str, every: str, limit: float | None = None) -> bool:
        """Repeat `question` on `every` (a Calendar schedule); an empty `every` stops repeating it."""
        from orkcraft.realm import watch
        question = " ".join((question or "").split())
        if not question:
            raise ValueError("Write the question")
        if every and not self._calendar():
            raise ValueError("A repeat shows on the Calendar — build a Calendar first")
        if every and not watch.schedule_ok(every):
            raise ValueError(f"Not a schedule: {every} (daily 09:00, weekly mon 09:00, every 6h, or a cron)")
        if "|" in question:
            raise ValueError("A question to repeat cannot hold |")
        rest = [research.repeat_line(r["every"], r["question"], r["limit"]) for r in self.repeats
                if r["question"] != question]
        if every:
            rest.append(research.repeat_line(every, question, float(limit) if limit else None))
        return self.save_config({"repeats": rest or None})

    # -- 🛑 and the hut ---------------------------------------------------------------------------

    def halt(self) -> int:
        if self.running is None:
            return 0
        self.cancel.set()
        return 1

    def status(self) -> str:
        if self.running is not None:
            return "WORKING"
        if self.researches and self.researches[0].get("status") == "failed":
            return "ERROR"
        return ""

    def quick_action(self, action_id: str) -> bool:
        return False


class _Limit(Exception):
    """The research's money is spent."""


def repeat_key(rep: dict) -> str:
    """A repeat's id: its question, in short."""
    return re.sub(r"\W+", "-", str(rep.get("question") or "").lower()).strip("-")[:60]
