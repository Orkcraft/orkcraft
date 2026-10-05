"""🚏 The Signpost's work: rules send what arrives down one of its roads, no model.

The rules (realm/signpost.py) are read top to bottom; the first that matches names the route, and the
cart goes on as `signpost.routed` with that route (each road from the Signpost waits for its own route).
No rule → `signpost.unmatched`. Every cart is kept in `.orkcraft/signpost/<id>/routes.jsonl`; `test`
says where a text would go without sending it.
"""
from __future__ import annotations

import json

from orkcraft.core.workers import Worker
from orkcraft.realm import jobs, pipes, signpost

KEEP = 100                  # carts the building shows
KEEP_LOG = 1000             # lines the log keeps (the counters count these)
HELP = ("route: contains text · route: matches regex · route: kind text|file|node · route: source building · "
        "route: event id · route: field == value · route: field != value · route: else")


class SignpostWorker(Worker):
    TYPE = "signpost"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.history: list[dict] = []        # newest first, up to KEEP
        self.counts: dict[str, int] = {}     # route ("" for no rule) → carts in the log

    @property
    def rules_text(self) -> list[str]:
        return [str(r) for r in (self.config.get("rules") or [])]

    @property
    def log_file(self):
        return self.state_dir / "routes.jsonl"

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        try:
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        if len(lines) > 2 * KEEP_LOG:                 # the log keeps its newest lines only
            lines = lines[-KEEP_LOG:]
            try:
                self.log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except OSError:
                pass
        lines = lines[-KEEP_LOG:]
        rows = []
        for line in lines:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        self.counts = {}
        for h in rows:
            self.counts[h.get("route") or ""] = self.counts.get(h.get("route") or "", 0) + 1
        self.history = list(reversed(rows))[:KEEP]
        self.changed()

    def status(self) -> str:
        return "ERROR" if signpost.rules_of(self.rules_text)[1] else ""

    # -- routing --------------------------------------------------------------------------------

    def test(self, text: str, title: str = "") -> dict:
        """Where `text` would go, sent nowhere: its route ("" for none) and the rule that picked it."""
        payload = pipes.Payload(pipes.TEXT, text, "test", "test", title)
        for i, line in enumerate(self.rules_text):
            rules, _ = signpost.rules_of([line])
            if rules and signpost.match(rules[0], payload):
                return {"route": rules[0].route, "rule": line, "index": i}
        return {"route": "", "rule": "", "index": -1}

    def receive(self, payload, title: str, markdown: str) -> None:
        rules, _ = signpost.rules_of(self.rules_text)
        route = signpost.route(rules, payload)
        rec = {"at": jobs.now_iso(), "route": route or "", "source": payload.source, "event": payload.mode,
               "title": payload.title or title, "value": payload.value[:4000]}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if route:                                     # the cart goes on: its trail and ref with it
            self.emit("signpost.routed", payload.value, route, trail=payload.trail, ref=payload.ref)
        else:
            self.emit("signpost.unmatched", payload.value, payload.title or title, trail=payload.trail, ref=payload.ref)
        self.refresh()

    def set_rules(self, lines: list[str]) -> bool:
        """The rules, one per line (checked like any spec: a rule that cannot be read is refused)."""
        if self.save_config({"rules": [ln.strip() for ln in lines if ln.strip()]}):
            self.changed()
            return True
        return False

    # -- the roads out --------------------------------------------------------------------------

    def roads_out(self) -> list[dict]:
        """Every road that leaves the post: its town-wide key, what it carries (`routes`, empty for every
        route; `unmatched` for the no-rule road) and how many carts of the log went its way."""
        from orkcraft.scroll import road_key
        out = []
        scroll = self.town.scroll
        for bs in (scroll.buildings if scroll is not None else []):
            if bs.demolished:
                continue
            for r in bs.roads:
                if r.source != self.building_id:
                    continue
                event = str(r.event or "")
                unmatched = event.startswith("signpost.unmatched")
                routes = [str(x) for x in ((r.filter or {}).get("route") or [])]
                if not routes and "#" in event:
                    routes = [event.split("#", 1)[1]]
                if unmatched:
                    count = self.counts.get("", 0)
                elif routes:
                    count = sum(self.counts.get(x, 0) for x in routes)
                else:
                    count = sum(n for k, n in self.counts.items() if k)
                out.append({"key": road_key(bs.id, r.id), "to": bs.id, "to_title": bs.title,
                            "routes": routes, "unmatched": unmatched, "count": count,
                            "label": r.label or ("no rule" if unmatched else ", ".join(routes) or "every route")})
        return out

    # -- the hut --------------------------------------------------------------------------------

    def hut_lines(self, widths: list[int]) -> list[str]:
        """Two boards on the post: where the last cart went, and how many routes there are.
        No rules and no carts yet → nothing, and the boards read DIS / WAY."""
        n = len(signpost.routes(self.rules_text))
        last = self.history[0]["route"] if self.history else ""
        if not n and not last:
            return []
        return [f"→{last}" if last else "—", f"{n} rt"]

    def mini_status(self) -> list[str]:
        routes = signpost.routes(self.rules_text)
        lines = [f"routes: {', '.join(routes)}" if routes else "no rules yet"]
        if self.history:
            h = self.history[0]
            lines.append(f"last → {h['route'] or '∅'}")
        return lines
