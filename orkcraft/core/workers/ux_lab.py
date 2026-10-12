"""⚗️ The UX bench's work (docs/design/improve-buildings.md §6): the look of one type of building.

Its settings say which type (`target`, picked from a list laid out as Build is, never from the map: a look is a
type's, not one building's) and which AI tool paints (`image_tool`, agy by default). It lays no road and takes none
(catalog `roads = "none"`). The gallery of the type's pictures is the view's (gui/views/ux_lab.py).

A picture painted again (realm/painter.py) is a **draft** beside the building until **Apply** puts it in this
machine's own pictures (design/tokens.py `assets_dir`), served before the design system's; **Reset** brings the shipped
one back (Apply then takes this machine's away). A window laid out again is its steward's redesign of the type's
UI document, a draft too until Apply gives it to every building of the type (core/buildings.py `set_ui`).

Its target may also be the operator's mascots (`MASCOTS`, §6.4): a head is drawn again as its grid by a text model
(realm/painter.py `mascot`), never by the image tool, and Apply keeps its picture, its @2x and its grid on this machine.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from orkcraft.core.workers import Worker
from orkcraft.design import agents, mascots, tokens
from orkcraft.realm import catalog, motion, painter

IMAGE_TOOL = "agy"            # paints unless its settings name another (asked 2026-10-11)
SHIPPED = "shipped"           # a draft that is the design system's own picture again (Reset)
MASCOTS = "mascots"           # a target that is no building: the operator's mascots (§6.4)


class UxLabWorker(Worker):
    TYPE = "ux_lab"

    @property
    def target(self) -> str:
        """The type whose look it works on, "" until one is picked (or when the one picked is gone)."""
        tid = str(self.config.get("target") or "")
        return tid if tid == MASCOTS or (tid in catalog.TYPES and tid != self.TYPE) else ""

    @property
    def image_tool(self) -> str:
        return str(self.config.get("image_tool") or IMAGE_TOOL)

    def pick(self, type_id: str) -> bool:
        """Work on `type_id`'s look (or the mascots'); False for a type the catalog has not (or itself)."""
        if type_id == MASCOTS:
            return self.save_config({"target": MASCOTS})
        tid = catalog.ALIASES.get(type_id, type_id)
        if tid not in catalog.TYPES or tid == self.TYPE:
            return False
        return self.save_config({"target": tid})

    def set_tool(self, tool: str) -> bool:
        return self.save_config({"image_tool": tool or None})

    # -- pictures painted again (docs/design/improve-buildings.md §6.2) ------------------------------------------------

    def start(self) -> None:
        self.painting: dict[str, str] = {}           # a picture's path → "" while it is painted, else what went wrong
        self.layout: dict | None = None             # a window laid out again: {doc, why, error, busy}
        self.card: dict | None = None               # its cards laid out again: {doc, error, busy, shipped}

    @staticmethod
    def _key(path: str) -> str:
        return path.replace("/", "__")

    def _draft(self, path: str) -> Path:
        return self.state_dir / "drafts" / f"{self._key(path)}"

    def _draft_grid(self, path: str) -> Path:
        """A mascot's draft as its grid (and the line on why), beside its picture."""
        f = self._draft(path)
        return f.with_name(f.name + ".grid.json")

    @staticmethod
    def own(path: str) -> Path:
        return tokens.assets_dir() / path

    def picture(self, path: str) -> bytes:
        """The picture as it stands on this machine: its own, else the design system's. A moving house's layer not
        painted yet is painted from the house itself (realm/motion.py)."""
        for p in (self.own(path), tokens.SYSTEM / path):
            if p.is_file():
                return p.read_bytes()
        got = motion.of_path(path)
        if got:
            return self.picture(f"sprites/buildings/{got[0]}/header.png")
        raise painter.PaintError("No such picture")

    @staticmethod
    def shipped(path: str) -> bytes:
        """The design system's own picture, b"" when it ships none (a moving house's layer not painted yet)."""
        p = tokens.SYSTEM / path
        return p.read_bytes() if p.is_file() else b""

    def draft(self, path: str) -> bytes | str | None:
        """Its draft: the new picture, SHIPPED when Reset asked for the design system's again, None when none."""
        f = self._draft(path)
        if f.with_suffix(".shipped").exists():
            return SHIPPED
        return f.read_bytes() if f.is_file() else None

    def paint(self, path: str, words: str, region: dict | None = None, runner=None) -> None:
        """Painted again on its own thread from the picture as it stands (or its draft): the draft comes back."""
        if mascots.is_mascot(path):
            return self.draw(path, words, region, runner)
        if not painter.kind_of(path):
            raise painter.PaintError("The UX bench paints the Build icons, the houses, their moving parts and the orks")
        if self.painting.get(path) == "":
            raise painter.PaintError("It is being painted already")
        have = self.draft(path)
        reference = have if isinstance(have, bytes) else self.picture(path) if have is None else \
            (self.shipped(path) or self.picture(path))
        self.painting[path] = ""
        self.changed()

        def work() -> None:
            try:
                data, error = painter.paint(self.image_tool, "", path, reference, words, region, runner=runner), ""
            except painter.PaintError as e:
                data, error = b"", str(e)
            self.town.call(done, data, error)

        def done(data: bytes, error: str) -> None:
            if data:
                f = self._draft(path)
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(data)
                f.with_suffix(".shipped").unlink(missing_ok=True)
            self.painting[path] = error
            if not error:
                self.painting.pop(path, None)
            self.changed()

        threading.Thread(target=work, daemon=True, name="ux-paint").start()

    def grid(self, path: str) -> list[str]:
        """A mascot's grid as it would be drawn again: its draft's, the design system's after Reset, else this
        machine's own or the design system's."""
        have = self.draft(path)
        if have == SHIPPED:
            return mascots.shipped_grid(path)
        try:
            g = json.loads(self._draft_grid(path).read_text(encoding="utf-8"))["grid"] if have is not None else None
        except (OSError, ValueError, KeyError):
            g = None
        return g if g and not mascots.problems(g) else mascots.grid(path)

    def why(self, path: str) -> str:
        try:
            return str(json.loads(self._draft_grid(path).read_text(encoding="utf-8")).get("why") or "")
        except (OSError, ValueError, AttributeError):
            return ""

    def draw(self, path: str, words: str, region: dict | None = None, runner=None) -> None:
        """A mascot drawn again on its own thread, as its grid, by the Alchemist on a text model: the draft comes back."""
        from orkcraft.core import runners
        from orkcraft.realm import steward_models
        if self.painting.get(path) == "":
            raise painter.PaintError("It is being drawn already")
        if len(words.strip()) < 3:
            raise painter.PaintError("Say what to change")
        current, what = self.grid(path), mascot_title(path)
        run = runner or steward_models.runner_for(None, "redesign", runners.STEWARD_RUNNER)
        self.painting[path] = ""
        self.changed()

        def work() -> None:
            g, why, wrong = painter.mascot(path, current, words, region, what, runner=run)
            self.town.call(done, g, why, "; ".join(wrong[:2]) if not g else "")

        def done(g, why: str, error: str) -> None:
            if g:
                f = self._draft(path)
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(mascots.png(g))
                self._draft_grid(path).write_text(json.dumps({"grid": g, "why": why}), encoding="utf-8")
                f.with_suffix(".shipped").unlink(missing_ok=True)
                self.painting.pop(path, None)
            else:
                self.painting[path] = error or "no grid came back"
            self.changed()

        threading.Thread(target=work, daemon=True, name="ux-mascot").start()

    def reset(self, path: str) -> None:
        """The draft is the design system's own picture again."""
        f = self._draft(path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.unlink(missing_ok=True)
        self._draft_grid(path).unlink(missing_ok=True)
        f.with_suffix(".shipped").write_text("", encoding="utf-8")
        self.changed()

    def drop(self, path: str) -> None:
        f = self._draft(path)
        f.unlink(missing_ok=True)
        self._draft_grid(path).unlink(missing_ok=True)
        f.with_suffix(".shipped").unlink(missing_ok=True)
        self.painting.pop(path, None)
        self.changed()

    def apply(self, path: str) -> bool:
        """The draft becomes this machine's picture (its @2x too, so a retina screen shows it); after Reset, this
        machine's goes and the design system's shows again. False when there is no draft."""
        have = self.draft(path)
        if have is None:
            return False
        if mascots.is_mascot(path):
            return self._apply_mascot(path, have)
        targets = [path] + ([path[:-4] + "@2x.png"] if not path.endswith("@2x.png") else [])
        for t in targets:
            own = self.own(t)
            if have == SHIPPED:
                own.unlink(missing_ok=True)
            else:
                own.parent.mkdir(parents=True, exist_ok=True)
                own.write_bytes(have)
        self.drop(path)
        return True

    def _apply_mascot(self, path: str, have) -> bool:
        """A mascot's draft drawn at both scales from its grid, the grid kept beside them; after Reset, all three go."""
        files = {path: mascots.SCALE, path[:-4] + "@2x.png": 2 * mascots.SCALE}
        if have == SHIPPED:
            for t in files:
                self.own(t).unlink(missing_ok=True)
            mascots.own_grid(path).unlink(missing_ok=True)
        else:
            g, why = self.grid(path), self.why(path)
            for t, scale in files.items():
                own = self.own(t)
                own.parent.mkdir(parents=True, exist_ok=True)
                own.write_bytes(mascots.png(g, scale))
            mascots.own_grid(path).write_text(json.dumps({"grid": g, "why": why}, indent=1), encoding="utf-8")
        self.drop(path)
        return True

    @staticmethod
    def owned() -> list[str]:
        """Every picture this machine has its own of (its @2x left out)."""
        root = tokens.assets_dir() / "sprites"
        if not root.is_dir():
            return []
        return sorted(p.relative_to(tokens.assets_dir()).as_posix() for p in root.rglob("*.png") if "@2x" not in p.name)

    # -- its window laid out again (docs/design/improve-buildings.md §6.2) -----------------------------------------------

    def first_of_type(self) -> str:
        tid = self.target
        return next((b.id for b in self.town.scroll.buildings
                     if not b.demolished and catalog.type_of(self.town.spec_of(b.id)).id == tid), "") if tid else ""

    def lay_out(self, request: str) -> None:
        """Its steward lays the type's window out again from the person's words (one call, checked against the type's
        contract): a draft until Apply."""
        import copy
        from orkcraft.core import runners
        from orkcraft.realm import steward
        bid = self.first_of_type()
        if not bid:
            raise painter.PaintError("Build one of them first: its window is laid out on it")
        if self.layout and self.layout.get("busy"):
            raise painter.PaintError("It is being laid out already")
        repo, snapshot, tid = self.repo_root, copy.deepcopy(self.town.scroll), self.target
        self.layout = {"busy": True, "doc": (self.layout or {}).get("doc"), "why": "", "error": ""}
        self.changed()

        def work() -> None:
            report = steward.redesign(repo, snapshot, bid, tid, f"{agents.brief('alchemist')}\n\n{request}",
                                      runner=steward.runner_for(snapshot.building(bid), "redesign", runners.STEWARD_RUNNER))
            self.town.call(done, report)

        def done(report) -> None:
            if report.proposals:
                p = report.proposals[0]
                self.layout = {"busy": False, "doc": p.data.get("ui"), "why": p.why, "error": ""}
            else:
                self.layout = {**self.layout, "busy": False,
                               "error": report.error or "; ".join(report.errors[:2]) or "no layout came back"}
            self.changed()

        threading.Thread(target=work, daemon=True, name="ux-layout").start()

    def apply_layout(self) -> list[str]:
        """The draft layout for every building of the type (each a checkpoint: undo takes it back); the problems."""
        from orkcraft.core import buildings
        doc = (self.layout or {}).get("doc")
        if not doc:
            return ["no layout to apply"]
        tid, problems = self.target, []
        for b in self.town.scroll.buildings:
            if not b.demolished and catalog.type_of(self.town.spec_of(b.id)).id == tid:
                problems += buildings.set_ui(self.town, b.id, doc, by="you", why="the UX bench's layout")
        if not problems:
            self.layout = None
            self.changed()
        return problems

    # -- its cards laid out again (docs/design/improve-buildings.md §6.3) ------------------------------------------------

    def card_now(self) -> dict:
        from orkcraft.realm import card_docs
        return card_docs.current(self.target) or card_docs.default(self.target)

    def card_ask(self, words: str, size: str = "", part: str = "", runner=None, after=None) -> None:
        """Its cards laid out again from the person's words (one checked call): a draft until Apply."""
        from orkcraft.core import runners
        from orkcraft.realm import card_docs, steward
        if not self.target:
            raise painter.PaintError("Pick a building first")
        if (getattr(self, "card", None) or {}).get("busy"):
            raise painter.PaintError("Its cards are being laid out already")
        current = (getattr(self, "card", None) or {}).get("doc") or self.card_now()
        bid, tid = self.first_of_type(), self.target
        b = self.town.scroll.building(bid) if bid else None
        run = runner or steward.runner_for(b, "redesign", runners.STEWARD_RUNNER)
        self.card = {"busy": True, "doc": (getattr(self, "card", None) or {}).get("doc"), "error": ""}
        self.changed()

        def work() -> None:
            doc, wrong, _cost = card_docs.ask(tid, catalog.TYPES[tid].title, current, words, size, part, runner=run)
            self.town.call(done, doc, wrong)

        def done(doc, wrong) -> None:
            self.card = {"busy": False, "doc": doc or self.card.get("doc"),
                         "error": "" if doc else "; ".join(wrong[:2]) or "no layout came back"}
            self.changed()
            if after is not None:
                after(bool(doc))

        threading.Thread(target=work, daemon=True, name="ux-card").start()

    def card_reset(self) -> None:
        from orkcraft.realm import card_docs
        self.card = {"busy": False, "doc": card_docs.shipped(self.target) or card_docs.default(self.target), "error": "",
                     "shipped": True}
        self.changed()

    def card_apply(self) -> list[str]:
        """The draft becomes this machine's card for the type; after Reset, its own goes and the code's card shows."""
        from orkcraft.realm import card_docs
        draft = getattr(self, "card", None) or {}
        if not draft.get("doc"):
            return ["nothing to apply: lay it out first"]
        if draft.get("shipped"):
            card_docs.remove(self.target)
            wrong = []
        else:
            wrong = card_docs.save(self.target, draft["doc"])
        if not wrong:
            self.card = None
            self.changed()                                 # the snapshot after it: every hut of the type draws it again
        return wrong


def mascot_title(path: str) -> str:
    """What a mascot's picture is, for the Alchemist: its nick, its role and its stage."""
    from orkcraft.realm import intents
    m = mascots.PATH.match(path)
    role = next((r for r in intents.ROLES if r.id == m[1]), None) if m else None
    return f"{role.nick}, the {role.title.lower()}'s mascot at stage {m[2]} of 4" if role else path
