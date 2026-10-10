"""🧪 The Test bench's reviews and written cases (docs/design/test-bench.md §3–6): agents read a building's own code and
say what they would change, each from its role, and one writes a test case when asked.

    bench_review.ROLES["ux"]                         who reviews a tab: (id, title, what they look at)
    bench_review.review(root, "barracks", "ux", role, tool, runner)    one role's findings, kept in the tab's file
    bench_review.load(root, "barracks", "ux")        the tab's last review: {at, version, tool, roles: {role: …}}
    bench_review.write_case(root, "barracks", brief, tool, runner)     a new case, not read yet (`reviewed: false`)
    bench_review.findings(root, "barracks")          every finding of every tab, with its id, for Make tasks

The agents only read (`jobs.run_read`), in Orkcraft's own source, and answer in JSON. A finding is advice: it
becomes a task only when the operator ticks it and presses Make tasks (gui/bench.py).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from pathlib import Path

import orkcraft
from orkcraft.realm import bench, catalog, jobs, lexicon

REVIEWS = bench.BENCH / "reviews"
TABS = ("tech", "ux", "product")
SEVERITIES = ("high", "medium", "low")
ROLES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "tech": (
        ("architect", "Architect",
         "how the building's work is split between its steward and its orks, its state, what fails and how it "
         "recovers, what breaks with many tasks at once, and what keeps it apart from the operator's project"),
        ("ai_engineer", "AI engineer",
         "the prompts its steward and orks get, the AI tools and model tiers they run on, the context they are "
         "given again or reuse, retries and reworks, tokens and spend: concrete changes to prompts and settings"),
        ("ai_researcher", "AI researcher",
         "how to show it does better than the bare AI tool: which test cases and checks would tell, what the "
         "current ones miss or reward by chance, how many runs a comparison needs, which numbers to watch"),
    ),
    "ux": (
        ("product_manager", "Product manager",
         "whether a person understands why the building exists and what each step is for, along the whole way: "
         "the build menu, its setup, its Work and Info, its quick actions; where a person stops and wonders"),
        ("product_designer", "Product designer",
         "labels, empty states, the number of decisions and fields before the first result, what each button "
         "costs or risks and whether it says so, and consistency with the rest of the town"),
    ),
    "product": (
        ("product_manager", "Product manager",
         "the AHA moment: the first time a person sees why the building is worth having, in their first session "
         "with it; how soon it comes, what stands in its way"),
        ("architect", "Architect",
         "what must be built or changed so that the AHA moment happens in the first session for everyone, what "
         "it costs and what could go wrong"),
    ),
}
TAB_GOALS = {
    "tech": "Review the building as an engineer would before trusting it with real work.",
    "ux": "Review the building's whole flow for a person who has never used it: there should be no strain "
          "anywhere from building it to using it every day.",
    "product": "Find the building's AHA moment and make sure it happens in the first session.",
}
WORDING = ("The interface writes ork / orks / orkestration, never orc or orchestration. Labels, settings and "
           "anything about money or safety say plainly what happens; only the Warchief's lines, growth news and "
           "the onboarding may joke. A building's words are its today's word (realm/lexicon.py TERMS); old Camp "
           "spellings stay only in code.")
_JSON = re.compile(r"\{.*\}", re.S)


def source_dir() -> Path:
    """Where the agents read: the Orkcraft checkout when this runs from one (its docs too), else the package."""
    pkg = Path(orkcraft.__file__).resolve().parent
    return pkg.parent if (pkg.parent / "docs" / "design").is_dir() else pkg


def _files(type_id: str, base: Path) -> list[str]:
    pkg = Path(orkcraft.__file__).resolve().parent
    found = [*pkg.glob(f"core/workers/{type_id}*.py"), *pkg.glob(f"realm/{type_id}*.py"),
             *pkg.glob(f"gui/views/{type_id}*.py"), *pkg.glob(f"gui/static/js/buildings/{type_id}*.*"),
             pkg / "realm" / "catalog.py", pkg / "realm" / "lexicon.py", pkg / "gui" / "static" / "js" / "build.js",
             pkg / "gui" / "static" / "js" / "console.js"]
    docs = base / "docs" / "design"
    if docs.is_dir():
        word = type_id.split("_")[0]
        found += [p for p in docs.glob("*.md") if word in p.name] + [docs / "building-views.md"]
    return sorted({str(p.relative_to(base)) for p in found if p.is_file()})


def context(root: Path, type_id: str) -> str:
    """What every reviewer is told about the building: its name, what it is, its settings and actions."""
    t = catalog.TYPES.get(type_id)
    if t is None:
        return f"Building type `{type_id}`."
    actions = ", ".join(a.label for a in t.actions) or "none"
    return (f"The building: **{lexicon.term(type_id)}** (type id `{type_id}`, code name {t.title}).\n"
            f"What it is: {t.summary}\nIts settings: {', '.join(t.config) or 'none'}.\nIts actions: {actions}.\n"
            f"Agents do its work: {'yes' if t.agentic else 'no, it is code'}.")


def _last_run(root: Path, type_id: str) -> str:
    kept = bench.runs(root, type_id)
    return bench.render(kept[0], lexicon.term(type_id)) if kept else "No Test bench run yet."


def prompt(root: Path, type_id: str, tab: str, role: str) -> str:
    rid, title, focus = next(r for r in ROLES[tab] if r[0] == role)
    base = source_dir()
    aha = ('\n  "aha": {"moment": "…", "script": ["step 1", "step 2", "…"], "measure": "…", "time_to_it": "…"},'
           if tab == "product" else "")
    run = f"\n\n## The last Test bench run\n\n{_last_run(root, type_id)}" if tab == "tech" else ""
    return f"""You are the {title} of Orkcraft, a town of AI agents drawn as a strategy game. {TAB_GOALS[tab]}

