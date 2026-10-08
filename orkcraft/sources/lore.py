"""Where the 🗑️ Scroll Dump's wiki comes from: one adapter per kind of source, read-only.

A building's `sources` (and the older `paths`) are strings, one per source:

    docs                         a folder of Markdown notes in the project (also `fs:docs`)
    code:src                     a folder of code in the project
    dir:~/Documents/specs        any folder, in the project or outside: notes, text, code, .docx, .pdf
                                 (docs/design/wiki-folders-rules.md §1)
    git:main                     the notes and code of a revision (`git:<rev>[:<folder>]`), via git
    confluence:ENG               a Confluence space; the site is `$ORKCRAFT_CONFLUENCE_URL`, or
    confluence:ENG@https://acme.atlassian.net/wiki
    gdrive:google-ann@gmail.com  the Google Drive of a Google sign-in (Settings → Accounts): its Docs as
    gdrive:google-ann@gmail.com/<folder id>   Markdown and its text files, the whole Drive or one folder

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
from orkcraft.realm import extract, shelves
from orkcraft.realm.shelves import Base, Note

DOC_EXT = (".md", ".markdown", ".mdx", ".rst", ".txt")
CODE_EXT = (".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".rb",
            ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".scala", ".lua", ".sh")
MAX_DOCS = shelves.MAX_NOTES
REMOTE_TTL_S = 15 * 60
FETCH_TIMEOUT_S = 20
FETCHING = "fetching…"
MAX_FILES = 2000                 # a `dir:` source reads at most this many files (`max_files`)
ICONS = {"fs": "📁", "code": "🧩", "dir": "📂", "git": "🌿", "confluence": "📘", "gdrive": "🗂"}
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
        """A project file under this folder (prefixed paths belong to the other sources)."""
        if ":" in path:
            return False
        folder = PurePosixPath(self.path.replace("\\", "/")).as_posix().strip("/")
        return folder in ("", ".") or path == folder or path.startswith(folder + "/")


# -- any folder ---------------------------------------------------------------------------------------

class DirSource(Source):
    """`dir:<folder>` — everything the wiki can read in a folder, in the project or outside it (read-only):
    notes and text, code, .docx (its text) and .pdf (the AI tool reads it). What the folder's .gitignore
    ignores, hidden folders, secrets and files over `extract.MAX_BYTES` are skipped.

    A file in the project keeps its repo-relative path; one outside is `dir:<folder>/<path>`, its
    version its size and mtime (a big folder is not hashed on every look)."""
    kind = "dir"

    def __init__(self, spec: str, repo_root: Path, path: str, max_files: int = MAX_FILES) -> None:
        super().__init__(spec, repo_root)
        self.path, self.max_files = path.strip() or ".", max_files

    @property
    def root(self) -> Path:
        p = Path(self.path).expanduser()
        return (p if p.is_absolute() else self.repo_root / p).resolve()

    @property
    def inside(self) -> bool:
        root, repo = self.root, self.repo_root.resolve()
        return root == repo or repo in root.parents

    @property
    def prefix(self) -> str:
        return f"dir:{self.root.as_posix().rstrip('/')}/"

    def scan(self) -> Base:
        root = self.root
        if not root.is_dir():
            return Base(self.path, error=f"{self.path}: no such folder", kind=self.kind)
        notes, cut = [], False
        for rel in self.files(root):
            p = root / rel
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size > extract.MAX_BYTES:
                continue
            if len(notes) >= self.max_files:
                cut = True
                break
            kind = extract.kind_of(rel)
            title = PurePosixPath(rel).name
            if kind == "doc" and rel.lower().endswith((".md", ".markdown")) and st.st_size < 1_000_000:
                title = shelves.read_note(p, self.repo_root).title
            if self.inside:
                notes.append(Note(shelves.rel_to(self.repo_root, p), title, [], st.st_mtime,
                                  kind="code" if kind == "code" else "doc"))
            else:
                notes.append(Note(self.prefix + rel, title, [], st.st_mtime, kind="code" if kind == "code" else "doc",
                                  rev=f"{st.st_size}-{int(st.st_mtime)}"))
        return Base(self.path, notes, error=f"cut at {self.max_files} files" if cut else "", kind=self.kind)

    def files(self, root: Path) -> list[str]:
        """The folder's files the wiki may read, relative to it: git's list when the folder is in a work
        tree (what .gitignore ignores is left out), else a walk."""
        listed = _git_files(root)
        if listed is None:
            listed = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in shelves.SKIP_DIRS and not d.startswith("."))
                base = Path(dirpath).relative_to(root).as_posix()
                listed += [n if base == "." else f"{base}/{n}" for n in sorted(filenames)]
        return [r for r in listed if extract.kind_of(r) and not extract.secret(r) and not _skipped(r)
                and not PurePosixPath(r).name.startswith(".")]

    def file_of(self, path: str) -> Path:
        """The file behind one of this source's paths."""
        if path.startswith(self.prefix):
            p = (self.root / path[len(self.prefix):]).resolve()
        else:
            p = shelves.inside(self.repo_root, path)
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"{path} is outside {self.path}")
        return p

    def read(self, path: str) -> str:
        p = self.file_of(path)
        kind = extract.kind_of(p.name)
        if kind == "pdf":
            return f"_A PDF ({p.name}): the librarian reads it with its own tools._"
        if kind == "docx":
            return extract.docx_text(p.read_bytes())
        return p.read_text(encoding="utf-8", errors="replace")

    def owns(self, path: str) -> bool:
        if path.startswith(self.prefix):
            return True
        if ":" in path or not self.inside:
            return False
        folder = shelves.rel_to(self.repo_root, self.root).strip("/")
        return folder in ("", ".") or path == folder or path.startswith(folder + "/")

    def in_place(self, path: str) -> Path | None:
        """The file the librarian reads where it is: a PDF anywhere, text and code in the project; None
        when it reads a snapshot instead (a .docx's text, a text file outside the project)."""
        kind = extract.kind_of(path)
        if kind == "pdf" or (self.inside and kind in ("doc", "code")):
            return self.file_of(path)
        return None


