"""The Catapult's eyes: the page snippets, the map of a form, the scout window and the browser profile."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable

from orkcraft.realm import halt


INSTALL_HINT = "Playwright is not installed — pip install 'orkcraft[browser]' && playwright install chromium"
WATCH_LIMIT_S = 15 * 60          # how long a scouting window may stay open
WATCH_TICK_S = 1.5
PRESS_TIMEOUT_S = 180            # fill and press
LEAVE_TIMEOUT_S = 60 * 60        # fill and wait for you to press and close the window
FINISHES = ("leave", "press")
FILLABLE = ("text", "textarea", "number", "email", "url", "tel", "date", "datetime-local", "time",
            "editable", "password", "search")

# Shared by the scout and the click recorder: labels, and selectors that survive a reload.
HELPERS_JS = r"""
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
"""

# Run in the page: every visible field and button.
SCOUT_JS = "() => {" + HELPERS_JS + r"""
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
  const links = [];
  for (const a of document.querySelectorAll('a[href], [role=link], [role=menuitem], [role=tab]')) {
    const text = clean(a.innerText || a.getAttribute('aria-label') || a.title);
    if (text && visible(a) && links.length < 60 && !a.closest('button'))
      links.push({ text, selector: selectorOf(a), role: a.getAttribute('role') || 'link', href: a.href || '' });
  }
  const login = [...document.querySelectorAll('input[type=password]')].some(visible);
  return { url: location.href, title: document.title, fields: fields.slice(0, 200), buttons, links, login };
}
"""

# Added to every page of a scouting window: each click on something that is not a field is told to
# the scout (`orkcraftClick`) as the role, name and selector it can be found by again.
CLICK_JS = "(() => {" + HELPERS_JS + r"""
  const FIELD = 'input:not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]), textarea, select, [contenteditable="true"], [role=textbox], [role=option]';
  const CLICKABLE = 'a, button, input[type=submit], input[type=button], summary, [role=button], [role=link], [role=menuitem], [role=tab], [role=treeitem], [role=checkbox], [role=radio], [role=switch]';
  const roleOf = el => { const r = el.getAttribute('role'); if (r) return r; const tag = el.tagName.toLowerCase();
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'button' || (tag === 'input' && ['submit', 'button'].includes(el.type))) return 'button';
    return ''; };
  document.addEventListener('click', e => {
    if (!e.isTrusted && !window.__orkcraftScripted) return;
    const t = e.target instanceof Element ? e.target : null;
    if (!t || t.closest('#orkcraft-scout') || t.closest(FIELD)) return;
    const el = t.closest(CLICKABLE) || t;
    const name = clean(el.getAttribute('aria-label') || el.innerText || el.value || el.title).slice(0, 80);
    if (!name || typeof window.orkcraftClick !== 'function') return;
    window.orkcraftClick({ role: roleOf(el), name, selector: selectorOf(el), url: location.href });
  }, true);
})();
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


def _signature(snap: dict) -> tuple:
    return tuple(sorted(f"{f.get('label')}|{f.get('selector')}" for f in snap.get("fields") or []))


def path_to_form(events: list[tuple], form_seen: float, fallback: str) -> tuple[str, list[dict]]:
    """From the scout's timeline — ("load", t, url) and ("click", t, info) — the page the form is
    reached from (the last page load before the form appeared) and the clicks made on it since."""
    start, clicks = fallback, []
    for kind, t, data in sorted(events, key=lambda e: e[1]):
        if t > form_seen:
            break
        if kind == "load":
            start, clicks = str(data), []
        elif kind == "click" and isinstance(data, dict):
            clicks.append({k: str(data.get(k) or "")[:300] for k in ("role", "name", "selector")})
    return start, clicks[-12:]


