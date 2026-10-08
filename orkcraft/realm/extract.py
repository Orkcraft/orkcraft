"""What a file is to the Wiki, and its text (docs/design/wiki-folders-rules.md §1).

    kind_of("notes/a.md")      == "doc"      text, read as it is
    kind_of("src/app.py")      == "code"
    kind_of("spec.docx")       == "docx"     its text is taken out (`docx_text`) into the wiki's raw/
    kind_of("paper.pdf")       == "pdf"      read by the AI tool itself: no converter here
    kind_of("photo.png")       is None       skipped
    secret("prod.env")         is True       never read, whatever its kind

Standard library only. Pure module, no Textual.
"""
from __future__ import annotations

import fnmatch
import io
import re
import zipfile
from pathlib import PurePosixPath

DOC_EXT = (".md", ".markdown", ".mdx", ".rst", ".txt", ".org", ".adoc", ".csv", ".tsv", ".json", ".yaml", ".yml",
           ".toml", ".html", ".htm")
CODE_EXT = (".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".rb",
            ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".scala", ".lua", ".sh", ".sql")
MAX_BYTES = 10 * 1024 * 1024           # a file larger than this is skipped
SECRETS = (".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*",
           "credentials*", "secrets*", "*.keystore", ".netrc", ".npmrc", ".pypirc")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def kind_of(path: str) -> str | None:
    """doc, code, docx, pdf — or None for a file the wiki does not read."""
    low = path.lower()
    if low.endswith(".docx"):
        return "docx"
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(DOC_EXT):
        return "doc"
    if low.endswith(CODE_EXT):
        return "code"
    return None


def secret(path: str) -> bool:
    """A file that by its name holds keys or passwords: never read."""
    name = PurePosixPath(path.replace("\\", "/")).name.lower()
    return any(fnmatch.fnmatch(name, p) for p in SECRETS)


def docx_text(data: bytes) -> str:
    """A Word document's text as Markdown-ish lines: headings (`Heading 1…3` styles) get `#`, list
    paragraphs `- `, table cells ` | `. ValueError when it is not a .docx."""
    from xml.etree import ElementTree as ET
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise ValueError(f"not a Word document: {e}") from None
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ValueError(f"not a Word document: {e}") from None
    out: list[str] = []
    body = root.find(f"{_W}body")
    for block in (body if body is not None else []):
        if block.tag == f"{_W}p":
            out.append(_paragraph(block))
        elif block.tag == f"{_W}tbl":
            for row in block.iter(f"{_W}tr"):
                cells = [" ".join(_paragraph(p) for p in c.iter(f"{_W}p")).strip() for c in row.iter(f"{_W}tc")]
                out.append("| " + " | ".join(cells) + " |")
            out.append("")
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _paragraph(p) -> str:
    words = "".join(t.text or "" for t in p.iter() if t.tag in (f"{_W}t", f"{_W}tab"))
    style = p.find(f"{_W}pPr/{_W}pStyle")
    name = (style.get(f"{_W}val") or "") if style is not None else ""
    m = re.match(r"(?i)heading\s*([1-6])$|title$", name)
    if m and words.strip():
        return "\n" + "#" * min(int(m.group(1) or 1), 3) + " " + words.strip()
    if p.find(f"{_W}pPr/{_W}numPr") is not None and words.strip():
        return "- " + words.strip()
    return words
