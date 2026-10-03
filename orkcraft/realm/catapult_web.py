"""🎯 The Catapult's browser mode: when a site has no API, the Catapult works its form instead.

    scout    a visible browser opens `page` with the camp's own profile (log in once — the login
             stays in `.orkcraft/catapult/<id>/profile`, outside the camp's git); you get to the
             form, the Catapult marks every field and button it sees; you close the window → the
             map is saved (`map.json`)
    plan     the cart's keys meet the map's fields: `fields` in the settings first
             ("Event name = title"), then the model's mapping (`m`, `mapping.json`), then plain
             name matching
    script   the plan becomes `fill.py` — a standalone Playwright script that reads the cart from
             stdin, opens the form, fills it and then either hands it to you (`finish: leave`, you
             press the button) or presses `submit` itself (`finish: press`). A script edited by
             hand is kept (`fill.sha` knows what the Catapult wrote)
    fire     `python fill.py` with the cart on stdin; its last stdout line is the summary

Playwright is optional: `pip install 'orkcraft[browser]'` (and `playwright install chromium`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

INSTALL_HINT = "Playwright is not installed — pip install 'orkcraft[browser]' && playwright install chromium"
WATCH_LIMIT_S = 15 * 60          # how long a scouting window may stay open
WATCH_TICK_S = 1.5
PRESS_TIMEOUT_S = 180            # fill and press
LEAVE_TIMEOUT_S = 60 * 60        # fill and wait for you to press and close the window
FINISHES = ("leave", "press")
FILLABLE = ("text", "textarea", "number", "email", "url", "tel", "date", "datetime-local", "time",
            "editable", "password", "search")

# Run in the page: every visible field and button, with a label and a selector that survives a reload.
SCOUT_JS = r"""
() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const unstable = id => /\d{3,}|^(mat|cdk|mdc)-|^:r|^ember\d|^react-/.test(id);
  const byIds = ids => clean((ids || '').split(/\s+/).map(i => { const n = document.getElementById(i);
    return n ? n.innerText || n.textContent : ''; }).join(' '));
  const labelOf = el => {
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    if (el.getAttribute('aria-labelledby')) { const t = byIds(el.getAttribute('aria-labelledby')); if (t) return t; }
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clean(l.innerText); }
    const wrap = el.closest('label'); if (wrap) return clean(wrap.innerText);
    if (el.placeholder) return clean(el.placeholder);
    if (el.title) return clean(el.title);
    return '';
  };
  const cssPath = el => { const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
      if (n.id && !unstable(n.id)) { parts.unshift('#' + CSS.escape(n.id)); break; }
      let i = 1; for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
      parts.unshift(`${n.tagName.toLowerCase()}:nth-of-type(${i})`);
    }
    return parts.join(' > '); };
  const selectorOf = el => {
    const one = q => { try { return document.querySelectorAll(q).length === 1 ? q : ''; } catch (e) { return ''; } };
    const tag = el.tagName.toLowerCase();
    return (el.id && !unstable(el.id) && one('#' + CSS.escape(el.id)))
      || (el.name && one(`${tag}[name="${CSS.escape(el.name)}"]`))
      || (el.getAttribute('aria-label') && one(`${tag}[aria-label="${CSS.escape(el.getAttribute('aria-label'))}"]`))
      || cssPath(el); };
  const kindOf = el => { const tag = el.tagName.toLowerCase(), role = el.getAttribute('role') || '';
    if (tag === 'select') return 'select';
    if (tag === 'textarea') return 'textarea';
    if (tag === 'input') return (el.type || 'text').toLowerCase();
    if (role === 'combobox' || role === 'listbox') return 'combobox';
    if (role === 'checkbox' || role === 'switch') return 'checkbox';
    if (role === 'radio') return 'radio';
    return 'editable'; };
  const fields = [], radios = {};
  const q = 'input, textarea, select, [contenteditable="true"], [role=textbox], [role=combobox], [role=checkbox], [role=switch], [role=radio]';
  for (const el of document.querySelectorAll(q)) {
    const kind = kindOf(el);
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(kind) || el.disabled) continue;
    if (kind !== 'file' && !visible(el)) continue;
    if (el.closest('[contenteditable="true"]') && el.getAttribute('contenteditable') !== 'true') continue;
    if (el.tagName === 'INPUT' && el.closest('[role=combobox]') && el.closest('[role=combobox]') !== el) continue;
    const label = labelOf(el);
    if (kind === 'radio') {
      const group = el.name || el.closest('[role=radiogroup]')?.getAttribute('aria-label') || label;
      const g = radios[group] || (radios[group] = { kind: 'radio', name: el.name || '', id: '', required: false,
        label: clean(el.closest('fieldset')?.querySelector('legend')?.innerText
                     || el.closest('[role=radiogroup]')?.getAttribute('aria-label') || el.name || label),
        selector: '', options: [], choices: [] });
      g.options.push(label || el.value); g.choices.push(selectorOf(el)); g.required ||= el.required;
      if (g.options.length === 1) fields.push(g);
      continue;
    }
    const options = kind === 'select' ? [...el.options].map(o => clean(o.text)).filter(Boolean).slice(0, 40) : [];
    fields.push({ kind, label, name: el.name || '', id: el.id || '', selector: selectorOf(el), options,
                  required: !!(el.required || el.getAttribute('aria-required') === 'true') });
  }
  const buttons = [];
  for (const b of document.querySelectorAll('button, input[type=submit], [role=button]')) {
    const text = clean(b.innerText || b.value || b.getAttribute('aria-label'));
    if (text && visible(b) && buttons.length < 40) buttons.push({ text, selector: selectorOf(b) });
  }
  return { url: location.href, title: document.title, fields: fields.slice(0, 200), buttons };
}
"""

# Shown in the scouting window, so the operator knows what the open browser is for.
BANNER_JS = r"""
(() => { const add = () => { if (document.getElementById('orkcraft-scout') || !document.body) return;
  const d = document.createElement('div'); d.id = 'orkcraft-scout';
  d.textContent = '🎯 Orkcraft is learning this page — log in, open the form, then close this window';
  d.style.cssText = 'position:fixed;z-index:2147483647;left:8px;bottom:8px;padding:6px 10px;border-radius:6px;'
    + 'background:#222;color:#fff;font:13px sans-serif;opacity:.85;pointer-events:none';
  document.body.appendChild(d); };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', add) : add(); })();
"""


def available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def url_ok(url: str) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


# -- the map --------------------------------------------------------------------------------------

def load_map(state_dir: Path) -> dict | None:
    try:
        m = json.loads((state_dir / "map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if isinstance(m, dict) and isinstance(m.get("fields"), list) else None


def save_map(state_dir: Path, page_map: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "map.json").write_text(json.dumps(page_map, ensure_ascii=False, indent=1), encoding="utf-8")


def scout(url: str, profile: Path, watch: bool = True, headless: bool = False,
          limit_s: float = WATCH_LIMIT_S) -> dict:
    """Open `url` and mark its form. `watch`: the window stays open while the operator logs in and
    gets to the form; the last snapshot with fields before the window closes wins. Without `watch`
    the page is marked once, after it loads. Raises RuntimeError when nothing can be marked."""
    if not url_ok(url):
        raise RuntimeError(f"page {url!r}: http or https only")
    try:
        from playwright.sync_api import Error as PwError, sync_playwright
    except ImportError as e:
        raise RuntimeError(INSTALL_HINT) from e
    profile.mkdir(parents=True, exist_ok=True)
    best: dict | None = None
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(str(profile), headless=headless)
        except PwError as e:
            raise RuntimeError(f"the browser did not start: {str(e).splitlines()[0][:200]}") from e
        try:
            if watch:
                ctx.add_init_script(BANNER_JS)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            if not watch:
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except PwError:
                    pass
                best = page.evaluate(SCOUT_JS)
            else:
                end = time.monotonic() + limit_s
                while time.monotonic() < end and ctx.pages:
                    for pg in list(ctx.pages):
                        try:
                            snap = pg.evaluate(SCOUT_JS)
                        except PwError:
                            continue                     # navigating, or just closed
                        if snap.get("fields"):
                            best = snap
                    try:
                        ctx.pages[-1].wait_for_timeout(WATCH_TICK_S * 1000)
                    except (PwError, IndexError):
                        break
        finally:
            try:
                ctx.close()
            except PwError:
                pass
    if not best or not best.get("fields"):
        raise RuntimeError("no form fields were seen — open the form before closing the window")
    best["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return best


# -- the plan -------------------------------------------------------------------------------------

@dataclass
class Step:
    field: dict
    path: str = ""             # a body path ("store.title", "images.0"), or
    literal: str | None = None  # a fixed value from the settings ('Category = "Major update"')
    by: str = "name"           # settings | model | name

    @property
    def label(self) -> str:
        return field_name(self.field)


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)       # body keys no field took
    unfilled: list[str] = field(default_factory=list)     # required fields nothing fills
    problems: list[str] = field(default_factory=list)     # settings lines that matched nothing


def field_name(f: dict) -> str:
    return str(f.get("label") or f.get("name") or f.get("id") or f.get("selector") or "?")


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", str(s).lower())


def _words(s: str) -> set[str]:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))
    return {w for w in re.split(r"[^0-9a-zа-яё]+", s.lower()) if len(w) > 1}


def leaves(body, prefix: str = "") -> dict[str, object]:
    """Every scalar of the body under its dotted path; a list of scalars stays one value."""
    if isinstance(body, dict):
        out: dict[str, object] = {}
        for k, v in body.items():
            out.update(leaves(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(body, list) and body and all(isinstance(x, dict) for x in body):
        out = {}
        for i, v in enumerate(body):
            out.update(leaves(v, f"{prefix}.{i}" if prefix else str(i)))
        return out
    return {prefix or "value": body}


def schema_paths(schema: dict, prefix: str = "") -> list[str]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return [prefix] if prefix else []
    out: list[str] = []
    for k, sub in props.items():
        out += schema_paths(sub, f"{prefix}.{k}" if prefix else str(k))
    return out


def pick(body, path: str):
    if path in ("", "value") and not isinstance(body, (dict, list)):
        return body
    cur = body
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def _find_field(fields: list[dict], name: str) -> int | None:
    name = name.strip()
    if name.startswith(("#", "[", "css:")):
        sel = name[4:].strip() if name.startswith("css:") else name
        return next((i for i, f in enumerate(fields) if f.get("selector") == sel), None)
    n = _norm(name)
    for key in ("label", "name", "id"):
        hit = next((i for i, f in enumerate(fields) if _norm(f.get(key, "")) == n and n), None)
        if hit is not None:
            return hit
    return next((i for i, f in enumerate(fields) if n and n in _norm(f.get("label", ""))), None)


def parse_rules(lines: list[str]) -> tuple[list[tuple[str, str | None, str | None]], list[str]]:
    """`Field = body.path` or `Field = "fixed text"` → (field, path, literal)."""
    rules, errors = [], []
    for line in lines or []:
        left, eq, right = str(line).partition("=")
        left, right = left.strip(), right.strip()
        if not eq or not left or not right:
            errors.append(f"{line!r}: say `Field label = body.path` or `Field label = \"text\"`")
            continue
        if len(right) >= 2 and right[0] == right[-1] and right[0] in "\"'":
            rules.append((left, None, right[1:-1]))
        else:
            rules.append((left, right, None))
    return rules, errors


def plan(page_map: dict, keys: list[str], rules: list[str] | None = None,
         model_mapping: dict | None = None) -> Plan:
    """Which field gets which body key. Settings first, then the model's mapping, then names."""
    fields = list(page_map.get("fields") or [])
    out, taken, used = Plan(), set(), set()
    parsed, out.problems = parse_rules(rules or [])
    for name, path, literal in parsed:
        i = _find_field(fields, name)
        if i is None:
            out.problems.append(f"{name!r}: no such field on the page")
            continue
        if i not in taken:
            out.steps.append(Step(fields[i], path or "", literal, "settings"))
            taken.add(i)
            used.add(path)
    for idx, path in (model_mapping or {}).items():
        i = int(idx) if str(idx).isdigit() else None
        if i is None or i >= len(fields) or i in taken or path not in keys or path in used:
            continue
        out.steps.append(Step(fields[i], path, None, "model"))
        taken.add(i)
        used.add(path)
    for path in keys:
        if path in used:
            continue
        last = path.split(".")[-1]
        best, score = None, 0
        for i, f in enumerate(fields):
            if i in taken:
                continue
            names = [f.get("label", ""), f.get("name", ""), f.get("id", "")]
            if any(_norm(x) and _norm(x) in (_norm(path), _norm(last)) for x in names):
                s = 3
            else:
                kw = _words(last) or _words(path)
                s = max((len(kw & _words(x)) for x in names), default=0)
                s = 2 if kw and s == len(kw) else 0
            if s > score:
                best, score = i, s
        if best is not None:
            out.steps.append(Step(fields[best], path, None, "name"))
            taken.add(best)
            used.add(path)
    out.unused = [k for k in keys if k not in used]
    out.unfilled = [field_name(f) for i, f in enumerate(fields) if f.get("required") and i not in taken]
    return out


def describe(p: Plan, body=None) -> str:
    """The plan as text, with the values when a body is given (the dry run)."""
    lines = []
    for s in p.steps:
        src = f'"{s.literal}"' if s.literal is not None else s.path
        val = "" if body is None or s.literal is not None else f"  ⇐ {str(pick(body, s.path))[:60]!r}"
        lines.append(f"  {s.label[:40]:<40} ← {src} ({s.by}){val}")
    out = ["fills:", *(lines or ["  nothing — load a cart, set a schema or map the fields"])]
    if p.unfilled:
        out.append("required, left empty: " + ", ".join(p.unfilled))
    if p.unused:
        out.append("not used: " + ", ".join(p.unused))
    if p.problems:
        out.append("settings: " + "; ".join(p.problems))
    return "\n".join(out)


# -- the model's mapping --------------------------------------------------------------------------

MAPPER = """You map data keys to the fields of a web form. The form's labels may be in any language.

FIELDS (index: kind, label, name, options):
{fields}

DATA KEYS (path: sample value):
{keys}

Answer with ONE JSON object and nothing else: {{"<field index>": "<data key path>", ...}}.
Map a key only when you are confident it belongs in that field; leave the rest out."""


def map_with_model(page_map: dict, body_sample: dict[str, object],
                   runner: Callable[[str], tuple[str, float | None]] | None = None) -> tuple[dict, float | None]:
    """One model call (the operator's Claude Code, in an empty folder): field index → key path."""
    from orkcraft.realm import builders
    runner = runner or builders.claude_runner
    fields = "\n".join(f"{i}: {f.get('kind')}, {f.get('label', '')!r}, {f.get('name', '')!r}"
                       + (f", {f['options'][:12]}" if f.get("options") else "")
                       for i, f in enumerate(page_map.get("fields") or []))
    keys = "\n".join(f"{k}: {str(v)[:60]!r}" for k, v in body_sample.items())
    text, cost = runner(MAPPER.format(fields=fields, keys=keys))
    got = builders.extract_json(text) or {}
    n = len(page_map.get("fields") or [])
    return {str(k): v for k, v in got.items()
            if str(k).isdigit() and int(k) < n and isinstance(v, str) and v in body_sample}, cost


def load_mapping(state_dir: Path) -> dict:
    try:
        m = json.loads((state_dir / "mapping.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return m if isinstance(m, dict) else {}


def save_mapping(state_dir: Path, mapping: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")


# -- the script -----------------------------------------------------------------------------------

SCRIPT = '''#!/usr/bin/env python3
"""Written by the orkcraft Catapult from the map of {url}
Fills the form with the cart from stdin, then {finish_text}.
Run by hand: python fill.py --profile <dir> [--press] [--headless] < cart.json
Edit it freely — the Catapult keeps a script edited by hand (rescouting writes fill.new.py instead)."""
import argparse, json, sys

from playwright.sync_api import Error, sync_playwright

PAGE = {page!r}
SUBMIT = {submit!r}
STEPS = {steps}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--press", action="store_true", help="press SUBMIT instead of handing the form over")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()
    body = json.loads(sys.stdin.read() or "null")
    filled, missed = [], []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(a.profile, headless=a.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(PAGE, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Error:
            pass
        for step in STEPS:
            value = step["literal"] if step["literal"] is not None else pick(body, step["path"])
            if value is None:
                missed.append(f"{{step['label']}}: no value at {{step['path']!r}}")
                continue
            try:
                put(page, step, value)
                filled.append(step["label"])
            except Exception as e:
                missed.append(f"{{step['label']}}: {{str(e).splitlines()[0][:120]}}")
        pressed = False
        if a.press and SUBMIT and not missed:
            page.get_by_role("button", name=SUBMIT, exact=True).first.click()
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Error:
                pass
            pressed = True
        summary = {{"filled": filled, "missed": missed, "pressed": pressed, "url": page.url, "title": page.title()}}
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if not a.press and not a.headless:
            try:                                   # the form is yours now: press it, then close the window
                page.wait_for_event("close", timeout=0)
            except Error:
                pass
        ctx.close()
    sys.exit(0 if not missed and (pressed or not a.press) else 2)


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
    return SCRIPT.format(url=page_map.get("url", ""), page=str(page_map.get("url", "")), submit=submit,
                         steps=steps, finish_text=finish_text)


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
               timeout: float | None = None) -> Result:
    """Run fill.py with the cart on stdin. Blocking: call from a worker thread."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}
    cmd = [sys.executable, str(script), "--profile", str(profile),
           *(["--press"] if press else []), *(["--headless"] if headless else [])]
    try:
        proc = subprocess.run(cmd, input=json.dumps(body, ensure_ascii=False), capture_output=True, text=True,
                              env=env, cwd=str(script.parent),
                              timeout=timeout or (PRESS_TIMEOUT_S if press else LEAVE_TIMEOUT_S))
    except subprocess.TimeoutExpired:
        return Result(False, -1, {}, "", "the script ran out of time")
    except OSError as e:
        return Result(False, -1, {}, "", str(e)[:300])
    summary = {}
    for line in reversed(proc.stdout.strip().splitlines()):
        try:
            summary = json.loads(line)
            break
        except ValueError:
            continue
    err = proc.stderr.strip()
    if "No module named 'playwright'" in err:
        err = INSTALL_HINT
    elif err:
        err = err.splitlines()[-1][:300]
    return Result(proc.returncode == 0, proc.returncode, summary if isinstance(summary, dict) else {},
                  proc.stdout[-2000:], err)
