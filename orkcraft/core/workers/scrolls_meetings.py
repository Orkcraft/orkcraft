"""The Wiki's meetings (docs/design/wiki-librarian.md §5–6): a part of `ScrollsWorker` (scrolls.py); its
methods run with the worker as `self`.

`keep_agenda()` (every refresh) reads the notes in the inbox: a note that names a meeting (its
`meeting:` id) goes under To discuss on that meeting's page; a note that names people but no meeting is
an open item and binds to the next meeting of the Calendar named after one of them. The page is
written at once, by rules (realm/agenda.py), and committed alone; the librarian writes the rest of it
at take-in. When a meeting is over, what was not ticked off is released: an open item for the next
meeting with the same person. `meeting_context` is what a meeting's brief reads first (`lend`).

Its state is `agenda.json`: `bound` (a note → the meeting it was bound to; "" released), `done` (a
note → the meetings it was on), `meetings` (an id → title, when, end, page, closed).
"""
from __future__ import annotations

import datetime as dt
import json

from orkcraft.realm import agenda, catalog, daybook, quicknote, shelves, wiki

FALLBACK_MINUTES = 30                   # a meeting with no end is over this long after it starts
COMING_DAYS = 14                        # how far ahead a note's meeting is looked for (§4)
COMING_MOST = 12                        # the meetings a note may be moved to, at most