{context(root, type_id)}

You look at {focus}.

Read the code and the design notes before you judge; the ones about this building:
{chr(10).join('- ' + f for f in _files(type_id, base))}
Wording rules of the product: {WORDING}{run}

Answer with JSON only, no other text:
{{{aha}
  "findings": [
    {{"title": "a short imperative line: what to change", "detail": "why, and what exactly to do",
      "severity": "high | medium | low", "where": "the file, the screen or the step"}}
  ]
}}
At most 8 findings, the most important first. A finding is something to change, never praise."""


def parse(text: str) -> dict:
    """The answer's JSON, cleaned: findings with a title, a known severity; the AHA when there is one."""
    m = _JSON.search(text or "")
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    out: dict = {"findings": []}
    for f in data.get("findings") or []:
        if isinstance(f, dict) and str(f.get("title") or "").strip():
            sev = str(f.get("severity") or "").lower()
            out["findings"].append({"title": str(f["title"]).strip()[:200], "detail": str(f.get("detail") or "")[:2000],
                                    "severity": sev if sev in SEVERITIES else "medium",
                                    "where": str(f.get("where") or "")[:200]})
    aha = data.get("aha")
    if isinstance(aha, dict) and aha.get("moment"):
        script = aha.get("script") or []
        out["aha"] = {"moment": str(aha["moment"])[:600],
                      "script": [str(s)[:300] for s in script][:10] if isinstance(script, list) else [str(script)],
                      "measure": str(aha.get("measure") or "")[:300], "time_to_it": str(aha.get("time_to_it") or "")[:100]}
    return out


# -- the tab's file -----------------------------------------------------------------------------------------

_LOCK = threading.Lock()


def path_of(root: Path, type_id: str, tab: str) -> Path:
    return root / REVIEWS / type_id / f"{tab}.json"


