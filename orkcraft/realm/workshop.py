"""🛠 The Workshop: a building made from scratch, script-first.

Its logic is one script the Builder wrote and the operator approved, kept in the camp's own git:

    .orkcraft/scripts/<id>/main.py | main.sh       the script
    .orkcraft/blueprints/<id>/blueprint.json       the interview, the mock carts, the steward prompt

The contract — stdin: one cart as JSON {"event", "source", "title", "value"}; stdout: the result
(plain text, a JSON object shown as a card, or a JSON list of objects shown as a table); the exit
code says what happened:

    0  done              → workshop.done with the output
    3  ask the steward   → the steward prompt gets the cart and the script's output (a model call,
                           only when the blueprint has a steward prompt and never in the demo)
    4  alert             → workshop.alert with the output
    *  failed            → workshop.failed with the error

Scripts run with no shell: `python3 -I main.py` or `bash main.sh`, a timeout, and an environment
without orkcraft's own variables. The sandbox runs them in an empty temporary folder with a bare
environment, on the blueprint's mock carts, before the operator approves anything.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

RUNTIMES = {"python": (["python3", "-I"], "main.py"), "bash": (["bash"], "main.sh")}
LAYOUTS = ("log", "table", "card")
DONE, ESCALATE, ALERT = 0, 3, 4
RUN_TIMEOUT_S = 20
SANDBOX_TIMEOUT_S = 5
OUT_KEEP = 4000
SCRIPTS = Path(".orkcraft") / "scripts"
BLUEPRINTS = Path(".orkcraft") / "blueprints"


@dataclass
class Run:
    at: str
    event: str
    source: str
    input: str               # the cart's value (cut)
    code: int                # the exit code; -1 when it could not start or timed out
    out: str = ""
    err: str = ""
    ms: int = 0
    steward: str = ""        # the steward's answer, when the script asked for it

    @property
    def outcome(self) -> str:
        if self.code == DONE:
            return "done"
        if self.code == ALERT:
            return "alert"
        if self.code == ESCALATE:
            return "done" if self.steward else "escalated"
        return "failed"

    @property
    def ok(self) -> bool:
        return self.outcome in ("done", "alert", "escalated")

    @property
    def result(self) -> str:
        return self.steward or self.out


def cart(event: str, source: str, value: str, title: str = "") -> dict:
    return {"event": event, "source": source, "title": title, "value": value}


def script_path(repo_root: Path, building_id: str, runtime: str) -> Path:
    return repo_root / SCRIPTS / building_id / RUNTIMES.get(runtime, RUNTIMES["python"])[1]


def save_script(repo_root: Path, building_id: str, runtime: str, source: str) -> Path:
    path = script_path(repo_root, building_id, runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _, name in RUNTIMES.values():                    # one runtime at a time
        (path.parent / name).unlink(missing_ok=True)
    path.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
    return path


def load_script(repo_root: Path, building_id: str, runtime: str) -> str:
    try:
        return script_path(repo_root, building_id, runtime).read_text(encoding="utf-8")
    except OSError:
        return ""


def save_blueprint(repo_root: Path, building_id: str, blueprint: dict) -> Path:
    path = repo_root / BLUEPRINTS / building_id / "blueprint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in blueprint.items() if k != "script"}
    path.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_blueprint(repo_root: Path, building_id: str) -> dict:
    try:
        data = json.loads((repo_root / BLUEPRINTS / building_id / "blueprint.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _env(bare: bool, home: Path | None = None) -> dict:
    if bare:
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home or "/nonexistent"),
                "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    return {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}


def run(script: Path, runtime: str, the_cart: dict, cwd: Path, timeout_s: int = RUN_TIMEOUT_S,
        bare: bool = False) -> Run:
    """One run of the script on one cart. Never raises."""
    argv = [*RUNTIMES.get(runtime, RUNTIMES["python"])[0], str(script)]
    value = str(the_cart.get("value", ""))
    at = dt.datetime.now().isoformat(timespec="seconds")
    base = dict(at=at, event=str(the_cart.get("event", "")), source=str(the_cart.get("source", "")),
                input=value[:OUT_KEEP])
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, input=json.dumps(the_cart, ensure_ascii=False), cwd=str(cwd),
                              env=_env(bare, cwd if bare else None), capture_output=True, text=True,
                              timeout=timeout_s)
    except FileNotFoundError as e:
        return Run(**base, code=-1, err=f"{argv[0]} not found: {e}")
    except subprocess.TimeoutExpired:
        return Run(**base, code=-1, err=f"no answer within {timeout_s} s", ms=timeout_s * 1000)
    except OSError as e:
        return Run(**base, code=-1, err=str(e)[:300])
    ms = int((time.monotonic() - start) * 1000)
    return Run(**base, code=proc.returncode, out=proc.stdout.strip()[:OUT_KEEP], err=proc.stderr.strip()[:OUT_KEEP], ms=ms)


def sandbox(source: str, runtime: str, mocks: list[dict]) -> list[Run]:
    """The script on every mock cart, in an empty temporary folder with a bare environment."""
    with tempfile.TemporaryDirectory(prefix="orkcraft-sandbox-") as tmp:
        path = Path(tmp) / RUNTIMES.get(runtime, RUNTIMES["python"])[1]
        path.write_text(source, encoding="utf-8")
        return [run(path, runtime, m, Path(tmp), SANDBOX_TIMEOUT_S, bare=True) for m in mocks]


def check_syntax(source: str, runtime: str) -> str:
    """'' when the script parses, else why not."""
    if not source.strip():
        return "the script is empty"
    if runtime == "python":
        import ast
        try:
            ast.parse(source)
        except SyntaxError as e:
            return f"line {e.lineno}: {e.msg}"
        return ""
    if runtime == "bash":
        try:
            proc = subprocess.run(["bash", "-n"], input=source, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as e:
            return f"bash -n failed: {e}"
        return proc.stderr.strip()[:200] if proc.returncode else ""
    return f"unknown runtime {runtime!r}"


def steward_prompt(prompt: str, the_cart: dict, script_out: str, liked: list[str] | None = None) -> str:
    good = "".join(f"\n- {x[:500]}" for x in (liked or [])[:3])
    return (f"{prompt.strip()}\n\nTHE CART (JSON):\n{json.dumps(the_cart, ensure_ascii=False)[:4000]}\n\n"
            f"WHAT THE SCRIPT FOUND:\n{script_out[:2000]}\n\n"
            + (f"RESULTS THE OPERATOR LIKED (match their shape):{good}\n\n" if good else "")
            + "Answer with the result only.")


def shape(out: str) -> tuple[str, object]:
    """How an output shows: ("rows", [dict…]) · ("card", {…}) · ("text", str)."""
    try:
        data = json.loads(out)
    except (TypeError, ValueError):
        return "text", out
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        return "rows", data[:200]
    if isinstance(data, dict):
        return "card", data
    return "text", out


def log(state_dir: Path, r: Run) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def runs(state_dir: Path, limit: int = 50) -> list[Run]:
    try:
        lines = (state_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(Run(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out
