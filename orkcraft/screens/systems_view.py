"""Multi-agent systems window: systems → stages → the scheme of the selected stage."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static, Tree

from orkcraft.sources.systems import Stage, System, discover_systems, scheme_lines


class SystemsView(Container):
    """Left: systems and their stages. Right: how the highlighted stage runs."""

    DEFAULT_CSS = """
    SystemsView {
        height: 100%;
        width: 100%;
    }
    SystemsView > Horizontal {
        height: 100%;
    }
    #systems-tree {
        width: 32;
        min-width: 20;
        height: 100%;
        border-right: solid $surface-lighten-2;
        background: transparent;
    }
    #systems-scroll {
        width: 1fr;
        height: 100%;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)
        self.systems: list[System] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            tree: Tree[object] = Tree("Systems", id="systems-tree")
            tree.show_root = False
            yield tree
            with VerticalScroll(id="systems-scroll"):
                yield Static(Text("Select a stage", style="dim"), id="systems-scheme")

    def on_mount(self) -> None:
        self.refresh_view()

    def mini_status(self) -> list[str]:
        """Hut lines: multi-agent systems."""
        return [f"{len(self.systems)} systems", self.systems[0].name if self.systems else "none found"]

    def refresh_view(self) -> None:
        self.systems = discover_systems(self.app.repo_root)  # type: ignore[attr-defined]
        tree = self.query_one("#systems-tree", Tree)
        tree.clear()
        for sysm in self.systems:
            node = tree.root.add(Text(f"🧩 {sysm.name}  ({len(sysm.stages)})", style="bold"), data=sysm)
            for stage in sysm.stages:
                prefix = f"{stage.order}. " if stage.order is not None else ""
                agents = len(stage.agent_steps())
                node.add_leaf(f"{prefix}{stage.name}  · {agents} agent step{'s' if agents != 1 else ''}", data=stage)
            node.expand()
        tree.root.expand()
        tree.cursor_line = 0  # show the first system's overview right away

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        data = event.node.data
        scheme = self.query_one("#systems-scheme", Static)
        if isinstance(data, Stage):
            scheme.update(self._render_stage(data))
        elif isinstance(data, System):
            scheme.update(self._render_system(data))
        event.stop()

    def _render_system(self, sysm: System) -> Text:
        t = Text()
        t.append(f"{sysm.name}\n", style="bold")
        t.append(f"{sysm.root.name}/pipelines · {len(sysm.stages)} stages\n\n", style="dim")
        for stage in sysm.stages:
            prefix = f"{stage.order}. " if stage.order is not None else "· "
            t.append(f"{prefix}{stage.name}", style="bold cyan")
            t.append(f"  {stage.description[:100]}\n", style="dim")
        return t

    def _render_stage(self, stage: Stage) -> Text:
        t = Text()
        t.append(f"{stage.name}\n", style="bold")
        if stage.description:
            t.append(f"{stage.description}\n", style="italic")
        t.append(f"spec: {stage.path.parent.parent.name}/pipelines/{stage.path.name}  ·  ", style="dim")
        t.append("🤖 agent (agy)  ⚙ script  ∥ parallel  ⟳ per item  ⇄ review loop\n\n", style="dim")
        for line in scheme_lines(stage):
            style = "bold" if line.startswith("──") else ("yellow" if "⇄" in line else "")
            if "⚙" in line:
                style = "blue"
            t.append(line + "\n", style=style)
        return t
