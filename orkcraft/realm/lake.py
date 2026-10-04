"""🌊 The Lake of Insight: what arrives, shown the way it reads best.

    diff       a unified diff (`git diff`, a patch) → side by side, old left, new right
    markdown   a .md file or Markdown text → rendered
    code       any other text file → the text (the first lines)
    url        an http(s) URL → the page as text (GET, 10 s, 1 MB); ↗ opens it in the browser
    git        a branch name the repository knows → its diff against the base, side by side
    text       anything else

A terminal cannot draw a web page or a diagram: a URL becomes text, a mermaid block stays code.

A text file on disk (`View.path`) can be edited in the Lake: `read_for_edit` gives its whole text,
`save` writes it back — never over a change made on disk since it was read (a conflict), keeping
the file's line endings and mode.
"""
from __future__ import annotations

import html.parser
import os
import re
import tempfile
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

FETCH_TIMEOUT_S = 10
FETCH_LIMIT = 1024 * 1024
SHOW_LIMIT = 200_000
EDIT_LIMIT = 2 * 1024 * 1024        # a bigger file is shown, not edited
URL = re.compile(r"^https?://\S+$")
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


@dataclass
class View:
    kind: str                  # diff | markdown | code | url | text
    title: str
    text: str = ""
    rows: list[tuple[str, str, str]] = field(default_factory=list)   # diff: (left, right, change)
    target: str = ""           # what ↗ opens: a URL or a file path
    path: str = ""             # a text file on disk: what `e` edits


class _Text(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre"}

    def __init__(self) -> None:
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        if tag in ("h1", "h2", "h3"):
            self.out.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(page: str) -> str:
    p = _Text()
    p.feed(page)
    text = re.sub(r"[ \t]+", " ", "".join(p.out))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def fetch(url: str, opener=urllib.request.urlopen) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "orkcraft-lake"})
    with opener(req, timeout=FETCH_TIMEOUT_S) as resp:
        body = resp.read(FETCH_LIMIT).decode("utf-8", errors="replace")
        ctype = resp.headers.get("Content-Type", "") if hasattr(resp, "headers") else ""
    return html_text(body) if "html" in ctype or body.lstrip().lower().startswith(("<!doctype", "<html")) else body


def side_by_side(diff: str) -> list[tuple[str, str, str]]:
    """Unified diff → rows (left, right, change): change is ' ' same, '-' removed, '+' added,
    '~' changed, '@' a hunk or file header."""
    rows: list[tuple[str, str, str]] = []
    minus: list[str] = []
    plus: list[str] = []

    def flush() -> None:
        for i in range(max(len(minus), len(plus))):
            left = minus[i] if i < len(minus) else ""
            right = plus[i] if i < len(plus) else ""
            rows.append((left, right, "~" if left and right else "-" if left else "+"))
        minus.clear()
        plus.clear()

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            flush()
            parts = line.split(" b/", 1)
            rows.append((f"── {parts[-1] if len(parts) > 1 else line}", "", "@"))
        elif line.startswith(("index ", "--- ", "+++ ", "new file", "deleted file", "similarity", "rename ")):
            continue
        elif m := HUNK.match(line):
            flush()
            rows.append((f"@@ {m.group(1)}", f"@@ {m.group(2)}{m.group(3)}", "@"))
        elif line.startswith("-"):
            if plus:
                flush()
            minus.append(line[1:])
        elif line.startswith("+"):
            plus.append(line[1:])
        else:
            flush()
            body = line[1:] if line.startswith(" ") else line
            rows.append((body, body, " "))
    flush()
    return rows


def _branch_diff(repo: Path, name: str) -> str:
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, timeout=10)
    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}").returncode != 0:
        return ""
    base = next((b for b in ("main", "master") if git("rev-parse", "--verify", "--quiet", f"refs/heads/{b}").returncode == 0),
                "HEAD")
    return git("diff", f"{base}...{name}").stdout if base != name else ""


def look(repo: Path, kind: str, value: str, title: str = "", opener=urllib.request.urlopen) -> View:
    """What the Lake shows for one payload (kind: text | file | node)."""
    value = value or ""
    if kind == "file":
        p = (repo / value) if not Path(value).is_absolute() else Path(value)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:SHOW_LIMIT]
        except OSError as e:
            return View("text", value, str(e))
        if "\0" in text[:4000]:
            return View("text", value, f"(binary, {p.stat().st_size} bytes)", target=str(p))
        if p.suffix.lower() in (".md", ".markdown"):
            return View("markdown", value, text, target=str(p), path=str(p))
        if p.suffix.lower() in (".diff", ".patch") or text.startswith("diff --git"):
            return View("diff", value, text, side_by_side(text), str(p), str(p))
        return View("code", value, text, target=str(p), path=str(p))
    stripped = value.strip()
    if URL.match(stripped):
        try:
            return View("url", stripped, fetch(stripped, opener)[:SHOW_LIMIT], target=stripped)
        except Exception as e:  # the network, of every kind
            return View("url", stripped, f"could not fetch it: {e}", target=stripped)
    if "diff --git" in stripped or (stripped.startswith("--- ") and "\n+++ " in stripped):
        return View("diff", title or "diff", stripped, side_by_side(stripped))
    if re.fullmatch(r"[\w./-]{1,100}", stripped) and "\n" not in stripped:
        diff = _branch_diff(repo, stripped)
        if diff:
            return View("diff", f"⎇ {stripped}", diff, side_by_side(diff))
    if re.search(r"^#{1,3} |\n[-*] |\*\*|```", stripped, re.M):
        return View("markdown", title or "note", stripped)
    return View("text", title or "text", stripped)


# -- editing a file on disk -------------------------------------------------------------------------

@dataclass
class Draft:
    """A file opened for editing: what was on disk when it was read (or last saved) and its line ending."""
    path: str
    text: str                  # with \n line endings, as the editor holds it
    newline: str = "\n"        # \n or \r\n, as the file has it


def _read_raw(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


def read_for_edit(path: str) -> Draft:
    """The whole file to edit. ValueError when it cannot be: missing, too big, binary or not UTF-8."""
    p = Path(path)
    try:
        if p.stat().st_size > EDIT_LIMIT:
            raise ValueError(f"too big to edit here ({p.stat().st_size // 1024} KB); ↗ opens it")
        raw = _read_raw(p)
    except UnicodeDecodeError:
        raise ValueError("not UTF-8 text") from None
    except OSError as e:
        raise ValueError(str(e)) from None
    if "\0" in raw[:4000]:
        raise ValueError("a binary file")
    newline = "\r\n" if "\r\n" in raw else "\n"
    return Draft(str(p), raw.replace("\r\n", "\n"), newline)


def save(draft: Draft, text: str, force: bool = False) -> str:
    """Write `text` over the draft's file: "saved", "unchanged" or "conflict" (the file changed on
    disk since the draft was read and `force` is off — nothing is written). On "saved" the draft
    holds the new text. OSError when the file cannot be written."""
    p = Path(draft.path)
    try:
        now = _read_raw(p).replace("\r\n", "\n")
    except FileNotFoundError:
        now = None
    except UnicodeDecodeError:
        now = None if force else ""
    if now is not None and now != draft.text and not force:
        return "conflict" if now != text else _taken(draft, text, "unchanged")
    if now == text:
        return _taken(draft, text, "unchanged")
    mode = p.stat().st_mode & 0o7777 if p.exists() else None
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text.replace("\n", draft.newline))
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return _taken(draft, text)


def _taken(draft: Draft, text: str, status: str = "saved") -> str:
    draft.text = text
    return status
