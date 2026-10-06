"""The script: the plan becomes `fill.py`, a standalone Playwright script, and runs with the cart."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orkcraft.realm import halt
from orkcraft.realm.catapult_web.planning import Plan, Step
from orkcraft.realm.catapult_web.scouting import INSTALL_HINT, LEAVE_TIMEOUT_S, PRESS_TIMEOUT_S, SCOUT_JS, ensure_profile


# -- the script -----------------------------------------------------------------------------------

SCRIPT = '''#!/usr/bin/env python3
"""Written by the orkcraft Catapult from the map of {url}
Fills the form with the cart from stdin, then {finish_text}.
Run by hand: python fill.py --profile <dir> [--press] [--headless] < cart.json
Edit it freely — the Catapult keeps a script edited by hand (rescouting writes fill.new.py instead)."""
import argparse, json, os, sys

from playwright.sync_api import Error, sync_playwright

PAGE = {page!r}
START = {start!r}          # where the form is reached from, when PAGE alone does not show it
PATH = {path}
SUBMIT = {submit!r}
STEPS = {steps}
SCOUT_JS = {scout_js!r}


def pick(body, path):
    cur = body
    for part in (path.split(".") if path else []):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def locate(page, step):
    if step["label"]:
        loc = page.get_by_label(step["label"], exact=True)
        if loc.count() == 1:
            return loc
    return page.locator(step["selector"]).first


def settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Error:
        pass


def shows_form(page, timeout=5000):
    if not STEPS:
        return True
    step = STEPS[0]
    loc = page.locator(step["choices"][0]).first if step["kind"] == "radio" and step["choices"] else locate(page, step)
    try:
        loc.wait_for(state="attached", timeout=timeout)
        return True
    except Error:
        return False


def click(page, c):
    tries = []
    if c["role"] and c["name"]:
        tries.append(page.get_by_role(c["role"], name=c["name"], exact=True))
    if c["name"]:
        tries.append(page.get_by_text(c["name"], exact=True))
    if c["selector"]:
        tries.append(page.locator(c["selector"]))
    for i, loc in enumerate(tries):
        try:
            loc.first.click(timeout=10000 if i == 0 else 3000)
            return
        except Error:
            continue
    raise RuntimeError(f"could not click {{c['name'] or c['selector']!r}} on the way to the form")


class LoginNeeded(Exception):
    pass


def host(url):
    return url.split("/")[2] if url.count("/") >= 2 else url


def check_login(page):
    """Sent to a login page (another host, or a password field): the operator must log in again."""
    try:
        password = page.locator("input[type=password]").first.is_visible(timeout=500)
    except Error:
        password = False
    if host(page.url) != host(PAGE) or password:
        raise LoginNeeded(f"a login page: {{page.url[:120]}}")


def reach(page):
    """Open the form: its address, or the start page and the clicks that lead to it."""
    page.goto(PAGE, wait_until="domcontentloaded")
    settle(page)
    check_login(page)
    if not PATH or shows_form(page):
        return
    page.goto(START, wait_until="domcontentloaded")
    settle(page)
    check_login(page)
    for c in PATH:
        click(page, c)
        settle(page)
    if not shows_form(page, 15000):
        raise RuntimeError("the clicks did not open the form — scout the page again")


def put(page, step, value):
    kind = step["kind"]
    if kind == "radio":
        i = next((i for i, o in enumerate(step["options"]) if o.strip().lower() == str(value).strip().lower()), None)
        if i is None:
            raise ValueError(f"no option {{value!r}}")
        page.locator(step["choices"][i]).first.check()
        return
    loc = locate(page, step)
    if kind in ("checkbox", "switch"):
        loc.set_checked(str(value).lower() not in ("", "0", "false", "no", "none"))
    elif kind == "select":
        try:
            loc.select_option(label=str(value))
        except Error:
            loc.select_option(value=str(value))
    elif kind == "combobox":
        loc.click()
        page.get_by_role("option", name=str(value), exact=True).first.click()
    elif kind == "file":
        loc.set_input_files([str(v) for v in value] if isinstance(value, list) else str(value))
    else:
        loc.fill(", ".join(map(str, value)) if isinstance(value, list) else str(value))


def look(page):
    """The page as it is now (its fields and buttons): what the overseer repairs from."""
    try:
        return page.evaluate(SCOUT_JS)
    except Exception:
        return {{"url": page.url}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--press", action="store_true", help="press SUBMIT instead of handing the form over")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--check", action="store_true", help="only reach the form and find every field")
    a = ap.parse_args()
    body = json.loads(sys.stdin.read() or "null")
    filled, missed, broken = [], [], []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(a.profile, headless=a.headless or a.check)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def report(pressed=False, code=0):
            summary = {{"filled": filled, "missed": missed, "broken": broken, "pressed": pressed,
                        "url": page.url, "title": page.title()}}
            if broken:
                summary["page"] = look(page)
            if os.environ.get("CATAPULT_SCREEN"):          # the Catapult keeps a picture of the page
                try:
                    page.screenshot(path=os.environ["CATAPULT_SCREEN"])
                except Error:
                    pass
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            return code

        try:
            reach(page)
        except LoginNeeded as e:
            print(json.dumps({{"filled": [], "missed": [], "broken": [], "login": str(e), "pressed": False,
                              "url": page.url, "title": page.title()}}, ensure_ascii=False), flush=True)
            ctx.close()
            sys.exit(4)
        except Exception as e:
            broken.append(str(e).splitlines()[0][:200])
            report()
            ctx.close()
            sys.exit(3)
        if a.check:
            for step in STEPS:
                loc = (page.locator(step["choices"][0]) if step["kind"] == "radio" and step["choices"]
                       else locate(page, step))
                (filled if loc.count() else broken).append(step["label"] + ("" if loc.count() else ": not found"))
            if SUBMIT and not page.get_by_role("button", name=SUBMIT, exact=True).count():
                broken.append(f"button {{SUBMIT!r}}: not found")
            code = report(code=0 if not broken else 2)
            ctx.close()
            sys.exit(code)
        for step in STEPS:
            value = step["literal"] if step["literal"] is not None else pick(body, step["path"])
            if value is None:
                missed.append(f"{{step['label']}}: no value at {{step['path']!r}}")
                continue
            try:
                put(page, step, value)
                filled.append(step["label"])
            except Exception as e:
                broken.append(f"{{step['label']}}: {{str(e).splitlines()[0][:120]}}")
        pressed = False
        if a.press and SUBMIT and not missed and not broken:
            try:
                page.get_by_role("button", name=SUBMIT, exact=True).first.click(timeout=15000)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Error:
                    pass
                pressed = True
            except Error as e:
                broken.append(f"button {{SUBMIT!r}}: {{str(e).splitlines()[0][:120]}}")
        report(pressed)
        if not a.press and not a.headless and not broken:
            try:                                   # the form is yours now: press it, then close the window
                page.wait_for_event("close", timeout=0)
            except Error:
                pass
        ctx.close()
    sys.exit(0 if not missed and not broken and (pressed or not a.press) else 2)


if __name__ == "__main__":
    main()
'''


def _step_data(s: Step) -> dict:
    f = s.field
    return {"label": str(f.get("label") or ""), "selector": str(f.get("selector") or ""),
            "kind": str(f.get("kind") or "text"), "options": list(f.get("options") or []),
            "choices": list(f.get("choices") or []), "path": s.path, "literal": s.literal}


def script_text(page_map: dict, p: Plan, submit: str = "", finish: str = "leave") -> str:
    steps = "[\n" + "".join(f"    {_step_data(s)!r},\n" for s in p.steps) + "]"
    finish_text = (f"presses {submit!r}" if finish == "press" and submit
                   else "hands the form to you: press the button yourself and close the window")
    path = "[\n" + "".join(f"    {dict(role=c.get('role', ''), name=c.get('name', ''), selector=c.get('selector', ''))!r},\n"
                            for c in page_map.get("path") or []) + "]"
    return SCRIPT.format(url=page_map.get("url", ""), page=str(page_map.get("url", "")),
                         start=str(page_map.get("start") or page_map.get("url", "")), path=path, submit=submit,
                         steps=steps, finish_text=finish_text, scout_js=SCOUT_JS)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def edited_by_hand(state_dir: Path) -> bool:
    script, mark = state_dir / "fill.py", state_dir / "fill.sha"
    try:
        return _sha(script.read_text(encoding="utf-8")) != mark.read_text(encoding="utf-8").strip()
    except OSError:
        return script.exists()


def write_script(state_dir: Path, text: str) -> Path:
    """Write fill.py — or fill.new.py beside a fill.py the operator edited by hand."""
    state_dir.mkdir(parents=True, exist_ok=True)
    if edited_by_hand(state_dir):
        target = state_dir / "fill.new.py"
        target.write_text(text, encoding="utf-8")
        return target
    (state_dir / "fill.py").write_text(text, encoding="utf-8")
    (state_dir / "fill.sha").write_text(_sha(text), encoding="utf-8")
    return state_dir / "fill.py"


@dataclass
class Result:
    ok: bool
    code: int
    summary: dict
    out: str
    err: str = ""


def run_script(script: Path, profile: Path, body, press: bool, headless: bool = False,
               timeout: float | None = None, check: bool = False,
               on_start: Callable[[subprocess.Popen], None] | None = None, screen: Path | None = None) -> Result:
    """Run fill.py with the cart on stdin (`check`: only reach the form and find its fields).
    `on_start` gets the process (🛑 Halt All kills it); `screen`, where the page's picture goes when
    it is done (a script edited by hand may not take one). Blocking: call from a worker thread."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}
    if screen is not None:
        screen.parent.mkdir(parents=True, exist_ok=True)
        env["CATAPULT_SCREEN"] = str(screen)
    cmd = [sys.executable, str(script), "--profile", str(profile), *(["--press"] if press else []),
           *(["--headless"] if headless else []), *(["--check"] if check else [])]
    ensure_profile(profile)
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env, cwd=str(script.parent), start_new_session=True)
    except OSError as e:
        return Result(False, -1, {}, "", str(e)[:300])
    if on_start is not None:
        on_start(proc)
    try:
        with halt.running(proc):                      # its browser is in its process group: Halt All kills both
            out, err_text = proc.communicate(json.dumps(body, ensure_ascii=False),
                                             timeout=timeout or (PRESS_TIMEOUT_S if press or check else LEAVE_TIMEOUT_S))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return Result(False, -1, {}, "", "the script ran out of time")
    except halt.Halted:
        return Result(False, -1, {}, "", "stopped by Halt All")
    summary = {}
    out, err_text = out or "", err_text or ""
    for line in reversed(out.strip().splitlines()):
        try:
            summary = json.loads(line)
            break
        except ValueError:
            continue
    err = err_text.strip()
    if "No module named 'playwright'" in err:
        err = INSTALL_HINT
    elif err:
        err = err.splitlines()[-1][:300]
    return Result(proc.returncode == 0, proc.returncode, summary if isinstance(summary, dict) else {},
                  out[-2000:], err)
