"""Agents: the roles and the task type of each (spec 34 §3, §4), as `gui/ideas.py`'s `Ideas` has them:
`ideas.agents`, `ideas.roles`, `ideas.role_save`, `ideas.role_drop`, `ideas.kind_set`.

A role is a small file in the repository's `.orkcraft/roles/` (realm/roles.py); the runner runs a task as its type's
role (core/idea_runner.py). Split from ideas.py to keep it under ~600 lines.
"""
from __future__ import annotations

import datetime as dt

from orkcraft.gui.ideas_args import IdeasError, _device, _opt, _text
from orkcraft.realm import event_log, ideas, roles


class RolesMixin:
    def _role_spend(self) -> dict[str, float]:
        """Today's cost of each role: the tasks it ran today, summed."""
        pairs = [(str(t.get("role") or roles.GRUNT), t) for _s, _title, plan in self._plans() for t in plan.get("tasks") or []]
        return roles.spend_today(pairs)

    def roles(self, args: dict) -> dict:
        spent = self._role_spend()
        mine = [{**r, "spend_today": spent.get(r["slug"], 0.0)} for r in roles.roles(self.state_dir)]
        kinds = roles.kinds(self.state_dir)
        return {"roles": mine, "kinds": [{"kind": k, "label": roles.KIND_LABELS[k], "role": kinds[k]} for k in roles.TASK_KINDS],
                "models": roles.models()}

    def role_save(self, args: dict) -> dict:
        slug = _opt(args, "slug") or None
        instruction = args.get("instruction", "")
        if not isinstance(instruction, str):
            raise IdeasError("instruction is not text")
        got = roles.save(self.state_dir, _text(args, "name", roles.NAME_CHARS), args.get("model", ""),
                         args.get("max_parallel"), instruction, slug)
        r = roles.role(self.state_dir, got)
        self._ev(event_log.ROLE_SAVED, args, role=got, model=r["model"], max_parallel=r["max_parallel"], new=slug is None)
        self.changed("")
        return {"slug": got}

    def role_drop(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        back = roles.drop(self.state_dir, slug)
        self._ev(event_log.ROLE_DROPPED, args, role=slug, kinds=back)
        self.changed("")
        return {"ok": True}

    def kind_set(self, args: dict) -> dict:
        kind, role = _text(args, "kind", 40), _text(args, "role", 100)
        roles.set_kind(self.state_dir, kind, role)
        self._ev(event_log.KIND_SET, args, kind=kind, role=role)
        self.changed("")
        return {"ok": True}

    def agents(self, args: dict) -> dict:
        """The Agents window: a block per role — the Taskmaster (the keeper, with what it does now), the Grunt and the
        person's own — each with a chip per live task of the types it has."""
        board = self.board(make=False)
        titles = {i["slug"]: i["title"] for i in board["ideas"]}
        chips, waits, mode = [], None, "waiting"
        for i in board["ideas"]:
            busy = self.keeper.busy(i["slug"])
            if i["state"] in ("reading", "planning") or busy:
                state = "planning" if i["state"] == "planning" else ("reading" if i["state"] == "reading" else "talking")
                chips.append({"idea": i["slug"], "title": i["title"], "state": state})
            elif i["state"] == "asks":
                chips.append({"idea": i["slug"], "title": i["title"], "state": "waiting"})
                waits = waits or {"idea": i["slug"], "text": f"waiting for your answers on “{i['title']}”"}
        for g in board["tracks"]:
            if self.keeper.busy_goal(g["slug"]):
                chips.append({"idea": "", "goal": g["slug"], "title": g["title"], "state": "reading"})
        for rank in ("planning", "reading", "talking"):
            if any(c["state"] == rank for c in chips):
                mode = rank
                break
        by_role: dict[str, list] = {}
        done, today = [], dt.date.today().isoformat()
        for slug, title, plan in self._plans():
            for t in plan.get("tasks") or []:
                state, role = t.get("state"), str(t.get("role") or roles.GRUNT)
                if state == "merged" and str(t.get("finished") or "").startswith(today):
                    done.append({"idea": slug, "task": t.get("id"), "title": t.get("title", ""), "role": role})
                elif state in ("running", "testing", "review", "ready", "held", "failed"):
                    by_role.setdefault(role, []).append(
                        {"idea": slug, "idea_title": titles.get(slug, title), "task": t.get("id"),
                         "title": t.get("title", ""), "state": state, "tier": t.get("tier", ""), "role": role,
                         "kind": t.get("kind") or roles.DEFAULT_KIND,
                         "note": t.get("note") or (t.get("error") if state == "failed" else "") or ""})
        spent, out = self._role_spend(), []
        for r in roles.roles(self.state_dir):
            block = {"role": r["slug"], "name": "Grunts" if r["slug"] == roles.GRUNT and r["name"] == "Grunt" else r["name"],
                     "model": r["model"], "max_parallel": r["max_parallel"], "builtin": r["builtin"],
                     "spend_today": spent.get(r["slug"], 0.0)}
            if r["slug"] == roles.TASKMASTER:
                out.append({**block, "state": mode, "waits_on": waits, "chips": chips})
            else:
                out.append({**block, "chips": by_role.pop(r["slug"], []),
                            "kinds": [k for k, v in roles.kinds(self.state_dir).items() if v == r["slug"]]})
        if by_role and out:                              # tasks of a role that was dropped since: Grunt's
            grunt = next(b for b in out if b["role"] == roles.GRUNT)
            grunt["chips"] += [c for cs in by_role.values() for c in cs]
        return {"roles": out, "done_today": done}
