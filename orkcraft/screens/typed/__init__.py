"""Typed building views: one view per building type of the catalog."""
from __future__ import annotations

from orkcraft.screens.custom_view import CustomBuildingView


def _views() -> dict[str, type]:
    from orkcraft.screens.typed.calendar_view import CalendarView
    from orkcraft.screens.typed.catapult_view import CatapultView
    from orkcraft.screens.typed.crag_view import CragView
    from orkcraft.screens.typed.pit_view import PitView
    from orkcraft.screens.typed.files_view import FilesView
    from orkcraft.screens.typed.generator_view import GeneratorView
    from orkcraft.screens.typed.git_view import GitView
    from orkcraft.screens.typed.knowledge_view import KnowledgeView
    from orkcraft.screens.typed.lake_view import LakeView
    from orkcraft.screens.typed.watchtower_view import WatchtowerView
    from orkcraft.screens.typed.mill_view import MillView
    from orkcraft.screens.typed.pool_view import PoolView
    from orkcraft.screens.typed.tasks_view import TasksView
    from orkcraft.screens.typed.team_view import TeamView
    from orkcraft.screens.typed.totem_view import TotemView
    from orkcraft.screens.typed.workshop_view import WorkshopView
    return {v.TYPE: v for v in (CalendarView, CatapultView, CragView, PitView, FilesView, GeneratorView, GitView,
                                KnowledgeView, LakeView, WatchtowerView, MillView, PoolView, TasksView, TeamView, TotemView,
                                WorkshopView)}


def view_for(spec: dict) -> CustomBuildingView:
    """The view of a building spec: its type's view, else the declarative custom view."""
    from orkcraft.realm import catalog
    cls = _views().get(catalog.type_of(spec).id)
    return cls(spec) if cls is not None else CustomBuildingView(spec)
