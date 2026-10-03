"""The code graph: the Scroll Dump's retriever for code (a first, small GraphRAG).

    graph = codegraph.build({path: text, …})       symbols and the edges between them
    codegraph.search(graph, "retry the upload")    the symbols that answer, each with its neighbours

A symbol is a module, a class or a function. Python is read with `ast` (qualified names, docstrings,
calls, imports); other languages by their definition keywords (`function`, `func`, `fn`, `class`,
`struct`…) and the names they call. Edges: a module contains its symbols, a symbol calls another
(by name; a name defined in more than `AMBIGUOUS` places links nowhere), a module imports a module.

A query is ranked against each symbol's name split into words (`retryUpload` → retry upload), its
docstring and its path (BM25, as the notes are); the best symbols come back with their code and
what they call, what calls them and what their module imports — then their best-scoring
neighbours, while the budget lasts. Pure module.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from orkcraft.realm import shelves
from orkcraft.realm.shelves import Chunk

AMBIGUOUS = 3
SNIPPET_LINES = 40
_DEF = re.compile(r"^\s*(?:export\s+|pub(?:\([^)]*\))?\s+|public\s+|private\s+|protected\s+|static\s+|async\s+|"
                  r"abstract\s+|final\s+|default\s+)*(?P<kw>function\*?|func|fn|def|class|struct|interface|trait|"
                  r"enum|impl|object|module)\s+(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_$][\w$]*)")
_ARROW = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?"
                    r"(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)")
_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
_KEYWORDS = frozenset("if for while switch return catch function func fn def class new typeof sizeof print "
                      "super self this await match elif with not and or".split())
_CLASSY = ("class", "struct", "interface", "trait", "enum", "impl", "object", "module")


@dataclass
class Symbol:
    id: str                              # path::Qual.name (a module: its path)
    name: str                            # the short name calls are matched by
    qual: str
    path: str
    kind: str                            # module | class | function
    line: int = 1
    end: int = 1
    doc: str = ""
    calls: set[str] = field(default_factory=set)


@dataclass
class Graph:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    texts: dict[str, list[str]] = field(default_factory=dict)          # path → its lines
    calls: dict[str, set[str]] = field(default_factory=dict)           # id → ids it calls
    callers: dict[str, set[str]] = field(default_factory=dict)         # id → ids that call it
    imports: dict[str, set[str]] = field(default_factory=dict)         # module id → module ids
    errors: dict[str, str] = field(default_factory=dict)               # path → why it was not parsed

    def neighbours(self, sid: str) -> set[str]:
        s = self.symbols[sid]
        return (self.calls.get(sid, set()) | self.callers.get(sid, set()) | self.imports.get(sid, set())
                | ({s.path} if s.kind != "module" else set())) - {sid}


# -- reading the code ---------------------------------------------------------------------------------

def _py_symbols(path: str, text: str, raw_imports: list[str]) -> list[Symbol]:
    tree = ast.parse(text)
    out = [Symbol(path, PurePosixPath(path).stem, PurePosixPath(path).stem, path, "module", 1,
                  max(len(text.splitlines()), 1), (ast.get_docstring(tree) or "")[:400])]

    def own_nodes(node: ast.AST):
        """`node`'s body, without the functions and classes defined in it (they are symbols of their own)."""
        stack = list(ast.iter_child_nodes(node))
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield n
            stack.extend(ast.iter_child_nodes(n))

    def calls_in(node: ast.AST) -> set[str]:
        names = set()
        for n in own_nodes(node):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    names.add(f.id)
                elif isinstance(f, ast.Attribute):
                    names.add(f.attr)
        return names

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = f"{prefix}{node.name}"
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                out.append(Symbol(f"{path}::{qual}", node.name, qual, path, kind, node.lineno,
                                  getattr(node, "end_lineno", node.lineno) or node.lineno,
                                  (ast.get_docstring(node) or "")[:400], calls_in(node) - {node.name}))
                visit(node.body, qual + ".")

    visit(tree.body, "")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            raw_imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            raw_imports.append(node.module)
            raw_imports += [f"{node.module}.{a.name}" for a in node.names]
    return out


def _generic_symbols(path: str, text: str) -> list[Symbol]:
    lines = text.splitlines()
    out = [Symbol(path, PurePosixPath(path).stem, PurePosixPath(path).stem, path, "module", 1, max(len(lines), 1))]
    starts = []
    for i, line in enumerate(lines, 1):
        m = _DEF.match(line) or _ARROW.match(line)
        if m:
            kw = m.groupdict().get("kw") or "function"
            starts.append((i, m.group("name"), "class" if kw in _CLASSY else "function", _comment_above(lines, i)))
    for k, (line, name, kind, doc) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line:end])
        calls = {c for c in _CALL.findall(body) if c not in _KEYWORDS} - {name}
        out.append(Symbol(f"{path}::{name}@{line}", name, name, path, kind, line, end, doc, calls))
    return out


