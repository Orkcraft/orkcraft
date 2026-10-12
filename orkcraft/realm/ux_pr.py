"""What the UX bench sends to Orkcraft as a pull request (docs/design/improve-buildings.md §6.5): what this machine
has applied, as the files of Orkcraft's repository it changes.

    items(window)      -> what may go: [{id, kind, label}] — a picture, a mascot's head, a type's cards, a type's window
    files(ids, window) -> {repository path: (as installed, as changed)} for the items picked (pictures as bytes)
    title(ids, window), body(ids, window) -> the pull request's

- **A picture** (`picture:<path>`): this machine's own (design/tokens.py `assets_dir`) and its @2x, over the design
  system's in `design-system/`; a moving house's layer is a new file there.
- **A mascot's head** (`mascot:<role>-<stage>`): its picture and @2x, its grid in `grids.json`, and the grid again in
  `drawn.json`, which tools/growth_sprites.py keeps over the heads its code draws, so a run of the tool keeps it.
- **A type's cards** (`card:<type>`): this machine's card document as the one Orkcraft ships,
  `design-system/cards/<type>.json` (realm/card_docs.py `shipped`).
- **A type's window** (`window:<type>`): the layout its buildings have here as the type's default, the `default` of
  `orkcraft/design/buildings/<type>.json`.

What is never sent: the person's words, their town, their projects. Pure: no face.
"""
from __future__ import annotations

import json
from pathlib import Path

import orkcraft
from orkcraft.design import mascots, tokens, ui
from orkcraft.realm import card_docs, catalog

SYSTEM = "design-system"                    # where tokens.SYSTEM is in Orkcraft's repository
BUILDINGS = Path(ui.__file__).resolve().parent / "buildings"
TITLE_CHARS = 72


def _own_pictures() -> list[str]:
    root = tokens.assets_dir() / "sprites"
    if not root.is_dir():
        return []
    return sorted(p.relative_to(tokens.assets_dir()).as_posix() for p in root.rglob("*.png") if "@2x" not in p.name)


def _own_cards() -> list[str]:
    root = tokens.assets_dir() / "cards"
    return sorted(p.stem for p in root.glob("*.json") if p.stem in catalog.TYPES) if root.is_dir() else []


def _shipped(path: str) -> bytes:
    p = tokens.SYSTEM / path
    return p.read_bytes() if p.is_file() else b""


def _twin(path: str) -> str:
    return path[:-4] + "@2x.png"


def _mascot_label(path: str) -> str:
    from orkcraft.realm import intents
    m = mascots.PATH.match(path)
    role = next((r for r in intents.ROLES if r.id == m[1]), None)
    return f"{role.nick if role else m[1]}, stage {m[2]}"


def window_changed(type_id: str, doc: dict | None) -> bool:
    return bool(doc) and (BUILDINGS / f"{type_id}.json").is_file() and doc != ui.default(type_id)


def items(window: tuple[str, dict] | None = None) -> list[dict]:
    """Everything this machine has applied that may go; `window` is (type, its layout) for the type the bench works
    on, when its buildings have one."""
    out = []
    for path in _own_pictures():
        if (tokens.assets_dir() / path).read_bytes() == _shipped(path):
            continue
        if mascots.is_mascot(path):
            out.append({"id": f"mascot:{path}", "kind": "mascot", "label": _mascot_label(path), "path": path})
        else:
            out.append({"id": f"picture:{path}", "kind": "picture", "label": path.removeprefix("sprites/"), "path": path})
    for t in _own_cards():
        if card_docs.load(t) != card_docs.shipped(t):
            out.append({"id": f"card:{t}", "kind": "card", "label": f"{catalog.TYPES[t].title}: its cards"})
    if window and window_changed(*window):
        out.append({"id": f"window:{window[0]}", "kind": "window",
                    "label": f"{catalog.TYPES[window[0]].title}: its Work window"})
    return out


