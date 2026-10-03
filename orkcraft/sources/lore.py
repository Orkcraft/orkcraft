"""Where the 🗑️ Scroll Dump's wiki comes from: one adapter per kind of source, read-only.

A building's `sources` (and the older `paths`) are strings, one per source:

    docs                         a folder of Markdown notes in the project (also `fs:docs`)
    code:src                     a folder of code in the project
    git:main                     the notes and code of a revision (`git:<rev>[:<folder>]`), via git
    confluence:ENG               a Confluence space; the site is `$ORKCRAFT_CONFLUENCE_URL`, or
    confluence:ENG@https://acme.atlassian.net/wiki

Every source lists its documents as a `shelves.Base` of `shelves.Note`s (each with its kind: doc,
code or design) and reads one by its path. Project files keep their repo-relative path (what
`knowledge.changed` sends); the rest are prefixed (`git:main:docs/a.md`, `confluence:123`).

Remote sources never block the screen: `scan()` gives what the cache has and refetches in the
background once it is older than `REMOTE_TTL_S`; a failed fetch keeps the cache and says why.
Confluence signs in with `$ORKCRAFT_CONFLUENCE_EMAIL` + `$ORKCRAFT_CONFLUENCE_TOKEN` (Cloud API
token) or `$ORKCRAFT_CONFLUENCE_PAT` (Server / Data Center). Standard library only.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from orkcraft.env import getenv
from orkcraft.realm import shelves
from orkcraft.realm.shelves import Base, Note

DOC_EXT = (".md", ".markdown", ".mdx", ".rst", ".txt")
CODE_EXT = (".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".rb",
            ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".scala", ".lua", ".sh")
MAX_DOCS = shelves.MAX_NOTES
REMOTE_TTL_S = 15 * 60
FETCH_TIMEOUT_S = 20
FETCHING = "fetching…"
ICONS = {"fs": "📁", "code": "🧩", "git": "🌿", "confluence": "📘"}
KINDS = tuple(ICONS)


def kind_of(path: str) -> str | None:
    """doc, code — or None for a file the scrolls do not read."""
    low = path.lower()
    if low.endswith(DOC_EXT):
        return "doc"
    if low.endswith(CODE_EXT):
        return "code"
    return None


def _title_of(text: str, path: str, kind: str) -> tuple[str, list[str]]:
    if kind == "code":
        return PurePosixPath(path).name, []
    return shelves.outline(text, PurePosixPath(path).stem)


class Source:
    """A place the scrolls come from. `spec` is the config string it was made from."""
    kind = ""

    def __init__(self, spec: str, repo_root: Path) -> None:
        self.spec, self.repo_root = spec, repo_root

    @property
    def label(self) -> str:
        return self.spec

    def scan(self) -> Base:
        raise NotImplementedError

    def read(self, path: str) -> str:
        raise NotImplementedError

    def owns(self, path: str) -> bool:
        return True


# -- the project's own folders ------------------------------------------------------------------------

class FolderSource(Source):
    """A folder in the project: its Markdown notes (`fs:`), or its code (`code:`)."""

    def __init__(self, spec: str, repo_root: Path, path: str, kind: str = "fs") -> None:
        super().__init__(spec, repo_root)
        self.path, self.kind = path or ".", kind

    @property
    def label(self) -> str:
        return self.path if self.kind == "fs" else self.spec

    def scan(self) -> Base:
        if self.kind == "fs":
            base = shelves.scan_base(self.repo_root, self.path)
            base.path = self.label
            return base
        try:
            root = shelves.inside(self.repo_root, self.path)
        except ValueError as e:
            return Base(self.label, error=str(e), kind=self.kind)
        if not root.is_dir():
            return Base(self.label, error=f"{self.path}: no such folder", kind=self.kind)
        notes = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in shelves.SKIP_DIRS and not d.startswith("."))
            for name in sorted(filenames):
                if kind_of(name) != "code":
                    continue
                p = Path(dirpath) / name
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    mtime = 0.0
                notes.append(Note(shelves.rel_to(self.repo_root, p), name, [], mtime, kind="code"))
                if len(notes) >= MAX_DOCS:
                    return Base(self.label, notes, kind=self.kind)
        return Base(self.label, notes, kind=self.kind)

    def read(self, path: str) -> str:
        return shelves.inside(self.repo_root, path).read_text(encoding="utf-8", errors="replace")

    def owns(self, path: str) -> bool:
        return ":" not in path


# -- a git revision -----------------------------------------------------------------------------------

class GitSource(Source):
    """`git:<rev>[:<folder>]` — the notes and code as they are in that revision, read through git."""
    kind = "git"

    def __init__(self, spec: str, repo_root: Path, rev: str, path: str = "") -> None:
        super().__init__(spec, repo_root)
        self.rev, self.path = rev or "HEAD", path.strip("/")
        self.prefix = f"git:{self.rev}:"

    def _git(self, *args: str, stdin: bytes | None = None) -> bytes:
        out = subprocess.run(["git", *args], cwd=self.repo_root, input=stdin, capture_output=True, timeout=30)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.decode(errors="replace").strip()[:200] or "git failed")
        return out.stdout

    def scan(self) -> Base:
        if self.rev.startswith("-"):
            return Base(self.label, error=f"{self.rev}: not a revision", kind=self.kind)
        try:
            listing = self._git("ls-tree", "-r", "-z", self.rev, "--", *([self.path] if self.path else []))
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            return Base(self.label, error=str(e), kind=self.kind)
        files = []
        for row in listing.decode(errors="replace").split("\0"):
            meta, _, path = row.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob" and kind_of(path) and not _skipped(path):
                files.append((parts[2], path))
            if len(files) >= MAX_DOCS:
                break
        texts = self._blobs([sha for sha, _ in files])
        notes = []
        for sha, path in files:
            kind = kind_of(path) or "doc"
            title, heads = _title_of(texts.get(sha, ""), path, kind)
            notes.append(Note(self.prefix + path, title, heads, kind=kind, rev=sha))
        return Base(self.label, notes, kind=self.kind)

    def _blobs(self, shas: list[str]) -> dict[str, str]:
        """The texts of the blobs (only their heads: enough for a title), in one `git cat-file`."""
        if not shas:
            return {}
        try:
            raw = self._git("cat-file", "--batch", stdin=("\n".join(shas) + "\n").encode())
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            return {}
        out, i = {}, 0
        while i < len(raw):
            nl = raw.index(b"\n", i)
            head = raw[i:nl].decode(errors="replace").split()
            if len(head) < 3 or head[1] == "missing":
                i = nl + 1
                continue
            size = int(head[2])
            out[head[0]] = raw[nl + 1:nl + 1 + min(size, 20000)].decode("utf-8", errors="replace")
            i = nl + 1 + size + 1
        return out

    def read(self, path: str) -> str:
        rel = path[len(self.prefix):] if path.startswith(self.prefix) else path
        return self._git("show", f"{self.rev}:{rel}").decode("utf-8", errors="replace")

    def owns(self, path: str) -> bool:
        return path.startswith(self.prefix)


def _skipped(path: str) -> bool:
    return any(part in shelves.SKIP_DIRS or part.startswith(".") for part in PurePosixPath(path).parts[:-1])


# -- remote sources -----------------------------------------------------------------------------------

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(getenv("SCROLLS_CACHE_DIR") or Path(base) / "orkcraft" / "scrolls").expanduser()


class RemoteSource(Source):
    """A source behind the network: a JSON cache of its documents, refetched in the background.

    Subclasses give `fetch()` → [{"id", "title", "text", "version", "url"}…]."""
    ttl = REMOTE_TTL_S

    def __init__(self, spec: str, repo_root: Path) -> None:
        super().__init__(spec, repo_root)
        self.prefix = f"{self.kind}:"
        self.error = ""
        self._lock = threading.Lock()
        self._busy = False

    @property
    def cache_file(self) -> Path:
        return cache_dir() / f"{hashlib.sha1(self.spec.encode()).hexdigest()[:16]}.json"

    def fetch(self) -> list[dict]:
        raise NotImplementedError

    def load(self) -> tuple[list[dict], float]:
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return list(data.get("docs") or []), float(data.get("at") or 0)
        except (OSError, ValueError, AttributeError):
            return [], 0.0

    def refresh(self) -> None:
        """Fetch now (on the caller's thread) and keep the result; a failure keeps the old cache."""
        try:
            docs = self.fetch()
        except Exception as e:                                     # network, auth, a bad answer
            self.error = _short(e)
            return
        finally:
            with self._lock:
                self._busy = False
        self.error = ""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"spec": self.spec, "at": time.time(), "docs": docs}), encoding="utf-8")
            tmp.replace(self.cache_file)
        except OSError as e:
            self.error = f"cache: {e}"

    def refresh_in_background(self) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self.refresh, name=f"scrolls:{self.spec}", daemon=True).start()

    def scan(self) -> Base:
        docs, at = self.load()
        if time.time() - at > self.ttl:
            self.refresh_in_background()
        notes = []
        for d in docs[:MAX_DOCS]:
            title, heads = shelves.outline(d.get("text") or "", d.get("title") or str(d.get("id")))
            notes.append(Note(self.prefix + str(d.get("id")), d.get("title") or title, heads,
                              kind=d.get("kind") or "doc", rev=str(d.get("version") or ""), url=d.get("url") or ""))
        error = self.error or ("" if docs or at else FETCHING)
        return Base(self.label, notes, error=error, kind=self.kind)

    def read(self, path: str) -> str:
        key = path[len(self.prefix):] if path.startswith(self.prefix) else path
        for d in self.load()[0]:
            if str(d.get("id")) == key:
                link = f"\n\n[open ↗]({d['url']})" if d.get("url") else ""
                return (d.get("text") or "") + link
        raise ValueError(f"{path}: not in the cache yet")

    def owns(self, path: str) -> bool:
        return path.startswith(self.prefix)