def _when(text: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(str(text or "")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    return [value] if isinstance(value, str) and value.strip() else []


class MeetingsMixin:
    clock = staticmethod(dt.datetime.now)          # tests move time here
    agenda_cache: dict = {"meetings": [], "open": []}   # agenda_view as of the last keep_agenda (the card's)

    # -- what it reads --------------------------------------------------------------------------

    def calendar_workers(self) -> list:
        """The War Drums meetings are matched in: the one `calendar` names, else every one in the town."""
        named = str(self.config.get("calendar") or "").strip()
        ids = [bid for bid, spec in self.town.custom_specs.items() if catalog.migrate(spec).get("type") == "war_drum"]
        return [self.town.worker(bid) for bid in ([named] if named in ids else ids)]

    def reads_calendar(self, drum_id: str) -> bool:
        """Whether this Wiki matches its notes in that War Drum's meetings."""
        return any(getattr(cal, "building_id", "") == drum_id for cal in self.calendar_workers())

    def meetings(self) -> list[agenda.Meeting]:
        """The Calendars' timed events of the coming days, as meetings."""
        out, seen = [], set()
        for cal in self.calendar_workers():
            for e in getattr(getattr(cal, "day", None), "events", None) or []:
                if not isinstance(e.start, dt.datetime) or daybook.meet_id(e) in seen:
                    continue
                seen.add(daybook.meet_id(e))
                end = e.end if isinstance(e.end, dt.datetime) else None
                out.append(agenda.Meeting(daybook.meet_id(e), e.summary, e.start.replace(tzinfo=None),
                                          end.replace(tzinfo=None) if end else None))
        return out

    def coming(self, now: dt.datetime | None = None) -> list[agenda.Meeting]:
        """The meetings a note may be for: not over yet and starting in the next `COMING_DAYS`, nearest first."""
        now = now or self.clock()
        until = now + dt.timedelta(days=COMING_DAYS)
        return sorted((m for m in self.meetings() if (m.end or m.start) >= now and m.start <= until),
                      key=lambda m: m.start)[:COMING_MOST]

    def inbox_notes(self) -> list[tuple[str, dict, str]]:
        """The notes of the inbox: (path, front matter, words)."""
        prefix = self.inbox.rstrip("/") + "/"
        out = []
        for b in self.bases:
            for n in b.notes:
                if not n.path.startswith(prefix):
                    continue
                try:
                    text = (self.repo_root / n.path).read_text(encoding="utf-8")
                except OSError:
                    continue
                out.append((n.path, quicknote.front_matter(text), quicknote.body_of(text)))
        return out

    def _agenda_file(self):
        return self.state_dir / "agenda.json"

    def load_agenda(self) -> dict:
        try:
            data = json.loads(self._agenda_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data = data if isinstance(data, dict) else {}
        for key in ("bound", "done", "meetings"):
            data[key] = data.get(key) if isinstance(data.get(key), dict) else {}
        return data

    def _save_agenda(self, data: dict) -> None:
        path = self._agenda_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- keeping it -----------------------------------------------------------------------------

    def keep_agenda(self, now: dt.datetime | None = None) -> list[str]:
        """Bind the notes to their meetings, write the meetings' pages, close the meetings that are over.
        The pages written (repo-relative)."""
        now = now or self.clock()
        state = self.load_agenda()
        bound, done, known = state["bound"], state["done"], state["meetings"]
        cal = {m.id: m for m in self.meetings()}
        people = agenda.people_of(self.repo_root, self.pages)
        notes = self.inbox_notes()
        for mid, m in cal.items():
            if mid in known:
                known[mid].update(title=m.title, when=m.when, end=f"{m.end:%Y-%m-%d %H:%M}" if m.end else "")
        target: dict[str, list[agenda.Item]] = {}
        for path, fm, words in notes:
            mid = bound[path] if path in bound else str(fm.get("meeting") or "")
            if mid and mid not in known:
                m = cal.get(mid)
                known[mid] = {"title": m.title if m else str(fm.get("meeting_title") or mid),
                              "when": m.when if m else str(fm.get("when") or ""),
                              "end": f"{m.end:%Y-%m-%d %H:%M}" if m and m.end else ""}
            if not mid:
                for person in _as_list(fm.get("with")):
                    m = agenda.next_with(person, list(cal.values()), people, now, set(done.get(path, [])))
                    if m is not None:
                        mid = bound[path] = m.id
                        known.setdefault(mid, {"title": m.title, "when": m.when,
                                               "end": f"{m.end:%Y-%m-%d %H:%M}" if m.end else ""})
                        break
            if mid and not known[mid].get("closed"):
                target.setdefault(mid, []).append(agenda.Item(path, words.splitlines()[0] if words else path))
        written, released = [], False
        for mid, info in known.items():
            if info.get("closed") or mid not in target:
                continue
            start = _when(info.get("when"))
            end = _when(info.get("end")) or (start + dt.timedelta(minutes=FALLBACK_MINUTES) if start else None)
            meeting = agenda.Meeting(mid, str(info.get("title") or mid), start or now, end)
            items = target[mid]
            page = self.repo_root / info["page"] if info.get("page") else agenda.page_path(self.wiki_root, meeting)
            try:
                before = page.read_text(encoding="utf-8") if page.is_file() else ""
            except OSError:
                before = ""
            after_line = ""
            if end is not None and end < now:                    # over: what was not ticked off moves on
                ticks = agenda.ticked(before)
                left = [i for i in items if not ticks.get(i.note)]
                released = released or bool(left)
                for i in left:
                    bound[i.note] = ""
                    done.setdefault(i.note, []).append(mid)
                items = [i for i in items if ticks.get(i.note)]
                info["closed"] = True
                after_line = self._after_line(mid, len(items), len(left))
            with_ = sorted({p for path, fm, _ in notes if bound.get(path, fm.get("meeting")) == mid
                            for p in _as_list(fm.get("with"))})
            text = agenda.with_items(self.repo_root, page, before, items) if before \
                else agenda.page_text(self.repo_root, page, meeting, with_, items)
            text = agenda.with_after(text, after_line)
            info["page"] = shelves.rel_to(self.repo_root, page)
            if text != before:
                try:
                    page.parent.mkdir(parents=True, exist_ok=True)
                    page.write_text(text, encoding="utf-8")
                except OSError:
                    continue
                written.append(info["page"])
                if not before:
                    self._list_in_index(page, meeting)
        try:
            self._save_agenda(state)
        except OSError:
            pass
        if written and self.config.get("commit", True) is not False and not self.simulated:
            index = shelves.rel_to(self.repo_root, self.wiki_root / wiki.PAGES / agenda.SECTION / wiki.INDEX)
            wiki.commit_files(self.repo_root, written + [index], f"wiki({self.topic}): what the meetings should cover")
        if released:                                       # what moved on finds its next meeting now
            return written + self.keep_agenda(now)
        view = self.agenda_view(now)
        if view != self.agenda_cache:                      # the Calendars say what is kept for their meetings
            self.agenda_cache = view
            for cal in self.calendar_workers():
                cal.changed()
        return written

    def _after_line(self, mid: str, covered: int, left: int) -> str:
        doc = next((d for cal in self.calendar_workers() if hasattr(cal, "docs") for d in [cal.docs().get(mid)] if d), {})
        parts = [f"{covered} covered" if covered else "", f"{left} not covered — moved on to the next meeting "
                 "with the same person, else kept as open items" if left else ""]
        line = "- " + "; ".join(p for p in parts if p) if covered or left else ""
        if doc.get("path"):
            line += ("\n" if line else "") + f"- The brief: `{doc['path']}`"
        return line

    def _list_in_index(self, page, meeting: agenda.Meeting) -> None:
        """A new meeting page gets its line in the section's index."""
        index = page.parent / wiki.INDEX
        try:
            text = index.read_text(encoding="utf-8") if index.is_file() else "# Meetings\n\n"
            if page.name not in text:
                index.write_text(text.rstrip("\n") + f"\n- [{meeting.title}]({page.name}) — {meeting.when}\n",
                                 encoding="utf-8")
        except OSError:
            pass

    # -- what it shows and hands over -------------------------------------------------------------

    def agenda_view(self, now: dt.datetime | None = None) -> dict:
        """The meetings with something to discuss, nearest first (each with its items and the pages its notes
        link), and the open items (people, no meeting)."""
        now = now or self.clock()
        state = self.load_agenda()
        notes = self.inbox_notes()
        meetings = []
        for mid, info in state["meetings"].items():
            if info.get("closed"):
                continue
            mine = [(p, fm, w) for p, fm, w in notes if state["bound"].get(p, fm.get("meeting")) == mid]
            if not mine:
                continue
            items = [{"path": p, "line": (w.splitlines()[0] if w else p)[:160]} for p, fm, w in mine]
            links = list(dict.fromkeys(x for _, fm, _ in mine for x in _as_list(fm.get("links"))))
            page = info.get("page") or ""
            ticks = {}
            try:
                ticks = agenda.ticked((self.repo_root / page).read_text(encoding="utf-8")) if page else {}
            except OSError:
                pass
            for i in items:
                i["done"] = bool(ticks.get(i["path"]))
            meetings.append({"id": mid, "title": info.get("title") or mid, "when": info.get("when") or "",
                             "page": page, "items": items, "links": links})
        meetings.sort(key=lambda m: m["when"])
        open_ = [{"path": p, "line": (w.splitlines()[0] if w else p)[:160], "with": _as_list(fm.get("with"))}
                 for p, fm, w in notes if _as_list(fm.get("with")) and not state["bound"].get(p, fm.get("meeting"))]
        return {"meetings": meetings, "open": open_}

    def kept_for(self, drum_id: str) -> dict[str, dict]:
        """What this Wiki keeps for the meetings of a War Drum, by meet id (as of its last refresh): how many
        items are still to discuss and how many pages its notes link. Empty when it reads another Calendar."""
        if not self.reads_calendar(drum_id):
            return {}
        out = {}
        for m in self.agenda_cache["meetings"]:
            left = sum(1 for i in m["items"] if not i.get("done"))
            if left:
                out[m["id"]] = {"discuss": left, "pages": len(m.get("links") or [])}
        return out

    def meeting_context(self, mid: str) -> tuple[str, list[str]]:
        """What a meeting's brief reads first: its page and what to discuss, as Markdown, and the pages the
        notes link (repo-relative); ("", []) when the Wiki keeps nothing for it."""
        if not mid:
            return "", []
        info = self.load_agenda()["meetings"].get(mid) or {}
        page = info.get("page") or ""
        state = self.load_agenda()
        items, links = [], []
        for path, fm, words in self.inbox_notes():
            if state["bound"].get(path, fm.get("meeting")) == mid:
                items.append(words.splitlines()[0] if words else path)
                links += [x for x in _as_list(fm.get("links")) if x not in links]
        if not page and not items:
            return "", []
        text = f"**Read first — the meeting's page:** `{page}`\n" if page else ""
        if items:
            text += "\n**To discuss** (left in the wiki for this meeting):\n" + "\n".join(f"- {i}" for i in items)
        return text, links
