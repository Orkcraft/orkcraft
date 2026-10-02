"""Custom building view: renders panes from a validated custom building spec.

Data comes exclusively through `masonry.fetch(...)`. Panes are laid out vertically
or horizontally using ratios, and refresh every 30 seconds or on `refresh_data()`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    DataTable,
    DirectoryTree,
    Label,
    Markdown,
    OptionList,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

from orkcraft.realm import huts, masonry


class CustomBuildingView(Container):
    """View container for a custom building specified by declarative JSON."""

    DEFAULT_CSS = """
    CustomBuildingView {
        width: 100%;
        height: 100%;
    }
    .panes-container-horizontal {
        layout: horizontal;
        width: 100%;
        height: 100%;
    }
    .panes-container-vertical {
        layout: vertical;
        width: 100%;
        height: 100%;
    }
    .custom-pane {
        height: 1fr;
        width: 1fr;
        padding: 0 1;
        border: round $surface-lighten-1;
    }
    .pane-title {
        height: 1;
        text-style: bold;
        color: $accent;
    }
    .pane-error {
        height: 1;
        color: $text-muted;
        text-style: italic;
    }
    .pane-content {
        height: 1fr;
        width: 100%;
    }
    .counter-box {
        height: 1fr;
        width: 100%;
        align: center middle;
        content-align: center middle;
    }
    .counter-number {
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .counter-title {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        spec: dict,
        repo_root: Path | None = None,
        graph: Any = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.spec = spec
        self._repo_root = repo_root
        self._graph = graph
        self._data_cache: dict[str, masonry.Data] = {}

    def _get_repo_root(self) -> Path:
        if self._repo_root is not None:
            return self._repo_root
        app = getattr(self, "app", None)
        if app is not None and getattr(app, "repo_root", None):
            return app.repo_root
        return Path.cwd()

    def _get_graph(self) -> Any:
        if self._graph is not None:
            return self._graph
        app = getattr(self, "app", None)
        if app is not None:
            return getattr(app, "graph", None)
        return None

    def _fetch_pane_data(self, data_name: str) -> masonry.Data:
        entry = next((d for d in self.spec.get("data", []) if d.get("name") == data_name), None)
        if not entry:
            return masonry.Data(masonry.TEXT, error=f"no data named {data_name!r}")
        repo_root = self._get_repo_root()
        graph = self._get_graph()
        return masonry.fetch(entry["source"], entry.get("params"), repo_root, graph)

    def compose(self) -> ComposeResult:
        layout = self.spec.get("layout", {})
        direction = layout.get("direction", "vertical")
        is_horizontal = direction == "horizontal"
        container_cls = "panes-container-horizontal" if is_horizontal else "panes-container-vertical"

        container_widget = Horizontal(classes=container_cls, id="panes-container") if is_horizontal else Vertical(classes=container_cls, id="panes-container")

        with container_widget:
            panes = layout.get("panes", [])
            for i, pane in enumerate(panes):
                ratio = max(1, min(4, int(pane.get("ratio", 1))))
                pane_box = Vertical(classes="custom-pane", id=f"pane-box-{i}")
                if is_horizontal:
                    pane_box.styles.width = f"{ratio}fr"
                    pane_box.styles.height = "100%"
                else:
                    pane_box.styles.height = f"{ratio}fr"
                    pane_box.styles.width = "100%"

                with pane_box:
                    data_name = pane.get("data", "")
                    pane_title = pane.get("title") or data_name
                    yield Label(Text(pane_title), classes="pane-title")

                    data = self._fetch_pane_data(data_name)
                    self._data_cache[data_name] = data
                    has_error = bool(data.error)

                    err_static = Static(Text(data.error, style="dim") if has_error else Text(""),
                                        classes="pane-error", id=f"pane-err-{i}")
                    err_static.display = has_error
                    yield err_static

                    widget_type = pane.get("widget", "list")
                    widget = self._create_pane_widget(i, pane, data)
                    widget.display = not has_error
                    yield widget

    def _create_pane_widget(self, i: int, pane: dict, data: masonry.Data):
        widget_type = pane.get("widget", "list")
        if widget_type == "list":
            ol = OptionList(id=f"pane-widget-{i}", classes="pane-content")
            for r in data.rows:
                parts = [r.title]
                if r.status:
                    parts.append(r.status)
                if r.meta:
                    parts.append(r.meta)
                prompt = " · ".join(parts)
                ol.add_option(Option(Text(prompt), id=r.id if r.id else None))
            return ol

        if widget_type == "table":
            dt = DataTable(id=f"pane-widget-{i}", classes="pane-content")
            dt.cursor_type = "row"
            cols = pane.get("columns") or ["id", "title", "status"]
            dt.add_columns(*cols)
            for r in data.rows:
                cells = [Text(r.get(c)) for c in cols]
                if r.id:
                    dt.add_row(*cells, key=r.id)
                else:
                    dt.add_row(*cells)
            return dt

        if widget_type == "counter":
            pane_title = pane.get("title") or pane.get("data", "")
            cnt_num = Static(Text(str(len(data.rows)), style="bold"), classes="counter-number", id=f"counter-num-{i}")
            cnt_lbl = Static(Text(pane_title, style="dim"), classes="counter-title")
            return Vertical(cnt_num, cnt_lbl, classes="counter-box pane-content", id=f"pane-widget-{i}")

        if widget_type == "markdown":
            return VerticalScroll(Markdown(data.text or "_No content._", id=f"pane-md-{i}"),
                                  id=f"pane-widget-{i}", classes="pane-content")

        if widget_type == "log":
            ta = TextArea(data.text, read_only=True, id=f"pane-widget-{i}", classes="pane-content")
            ta.scroll_end(animate=False)
            return ta

        if widget_type == "tree":
            path = data.path or self._get_repo_root()
            return DirectoryTree(str(path), id=f"pane-widget-{i}", classes="pane-content")

        return Static(Text(f"Unsupported widget: {widget_type}"), id=f"pane-widget-{i}", classes="pane-content")

    def on_mount(self) -> None:
        self.set_interval(30.0, self.refresh_data)

    def show_incoming(self, title: str, markdown: str) -> None:
        """What arrived along a road (a node, a file, a handler's result): a pane at the end,
        added on the first delivery."""
        self.incoming_title = title
        incoming = getattr(self, "_incoming", None)
        if incoming is not None:
            label, md = incoming
            if md.is_mounted:
                label.update(Text(f"📥 {title}"))
                md.update(markdown or "_empty_")
            else:  # still mounting: try again after the next refresh
                self.call_after_refresh(self.show_incoming, title, markdown)
            return
        try:
            container = self.query_one("#panes-container")
        except Exception:
            return
        label = Label(Text(f"📥 {title}"), classes="pane-title")
        md = Markdown(markdown or "_empty_")
        box = Vertical(label, VerticalScroll(md, classes="pane-content"), classes="custom-pane pane-incoming")
        if isinstance(container, Horizontal):
            box.styles.width, box.styles.height = "1fr", "100%"
        else:
            box.styles.height, box.styles.width = "1fr", "100%"
        self._incoming = (label, md)
        container.mount(box)

    def mini_status(self) -> list[str]:
        """Hut lines: the spec's `mini` templates over the data this building fetched."""
        lines = huts.custom_status(self.spec, dict(self._data_cache))
        incoming = getattr(self, "incoming_title", "")
        if incoming and len(lines) < huts.STATUS_LINES:
            lines.append(f"📥 {incoming}")
        return lines

    def refresh_view(self) -> None:
        """Alias for refresh_data called by app on global refresh."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reload all data sources and update pane widgets while preserving selection where possible."""
        layout = self.spec.get("layout", {})
        panes = layout.get("panes", [])

        for i, pane in enumerate(panes):
            data_name = pane.get("data", "")
            data = self._fetch_pane_data(data_name)
            self._data_cache[data_name] = data
            has_error = bool(data.error)

            try:
                err_static = self.query_one(f"#pane-err-{i}", Static)
                err_static.update(Text(data.error, style="dim") if has_error else Text(""))
                err_static.display = has_error
            except Exception:
                pass

            try:
                widget = self.query_one(f"#pane-widget-{i}")
                widget.display = not has_error
            except Exception:
                continue

            if has_error:
                continue

            widget_type = pane.get("widget", "list")
            if widget_type == "list" and isinstance(widget, OptionList):
                old_id = None
                old_idx = widget.highlighted
                if widget.highlighted is not None and widget.highlighted < widget.option_count:
                    try:
                        old_id = widget.get_option_at_index(widget.highlighted).id
                    except Exception:
                        pass
                widget.clear_options()
                for r in data.rows:
                    parts = [r.title]
                    if r.status:
                        parts.append(r.status)
                    if r.meta:
                        parts.append(r.meta)
                    prompt = " · ".join(parts)
                    widget.add_option(Option(Text(prompt), id=r.id if r.id else None))
                restored = False
                if old_id is not None:
                    for idx in range(widget.option_count):
                        if widget.get_option_at_index(idx).id == old_id:
                            widget.highlighted = idx
                            restored = True
                            break
                if not restored and old_idx is not None and old_idx < widget.option_count:
                    widget.highlighted = old_idx

            elif widget_type == "table" and isinstance(widget, DataTable):
                cols = pane.get("columns") or ["id", "title", "status"]
                old_key = None
                if widget.row_count:
                    try:
                        old_key = widget.coordinate_to_cell_key(widget.cursor_coordinate).row_key.value
                    except Exception:
                        pass
                widget.clear()
                for r in data.rows:
                    cells = [Text(r.get(c)) for c in cols]
                    if r.id:
                        widget.add_row(*cells, key=r.id)
                    else:
                        widget.add_row(*cells)
                if old_key is not None:
                    for row_idx, rk in enumerate(widget.rows.keys()):
                        if rk.value == old_key:
                            widget.move_cursor(row=row_idx)
                            break

            elif widget_type == "counter":
                try:
                    num_widget = widget.query_one(f"#counter-num-{i}", Static)
                    num_widget.update(Text(str(len(data.rows)), style="bold"))
                except Exception:
                    pass

            elif widget_type == "markdown":
                try:
                    md_widget = widget.query_one(f"#pane-md-{i}", Markdown)
                    md_widget.update(data.text or "_No content._")
                except Exception:
                    pass

            elif widget_type == "log" and isinstance(widget, TextArea):
                widget.text = data.text
                widget.scroll_end(animate=False)

            elif widget_type == "tree" and isinstance(widget, DirectoryTree):
                try:
                    widget.reload()
                except Exception:
                    pass

    def get_selected_node(self) -> str | None:
        """Find the currently highlighted node id in this building's panes, if any."""
        from orkcraft.wm.desktop import node_id_of

        app = getattr(self, "app", None)
        if app is not None and app.focused is not None:
            w = app.focused
            if isinstance(w, DataTable) and w.row_count:
                try:
                    nid = node_id_of(w.coordinate_to_cell_key(w.cursor_coordinate).row_key.value)
                    if nid:
                        return nid
                except Exception:
                    pass
            elif isinstance(w, OptionList) and w.highlighted is not None:
                try:
                    nid = node_id_of(w.get_option_at_index(w.highlighted).id)
                    if nid:
                        return nid
                except Exception:
                    pass

        for dt in self.query(DataTable):
            if dt.row_count:
                try:
                    nid = node_id_of(dt.coordinate_to_cell_key(dt.cursor_coordinate).row_key.value)
                    if nid:
                        return nid
                except Exception:
                    pass

        for ol in self.query(OptionList):
            if ol.highlighted is not None and ol.highlighted < ol.option_count:
                try:
                    nid = node_id_of(ol.get_option_at_index(ol.highlighted).id)
                    if nid:
                        return nid
                except Exception:
                    pass

        return None
