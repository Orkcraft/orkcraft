"""Markdown as HTML for the page: CommonMark with raw HTML off, so a page an ork wrote or a site the
Lake fetched can never put markup or script into the window (markdown-it also refuses
`javascript:` links)."""
from __future__ import annotations

import functools

from markdown_it import MarkdownIt

LIMIT = 200_000          # characters: a huge file is cut, the window stays quick


@functools.lru_cache(maxsize=1)
def _md() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")


def render(text: str) -> str:
    return _md().render((text or "")[:LIMIT])
