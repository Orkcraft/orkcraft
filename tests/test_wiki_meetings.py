"""The Wiki's meetings (docs/design/wiki-librarian.md §5–6): a note that names a meeting, or a person and
a day, lands under To discuss on the meeting's page; the meeting's brief reads that page first; after
the meeting what was not ticked off moves on to the next meeting with the same person."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from orkcraft.core import buildings
from orkcraft.core.workers.scrolls import ScrollsWorker
from orkcraft.core.workers.war_drum import WarDrumWorker
from orkcraft.gui.host import Host
from orkcraft.realm import agenda, checkpoint, pipes, quicknote

DAY = dt.date(2026, 10, 7)                      # a Wednesday
NOW = dt.datetime(2026, 10, 7, 15, 0)
PEOPLE = {"Sergey": ["Sergey", "Сергей"], "Ann": ["Ann Lee", "Анна"]}


def _m(mid: str, title: str, day: int, hour: int) -> agenda.Meeting:
    start = dt.datetime(2026, 10, day, hour)
    return agenda.Meeting(mid, title, start, start + dt.timedelta(minutes=30))


MEETINGS = [_m("a", "Sergey 1:1", 7, 17), _m("b", "Pricing review with Sergey", 8, 11), _m("c", "Standup", 8, 9),
            _m("d", "Design sync with Ann Lee", 9, 10)]


def test_the_day_a_note_names():
    assert agenda.day_of("discuss it tomorrow", DAY) == dt.date(2026, 10, 8)
    assert agenda.day_of("обсудить завтра на встрече", DAY) == dt.date(2026, 10, 8)
    assert agenda.day_of("послезавтра", DAY) == dt.date(2026, 10, 9)
    assert agenda.day_of("on Friday", DAY) == dt.date(2026, 10, 9)
    assert agenda.day_of("в пятницу", DAY) == dt.date(2026, 10, 9)
    assert agenda.day_of("в среду", DAY) == dt.date(2026, 10, 14)        # the next one, not today
    assert agenda.day_of("by 2026-10-20", DAY) == dt.date(2026, 10, 20)
    assert agenda.day_of("no day here", DAY) is None


def test_the_meeting_a_note_is_for():
    found = agenda.match("Обсудить тарифы с Сергеем завтра", MEETINGS, PEOPLE, NOW)
    assert found.meeting.id == "b" and found.people == ["Sergey"]          # the day and the person
    assert agenda.match("ask Sergey about invoices", MEETINGS, PEOPLE, NOW).meeting.id == "a"   # the nearest with him
    assert agenda.match("standup tomorrow: the release", MEETINGS, PEOPLE, NOW).meeting.id == "c"
    assert agenda.match("Анне показать макеты", MEETINGS, PEOPLE, NOW).meeting.id == "d"
    assert agenda.match("buy milk", MEETINGS, PEOPLE, NOW).meeting is None
    assert agenda.match("show Lee the draft", MEETINGS, {}, NOW).meeting.id == "d"      # a name the wiki has no page for
    assert agenda.match("ask Sergey", MEETINGS, PEOPLE, dt.datetime(2026, 10, 10)).meeting is None   # all over
    assert agenda.next_with("Sergey", MEETINGS, PEOPLE, NOW, {"a"}).id == "b"


def test_the_page_keeps_its_ticks_and_the_rest(tmp_path: Path):
    page = tmp_path / "llm-wiki/team/pages/meetings/x.md"
    m = MEETINGS[1]
    items = [agenda.Item("notes/inbox/one.md", "Pricing tiers"), agenda.Item("notes/inbox/two.md", "Invoices")]
    text = agenda.page_text(tmp_path, page, m, ["Sergey"], items)
    assert "calendar: meet:b" in text and "- [ ] Pricing tiers — [note](../../../../notes/inbox/one.md)" in text
    assert agenda.meeting_of_page(text) == "b"
    text = text.replace("- [ ] Pricing tiers", "- [x] Pricing tiers") + "\nA person's line.\n"
    text = text.replace("## Background\n", "## Background\nThe librarian's words.\n")
    again = agenda.with_items(tmp_path, page, text, items + [agenda.Item("notes/inbox/three.md", "Discounts")])
    assert agenda.ticked(again) == {"notes/inbox/one.md": True, "notes/inbox/two.md": False,
                                    "notes/inbox/three.md": False}
    assert "The librarian's words." in again and "A person's line." in again
    assert agenda.with_after(again, "- 1 covered").count("- 1 covered") == 1


def _ics(repo: Path) -> None:
    rows = []
    for summary, start in (("Sergey 1:1", "20261007T170000"), ("Pricing review with Sergey", "20261008T110000"),
                           ("Pricing review with Sergey", "20261013T110000")):
        end = start[:9] + f"{int(start[9:11]):02d}3000"
        rows += ["BEGIN:VEVENT", f"UID:{summary}-{start}", f"DTSTART:{start}", f"DTEND:{end}", f"SUMMARY:{summary}",
                 "END:VEVENT"]
    (repo / "cal.ics").write_text("\r\n".join(["BEGIN:VCALENDAR", *rows, "END:VCALENDAR"]) + "\r\n")
    person = repo / "llm-wiki/team/pages/people/sergey.md"
    person.parent.mkdir(parents=True, exist_ok=True)
    person.write_text("---\nkind: person\naliases: [Сергей]\n---\n# Sergey\n\nOwns billing.\n", encoding="utf-8")
    tiers = repo / "llm-wiki/team/pages/product/pricing-tiers.md"
    tiers.parent.mkdir(parents=True, exist_ok=True)
    tiers.write_text("# Pricing tiers\n\nFree, Team, Business.\n", encoding="utf-8")


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    host.town.worker(built.id)
    return built.id


def test_a_note_for_a_meeting_reaches_its_brief_and_moves_on(fake_repo: Path, monkeypatch):
    clock = {"now": NOW}
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: clock["now"]))
    monkeypatch.setattr(ScrollsWorker, "clock", staticmethod(lambda: clock["now"]))
    _ics(fake_repo)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    drum = _raised(host, "war_drum", ics="cal.ics")
    bid = _raised(host, "scrolls", topic="team", auto_ingest=False, commit=False)
    w = host.town.worker(bid)
    host.town.worker(drum).refresh()

    hint = host.command("act", {"id": bid, "act": "suggest", "args": {"text": "Обсудить тарифы с Сергеем завтра"}})
    assert hint["meeting"]["title"] == "Pricing review with Sergey" and hint["meeting"]["when"] == "2026-10-08 11:00"
    assert hint["people"] == ["Sergey"] and hint["section"] == "meetings" and "to discuss" in hint["tags"]
    path = host.command("act", {"id": bid, "act": "note", "args": {
        "text": "Обсудить тарифы с Сергеем завтра", "section": hint["section"], "tags": hint["tags"],
        "links": [x["path"] for x in hint["links"]], "meeting": hint["meeting"], "people": hint["people"],
        "take_in": False}})
    meta = quicknote.front_matter((fake_repo / path).read_text(encoding="utf-8"))
    assert meta["kind"] == "to-discuss" and meta["meeting"] == hint["meeting"]["id"] and meta["with"] == ["Sergey"]

    view = host.detail(bid)["data"]["agenda"]
    assert [m["title"] for m in view["meetings"]] == ["Pricing review with Sergey"]
    page = fake_repo / view["meetings"][0]["page"]
    assert page.is_file() and "Обсудить тарифы с Сергеем завтра" in page.read_text(encoding="utf-8")
    assert "Pricing review with Sergey" in (page.parent / "index.md").read_text(encoding="utf-8")
    host.tick()
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card["discuss"] == {"title": "Pricing review with Sergey", "when": "2026-10-08 11:00", "count": 1}

    # an open item: a person, no meeting picked — it binds to the next meeting with him (today's 1:1)
    host.command("act", {"id": bid, "act": "note", "args": {"text": "Invoices for Q4", "people": ["Sergey"],
                                                            "take_in": False}})
    both = host.detail(bid)["data"]["agenda"]["meetings"]
    assert [(m["title"], [i["line"] for i in m["items"]]) for m in both] == [
        ("Sergey 1:1", ["Invoices for Q4"]), ("Pricing review with Sergey", ["Обсудить тарифы с Сергеем завтра"])]

    # the Calendar asks for the brief: the meeting's page comes first
    sent = []
    monkeypatch.setattr(w, "emit", lambda *a, **k: sent.append(a) or True)
    mid = hint["meeting"]["id"]
    w.lend(pipes.Payload(pipes.TEXT, f"11:00 Pricing review with Sergey (Thu 08) [meet:{mid}]", drum,
                         "calendar.event_upcoming", "Pricing review with Sergey"))
    context = sent[0][1]
    assert context.startswith(f"**Read first — the meeting's page:** `{view['meetings'][0]['page']}`")
    assert "- Обсудить тарифы с Сергеем завтра" in context

    # the person ticks the pricing item; the 1:1 passes untouched: its item moves on to the next meeting with Sergey
    first = view["meetings"][0]["page"]
    text = page.read_text(encoding="utf-8").replace("- [ ] Обсудить", "- [x] Обсудить")
    page.write_text(text, encoding="utf-8")
    clock["now"] = dt.datetime(2026, 10, 8, 12, 0)
    host.town.worker(drum).refresh()
    w.refresh()
    after = page.read_text(encoding="utf-8")
    assert "- 1 covered\n" in after and "- [x] Обсудить" in after and "Invoices" not in after
    nxt = host.detail(bid)["data"]["agenda"]["meetings"]
    assert [(m["when"], [i["line"] for i in m["items"]]) for m in nxt] == [("2026-10-13 11:00", ["Invoices for Q4"])]
    assert nxt[0]["page"] != first