def _comment_above(lines: list[str], line: int) -> str:
    doc = []
    for prev in reversed(lines[max(line - 6, 0):line - 1]):
        s = prev.strip()
        if s.startswith(("//", "#", "*", "/*", "///", "--")):
            doc.insert(0, s.lstrip("/#*- ").strip())
        else:
            break
    return " ".join(doc)[:400]


def _module_names(path: str) -> list[str]:
    """The dotted names an import may use for `path` (`orkcraft/realm/pit.py` → realm.pit, orkcraft.realm.pit…)."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return [".".join(parts[i:]) for i in range(len(parts)) if parts[i:]]


def build(texts: dict[str, str]) -> Graph:
    """The graph of `texts` (path → source code)."""
    g = Graph()
    raw_imports: dict[str, list[str]] = {}
    for path, text in texts.items():
        g.texts[path] = text.splitlines()
        imports: list[str] = []
        try:
            syms = _py_symbols(path, text, imports) if path.endswith((".py", ".pyi")) else _generic_symbols(path, text)
        except (SyntaxError, ValueError, RecursionError) as e:
            g.errors[path] = str(e)[:120]
            syms = _generic_symbols(path, text)
        raw_imports[path] = imports
        for s in syms:
            g.symbols[s.id] = s
    by_name: dict[str, list[str]] = {}
    for s in g.symbols.values():
        if s.kind != "module":
            by_name.setdefault(s.name, []).append(s.id)
    for s in g.symbols.values():
        for name in s.calls:
            targets = by_name.get(name, [])
            if 0 < len(targets) <= AMBIGUOUS:
                for t in targets:
                    if t != s.id:
                        g.calls.setdefault(s.id, set()).add(t)
                        g.callers.setdefault(t, set()).add(s.id)
    modules = {name: path for path in texts for name in _module_names(path)}
    for path, names in raw_imports.items():
        for name in names:
            target = modules.get(name) or modules.get(name.rpartition(".")[0])
            if target and target != path:
                g.imports.setdefault(path, set()).add(target)
    return g


# -- answering ------------------------------------------------------------------------------------------

def words(name: str) -> str:
    """`retryUpload_now` → `retry upload now`: identifiers as the words a question uses."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return re.sub(r"[_\-.$/]+", " ", spaced).lower()


def _label(g: Graph, sid: str) -> str:
    s = g.symbols[sid]
    return s.path if s.kind == "module" else f"{s.qual} ({PurePosixPath(s.path).name}:{s.line})"


def fragment(g: Graph, sid: str, score: float = 0.0) -> Chunk:
    """A symbol as a prompt fragment: its code (cut at SNIPPET_LINES) and its place in the graph."""
    s = g.symbols[sid]
    lines = g.texts.get(s.path, [])
    end = min(s.end, s.line + SNIPPET_LINES - 1)
    code = "\n".join(lines[s.line - 1:end]) + ("\n…" if s.end > end else "")
    rel = []
    for title, ids in (("calls", g.calls.get(sid)), ("called by", g.callers.get(sid)), ("imports", g.imports.get(sid))):
        if ids:
            names = sorted(_label(g, i) for i in ids)
            rel.append(f"{title}: " + ", ".join(names[:8]) + (f" +{len(names) - 8}" if len(names) > 8 else ""))
    lang = PurePosixPath(s.path).suffix.lstrip(".")
    text = f"```{lang}\n{code}\n```" + ("\n" + "\n".join(rel) if rel else "")
    heading = s.path if s.kind == "module" else f"{s.qual} ({s.kind}, L{s.line}–{s.end})"
    return Chunk(s.path, heading, text, score)


def search(g: Graph, query: str, k: int = 5, budget: int = 4000) -> list[Chunk]:
    """The symbols that answer `query` best, then their best neighbours, within `k` and `budget`."""
    ids = [sid for sid, s in g.symbols.items() if s.kind != "module"] or list(g.symbols)
    probes = [Chunk(sid, words(g.symbols[sid].qual), f"{g.symbols[sid].doc} {words(g.symbols[sid].path)}")
              for sid in ids]
    ranked = shelves.rank(probes, query)
    if not ranked:
        return []
    scores = {c.path: c.score for c in ranked}
    order, seen = [], set()
    for c in ranked[:k]:
        if c.path not in seen:
            order.append((c.path, c.score))
            seen.add(c.path)
    for sid, score in list(order):                           # one hop out: the neighbours that matter
        near = sorted((n for n in g.neighbours(sid) if n not in seen and g.symbols[n].kind != "module"),
                      key=lambda n: scores.get(n, 0.0), reverse=True)
        for n in near[:2]:
            order.append((n, score * 0.5 + scores.get(n, 0.0)))
            seen.add(n)
    order.sort(key=lambda p: p[1], reverse=True)
    return shelves.within([fragment(g, sid, score) for sid, score in order], k, budget)
