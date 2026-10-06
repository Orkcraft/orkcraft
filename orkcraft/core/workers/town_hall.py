"""🏰 Town Hall's work: the town's way in, without a face.

- **The hall** (`hall()`): its agents and what the last audit found, the Elders' judgements, the
  Council's Fast Path, 👍 / 👎 of the stewards, the retros' proposals — plain data each face draws
  (the TUI's `screens/town_hall.py`, the GUI's `gui/views/town_hall.py`). `audit()` runs the hall's
  three agents over the town (rules, no model call) and sends `hall.audit_done` down its roads.
- **The Warchief** (`ask(text, about)`): the hall's lead ork answers the person in a chat — what the
  town is, what to build, how — one model call per question in a thread (`runners.WARCHIEF_RUNNER`,
  else the Claude CLI). It does not build: an answer that asks for work gives it to a specialist and
  carries a card (core/warchief.py): the Town Builder's plan (made here, in a thread, then the Council's
  rules), one building of the catalog, or a face's job (a road, an ork, a keeper's change, `bus.ORDER`).
  A card is answered by `card_act` (build, cancel, undo). The chat is kept in `chat.jsonl`.
- **Limits**: spend against the run's budget, and the claude / agy quotas read in a thread every
  `LIMITS_REFRESH_S` (`read_limits()`).

The sandbox (`orkcraft --demo`) never calls a model nor a CLI: the Warchief answers from the
catalog and the quotas are a sample.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import re
import threading

from orkcraft import scroll as ts
from orkcraft.core import buildings as core_buildings
from orkcraft.core import bus, runners, warchief
from orkcraft.core import roads as core_roads
from orkcraft.core.workers import Worker
from orkcraft.realm import audit, catalog, elders, fastpath, feedback, optimize, pipes, town_presets, weekly
from orkcraft.sources.limits import Limit, fetch_limits

TOWN_HALL = "town_hall"
CHAT_FILE = "chat.jsonl"
CHAT_KEPT = 60                  # messages the chat keeps
CONTEXT_TURNS = 8               # of them, what the Warchief reads again with a new question
ASK_LIMIT = 4000                # characters of one question
LIMITS_REFRESH_S = 10 * 60      # as the TUI's Limits

# The hall's own agents that are not the audit's: they build (realm/masonry.py).
BUILDERS = (("🏗", "Mason", "plans a building's data"), ("🎨", "Artisan", "lays out its panes and hut"))

DEMO_LIMITS = (Limit("claude", "", "5h session", 0.62, None), Limit("claude", "", "weekly", 0.81, None),
               Limit("agy", "", "daily", 0.4, None))

PROMPT = """You are the Warchief, the lead ork of an Orkcraft town. A town is a project: buildings (typed
modules) take carts (messages) along roads (links) and orks (agents) work in them. The person who runs
the town asks you; answer briefly and plainly in Markdown, as a guide who knows this town.

The town now ({project}):
{town}

The buildings that can be built (type id — what it does):
{catalog}