def _short(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}" + (" — check the token" if e.code in (401, 403) else "")
    return (str(e) or type(e).__name__)[:160]


def http_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "orkcraft", "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class ConfluenceSource(RemoteSource):
    """`confluence:<SPACE>[@<site>]` — the pages of a space, as Markdown-ish text."""
    kind = "confluence"
    PAGE = 50

    def __init__(self, spec: str, repo_root: Path, arg: str) -> None:
        super().__init__(spec, repo_root)
        space, _, site = arg.partition("@")
        self.space = space.strip()
        self.site = (site.strip() or getenv("CONFLUENCE_URL")).rstrip("/")

    def headers(self) -> dict[str, str]:
        pat = getenv("CONFLUENCE_PAT")
        if pat:
            return {"Authorization": f"Bearer {pat}"}
        email, token = getenv("CONFLUENCE_EMAIL"), getenv("CONFLUENCE_TOKEN")
        if email and token:
            return {"Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()}
        return {}

    def fetch(self) -> list[dict]:
        if not self.space:
            raise ValueError("no space: confluence:<SPACE>")
        if not self.site.startswith(("https://", "http://")):
            raise ValueError("no site: set ORKCRAFT_CONFLUENCE_URL or write confluence:SPACE@https://…/wiki")
        headers = self.headers()
        if not headers:
            raise ValueError("no token: set ORKCRAFT_CONFLUENCE_EMAIL + _TOKEN, or _PAT")
        docs, start = [], 0
        while len(docs) < MAX_DOCS:
            q = urllib.parse.urlencode({"spaceKey": self.space, "type": "page", "limit": self.PAGE, "start": start,
                                        "expand": "body.storage,version"})
            data = http_json(f"{self.site}/rest/api/content?{q}", headers)
            results = data.get("results") or []
            base = (data.get("_links") or {}).get("base") or self.site
            for page in results:
                webui = (page.get("_links") or {}).get("webui") or ""
                docs.append({"id": str(page.get("id")), "title": page.get("title") or "",
                             "text": storage_to_markdown(((page.get("body") or {}).get("storage") or {}).get("value") or ""),
                             "version": str((page.get("version") or {}).get("number") or ""),
                             "url": base + webui if webui else "", "kind": "doc"})
            if len(results) < self.PAGE or not (data.get("_links") or {}).get("next"):
                break
            start += len(results)
        return docs[:MAX_DOCS]


class _Storage(HTMLParser):
    """Confluence storage format (XHTML) → Markdown-ish text: headings, lists, paragraphs, code."""
    BLOCK = {"p", "div", "br", "tr", "table", "blockquote", "pre", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * min(int(tag[1]), 3) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "table"):
            self.out.append("\n\n")

    def handle_data(self, data):
        self.out.append(data)


def storage_to_markdown(html: str) -> str:
    p = _Storage()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    lines = [ln.rstrip() for ln in "".join(p.out).splitlines()]
    text, blank = [], False
    for ln in lines:
        if not ln.strip():
            if not blank and text:
                text.append("")
            blank = True
        else:
            text.append(ln.strip() if not ln.lstrip().startswith(("- ", "|")) else ln.lstrip())
            blank = False
    return "\n".join(text).strip()


# -- the config -----------------------------------------------------------------------------------------

def parse(spec: str, repo_root: Path) -> Source:
    """One config string → its source (a bare path is a folder of notes)."""
    spec = spec.strip()
    kind, sep, arg = spec.partition(":")
    if not sep or kind not in KINDS:
        return FolderSource(spec, repo_root, spec)
    if kind in ("fs", "code"):
        return FolderSource(spec, repo_root, arg.strip(), kind)
    if kind == "git":
        rev, _, path = arg.partition(":")
        return GitSource(spec, repo_root, rev.strip(), path.strip())
    return ConfluenceSource(spec, repo_root, arg)


def from_config(config: dict, repo_root: Path) -> list[Source]:
    """The building's sources: `sources` and the older `paths`, else the project's usual notes folders."""
    specs = [str(s).strip() for key in ("sources", "paths") for s in (config.get(key) or []) if str(s).strip()]
    specs = list(dict.fromkeys(specs)) or shelves.default_bases(repo_root)
    return [parse(s, repo_root) for s in specs]


# -- reading across the sources ---------------------------------------------------------------------

def reader(sources: list[Source]):
    """read(path) → the text of a document of any of `sources` (ValueError when none has it)."""
    def read(path: str) -> str:
        for s in sources:
            if s.owns(path):
                try:
                    return s.read(path)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                    raise ValueError(str(e)) from e
        raise ValueError(f"{path}: no source has it")
    return read


class Library:
    """The sources of one building and what they hold."""

    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources
        self.bases: list[Base] = []
        self.read = reader(sources)

    def scan(self) -> list[Base]:
        self.bases = [s.scan() for s in self.sources]
        return self.bases

    def notes(self, kind: str | None = None) -> list[Note]:
        return [n for b in self.bases for n in b.notes if kind is None or n.kind == kind]

    def is_project_file(self, path: str) -> bool:
        """A file of the project itself (the wiki's orc reads it in place) — not a snapshot to take."""
        return any(isinstance(s, FolderSource) and s.owns(path) for s in self.sources)
