"""The Wiki's folders and its rules for AI tools (docs/design/wiki-folders-rules.md): a part of
`ScrollsWorker` (scrolls.py); its methods run with the worker as `self`.

`connect` makes any folder a source (`dir:`), in the project or outside it; a folder outside may also
get the rules' block when the person said so (`rules_in`). After the Review board approves a spot-check,
`approved` writes the rules (`agent_rules: review`), or keeps them ready for the person (`ask`, the
default), or does nothing (`off`). `write_rules` writes `RULES.md` in the wiki's folder and the blocks
in the project and the folders of `rules_in`, for the AI tools on in the machine's settings;
`remove_rules` takes the blocks out. The state is `rules.json`: `ready`, `written`, `files`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orkcraft.realm import shelves, wiki, wikirules


class RulesMixin:

    # -- any folder -------------------------------------------------------------------------------

    def connect(self, path: str, rules: bool = False) -> str:
        """Make a folder, in the project or outside it, a source of the wiki (`dir:`), read-only. `rules`:
        a folder outside also gets the rules for AI tools. What is wrong with it, or ""."""
        raw = (path or "").strip()
        if not raw:
            return "Which folder?"
        p = Path(raw).expanduser()
        folder = (p if p.is_absolute() else self.repo_root / p).resolve()
        if not folder.is_dir():
            return f"{raw}: no such folder"
        own = self.wiki_root.resolve()
        if folder == own or own in folder.parents:
            return "That is the wiki's own folder: a wiki is never its own source."
        repo = self.repo_root.resolve()
        inside = folder == repo or repo in folder.parents
        spec = "dir:" + (shelves.rel_to(repo, folder) if inside else folder.as_posix())
        sources = list(self.config.get("sources") or [])
        if not sources and not self.config.get("paths"):
            sources = list(self.paths)                       # the folders it read by default stay
        changes: dict = {"sources": list(dict.fromkeys([*sources, spec]))}
        if rules and not inside:
            changes["rules_in"] = list(dict.fromkeys([*(self.config.get("rules_in") or []), folder.as_posix()]))
        self.save_config(changes)
        self.refresh()
        return ""

    # -- rules for AI tools -----------------------------------------------------------------------

    @property
    def rules_mode(self) -> str:
        return wikirules.mode_of(self.config)

    def _rules_file(self) -> Path:
        return self.state_dir / "rules.json"

    def rules_state(self) -> dict:
        try:
            data = json.loads(self._rules_file().read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_rules_state(self, **changes) -> None:
        data = {**self.rules_state(), **changes}
        try:
            self._rules_file().parent.mkdir(parents=True, exist_ok=True)
            self._rules_file().write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        except OSError:
            pass

    def tools_on(self) -> list[str]:
        machine = getattr(self.town, "machine", None)
        tools = getattr(machine, "tools", {}) or {}
        return [t for t, c in tools.items() if getattr(c, "enabled", False)] or ["claude"]

    def rules_folders(self) -> list[Path]:
        """Where the blocks go: the project, and the folders outside it the person allowed."""
        out = [self.repo_root]
        for f in self.config.get("rules_in") or []:
            p = Path(str(f)).expanduser()
            if p.is_absolute() and p.is_dir():
                out.append(p)
        return out

    def approved(self) -> None:
        """The Review board approved a spot-check: the rules are written, or kept ready, as the setting says."""
        mode = self.rules_mode
        if mode == "review":
            self.write_rules()
        elif mode == "ask":
            self._save_rules_state(ready=True)
            self.changed()

    def write_rules(self) -> list[str]:
        """RULES.md in the wiki's folder, the blocks where the AI tools read them. The files written."""
        root, repo = self.wiki_root, self.repo_root
        wiki_rel = shelves.rel_to(repo, root)
        try:
            known = wiki.SECTIONS.get(self.topic, wiki.SECTIONS["general"])
            text = wikirules.rules_text(wiki_rel, wikirules.structure(root, known), self.inbox, self.topic)
            root.mkdir(parents=True, exist_ok=True)
            (root / wikirules.RULES).write_text(text, encoding="utf-8")
            clean = _clean(repo, [wikirules.CLAUDE, wikirules.AGENTS,
                                  wikirules.cursor_file(self.building_id).as_posix()])
            changed: list[Path] = []
            tools = self.tools_on()
            for folder in self.rules_folders():
                ref = f"{wiki_rel}/{wikirules.RULES}" if folder == repo else (root / wikirules.RULES).as_posix()
                changed += wikirules.write(folder, self.building_id, tools, ref)
        except OSError as e:
            self.last_note = f"the rules for AI tools: {e}"
            self.changed()
            return []
        written = [wiki_rel + "/" + wikirules.RULES] + [shelves.rel_to(repo, p) for p in changed]
        self._commit_rules([p for p in written if p in clean or p.startswith(wiki_rel + "/")],
                           "wiki: the rules for AI tools")
        self._save_rules_state(ready=False, written=self.clock().isoformat(timespec="minutes"), files=self.rules_files())
        self.changed()
        return written

    def remove_rules(self) -> list[str]:
        """Take every block of this Wiki out (RULES.md stays in the wiki's folder). The files changed."""
        repo = self.repo_root
        clean = _clean(repo, [wikirules.CLAUDE, wikirules.AGENTS, wikirules.cursor_file(self.building_id).as_posix()])
        changed: list[Path] = []
        for folder in self.rules_folders():
            try:
                changed += wikirules.remove(folder, self.building_id)
            except OSError as e:
                self.last_note = f"the rules for AI tools: {e}"
        rels = [shelves.rel_to(repo, p) for p in changed]
        self._commit_rules([p for p in rels if p in clean], "wiki: the rules for AI tools removed")
        self._save_rules_state(ready=False, written="", files=[])
        self.changed()
        return rels

    def rules_files(self) -> list[str]:
        """The files that carry this Wiki's block now (the project's relative, the others absolute)."""
        out = []
        for folder in self.rules_folders():
            for name in wikirules.written(folder, self.building_id):
                out.append(name if folder == self.repo_root else (folder / name).as_posix())
        return out

    def _commit_rules(self, paths: list[str], message: str) -> None:
        if paths and self.config.get("commit", True) is not False and not self.simulated:
            wiki.commit_files(self.repo_root, paths, message)

    def rules_view(self) -> dict:
        state = self.rules_state()
        return {"mode": self.rules_mode, "ready": bool(state.get("ready")), "written": state.get("written") or "",
                "files": self.rules_files(), "tools": self.tools_on(),
                "folders": [str(f) for f in self.config.get("rules_in") or []]}


def _clean(repo: Path, paths: list[str]) -> set[str]:
    """The files among `paths` with nothing of a person's waiting to be committed: only these are committed
    by the librarian (a CLAUDE.md someone is editing stays theirs to commit). None without git."""
    try:
        done = wiki._git(repo, "status", "--porcelain", "-z", "--", *paths)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if done.returncode != 0:
        return set()
    dirty = {row[3:] for row in done.stdout.split("\0") if len(row) > 3}
    return {p for p in paths if p not in dirty}