def _git_files(root: Path) -> list[str] | None:
    try:
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, timeout=10)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                             capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return sorted(p for p in out.stdout.decode("utf-8", errors="replace").split("\0") if p)


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
class GoogleDriveSource(RemoteSource):
    """`gdrive:<login>[/<folder id>]` — the Docs (as Markdown) and text files of a Google Drive, or of one folder
    and the folders in it; read-only (realm/google.py). A file whose version is the cache's is not read again."""
    kind = "gdrive"

    def __init__(self, spec: str, repo_root: Path, arg: str) -> None:
        super().__init__(spec, repo_root)
        name, _, self.folder = arg.strip().partition("/")
        self.ref = f"keychain:{name.strip()}"
        self.folder = self.folder.strip()

    @property
    def label(self) -> str:
        account = self.ref.removeprefix("keychain:google-")
        return f"Google Drive · {account}" + (" · a folder" if self.folder else "")

    def fetch(self) -> list[dict]:
        from orkcraft.realm import google
        try:
            files = google.drive_files(self.ref, self.folder, MAX_DOCS)
            held = {d.get("id"): d for d in self.load()[0]}
            docs = []
            for f in files:
                fid, version = str(f.get("id")), str(f.get("modifiedTime") or "")
                old = held.get(fid)
                text = old.get("text") if old and old.get("version") == version else google.drive_text(self.ref, f)
                docs.append({"id": fid, "title": f.get("name") or fid, "text": text or "", "version": version,
                             "url": f.get("webViewLink") or "", "kind": "doc"})
        except google.GoogleError as e:
            raise ValueError(str(e)) from None
        return docs


def parse(spec: str, repo_root: Path, max_files: int = MAX_FILES) -> Source:
    """One config string → its source (a bare path is a folder of notes)."""
    spec = spec.strip()
    kind, sep, arg = spec.partition(":")
    if not sep or kind not in KINDS:
        return FolderSource(spec, repo_root, spec)
    if kind in ("fs", "code"):
        return FolderSource(spec, repo_root, arg.strip(), kind)
    if kind == "dir":
        return DirSource(spec, repo_root, arg.strip(), max_files)
    if kind == "git":
        rev, _, path = arg.partition(":")
        return GitSource(spec, repo_root, rev.strip(), path.strip())
    if kind == "gdrive":
        return GoogleDriveSource(spec, repo_root, arg)
    return ConfluenceSource(spec, repo_root, arg)


def from_config(config: dict, repo_root: Path) -> list[Source]:
    """The building's sources: `sources` and the older `paths`, else the project's usual notes folders."""
    specs = [str(s).strip() for key in ("sources", "paths") for s in (config.get(key) or []) if str(s).strip()]
    specs = list(dict.fromkeys(specs)) or shelves.default_bases(repo_root)
    try:
        most = max(1, int(config.get("max_files") or MAX_FILES))
    except (TypeError, ValueError):
        most = MAX_FILES
    return [parse(s, repo_root, most) for s in specs]


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

    def outside(self) -> list[str]:
        """The folders outside the project the librarian reads (`dir:` sources): its AI tool is let in, read-only."""
        return [str(s.root) for s in self.sources if isinstance(s, DirSource) and not s.inside and s.root.is_dir()]

    def in_place(self, path: str) -> Path | None:
        """The file the librarian reads where it is, for a `dir:` source's document (else None)."""
        for s in self.sources:
            if isinstance(s, DirSource) and s.owns(path):
                try:
                    return s.in_place(path)
                except ValueError:
                    return None
        return None