def load(root: Path, type_id: str, tab: str) -> dict:
    try:
        data = json.loads(path_of(root, type_id, tab).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def put(root: Path, type_id: str, tab: str, role: str, entry: dict, tool: str = "", fresh: bool = False) -> dict:
    """One role's entry in the tab's file (`fresh`: a new review, the other roles' old entries go)."""
    with _LOCK:
        data = {} if fresh else load(root, type_id, tab)
        data.update(tab=tab, at=dt.datetime.now().isoformat(timespec="seconds"), version=orkcraft.__version__)
        if tool:
            data["tool"] = tool
        data.setdefault("roles", {})[role] = entry
        path = path_of(root, type_id, tab)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return data


def review(root: Path, type_id: str, tab: str, role: str, tool: str = "main", runner=None,
           cancel: threading.Event | None = None) -> dict:
    """One role reads the building and answers; its entry is kept in the tab's file and returned."""
    title = next(r[1] for r in ROLES[tab] if r[0] == role)
    start = time.monotonic()
    entry: dict = {"title": title, "status": "done", "error": "", "findings": [], "cost": 0.0, "tokens": 0}
    try:
        text, cost, tokens, _ = (runner or jobs.run_read)(tool, prompt(root, type_id, tab, role), source_dir(),
                                                           cancel or threading.Event(), "")
        entry.update(parse(text), cost=round(float(cost or 0.0), 4), tokens=int(tokens or 0))
        if not entry["findings"] and not entry.get("aha"):
            entry.update(status="failed", error="the answer had no findings: " + (text or "")[:300])
    except (RuntimeError, OSError) as e:
        entry.update(status="failed", error=str(e)[:500] or type(e).__name__)
    entry["seconds"] = round(time.monotonic() - start, 1)
    put(root, type_id, tab, role, entry, tool)
    return entry


def findings(root: Path, type_id: str) -> list[dict]:
    """Every finding of the type's reviews, each with its id (`tab:role:n`), its tab and who found it."""
    out = []
    for tab in TABS:
        for role, entry in (load(root, type_id, tab).get("roles") or {}).items():
            for n, f in enumerate(entry.get("findings") or []):
                out.append({**f, "id": f"{tab}:{role}:{n}", "tab": tab, "role": entry.get("title") or role})
    return out


# -- a written case -----------------------------------------------------------------------------------------

def case_prompt(root: Path, type_id: str, brief: str) -> str:
    have = ", ".join(c.id for c in bench.cases(root, type_id)) or "none"
    shipped = json.dumps(next(iter(bench.bench_cases_of(type_id)), {}), ensure_ascii=False)[:3000]
    return f"""You write a test case for Orkcraft's Test bench. It gives the same task to the building and to the bare AI
tool on the same model, then runs the case's check on each result.

{context(root, type_id)}

The cases it has: {have}. A shipped one, for its shape: {shipped}

{('What the operator wants the case to test: ' + brief) if brief.strip() else 'Write a case the current ones do not cover, where the building should do better than the bare AI tool.'}

Rules: `files` is the whole small project (a few files, standard library only); `check` is a shell command run in the
result's tree that exits 0 only when the task is done right, and fails when the tests the case came with were
changed (`git diff --quiet $(git rev-list --max-parents=0 HEAD) -- tests && …`); `expect` says in words what a good
result has. Answer with the case's JSON only:
{{"id": "short-id", "title": "…", "task": "…", "files": {{"path": "content"}}, "check": "…", "expect": "…"}}"""


def write_case(root: Path, type_id: str, brief: str = "", tool: str = "main", runner=None,
               cancel: threading.Event | None = None) -> bench.Case:
    """An agent writes a case; it is kept in the town's cases, not read yet, so it does not count until the
    operator has read it. Raises RuntimeError when the answer is not a case."""
    text, _cost, _tokens, _ = (runner or jobs.run_read)(tool, case_prompt(root, type_id, brief), source_dir(),
                                                        cancel or threading.Event(), "")
    m = _JSON.search(text or "")
    try:
        data = json.loads(m.group(0)) if m else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or not data.get("task"):
        raise RuntimeError("the agent's answer was not a case: " + (text or "")[:300])
    case = bench.Case.of({**data, "reviewed": False}, type_id)
    taken = {c.id for c in bench.cases(root, type_id)}
    base, n = case.id, 2
    while case.id in taken:
        case.id, n = f"{base}-{n}", n + 1
    bench.save_case(root, case)
    return case
