"""Markdown as HTML for the page: CommonMark with raw HTML off, so a page an ork wrote or a site the
Lake fetched can never put markup or script into the window (markdown-it also refuses
`javascript:` links). A bare address in the text (https://…, tailscale.com/download) becomes a link too, as the
page's own text does (js/html.js `linked`)."""
from __future__ import annotations

import functools
import re

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.token import Token

LIMIT = 200_000          # characters: a huge file is cut, the window stays quick


# as js/html.js ADDRESS: a full URL, or a bare host of a known kind with its path, never a file name (roads.py); a
# sentence's closing stop or bracket stays outside it, and an e-mail address's domain is no link
_ADDRESS = re.compile(r"\bhttps?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]"
                      r"|(?<![@\w.-])(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|ai)\b(?:/[^\s<>\"']*[^\s<>\"'.,;:!?)\]])?"
                      r"(?![\w.-]*@)", re.IGNORECASE)


def _linkify(state: StateCore) -> None:
    """Bare addresses in the text as links, outside links and code."""
    for block in state.tokens:
        if block.type != "inline" or not block.children:
            continue
        out: list[Token] = []
        inside = 0
        for t in block.children:
            inside += t.type == "link_open"
            inside -= t.type == "link_close"
            if t.type != "text" or inside or not _ADDRESS.search(t.content):
                out.append(t)
                continue
            at = 0
            for m in _ADDRESS.finditer(t.content):
                if m.start() > at:
                    out.append(_text(t.content[at:m.start()]))
                url = m.group(0)
                href = url if url.lower().startswith(("http://", "https://")) else f"https://{url}"
                link = Token("link_open", "a", 1)
                link.attrs = {"href": href}
                out += [link, _text(url), Token("link_close", "a", -1)]
                at = m.end()
            if at < len(t.content):
                out.append(_text(t.content[at:]))
        block.children = out


def _text(content: str) -> Token:
    t = Token("text", "", 0)
    t.content = content
    return t


@functools.lru_cache(maxsize=1)
def _md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")
    md.core.ruler.push("bare_addresses", _linkify)
    return md


def render(text: str) -> str:
    return _md().render((text or "")[:LIMIT])