def scout(url: str, profile: Path, watch: bool = True, headless: bool = False,
          limit_s: float = WATCH_LIMIT_S, driver: Callable | None = None, need_fields: bool = True) -> dict:
    """Open `url` and mark its form. `watch`: the window stays open while the operator logs in and
    gets to the form; the last snapshot with fields before the window closes wins, and the clicks
    that led to it are kept (`start`, `path`). Without `watch` the page is marked once, after it
    loads. `driver(page, tick)` plays the operator (tests, scripted scouting). Raises RuntimeError
    when nothing can be marked — unless `need_fields` is off (a login window): then the last page
    seen comes back, fields or not."""
    if not url_ok(url):
        raise RuntimeError(f"page {url!r}: http or https only")
    try:
        from playwright.sync_api import Error as PwError, sync_playwright
    except ImportError as e:
        raise RuntimeError(INSTALL_HINT) from e
    ensure_profile(profile)
    best: dict | None = None
    last: dict = {}
    events: list[tuple] = []
    seen: dict[tuple, float] = {}
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(str(profile), headless=headless)
        except PwError as e:
            raise RuntimeError(f"the browser did not start: {str(e).splitlines()[0][:200]}") from e
        try:
            if watch:
                ctx.add_init_script(BANNER_JS)
                ctx.add_init_script(CLICK_JS)
                ctx.expose_binding("orkcraftClick", lambda source, info: events.append(("click", time.monotonic(), info)))

                def follow(pg) -> None:
                    pg.on("load", lambda pg: events.append(("load", time.monotonic(), pg.url)))

                ctx.on("page", follow)
                for pg in ctx.pages:
                    follow(pg)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            if not watch:
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except PwError:
                    pass
                best = page.evaluate(SCOUT_JS)
            else:
                end, tick, seen0 = time.monotonic() + limit_s, 0, halt.count()
                while time.monotonic() < end and ctx.pages:
                    halt.check(seen0)                   # 🛑 Halt All closes the window too
                    for pg in list(ctx.pages):
                        try:
                            snap = pg.evaluate(SCOUT_JS)
                        except PwError:
                            continue                     # navigating, or just closed
                        last = snap
                        if snap.get("fields"):
                            best = snap
                            seen.setdefault(_signature(snap), time.monotonic())
                    if driver is not None and ctx.pages:
                        try:
                            driver(ctx.pages[-1], tick)
                        except PwError:
                            pass
                    tick += 1
                    try:
                        ctx.pages[-1].wait_for_timeout(WATCH_TICK_S * 1000)
                    except (PwError, IndexError):
                        break
        finally:
            try:
                ctx.close()
            except PwError:
                pass
    if (not best or not best.get("fields")) and not need_fields:
        return dict(last or {"url": url}, fields=[], buttons=(last or {}).get("buttons") or [])
    if not best or not best.get("fields"):
        raise RuntimeError("no form fields were seen — open the form before closing the window")
    best["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    best["start"], best["path"] = best["url"], []
    if watch:
        best["start"], best["path"] = path_to_form(events, seen.get(_signature(best), time.monotonic()), url)
    return best


def path_text(page_map: dict) -> str:
    path = page_map.get("path") or []
    return " → ".join(str(c.get("name") or c.get("selector")) for c in path) if path else ""


# -- the plan -------------------------------------------------------------------------------------


# -- the profile stays out of the project's git ---------------------------------------------------

def ensure_profile(profile: Path) -> None:
    """Create the browser profile (it holds the login) and keep `.orkcraft/` out of the project's
    git: a line in the repository's own `info/exclude` (local, never committed) unless ignored."""
    profile.mkdir(parents=True, exist_ok=True)
    root = next((p for p in profile.parents if p.name == ".orkcraft"), None)
    repo = root.parent if root is not None else None
    if repo is None:
        return
    try:
        ignored = subprocess.run(["git", "check-ignore", "-q", str(profile)], cwd=repo, capture_output=True,
                                 timeout=10).returncode == 0
        if ignored:
            return
        rel = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=repo, capture_output=True,
                             text=True, timeout=10)
        if rel.returncode != 0:
            return
        exclude = (repo / rel.stdout.strip()).resolve()
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if ".orkcraft/" not in text.splitlines():
            exclude.write_text(text + ("" if text.endswith("\n") or not text else "\n")
                               + "# orkcraft's local state (the Catapult's browser login lives here)\n.orkcraft/\n",
                               encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        pass