def _json(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _window_text(type_id: str, doc: dict) -> tuple[str, str]:
    """The type's contract file with `doc` as its default: the rest of the file as it is written."""
    base = (BUILDINGS / f"{type_id}.json").read_text(encoding="utf-8")
    at = base.rfind('\n  "default":')
    if at < 0 or not base.rstrip().endswith("}"):
        return base, json.dumps({**json.loads(base), "default": doc}, indent=2, ensure_ascii=False) + "\n"
    dumped = json.dumps(doc, indent=2, ensure_ascii=False).replace("\n", "\n  ")
    return base, base[:at] + f'\n  "default": {dumped}\n}}\n'


def files(ids: list[str], window: tuple[str, dict] | None = None) -> dict[str, tuple]:
    """The repository's files the picked items change: {path: (as installed, as changed)}."""
    picked = {i["id"]: i for i in items(window) if i["id"] in set(ids)}
    out: dict[str, tuple] = {}
    heads = {}
    for item in picked.values():
        if item["kind"] in ("picture", "mascot"):
            for path in (item["path"], _twin(item["path"])):
                own = tokens.assets_dir() / path
                if own.is_file():
                    out[f"{SYSTEM}/{path}"] = (_shipped(path), own.read_bytes())
            if item["kind"] == "mascot":
                m = mascots.PATH.match(item["path"])
                heads[f"{m[1]}-{m[2]}"] = mascots.grid(item["path"])
        elif item["kind"] == "card":
            t = item["id"].split(":", 1)[1]
            rel = f"cards/{t}.json"
            out[f"{SYSTEM}/{rel}"] = (_shipped(rel).decode("utf-8"), _json(card_docs.load(t)))
        elif item["kind"] == "window" and window:
            out[f"orkcraft/design/buildings/{window[0]}.json"] = _window_text(*window)
    if heads:
        grids_path, drawn_path = "sprites/mascots/grids.json", "sprites/mascots/drawn.json"
        base = _shipped(grids_path).decode("utf-8")
        shipped = json.loads(base)
        out[f"{SYSTEM}/{grids_path}"] = (base, _json({**shipped, "grids": {**shipped["grids"], **heads}}))
        drawn_base = _shipped(drawn_path).decode("utf-8")
        drawn = json.loads(drawn_base) if drawn_base else {}
        out[f"{SYSTEM}/{drawn_path}"] = (drawn_base, _json(dict(sorted({**drawn, **heads}.items()))))
    return out


def _why(path: str) -> str:
    """What the Alchemist said it changed in a head (kept beside its grid when it was applied)."""
    try:
        return str(json.loads(mascots.own_grid(path).read_text(encoding="utf-8")).get("why") or "")[:200]
    except (OSError, ValueError, AttributeError):
        return ""


def title(ids: list[str], window: tuple[str, dict] | None = None) -> str:
    picked = [i for i in items(window) if i["id"] in set(ids)]
    count = lambda kind, one, many: (lambda n: f"{n} {one if n == 1 else many}" if n else "")(  # noqa: E731
        sum(i["kind"] == kind for i in picked))
    parts = [x for x in (count("picture", "picture", "pictures"), count("mascot", "mascot", "mascots"),
                         count("card", "type's cards", "types' cards"), count("window", "window", "windows")) if x]
    text = "UX bench: " + ", ".join(parts or ["nothing"])
    return text if len(text) <= TITLE_CHARS else text[:TITLE_CHARS - 1] + "…"


def body(ids: list[str], window: tuple[str, dict] | None = None, why: dict[str, str] | None = None) -> str:
    picked = [i for i in items(window) if i["id"] in set(ids)]
    lines = [f"Made in the UX bench of Orkcraft {orkcraft.__version__} (docs/design/improve-buildings.md §6): what "
             "this machine applied, drawn and laid out there by the Alchemist from the person's words.", ""]
    words = {"picture": "Picture", "mascot": "Mascot", "card": "Cards", "window": "Window"}
    for i in picked:
        said = (why or {}).get(i["id"], "") or (_why(i["path"]) if i["kind"] == "mascot" else "")
        lines.append(f"- **{words[i['kind']]}** {i['label']}" + (f" — {said}" if said else ""))
    if any(i["kind"] == "mascot" for i in picked):
        lines += ["", "A mascot's grid goes into `design-system/sprites/mascots/drawn.json` too, which "
                  "`tools/growth_sprites.py` keeps over the heads its code draws."]
    lines += ["", "_Sent from Orkcraft: the pictures and documents as they are on the sender's machine; nothing of "
              "their town or projects._"]
    return "\n".join(lines)
