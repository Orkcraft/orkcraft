"""The Town Hall's audit: three agents look over the town — security, usability,
efficiency — by rules first, so an audit is free and instant and its findings are facts.

    Warder      (🛡 security)    recent denies / asks; secrets written into building settings
    Pathfinder  (🧭 usability)   buildings no road reaches or leaves, typed buildings that send
                                 nothing or miss required settings, huts without quick actions
    Treasurer   (🪙 efficiency)  the steward findings of every building, spend against the budget

A finding names its building, so the operator can jump there. The report is kept in
`.orkcraft/audit/latest.json`; the last one is what the Town Hall shows.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import catalog, council, steward

AUDIT_DIR = Path(".orkcraft") / "audit"
AGENTS = (("warder", "🛡", "Warder", "security"),
          ("pathfinder", "🧭", "Pathfinder", "usability"),
          ("treasurer", "🪙", "Treasurer", "efficiency"),
          ("peon", "⛏", "Peon", "housekeeping"))

# A setting that holds a secret instead of naming the variable that does.
_SECRET_KEY = re.compile(r"(pass|secret|token|api[_-]?key|private)", re.I)
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_TOKENISH = re.compile(r"(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})")


@dataclass
class Finding:
    agent: str           # warder | pathfinder | treasurer
    text: str
    building: str = ""   # the building to jump to
    severity: str = "info"   # info | warn | high


@dataclass
class Report:
    ts: str
    findings: list[Finding] = field(default_factory=list)

    def of(self, agent: str) -> list[Finding]:
        return [f for f in self.findings if f.agent == agent]

    def summary(self) -> str:
        parts = [f"{icon} {name}: {len(self.of(aid))}" for aid, icon, name, _ in AGENTS]
        return " · ".join(parts)

    def markdown(self) -> str:
        lines = [f"## Audit · {self.ts[:16].replace('T', ' ')}", ""]
        for aid, icon, name, area in AGENTS:
            lines.append(f"### {icon} {name} — {area}")
            found = self.of(aid)
            lines += [f"- {'⚠ ' if f.severity != 'info' else ''}{f.text}" for f in found] or ["- nothing found"]
            lines.append("")
        return "\n".join(lines)


def _security(repo_root: Path, specs: dict[str, dict]) -> list[Finding]:
    out = []
    events = council.warder_events(repo_root)
    denies = [e for e in events if e.decision == "deny"]
    if events:
        out.append(Finding("warder", f"{len(events)} guarded calls in the last day ({len(denies)} denied) — "
                                     f"latest: {events[0].reason}", severity="warn" if denies else "info"))
    for bid, spec in specs.items():
        spec = catalog.migrate(spec)
        cfg, kind = spec.get("config") or {}, spec.get("type")
        for step in cfg.get("steps") or [] if kind == "mill" else []:
            if str(step).startswith("script:"):
                out.append(Finding("warder", f"{spec.get('title', bid)}: runs a command — {str(step)[7:].strip()[:60]}", bid))
        if kind == "forge" and not cfg.get("test_cmd") and not cfg.get("confirm"):
            out.append(Finding("warder", f"{spec.get('title', bid)}: merges into the base without tests or a "
                                         "confirmation — set test_cmd, or c in the Forge", bid, "warn"))
        if kind == "catapult" and cfg.get("mode") == "browser" and cfg.get("finish") == "press" \
                and not cfg.get("schema") and not cfg.get("confirm"):
            forms = ", ".join(str(f).split("=")[0].strip() for f in cfg.get("forms") or [])[:60]
            out.append(Finding("warder", f"{spec.get('title', bid)}: presses submit on its forms ({forms}) "
                                         "unchecked and unasked — set schema, or c", bid, "warn"))
        elif kind == "catapult" and cfg.get("url") and not cfg.get("schema") and cfg.get("mode") != "browser":
            out.append(Finding("warder", f"{spec.get('title', bid)}: sends to {str(cfg['url'])[:40]} without a schema "
                                         "check — set schema", bid, "warn"))
        if kind == "barracks" and cfg.get("worktrees") is False:
            out.append(Finding("warder", f"{spec.get('title', bid)}: its orcs share the working tree and may "
                                         "overwrite each other — turn worktrees on", bid, "warn"))
        for key, value in cfg.items():
            vals = value if isinstance(value, list) else [value]
            for v in vals:
                if not isinstance(v, str):
                    continue
                # `password_env: MAIL_PASSWORD` names the variable; `password_env: hunter2` is the secret
                if _TOKENISH.search(v) or (_SECRET_KEY.search(key) and not _ENV_NAME.match(v)):
                    out.append(Finding("warder", f"{spec.get('title', bid)}: setting '{key}' looks like a secret "
                                                 "written in the spec — keep it in an environment variable",
                                       bid, "high"))
    return out


def _usability(scroll: ts.TownScroll, specs: dict[str, dict]) -> list[Finding]:
    out = []
    shown = [b for b in scroll.buildings_in(scroll.active_orkspace_id) if not b.demolished]
    if len(shown) > 12:                          # the Artisan's cognitive load
        out.append(Finding("pathfinder", f"{len(shown)} buildings on one canvas — split them into orkspaces (N)",
                           severity="warn"))
    connected = {b.id for b in shown if b.roads} | {r.source for b in shown for r in b.roads}
    for b in shown:
        if b.id == "town_hall":
            continue
        spec = specs.get(b.id)
        t = catalog.type_of(spec) if spec else None
        if b.id not in connected:
            out.append(Finding("pathfinder", f"{b.title}: no road reaches or leaves it — Y on a building links it", b.id))
        if t is None or t.id == catalog.DEFAULT_TYPE:
            continue
        if t.events and not catalog.events_of(spec):
            out.append(Finding("pathfinder", f"{b.title}: sends no events — nothing can follow it", b.id, "warn"))
        if t.actions and not catalog.quick_actions_of(spec):
            out.append(Finding("pathfinder", f"{b.title}: no quick action on its hut", b.id))
        missing = [k for k, (_, _, req) in t.config.items() if req and k not in (spec.get("config") or {})]
        if missing:
            out.append(Finding("pathfinder", f"{b.title}: settings missing: {', '.join(missing)}", b.id, "warn"))
    return out


def _efficiency(repo_root: Path, scroll: ts.TownScroll, spent_usd: float, limit_usd: float) -> list[Finding]:
    out = []
    if limit_usd > 0 and spent_usd >= 0.8 * limit_usd:
        out.append(Finding("treasurer", f"spent ${spent_usd:.2f} of ${limit_usd:.2f} this session",
                           severity="warn" if spent_usd < limit_usd else "high"))
    for b in scroll.buildings:
        report = steward.load_report(repo_root, b.id) or {}
        for f in report.get("findings", [])[:3]:
            out.append(Finding("treasurer", f"{b.title}: {f.get('summary') or f.get('kind', '')}", b.id))
        if report.get("proposals"):
            out.append(Finding("treasurer", f"{b.title}: the steward proposes {len(report['proposals'])} cheaper "
                                            "handler(s) — W there to review", b.id, "warn"))
    return out


def run(repo_root: Path, scroll: ts.TownScroll, specs: dict[str, dict], spent_usd: float = 0.0,
        limit_usd: float = 0.0, now: dt.datetime | None = None) -> Report:
    report = Report((now or dt.datetime.now()).isoformat(timespec="seconds"))
    report.findings += _security(repo_root, specs)
    report.findings += _usability(scroll, specs)
    report.findings += _efficiency(repo_root, scroll, spent_usd, limit_usd)
    report.findings += _housekeeping(repo_root, scroll)
    return report


def _housekeeping(repo_root: Path, scroll: ts.TownScroll) -> list[Finding]:
    """⛏ Peon: logs that grew, state of gone buildings, stale worktrees."""
    from orkcraft.realm import housekeeping
    chores = housekeeping.scan(repo_root, {b.id for b in scroll.buildings})
    out = [Finding("peon", f"{c.detail}: {c.path}", severity="warn" if c.size > housekeeping.LOG_LIMIT else "info")
           for c in chores[:10]]
    if chores:
        out.append(Finding("peon", f"{len(chores)} chore(s) — F10 → 🧹 Clean up"))
    return out


def save(repo_root: Path, report: Report) -> Path:
    path = repo_root / AUDIT_DIR / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ts": report.ts, "findings": [asdict(f) for f in report.findings]},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(repo_root: Path) -> Report | None:
    try:
        data = json.loads((repo_root / AUDIT_DIR / "latest.json").read_text(encoding="utf-8"))
        return Report(str(data["ts"]), [Finding(**f) for f in data.get("findings", [])])
    except (OSError, ValueError, KeyError, TypeError):
        return None
