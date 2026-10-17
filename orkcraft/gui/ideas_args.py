"""What the board's commands share (gui/ideas.py and its mixins): the refusal and the readers of a command's args."""
from __future__ import annotations


class IdeasError(Exception):
    """A board command the host refuses, in plain words."""


def _device(args: dict) -> str:
    """"phone" when the listener says so (gui/mobile.py `guard`), else the computer's own window."""
    return "phone" if args.get("device") == "phone" else "desktop"


def _str(args: dict, key: str, limit: int) -> str:
    value = args.get(key, "")
    if not isinstance(value, str):
        raise IdeasError(f"{key} is not text")
    return value[:limit]


def _text(args: dict, key: str, limit: int) -> str:
    value = _str(args, key, limit).strip()
    if not value:
        raise IdeasError(f"{key} is missing")
    return value


def _opt(args: dict, key: str) -> str:
    value = args.get(key)
    return value.strip()[:100] if isinstance(value, str) else ""
