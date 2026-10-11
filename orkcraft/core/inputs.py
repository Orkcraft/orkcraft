"""A building's inputs (docs/design/improve-buildings.md §3): every way something comes into it — a cart down a road
of a kind it takes, or one of its quick actions pressed with what a person gives it (a task's brief, a question).

A person's press in the GUI opens a form and ends in an act of the type's view; `press` ends in the same act
(catalog `QUICK_INPUTS`), so a bench can give a building an input the way a person does, and every press is
published (`bus.INPUT`) to be recorded and played again. Which act runs is the face's: the core holds no view, the
face sets `town.presser` (gui/console.py), and a town without one presses nothing.

    inputs.of(town, "camp")                                  # [Input("road", …), Input("pool.task", …), …]
    inputs.press(town, "camp", "pool.task", "Fix the login page")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from orkcraft.core import bus
from orkcraft.realm import catalog

ROAD = "road"                 # the input of a cart down a plain road
VALUE_MAX = 50_000            # characters a press may carry


class InputError(ValueError):
    """An input that cannot be pressed: its text is shown to the person."""


@dataclass(frozen=True)
class Input:
    id: str                   # ROAD, or the quick action's id
    label: str
    takes: str                # "" nothing, "text"; a road's: the kinds it takes, "text, file"
    act: str = ""             # the view's act a press ends in ("" its worker's quick_action)
    arg: str = ""             # the act's argument the text goes to
    fixed: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {"id": self.id, "label": self.label, "takes": self.takes}


def of(town, building_id: str) -> list[Input]:
    """Its inputs: a road's when its type takes carts, then each quick action that is one, in the type's order."""
    spec = town.custom_specs.get(building_id)
    if spec is None:
        return []
    t = catalog.type_of(spec)
    out = []
    kinds = catalog.ACCEPTS.get(t.id)
    if kinds and catalog.lays_roads(t.id, setup=True):
        out.append(Input(ROAD, "a cart down a road", ", ".join(sorted(kinds))))
    for a in t.actions:
        how = catalog.QUICK_INPUTS.get(a.id)
        if how is not None:
            act, arg, fixed = how
            out.append(Input(a.id, a.label, "text" if arg else "", act, arg, dict(fixed)))
    return out


def press(town, building_id: str, input_id: str, value: str = "", by: str = "person") -> Any:
    """Press one of its quick-action inputs with `value` (the text a person gives it, when it takes one); what the
    act answers comes back. `by`: who pressed — a person, or a bench (the Test bench)."""
    inp = next((i for i in of(town, building_id) if i.id == input_id), None)
    if inp is None or inp.id == ROAD:
        raise InputError(f"{building_id} has no input {input_id!r}")
    value = (value or "").strip()[:VALUE_MAX]
    if inp.takes == "text" and not value:
        raise InputError(f"{inp.label}: say what it takes")
    presser = getattr(town, "presser", None)
    if presser is None:
        raise InputError("Nothing here presses a building's inputs")
    args = {**inp.fixed, **({inp.arg: value} if inp.arg else {})}
    town.publish(bus.INPUT, building=building_id, input=inp.id, value=value, by=by)
    return presser(building_id, inp, args)