{orders}{history}
The person asks: {question}"""


def buildable() -> list[catalog.BuildingType]:
    """The catalog a person builds from (the Build dialog's list)."""
    hidden = catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | catalog.RETIRED_TYPES
    return [t for t in catalog.TYPES.values() if t.id not in hidden]


def _when(ts_: str) -> str:
    return str(ts_ or "")[5:16].replace("T", " ")


class TownHallWorker(Worker):
    TYPE = "town_hall"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.chat: list[dict] = []
        self.thinking = False
        self.limits: list[Limit] | None = None
        self.limits_at: dt.datetime | None = None
        self.reading_limits = False
        self._plans: dict = {}                # card id → the Town Builder's plan it holds (town_builder.TownPlan)
        self.order_waits = False              # what the hut says, read again by `look()`, not per snapshot
        self.serious = 0
        self._asked = 0                       # which question the answer that comes back is for

    def start(self) -> None:
        self.chat = self._load_chat()
        self.look()

    def look(self) -> None:
        """What happens in the hall, read again (a town order waits, the audit's serious findings):
        a face's hut shows it without reading files on every snapshot."""
        report = audit.load(self.repo_root)
        now = (town_presets.pending_order(self.repo_root) is not None,
               sum(f.severity != "info" for f in report.findings) if report else 0)
        if now != (self.order_waits, self.serious):
            self.order_waits, self.serious = now
            self.changed()

    # -- the Warchief --------------------------------------------------------------------------

    @property
    def warchief(self) -> str:
        bs = self.town.scroll.building(self.building_id) if self.town.scroll is not None else None
        lead = bs.garrison.steward if bs is not None else None
        return lead.name if lead is not None else catalog.TYPES[TOWN_HALL].orc

    def ask(self, text: str, about: list[str] | None = None) -> str:
        """A question for the Warchief (`about`: the buildings the person points at): "" when it is
        asked, else why not."""
        text = (text or "").strip()[:ASK_LIMIT]
        if not text:
            return "Ask the Warchief something"
        if self.thinking:
            return f"{self.warchief} is still answering"
        self._say("you", text)
        if self.simulated:
            answer, type_id = self._demo_answer(text)
            self._say("warchief", answer, card=warchief.card({"kind": "build", "type": type_id}) if type_id else None)
            return ""
        if self.out_of_gold("the Warchief's answer"):
            self._say("warchief", "The budget of this run is spent — raise it, and ask again.", error=True)
            return ""
        self._asked += 1
        asked, prompt = self._asked, self._prompt(text, about or [])
        self.thinking = True
        self.changed()

        def work() -> None:
            try:
                from orkcraft.realm import builders
                runner = runners.WARCHIEF_RUNNER or functools.partial(builders.claude_runner, model=None)
                answer, _cost = runner(prompt)
                result = (str(answer or "").strip() or "(no answer)", False)
            except Exception as e:             # the CLI missing, a timeout, Halt All: said in the chat
                result = (f"No answer: {e}" if str(e) else "No answer: stopped", True)
            self.town.call(self._answered, asked, *result)

        threading.Thread(target=work, daemon=True, name="warchief").start()
        return ""

    def _answered(self, asked: int, answer: str, error: bool) -> None:
        if asked != self._asked or not self.thinking:
            return                              # forgotten or halted meanwhile
        self.thinking = False
        order = None
        if not error:
            live = {b.id for b in self.town.scroll.buildings if not b.demolished}
            answer, order = warchief.parse(answer, {t.id for t in buildable()}, live)
        c = warchief.card(order) if order else None
        self._say("warchief", answer or "(no answer)", card=c, error=error)
        if c is not None:
            self._start(c)

    def forget(self) -> None:
        """A fresh chat (the file goes too)."""
        self.chat, self.thinking = [], False
        self._asked += 1
        try:
            (self.state_dir / CHAT_FILE).unlink(missing_ok=True)
        except OSError:
            pass
        self.changed()

    def halt(self) -> int:
        if not self.thinking:
            return 0
        self.thinking = False                   # the call itself is Halt All's (halt.run): its answer is dropped
        self._asked += 1
        self._say("warchief", "Stopped.", error=True)
        return 1

    def status(self) -> str:
        return "WORKING" if self.thinking else ""

    # -- the Warchief's cards: the specialists' work (core/warchief.py) -------------------------------

    def _start(self, c: dict) -> None:
        """A new card's work: the plan in a thread, a face's job on the bus, a building at once when unchained."""
        if c["kind"] == "plan":
            self._plan(c)
        elif c["kind"] in warchief.FACE_KINDS:
            self.town.publish(bus.ORDER, kind=c["kind"], building=c["building"], source=c.get("source", ""),
                              order=c["order"], card=c["id"])
        elif c["kind"] == "build" and self._unchained():
            self.card_act(c["id"], "build")

    def _unchained(self) -> bool:
        from orkcraft import autonomy
        return self.town.machine.autonomy == autonomy.FREE

    def _plan(self, c: dict) -> None:
        if self.simulated:
            self._set_card(c["id"], state="failed", error="The demo calls no model: the Town Builder plans for real only",
                           steps=[{"who": "Town Builder", "state": "failed"}])
            return
        if self.out_of_gold("the Town Builder's plan"):
            self._set_card(c["id"], state="failed", error="The budget of this run is spent",
                           steps=[{"who": "Town Builder", "state": "failed"}])
            return
        from orkcraft.realm import builders, town_builder
        repo, taken, order = self.repo_root, self.town.taken_ids(), c["order"]

        def work() -> None:
            try:
                plan = town_builder.plan(order, repo, taken, runners.BUILD_RUNNER or builders.claude_runner)
            except Exception as e:             # never raises, but a town never falls over a plan
                plan = town_builder.TownPlan(error=str(e))
            self.town.call(self._planned, c["id"], plan)

        threading.Thread(target=work, daemon=True, name="warchief-plan").start()

    def _planned(self, card_id: str, plan) -> None:
        c = self._card(card_id)
        if c is None or c["state"] != "working":
            return                              # forgotten or let go meanwhile
        if not plan.ok:
            self._set_card(card_id, state="failed", error=plan.error or "No plan came", steps=[{"who": "Town Builder", "state": "failed"}])
            return
        blocks, warns = warchief.review(self.town, plan.specs, runners.FASTPATH_RUNNER)
        steps = [{"who": "Town Builder", "state": "done"}, {"who": "Council", "state": "failed" if blocks else "done"}]
        titles = {s["id"]: s.get("title", s["id"]) for s in plan.specs}
        shown = {"title": plan.title, "summary": plan.summary,
                 "buildings": [{"title": s.get("title", s["id"]), "type": catalog.type_of(s).id, "why": plan.whys.get(s["id"], "")}
                               for s in plan.specs],
                 "roads": [{"from": titles.get(r.source, r.source), "to": titles.get(r.target, r.target), "event": r.event}
                           for r in plan.roads]}
        self._plans[card_id] = plan
        cost = f"${plan.cost_usd:.2f}" if plan.cost_usd is not None else ""
        if blocks:
            self._set_card(card_id, state="failed", steps=steps, plan=shown, cost=cost,
                           error="The Council stopped it: " + "; ".join(blocks[:3]))
            return
        self._set_card(card_id, state="ready", steps=steps, plan=shown, cost=cost, notes=warns[:4])
        if self._unchained():
            self.card_act(card_id, "build")

    def card_act(self, card_id: str, choice: str) -> bool:
        """A card answered: build (raise what it holds), cancel, undo (take down what it raised)."""
        c = self._card(card_id)
        if c is None:
            return False
        if choice == "cancel" and c["state"] in ("ready", "working", "sent"):
            self._plans.pop(card_id, None)
            self._set_card(card_id, state="dropped")
            return True
        if choice == "build" and c["state"] == "ready":
            made = self._raise(c)
            if made is None:
                return False
            self._set_card(card_id, state="done", made=made)
            return True
        if choice == "undo" and c["state"] == "done":
            for key in c.get("made", {}).get("roads", []):
                core_roads.remove(self.town, key)
            for bid in c.get("made", {}).get("buildings", []):
                core_buildings.demolish(self.town, bid)
            self._set_card(card_id, state="undone")
            return True
        return False

    def card_failed(self, card_id: str, error: str) -> None:
        """A face could not start the job an order asked for."""
        c = self._card(card_id)
        if c is not None:
            self._set_card(card_id, state="failed", error=error[:300],
                           steps=[{**s, "state": "failed"} for s in c.get("steps", [])])

    def _raise(self, c: dict) -> dict | None:
        """What a card holds stands in the town: one building of the catalog, or a plan's buildings and roads."""
        if c["kind"] == "build":
            spec = core_buildings.type_spec(self.town, c["type"])
            built = core_buildings.raise_spec(self.town, spec) if spec is not None else None
            if built is None:
                return None
            self.town.record(built.id, "building_raised", by=self.warchief)
            self.town.publish(bus.ROADS)
            return {"buildings": [built.id], "roads": []}
        plan = self._plans.pop(c["id"], None)
        if plan is None:
            self._set_card(c["id"], state="failed", error="The plan was lost when the town closed: ask again")
            return None
        made: dict[str, list[str]] = {"buildings": [], "roads": []}
        for spec in plan.specs:
            built = core_buildings.raise_spec(self.town, spec)
            if built is not None:
                made["buildings"].append(built.id)
        for r in plan.roads:
            road = core_roads.lay(self.town, r.target, r.source, r.subscription, None, quiet=True)
            if road is not None:
                made["roads"].append(f"{r.target}:{road.id}")
        self.town.checkpoint("create", "camp", f"town: {plan.title or 'the Warchief’s plan'}")
        self.town.toast(f"{len(made['buildings'])} buildings · {len(made['roads'])} roads",
                        title=f"🏰 {plan.title or 'The plan'} stands")
        return made

    def _card(self, card_id: str) -> dict | None:
        return next((m["card"] for m in self.chat if isinstance(m.get("card"), dict) and m["card"].get("id") == card_id), None)

    def _set_card(self, card_id: str, **changes) -> None:
        c = self._card(card_id)
        if c is None:
            return
        c.update(changes)
        self._save_chat(self.chat)
        self.changed()

    def _say(self, who: str, text: str, card: dict | None = None, error: bool = False) -> None:
        msg = {"who": who, "text": text, "ts": dt.datetime.now().isoformat(timespec="seconds")}
        if card:
            msg["card"] = card
        if error:
            msg["error"] = True
        chat = (self.chat + [msg])[-CHAT_KEPT:]
        self._save_chat(chat)                   # kept first: what the faces see is on disk already
        self.chat = chat
        self.changed()

    def _load_chat(self) -> list[dict]:
        try:
            lines = (self.state_dir / CHAT_FILE).read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-CHAT_KEPT:]:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("who") in ("you", "warchief") and isinstance(msg.get("text"), str):
                c = msg.get("card")
                if isinstance(c, dict) and c.get("state") in ("working", "sent") or (
                        isinstance(c, dict) and c.get("kind") == "plan" and c.get("state") == "ready"):
                    c.update(state="failed", error="The town closed before it was done: ask again")
                out.append(msg)
        return out

    def _save_chat(self, chat: list[dict]) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / CHAT_FILE).write_text(
                "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in chat), encoding="utf-8")
        except OSError:
            pass

    def town_lines(self) -> list[str]:
        """The town as the Warchief reads it: a building per line, then its roads."""
        sc = self.town.scroll
        lines = []
        for bs in sc.buildings:
            if bs.demolished:
                continue
            t = catalog.type_of(self.town.spec_of(bs.id)).id
            lines.append(f"- {bs.id} · {t} · {bs.title}")
            lines += [f"  road from {r.source} ({r.event})" for r in bs.roads]
        return lines or ["- (no buildings yet)"]

    def _prompt(self, question: str, about: list[str] | None = None) -> str:
        turns = self.chat[:-1][-CONTEXT_TURNS:]             # the question itself is the last
        history = "".join(f"\n{'Person' if m['who'] == 'you' else 'You'}: {m['text'][:1500]}" for m in turns)
        return PROMPT.format(
            project=self.town.scroll.meta.get("project_name") or self.repo_root.name,
            town="\n".join(self.town_lines()[:200]),
            catalog="\n".join(f"- {t.id} — {t.title}: {t.summary}" for t in buildable()),
            orders=warchief.PROMPT.format(about=warchief.about_text(self.town, about or [])),
            history=f"\nThe conversation so far:{history}\n" if history else "", question=question)

    def _demo_answer(self, question: str) -> tuple[str, str]:
        """The sandbox's Warchief: the catalog building whose words the question shares most."""
        words = {w for w in re.findall(r"[a-z]{4,}", question.lower())}
        best, score = None, 0
        for t in buildable():
            have = set(re.findall(r"[a-z]{4,}", f"{t.title} {t.summary} {t.preview}".lower()))
            n = len(words & have)
            if n > score:
                best, score = t, n
        note = "_(demo — no model is called here)_"
        if best is None:
            return (f"{note} Ask me what to build — say what should come in, what should happen to it and "
                    "where it should go — and I point you at the building that does it.", "")
        return f"{note} For that, a **{best.title}** fits: {best.summary}.", best.id

    # -- the hall ------------------------------------------------------------------------------

    def hall(self, report: audit.Report | None = None) -> dict:
        """What the Hall shows, as plain data (emoji as the TUI writes them; a face drops them)."""
        repo = self.repo_root
        report = report or audit.load(repo)
        order = town_presets.pending_order(repo)
        agents = []
        for aid, icon, name, area in audit.AGENTS:
            found = report.of(aid) if report else []
            agents.append({"id": aid, "icon": icon, "name": name, "area": area, "found": len(found),
                           "serious": sum(1 for f in found if f.severity != "info")})
        findings = []
        if report is not None:
            icons = {aid: icon for aid, icon, _, _ in audit.AGENTS}
            for aid, _, _, _ in audit.AGENTS:
                findings += [{"agent": aid, "icon": icons[aid], "text": f.text, "severity": f.severity,
                              "building": f.building} for f in report.of(aid)[:6]]
        elders_seen = []
        for r in elders.recent(repo, 8):
            options, key = r.get("options") or {}, r.get("key")
            how = "answered" if r.get("sent") else "advised" if key is not None else "left"
            elders_seen.append({"ts": _when(r.get("ts")), "who": str(r.get("who") or ""),
                                "question": str(r.get("question", ""))[:50], "how": how, "key": key,
                                "option": str(options.get(key, "")) if key is not None else "",
                                "why": str(r.get("why") or "")[:60], "warn": bool(r.get("warn"))})
        reviews = []
        for r in fastpath.recent(repo, 6):
            first = next(iter(r.get("notes") or []), None)
            reviews.append({"ts": _when(r.get("ts")), "kind": str(r.get("kind", "")), "id": str(r.get("id", "")),
                            "decision": str(r.get("decision", "")), "note": first["text"][:60] if first else ""})
        board = []
        for bid, row in sorted(feedback.scores(repo).items(), key=lambda kv: -kv[1].get("penalty", 0))[:5]:
            quiet = {k: v for k, v in (row.get("by") or {}).items() if k != feedback.EXPLICIT}
            board.append({"building": bid, "likes": row.get("likes", 0), "dislikes": row.get("dislikes", 0),
                          "penalty": row.get("penalty", 0), "quiet": sum(quiet.values()) if quiet else None})
        incidents = [{"ts": _when(i.ts), "building": i.building, "kind": i.kind, "note": i.note[:50],
                      "how": "" if i.source == feedback.EXPLICIT else feedback.LABELS.get(i.source, i.source),
                      "blamed": ", ".join(f"{b} −{p:g}" for b, p in i.blamed.items())}
                     for i in feedback.incidents(repo, 5)]
        proposals = [{"id": p.id, "ts": _when(p.ts), "building": p.building, "action": p.action, "target": p.target,
                      "why": p.why[:50], "status": p.status} for p in optimize.proposals(repo)[:4]]
        wk = weekly.latest(repo)
        waiting = [{"n": i.n, "title": i.title[:80], "why": i.why[:80], "building": i.building, "change": i.change}
                   for i in (wk.items if wk else []) if i.applicable and i.n not in wk.applied and i.n not in wk.declined]
        return {
            "order": str(order["prompt"])[:300] if order else "",
            "builders": [{"icon": i, "name": n, "role": r} for i, n, r in BUILDERS],
            "agents": agents,
            "audit": {"ts": report.ts, "findings": findings, "count": len(report.findings)} if report else None,
            "elders": elders_seen,
            "fast_path": [{"icon": icon, "name": name, "duty": duty} for _, icon, name, duty, _ in fastpath.ROLES],
            "reviews": reviews, "board": board, "incidents": incidents, "proposals": proposals,
            "pending": len(optimize.pending(repo)),
            "weekly": {"ts": wk.ts, "items": len(wk.items), "applied": len(wk.applied),
                       "waiting": len(waiting), "rows": waiting} if wk else None,
        }

    def audit(self) -> audit.Report:
        """🔍 The hall's three agents look over the town (rules, no model call): the report is kept,
        sent as `hall.audit_done` where a road carries it, and said in a toast."""
        town = self.town
        report = audit.run(self.repo_root, town.scroll, dict(town.custom_specs), town.snapshot.spent_usd,
                           town.scroll.budget.gold_session_limit_usd)
        try:
            audit.save(self.repo_root, report)
        except OSError:
            pass
        if ts.has_outgoing(town.scroll, self.building_id, "hall.audit_done"):
            town.roads.emit(pipes.Payload(pipes.TEXT, report.markdown(), self.building_id, "hall.audit_done", "Audit"))
        serious = sum(f.severity != "info" for f in report.findings)
        self.toast(report.summary() + (f" — {serious} to look at" if serious else ""), title="🔍 Audit")
        self.serious = serious
        self.changed()
        return report

    def quick_action(self, action_id: str) -> bool:
        """A quick action asked of the host: Audit is done here; Build is a face's dialog."""
        if action_id == "hall.audit":
            self.audit()
            return True
        return False

    # -- spend and quotas ----------------------------------------------------------------------

    def spend(self) -> dict:
        spent, limit = self.town.snapshot.spent_usd, self.town.scroll.budget.gold_session_limit_usd
        return {"spent": round(spent, 2), "limit": limit,
                "level": "over" if limit and spent >= limit else "warn" if limit and spent >= 0.8 * limit else "ok"}

    def read_limits(self) -> None:
        """The quotas again, in a thread (the CLIs answer slowly); the sandbox shows a sample."""
        if self.simulated:
            self.limits, self.limits_at = list(DEMO_LIMITS), dt.datetime.now()
            self.changed()
            return
        if self.reading_limits:
            return
        self.reading_limits = True
        self.changed()

        def work() -> None:
            try:
                found = fetch_limits(self.repo_root)
            except Exception as e:             # a quota never takes the hall down
                found = [Limit("limits", "—", "—", None, None, str(e))]
            self.town.call(self._limits_read, found)

        threading.Thread(target=work, daemon=True, name="limits").start()

    def _limits_read(self, found: list[Limit]) -> None:
        self.limits, self.limits_at, self.reading_limits = found, dt.datetime.now(), False
        self.town.limits = list(found)
        self.changed()

    def lowest(self) -> list[str]:
        """The lowest remaining quota per provider: `claude 62% left`."""
        out = []
        for provider in ("claude", "agy"):
            left = [x.remaining for x in self.limits or () if x.provider == provider and x.remaining is not None]
            if left:
                out.append(f"{provider} {round(min(left) * 100)}% left")
        return out

    def mini_status(self) -> list[str]:
        """The hut's lines where a face has no card of its own: what waits, then spend and quota."""
        lines = []
        if town_presets.pending_order(self.repo_root) is not None:
            lines.append("📜 a town order waits")
        if self.thinking:
            lines.append(f"{self.warchief} is answering…")
        s = self.spend()
        lines.append(f"🪙 ${s['spent']:.2f} / ${s['limit']:.0f}")
        return (lines + self.lowest())[:3]
