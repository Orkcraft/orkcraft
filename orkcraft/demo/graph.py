"""Simple markdown entity reader for demo showcase sandbox only."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DemoEntity:
    id: str
    title: str = ""
    type: str = "task"
    status: str = "todo"
    subtype: str = ""
    priority: str = "medium"
    assignee: str = ""
    tags: list[str] = field(default_factory=list)
    deadline: str | None = None
    summary: str = ""
    is_personal: bool = False


class Graph:
    """Lightweight in-memory entity index for simulated demo files."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.entities: dict[str, DemoEntity] = {}
        self._load()

    def _load(self) -> None:
        for md in self.root.glob("**/*.md"):
            try:
                text = md.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                parts = text.split("---", 2)
                if len(parts) < 3:
                    continue
                data = {}
                for line in parts[1].splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if v.startswith("[") and v.endswith("]"):
                            v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                        data[k] = v
                eid = str(data.get("id") or md.stem)
                tags = data.get("tags")
                if not isinstance(tags, list):
                    tags = [tags] if tags else []
                self.entities[eid] = DemoEntity(
                    id=eid,
                    title=str(data.get("title", "")),
                    type=str(data.get("type", "task")),
                    status=str(data.get("status", "todo")),
                    subtype=str(data.get("subtype", "")),
                    priority=str(data.get("priority", "medium")),
                    assignee=str(data.get("assignee", "")),
                    tags=tags,
                    deadline=data.get("deadline") if data.get("deadline") != "null" else None,
                    summary=str(data.get("summary", "")),
                )
            except Exception:
                pass

    def get_entity(self, ident: str) -> DemoEntity | None:
        return self.entities.get(ident)
