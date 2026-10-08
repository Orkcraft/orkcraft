"""The Wiki as an MCP server: any AI tool searches and reads one LLM wiki (docs/design/wiki-mcp.md).

    python -m orkcraft.wiki_mcp --project <repo> --wiki <the wiki's folder>

It speaks MCP over stdio (one JSON-RPC message per line) and offers three tools, read-only:

    wiki_map       the wiki's map (index.md) and its rules for AI tools (RULES.md)
    wiki_search    the pages that match a query: title, aliases, text — no model
    wiki_read      one page, by its path

A page's path is relative to the project, as the rules cite it; nothing outside the wiki's folder is
read. Standard library only, no Textual: AI tools start it, not the town.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orkcraft import __version__
from orkcraft.realm import shelves, wiki, wikifind, wikirules

PROTOCOL = "2025-06-18"
NAME = "orkcraft-wiki"
READ_CHARS = 60_000
TOOLS = [
    {"name": "wiki_map", "description": "The project's LLM wiki: its map (index.md) and its rules for AI tools — "
                                        "where things are and how to use it. Read it first.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "wiki_search", "description": "Search the project's LLM wiki (titles, aliases, text) before answering "
                                           "about the project. Returns pages with their path and the line that matched.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "what to look for, in any language"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8}}, "required": ["query"]},
     "annotations": {"readOnlyHint": True}},
    {"name": "wiki_read", "description": "Read one page of the project's LLM wiki by its path (as wiki_search or the "
                                         "map gives it). Cite it by that path.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
     "annotations": {"readOnlyHint": True}},
]


class Wiki:
    """One wiki of a project, read as the tools ask."""

    def __init__(self, project: Path, root: Path) -> None:
        self.project, self.root = project.resolve(), root.resolve()

    @property
    def rel(self) -> str:
        return shelves.rel_to(self.project, self.root)

    def map(self) -> str:
        parts = []
        for name in (wiki.INDEX, wikirules.RULES):
            text = _read(self.root / name)
            if text:
                parts.append(f"<!-- {self.rel}/{name} -->\n{text.strip()}")
        return "\n\n".join(parts) or f"The wiki at {self.rel}/ has no map yet: its librarian has not taken anything in."

    def search(self, query: str, limit: int = 8) -> str:
        pages = [n for n in wiki.pages(self.root, self.project) if wiki.is_page(n.path)]
        hits = wikifind.find(self.project, pages, query, max(1, min(int(limit or 8), 30)))
        if not hits:
            return f"Nothing in the wiki matches {query!r}. Say so rather than guess; then look in the code or the sources."
        return "\n".join(f"- `{h['path']}` — {h['title']}" + (f": {h['line']}" if h.get("line") else "") for h in hits)

    def read(self, path: str) -> str:
        p = Path(path.strip())
        target = (p if p.is_absolute() else self.project / p).resolve()
        if not (target == self.root or self.root in target.parents):
            target = (self.root / p).resolve()                      # a path relative to the wiki's folder
        if not (self.root in target.parents) or not target.is_file():
            raise ValueError(f"{path}: no such page in the wiki at {self.rel}/")
        if wiki.RAW in target.relative_to(self.root).parts[:1]:
            raise ValueError(f"{path}: a snapshot of a source, not a page")
        return (_read(target) or "")[:READ_CHARS]

    def call(self, name: str, args: dict) -> str:
        if name == "wiki_map":
            return self.map()
        if name == "wiki_search":
            return self.search(str(args.get("query") or ""), args.get("limit") or 8)
        if name == "wiki_read":
            return self.read(str(args.get("path") or ""))
        raise KeyError(name)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def answer(w: Wiki, msg: dict) -> dict | None:
    """The reply to one JSON-RPC message (None for a notification)."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or PROTOCOL,
                  "capabilities": {"tools": {}}, "serverInfo": {"name": NAME, "version": __version__},
                  "instructions": f"The project's LLM wiki at {w.rel}/: call wiki_map first, search before answering "
                                  "about the project, cite pages by path, and never make up what it does not say."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = str(params.get("name") or ""), params.get("arguments") or {}
        try:
            result = {"content": [{"type": "text", "text": w.call(name, args if isinstance(args, dict) else {})}]}
        except KeyError:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"no tool {name!r}"}}
        except (ValueError, OSError) as e:
            result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method!r}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(w: Wiki, stdin=None, stdout=None) -> None:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}
        else:
            reply = answer(w, msg) if isinstance(msg, dict) else None
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orkcraft.wiki_mcp", description="The Wiki as an MCP server (stdio)")
    parser.add_argument("--project", required=True, help="the project's folder")
    parser.add_argument("--wiki", required=True, help="the wiki's folder")
    args = parser.parse_args(argv)
    serve(Wiki(Path(args.project).expanduser(), Path(args.wiki).expanduser()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
