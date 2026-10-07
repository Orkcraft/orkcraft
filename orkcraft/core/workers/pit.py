"""🕳️ The Pit's work: what is dropped or pasted is sorted, kept and sent on (realm/pit.py).

A path, a link or a text (`drop`), a file's bytes from a page (`drop_file`) or the clipboard (`paste`)
becomes items in `.orkcraft/pit/`, each one cart down the road: `drop.file` with a path, `pit.link`
with the URL, `pit.text` with the text. Every cart carries a `ref` of its own (`<building>:<item>`),
which the buildings after it pass on; the worker follows it on the bus and keeps, per item, where
it arrived, what was made of it and what that cost (`chains.json`).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from orkcraft.core import bus
from orkcraft.core.workers import Worker
from orkcraft.realm import pipes, pit

STOPS = 30                  # what a chain keeps of where its carts went
VALUE = 2000                # what a stop keeps of what arrived there


def item_id(it: pit.Item) -> str:
    return hashlib.sha1(f"{it.at}|{it.value}".encode("utf-8")).hexdigest()[:10]


def _name(raw: str) -> str:
    """A dropped file's own name, never a path."""
    name = Path(str(raw).replace("\\", "/")).name.strip().lstrip(".")
    return "".join(ch if ch.isalnum() or ch in "-_. " else "_" for ch in name)[:120] or "dropped"


class PitWorker(Worker):
    TYPE = "pit"
    clipboard_reader = staticmethod(pit.clipboard)      # tests put a fake clipboard here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.items: list[pit.Item] = []
        self.chains: dict[str, dict] = {}                 # item id → {"cost", "hops", "stops"}
        self._off: list = []

    @property
    def chains_file(self) -> Path:
        return self.state_dir / "chains.json"

    def start(self) -> None:
        try:
            self.chains = dict(json.loads(self.chains_file.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            self.chains = {}
        on = self.town.bus.subscribe
        self._off = [on(bus.DELIVERED, self._delivered), on(bus.OUTPUT, self._output), on(bus.RUN, self._ran)]
        self.refresh()

    def refresh(self) -> None:
        self.items = pit.history(self.repo_root)
        self.changed()

    def ref(self, it: pit.Item) -> str:
        return f"{self.building_id}:{item_id(it)}"

    # -- taking things in -----------------------------------------------------------------------

    def drop(self, text: str, paths: bool = True) -> int:
        """Take what a paste or a drop brought. Returns how many items it made. `paths` False: the text is
        never read as files on this machine (a phone's drop: it names no path)."""
        try:
            items = pit.sort(self.repo_root, text, paths=paths)
        except OSError as e:
            self.toast(str(e), severity="error")
            return 0
        return self._send(items)

    def drop_file(self, name: str, data: bytes) -> int:
        """A file dropped on a page: its bytes kept in the pit (it has no path here), then sent on."""
        if len(data) > pit.MAX_COPY:
            self.toast(f"{_name(name)}: larger than {pit.MAX_COPY // (1024 * 1024)} MB", severity="error")
            return 0
        now = dt.datetime.now()
        folder = self.repo_root / pit.PIT_DIR
        try:
            folder.mkdir(parents=True, exist_ok=True)
            dst = pit._free(folder / f"{pit._stamp(now)}-{_name(name)}")
            dst.write_bytes(data)
        except OSError as e:
            self.toast(str(e), severity="error")
            return 0
        rel = dst.relative_to(self.repo_root).as_posix()
        return self._send([pit.Item(now.isoformat(timespec="seconds"), pit.kind_of(dst), rel, _name(name), copied=True)])

    def paste(self, text: str | None = None) -> int:
        """📋 The clipboard (or `text` a face read from it)."""
        text = type(self).clipboard_reader() if text is None else text
        if not text.strip():
            self.toast("the clipboard is empty (or cannot be read here)")
            return 0
        n = self.drop(text)
        if n:
            self.toast(f"{self.items[0].kind}: {self.items[0].title}", title="🕳️ Into the pit")
        return n

    def _send(self, items: list[pit.Item]) -> int:
        if not items:
            return 0
        pit.log(self.repo_root, items)
        for it in items:
            self.chains[item_id(it)] = {"cost": 0.0, "hops": [], "stops": []}
            value = it.value
            if it.kind == "text":
                try:
                    value = (self.repo_root / it.value).read_text(encoding="utf-8")
                except OSError:
                    pass
            self.emit(it.event, value, it.title, ref=self.ref(it))
        self._keep_chains()
        self.refresh()
        return len(items)

    def quick_action(self, action_id: str) -> bool:
        if action_id != "pit.paste":
            return False
        self.paste()
        return True

    # -- following what it sent -----------------------------------------------------------------

    def _mine(self, ref: str) -> dict | None:
        head, _, iid = str(ref or "").partition(":")
        if head != self.building_id or not iid:
            return None
        return self.chains.setdefault(iid, {"cost": 0.0, "hops": [], "stops": []})

    def _hops(self, chain: dict, trail) -> None:
        for h in trail or ():
            if not isinstance(h, pipes.Hop):
                continue
            key = f"{h.building}|{h.orc}|{h.at}"
            if key in chain["hops"]:
                continue
            chain["hops"] = (chain["hops"] + [key])[-200:]
            if h.cost:
                chain["cost"] = round(chain["cost"] + float(h.cost), 6)

    def _stop(self, chain: dict, building: str, title: str, event: str, kind: str, value: str) -> None:
        chain["stops"] = (chain["stops"] + [{
            "building": building, "title": str(title or "")[:120], "event": event, "kind": kind,
            "value": str(value or "")[:VALUE], "at": dt.datetime.now().isoformat(timespec="seconds"),
        }])[-STOPS:]

    def _delivered(self, e: bus.Event) -> None:
        payload = e.data.get("payload")
        chain = self._mine(getattr(payload, "ref", ""))
        if chain is None:
            return
        self._hops(chain, payload.trail)
        self._stop(chain, str(e.data.get("building", "")), e.data.get("title") or payload.title, payload.mode,
                   payload.kind, payload.value)
        self._keep_chains()

    def _output(self, e: bus.Event) -> None:
        chain = self._mine(e.data.get("ref", ""))
        if chain is None:
            return
        self._hops(chain, e.data.get("trail"))
        self._stop(chain, str(e.data.get("building", "")), e.data.get("title", ""), "output", pipes.TEXT,
                   e.data.get("markdown", ""))
        self._keep_chains()

    def _ran(self, e: bus.Event) -> None:
        run = e.data.get("run")
        chain = self._mine(getattr(run, "ref", ""))
        if chain is None:
            return
        self._hops(chain, run.trail)
        self._keep_chains()

    def _keep_chains(self) -> None:
        keep = {item_id(it) for it in pit.history(self.repo_root)}
        self.chains = {k: v for k, v in self.chains.items() if k in keep}
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.chains_file.write_text(json.dumps(self.chains, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        self.changed()

    # -- the hut --------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if not self.items:
            return ["drop or paste"]
        it = self.items[0]
        name = it.value.rsplit("/", 1)[-1] if it.is_file else it.title
        return [f"{pit.ICON.get(it.kind, '·')} {name}", f"{len(self.items)} in the pit"]
